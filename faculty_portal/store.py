"""Generation-checked draft and atomic public release pointer.

Cloud mode requires an explicitly separate private bucket. Local mode is for the
single-process loopback pilot only. No main-site or graduate data is overwritten.
"""
import json
import os
import threading
import uuid
from pathlib import Path

from .model import encode, release_files, validate, version


class Conflict(Exception):
    pass


class LocalStore:
    def __init__(self, root):
        self.root = Path(root)
        self.lock = threading.RLock()

    def read(self, key):
        path = self.root / key
        if not path.exists():
            return None, "0"
        raw = path.read_bytes()
        data = json.loads(raw)
        return data, version(data)

    def write(self, key, value, expected=None):
        with self.lock:
            _, current = self.read(key)
            if expected is not None and current != expected:
                raise Conflict("資料已更新，請重新載入後再編輯。")
            path = self.root / key
            path.parent.mkdir(parents=True, exist_ok=True)
            temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
            temp.write_bytes(encode(value))
            os.replace(temp, path)

    def upload_media(self, filename, body, content_type):
        path = self.root / "public" / "media" / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            if path.read_bytes() != body:
                raise Conflict("同名照片內容不一致，停止上傳。")
        else:
            path.write_bytes(body)
        return f"/faculty/media/{filename}"

    def remove_public_profiles(self, hidden_profiles):
        for release_dir in (self.root / "public" / "releases").glob("*"):
            for filename in hidden_profiles:
                (release_dir / filename).unlink(missing_ok=True)


class CloudStore:
    def __init__(self, private_bucket, public_bucket, prefix, client=None):
        from google.cloud import storage
        if not private_bucket or not public_bucket or private_bucket == public_bucket:
            raise ValueError("教師草稿必須使用獨立私有 bucket")
        if not prefix.startswith("faculty-pilot/"):
            raise ValueError("試作僅允許 faculty-pilot/ 發布前綴")
        self.client = client or storage.Client()
        self.private_bucket = private_bucket
        self.public_bucket = public_bucket
        self.prefix = prefix.strip("/")
        self.lock = threading.RLock()

    def blob(self, key):
        public = key.startswith("public/")
        bucket = self.public_bucket if public else self.private_bucket
        path = key.removeprefix("public/") if public else key
        return self.client.bucket(bucket).blob(self.prefix + "/" + path)

    def read(self, key):
        from google.api_core.exceptions import NotFound
        blob = self.blob(key)
        try:
            blob.reload()
            # Pin the download to the exact generation whose token we return.
            body = blob.download_as_bytes(if_generation_match=int(blob.generation))
            return json.loads(body), str(blob.generation)
        except NotFound:
            return None, "0"

    def write(self, key, value, expected=None):
        from google.api_core.exceptions import PreconditionFailed
        blob = self.blob(key)
        blob.cache_control = ("public, max-age=31536000, immutable" if "/releases/" in key
                              else "no-cache" if key.startswith("public/") else "no-store")
        try:
            blob.upload_from_string(encode(value), content_type="application/json; charset=utf-8",
                                    if_generation_match=int(expected) if expected is not None else None)
        except PreconditionFailed as exc:
            raise Conflict("資料已更新，請重新載入。") from exc

    def upload_media(self, filename, body, content_type):
        from google.api_core.exceptions import PreconditionFailed
        blob = self.client.bucket(self.public_bucket).blob(
            f"{self.prefix}/media/{filename}"
        )
        blob.cache_control = "public, max-age=31536000, immutable"
        try:
            blob.upload_from_string(
                body,
                content_type=content_type,
                if_generation_match=0,
            )
        except PreconditionFailed:
            if blob.download_as_bytes() != body:
                raise Conflict("同名照片內容不一致，停止上傳。")
        return (
            f"https://storage.googleapis.com/{self.public_bucket}/"
            f"{self.prefix}/media/{filename}"
        )

    def remove_public_profiles(self, hidden_profiles):
        """Remove private profile detail objects from every public release.

        Immutable releases are public URLs, so merely omitting a record from a
        new index is insufficient when an administrator later hides it.
        """
        names = set(hidden_profiles)
        if not names:
            return
        release_prefix = f"{self.prefix}/releases/"
        for blob in self.client.list_blobs(self.public_bucket, prefix=release_prefix):
            relative = blob.name.removeprefix(release_prefix)
            if "/" in relative:
                _release, filename = relative.split("/", 1)
                if filename in names:
                    blob.delete()


def save_draft(store, payload, expected):
    validate(payload)
    with store.lock:
        old, current = store.read("draft.json")
        if expected != current:
            raise Conflict("草稿已被其他編輯者更新，請重新載入。")
        if old is not None:
            # Backup failure must stop the write. Unique names avoid timestamp collisions.
            store.write(f"backups/{uuid.uuid4().hex}.json", old, "0")
        store.write("draft.json", payload, expected)


def publish(store, expected_draft, expected_public):
    with store.lock:
        draft, token = store.read("draft.json")
        _, pointer_token = store.read("public/current.json")
        if expected_draft != token or expected_public != pointer_token:
            raise Conflict("草稿或發布版本已改變，請重新載入並確認。")
        release, files = release_files(draft)
        for filename, data in files.items():
            key = f"public/releases/{release}/{filename}"
            existing, generation = store.read(key)
            if existing is None:
                try:
                    store.write(key, data, "0")
                except Conflict:
                    existing, _ = store.read(key)
                    if existing != data:
                        raise
            elif existing != data:
                raise Conflict("發布快照不一致，停止切換。")
        # A concurrent save must never silently publish an older draft.
        _, latest = store.read("draft.json")
        if latest != token:
            raise Conflict("發布期間草稿已更新；公開版本未切換。")
        pointer = {"schemaVersion": 1, "release": release, "draftVersion": token}
        # All immutable files exist before this generation-checked bilingual switch.
        # Do not delete profiles from older releases before the switch: if the
        # pointer write loses a concurrent-publish race, the old index must
        # still be able to resolve every profile it lists.
        store.write("public/current.json", pointer, pointer_token)
        hidden_profiles = {
            f"{record['id']}.{lang}.json"
            for record in draft["records"]
            for lang in ("zh", "en")
            if not record["locales"][lang].get("visible", lang == "zh" or record["category"] == "fulltime")
        }
        # The current release never contains these profiles.  Cleanup therefore
        # happens only after the public index has atomically stopped referring
        # to them; a cleanup failure cannot break the active release.
        store.remove_public_profiles(hidden_profiles)
        return pointer
