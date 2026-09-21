"""Explicit one-time pilot seed. Refuses to overwrite an existing cloud draft.

Uses the operator's existing gcloud login; never reads FTP credentials or graduate
course/student/alumni data. Normal generation never calls this command.
"""
import copy
import json
import subprocess
from pathlib import Path

from google.cloud import storage
from google.oauth2.credentials import Credentials

from .store import CloudStore, publish, save_draft


def main():
    root = Path(__file__).resolve().parents[1] / "output/faculty-pilot"
    token = subprocess.check_output(["gcloud", "auth", "print-access-token"], text=True).strip()
    client = storage.Client(project="ntujour", credentials=Credentials(token))
    store = CloudStore("ntujour-faculty-admin-private", "ntujour-graduate", "faculty-pilot/v1", client)
    existing, _ = store.read("draft.json")
    if existing is not None:
        raise SystemExit("雲端已有草稿，禁止重新匯入覆蓋。")
    payload = copy.deepcopy(json.loads((root / "draft.json").read_text()))
    base = "https://storage.googleapis.com/ntujour-graduate/faculty-pilot/v1/media/"
    for record in payload["records"]:
        photo = record["shared"]["photo"]
        if photo.startswith("http://127.0.0.1:8766/faculty/media/"):
            record["shared"]["photo"] = base + photo.rsplit("/", 1)[-1]
    import mimetypes
    for path in sorted((root / "public/media").iterdir()):
        blob = client.bucket("ntujour-graduate").blob("faculty-pilot/v1/media/" + path.name)
        if blob.exists():
            if blob.download_as_bytes() != path.read_bytes():
                raise RuntimeError("既有圖片與本機不一致")
            continue
        blob.cache_control = "public, max-age=31536000, immutable"
        blob.upload_from_filename(path, content_type=mimetypes.guess_type(path.name)[0], if_generation_match=0)
    save_draft(store, payload, "0")
    _, generation = store.read("draft.json")
    result = publish(store, generation, "0")
    (root / "cloud-release.json").write_text(json.dumps(result))
    print(json.dumps({"teachers": len(payload["records"]), "release": result["release"]}))


if __name__ == "__main__":
    main()
