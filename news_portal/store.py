"""Private news drafts with backups and atomic public release pointers."""
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
        value = json.loads(path.read_bytes())
        return value, version(value)

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
        if not path.exists():
            path.write_bytes(body)
        elif path.read_bytes() != body:
            raise Conflict("同名圖片內容不一致，停止上傳。")
        return f"/news-admin/media/{filename}"


class CloudStore:
    def __init__(self, private_bucket, public_bucket, prefix, client=None):
        from google.cloud import storage
        if not private_bucket or not public_bucket or private_bucket == public_bucket:
            raise ValueError("消息草稿必須使用獨立私有 bucket")
        if not prefix.startswith("news/"):
            raise ValueError("消息只能發布至 news/ 前綴")
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
            value = json.loads(blob.download_as_bytes(if_generation_match=int(blob.generation)))
            return value, str(blob.generation)
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
        blob = self.client.bucket(self.public_bucket).blob(f"{self.prefix}/media/{filename}")
        blob.cache_control = "public, max-age=31536000, immutable"
        try:
            blob.upload_from_string(body, content_type=content_type, if_generation_match=0)
        except PreconditionFailed:
            if blob.download_as_bytes() != body:
                raise Conflict("同名圖片內容不一致，停止上傳。")
        return f"https://storage.googleapis.com/{self.public_bucket}/{self.prefix}/media/{filename}"


def save_draft(store, payload, expected):
    validate(payload)
    with store.lock:
        old, current = store.read("draft.json")
        if expected != current:
            raise Conflict("草稿已被其他編輯者更新，請重新載入。")
        if old is not None:
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
            existing, _ = store.read(key)
            if existing is None:
                store.write(key, data, "0")
            elif existing != data:
                raise Conflict("發布快照不一致，停止切換。")
        _, latest = store.read("draft.json")
        if latest != token:
            raise Conflict("發布期間草稿已更新；公開版本未切換。")
        pointer = {"schemaVersion": 1, "release": release, "draftVersion": token}
        store.write("public/current.json", pointer, pointer_token)
        return pointer
