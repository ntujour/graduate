import json
import hashlib
import os
import shutil
import subprocess
import tempfile
import webbrowser
import uuid
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

from google.api_core.exceptions import PreconditionFailed
from google.cloud import storage


ROOT = Path(__file__).resolve().parent
DATA_FILE = ROOT / "data" / "courses.json"
ADVISEES_FILE = ROOT / "data" / "advisees.json"
REGULAR_EVENTS_FILE = ROOT / "data" / "regular_event.json"
BACKUP_DIR = ROOT / "backup"
ALUMNI_STORAGE_BUCKET = os.environ.get("ALUMNI_STORAGE_BUCKET", "").strip()
ALUMNI_STORAGE_PREFIX = os.environ.get("ALUMNI_STORAGE_PREFIX", "alumni/raw-submissions").strip().strip("/")
ALUMNI_LOCAL_DIR = ROOT / "tmp" / ALUMNI_STORAGE_PREFIX
HOST = "127.0.0.1"
PORT = int(os.environ.get("COURSE_ADMIN_PORT", "8765"))
BUCKET_NAME = os.environ.get("DATA_BUCKET") or os.environ.get("COURSES_BUCKET", "")
COURSES_OBJECT = os.environ.get("COURSES_OBJECT", "data/courses.json")
ADVISEES_OBJECT = os.environ.get("ADVISEES_OBJECT", "data/advisees.json")
REGULAR_EVENTS_OBJECT = os.environ.get("REGULAR_EVENTS_OBJECT", "data/regular_event.json")
REMOTE_OBJECTS = {
    "courses": (COURSES_OBJECT, DATA_FILE),
    "advisees": (ADVISEES_OBJECT, ADVISEES_FILE),
    "regular-events": (REGULAR_EVENTS_OBJECT, REGULAR_EVENTS_FILE),
}
REMOTE_GENERATIONS = {
    object_name: None
    for object_name, _destination in REMOTE_OBJECTS.values()
}
ADMIN_RUNTIME = {
    "read_only": True,
    "reason": "尚未完成遠端資料同步。",
    "remote_configured": bool(BUCKET_NAME),
    "last_sync_at": None,
    "alumni_read_only": False,
    "alumni_reason": "",
}


class VersionConflictError(Exception):
    def __init__(self, current_version, message="資料已在另一個版本更新，請先重新載入最新資料再儲存。"):
        super().__init__(message)
        self.current_version = current_version


class ReadOnlyModeError(Exception):
    pass


class RemoteVersionConflictError(Exception):
    pass


def canonical_etag(payload):
    canonical = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def etag_header(payload):
    return f'"{canonical_etag(payload)}"'


def normalize_if_match(value):
    value = str(value or "").strip()
    if value.startswith("W/"):
        value = value[2:].strip()
    return value.strip('"')


def set_admin_runtime(read_only, reason):
    ADMIN_RUNTIME["read_only"] = read_only
    ADMIN_RUNTIME["reason"] = reason
    if not read_only:
        ADMIN_RUNTIME["last_sync_at"] = datetime.now(timezone.utc).isoformat()


def admin_headers():
    return {
        "X-Admin-Read-Only": "true" if ADMIN_RUNTIME["read_only"] else "false",
        "X-Alumni-Read-Only": "true" if ADMIN_RUNTIME["alumni_read_only"] else "false",
    }


def admin_state_payload():
    return {
        "readOnly": ADMIN_RUNTIME["read_only"],
        "reason": ADMIN_RUNTIME["reason"],
        "remoteConfigured": ADMIN_RUNTIME["remote_configured"],
        "lastSyncAt": ADMIN_RUNTIME["last_sync_at"],
        "alumniReadOnly": ADMIN_RUNTIME["alumni_read_only"],
        "alumniReason": ADMIN_RUNTIME["alumni_reason"],
    }


def get_remote_blob(object_name):
    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)
    return bucket.blob(object_name)


def gcloud_storage_describe(object_name):
    uri = f"gs://{BUCKET_NAME}/{object_name}"
    result = subprocess.run(
        ["gcloud", "storage", "objects", "describe", uri, "--format=json(generation)"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        raise RuntimeError(stderr or f"`gcloud storage objects describe {uri}` failed")
    return json.loads(result.stdout or "{}")


def gcloud_storage_cat(object_name):
    uri = f"gs://{BUCKET_NAME}/{object_name}"
    result = subprocess.run(
        ["gcloud", "storage", "cat", uri],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        raise RuntimeError(stderr or f"`gcloud storage cat {uri}` failed")
    return result.stdout


def download_remote_snapshot(object_name):
    blob_error = None
    try:
        blob = get_remote_blob(object_name)
        if not blob.exists():
            raise FileNotFoundError(f"遠端物件不存在：gs://{BUCKET_NAME}/{object_name}")
        blob.reload()
        REMOTE_GENERATIONS[object_name] = int(blob.generation or 0)
        return blob.download_as_text(encoding="utf-8")
    except Exception as exc:
        blob_error = exc

    try:
        metadata = gcloud_storage_describe(object_name)
        REMOTE_GENERATIONS[object_name] = int(metadata.get("generation") or 0)
        return gcloud_storage_cat(object_name)
    except Exception as gcloud_exc:
        raise RuntimeError(
            f"無法讀取 gs://{BUCKET_NAME}/{object_name}。"
            f" storage client: {blob_error}; gcloud: {gcloud_exc}"
        ) from gcloud_exc


def backup_object_name(object_name):
    base_name = Path(object_name).stem
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"backup/{base_name}-{timestamp}.json"


def write_body_to_tempfile(body, directory):
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=directory, delete=False) as handle:
        handle.write(body)
        return Path(handle.name)


def upload_text_via_gcloud(object_name, body, extra_args=None):
    extra_args = extra_args or []
    uri = f"gs://{BUCKET_NAME}/{object_name}"
    temp_path = write_body_to_tempfile(body, ROOT)
    try:
        command = [
            "gcloud",
            "storage",
            "cp",
            "--cache-control=no-cache",
            "--content-type=application/json;charset=utf-8",
            *extra_args,
            str(temp_path),
            uri,
        ]
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            if "412" in stderr or "conditionNotMet" in stderr or "Precondition" in stderr:
                raise RemoteVersionConflictError(stderr)
            raise RuntimeError(stderr or f"`{' '.join(command)}` failed")
    finally:
        temp_path.unlink(missing_ok=True)


def backup_remote_snapshot(object_name, body):
    backup_name = backup_object_name(object_name)
    blob_error = None
    try:
        bucket = storage.Client().bucket(BUCKET_NAME)
        backup_blob = bucket.blob(backup_name)
        backup_blob.cache_control = "no-cache"
        backup_blob.upload_from_string(body, content_type="application/json; charset=utf-8")
        return backup_name
    except Exception as exc:
        blob_error = exc

    try:
        upload_text_via_gcloud(backup_name, body)
        return backup_name
    except Exception as gcloud_exc:
        raise RuntimeError(
            f"無法備份 gs://{BUCKET_NAME}/{object_name}。"
            f" storage client: {blob_error}; gcloud: {gcloud_exc}"
        ) from gcloud_exc


def upload_remote_snapshot(object_name, body, expected_generation):
    if expected_generation is None:
        raise RuntimeError("缺少遠端 generation，請先重新載入最新資料。")

    blob_error = None
    try:
        blob = get_remote_blob(object_name)
        blob.cache_control = "no-cache"
        blob.upload_from_string(
            body,
            content_type="application/json; charset=utf-8",
            if_generation_match=int(expected_generation),
        )
        blob.reload()
        REMOTE_GENERATIONS[object_name] = int(blob.generation or 0)
        return
    except PreconditionFailed as exc:
        raise RemoteVersionConflictError(str(exc)) from exc
    except Exception as exc:
        blob_error = exc

    try:
        upload_text_via_gcloud(
            object_name,
            body,
            extra_args=[f"--if-generation-match={expected_generation}"],
        )
        metadata = gcloud_storage_describe(object_name)
        REMOTE_GENERATIONS[object_name] = int(metadata.get("generation") or 0)
        return
    except RemoteVersionConflictError:
        raise
    except Exception as gcloud_exc:
        raise RuntimeError(
            f"無法寫入 gs://{BUCKET_NAME}/{object_name}。"
            f" storage client: {blob_error}; gcloud: {gcloud_exc}"
        ) from gcloud_exc


def write_json_snapshot(destination, body):
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = json.loads(body)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=destination.parent, delete=False) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temp_name = handle.name
    os.replace(temp_name, destination)


def sync_remote_snapshots(strict):
    if not BUCKET_NAME:
        set_admin_runtime(True, "未設定 `DATA_BUCKET` 或 `COURSES_BUCKET`，本機管理介面只允許唯讀。")
        if strict:
            raise ReadOnlyModeError(ADMIN_RUNTIME["reason"])
        return False

    try:
        for object_name, destination in REMOTE_OBJECTS.values():
            write_json_snapshot(destination, download_remote_snapshot(object_name))
    except Exception as exc:
        set_admin_runtime(True, f"遠端同步失敗：{exc}")
        if strict:
            raise ReadOnlyModeError(ADMIN_RUNTIME["reason"])
        return False

    set_admin_runtime(False, f"已同步遠端正式資料：gs://{BUCKET_NAME}")
    return True


def refresh_remote_state(strict=False):
    return sync_remote_snapshots(strict=strict)


def require_writable():
    if ADMIN_RUNTIME["read_only"]:
        raise ReadOnlyModeError(ADMIN_RUNTIME["reason"])


def require_alumni_writable():
    if ADMIN_RUNTIME["alumni_read_only"]:
        raise ReadOnlyModeError(ADMIN_RUNTIME["alumni_reason"] or "系友收件目前為唯讀模式。")


def load_courses():
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def load_advisees():
    return json.loads(ADVISEES_FILE.read_text(encoding="utf-8"))


def canonical_source(object_name):
    if object_name == "data/courses.json":
        import_sources = "CSV files"
    elif object_name == "data/regular_event.json":
        import_sources = "CSV files"
    else:
        import_sources = "Word and CSV files"
    return {
        "type": "canonical-json",
        "value": object_name,
        "note": f"Official source for public pages and admin edits. {import_sources} are import sources only.",
    }


def set_canonical_source(payload, object_name):
    existing_source = payload.get("source")
    if isinstance(existing_source, dict) and existing_source.get("type") != "canonical-json":
        payload.setdefault("importSource", existing_source)
    payload["source"] = canonical_source(object_name)


def backup_path_for(data_file):
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return BACKUP_DIR / f"{data_file.stem}-{timestamp}.json"


def backup_local_json(data_file):
    if not data_file.exists():
        return None
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_file = backup_path_for(data_file)
    shutil.copy2(data_file, backup_file)
    return backup_file


def current_payload_version(data_file):
    if not data_file.exists():
        return None
    return canonical_etag(json.loads(data_file.read_text(encoding="utf-8")))


def require_matching_version(data_file, expected_version):
    current_version = current_payload_version(data_file)
    if current_version and normalize_if_match(expected_version) != current_version:
        raise VersionConflictError(current_version)
    return current_version


def save_canonical_json(data_file, object_name, payload, expected_version, normalizer):
    require_writable()
    require_matching_version(data_file, expected_version)
    normalized = normalizer(payload)
    body = json.dumps(normalized, ensure_ascii=False, indent=2) + "\n"
    existing_body = data_file.read_text(encoding="utf-8") if data_file.exists() else None
    expected_generation = REMOTE_GENERATIONS.get(object_name)

    if existing_body:
        backup_local_json(data_file)
        backup_remote_snapshot(object_name, existing_body)

    try:
        upload_remote_snapshot(object_name, body, expected_generation)
    except RemoteVersionConflictError as exc:
        refresh_remote_state(strict=False)
        raise VersionConflictError(current_payload_version(data_file)) from exc

    write_json_snapshot(data_file, body)
    return normalized


def normalize_payload(payload):
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")

    courses = payload.get("courses")
    semesters = payload.get("semesters")
    if not isinstance(courses, list):
        raise ValueError("courses must be a list")
    if not isinstance(semesters, list):
        raise ValueError("semesters must be a list")

    normalized_courses = []
    for index, course in enumerate(courses, start=1):
        if not isinstance(course, dict):
            raise ValueError("each course must be an object")
        name = str(course.get("cname") or "").strip()
        if not name:
            raise ValueError(f"course #{index} is missing cname")

        sequence = course.get("sequence") or index
        try:
            sequence = int(sequence)
        except (TypeError, ValueError):
            sequence = index

        try:
            credit = int(course.get("credit") or 0)
        except (TypeError, ValueError):
            credit = 0

        offerings = course.get("offerings") if isinstance(course.get("offerings"), dict) else {}
        normalized_courses.append(
            {
                "id": str(course.get("id") or f"course-{sequence:03d}"),
                "sequence": sequence,
                "cname": name,
                "cname_en": str(course.get("cname_en") or "").strip(),
                "offer_by": str(course.get("offer_by") or "").strip(),
                "category": str(course.get("category") or "").strip(),
                "credit": credit,
                "last": str(course.get("last") or "").strip(),
                "period": str(course.get("period") or "").strip(),
                "active": str(course.get("active") or "").strip(),
                "info": str(course.get("info") or "").strip(),
                "skill": str(course.get("skill") or "").strip(),
                "description": str(course.get("description") or "").strip(),
                "offerings": {
                    str(semester): bool(offerings.get(str(semester)))
                    for semester in semesters
                },
            }
        )

    payload["schemaVersion"] = int(payload.get("schemaVersion") or 1)
    payload["updatedAt"] = datetime.now(timezone.utc).isoformat()
    set_canonical_source(payload, "data/courses.json")
    payload["semesters"] = [str(semester).strip() for semester in semesters if str(semester).strip()]
    payload["courses"] = sorted(normalized_courses, key=lambda item: item["sequence"])
    return payload


def save_courses(payload, expected_version):
    return save_canonical_json(DATA_FILE, COURSES_OBJECT, payload, expected_version, normalize_payload)


def split_advisor_lines(value):
    if isinstance(value, list):
        parts = value
    else:
        parts = str(value or "").replace("，", ",").replace("、", ",").splitlines()
        parts = ",".join(parts).split(",")
    return [str(part).strip() for part in parts if str(part).strip()]


def truthy(value):
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def infer_advisee_statuses(student, advisor, thesis_title):
    if not advisor:
        return {"advised": False, "proposal": False, "final": False}

    final = bool(thesis_title and thesis_title not in {"在學中", "休學"})
    return {
        "advised": True if final else truthy(student.get("advised", True)),
        "proposal": True if final else truthy(student.get("proposal")),
        "final": final,
    }


def normalize_advisees_payload(payload):
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")

    students = payload.get("students")
    if not isinstance(students, list):
        raise ValueError("students must be a list")

    advisors = payload.get("advisors") if isinstance(payload.get("advisors"), dict) else {}
    normalized_students = []
    for index, student in enumerate(students, start=1):
        if not isinstance(student, dict):
            raise ValueError("each student must be an object")
        name = str(student.get("name") or "").strip()
        if not name:
            continue
        advisor = str(student.get("advisor") or "").strip()
        thesis_title = str(student.get("thesisTitle") or "").strip()
        statuses = infer_advisee_statuses(student, advisor, thesis_title)
        normalized_students.append(
            {
                "id": str(student.get("id") or f"advisee-{index:03d}"),
                "cohort": str(student.get("cohort") or "").strip(),
                "admissionYear": str(student.get("admissionYear") or "").strip(),
                "name": name,
                "thesisType": str(student.get("thesisType") or "").strip(),
                "advisor": advisor,
                "thesisTitle": thesis_title,
                **statuses,
                "job": str(student.get("job") or "").strip(),
                "workType": str(student.get("workType") or "").strip(),
                "url": str(student.get("url") or "").strip(),
            }
        )

    payload["schemaVersion"] = int(payload.get("schemaVersion") or 1)
    payload["updatedAt"] = datetime.now(timezone.utc).isoformat()
    set_canonical_source(payload, "data/advisees.json")
    payload["advisors"] = {
        "fulltime": split_advisor_lines(advisors.get("fulltime")),
        "adjunct": split_advisor_lines(advisors.get("adjunct")),
    }
    payload["students"] = normalized_students
    return payload


def save_advisees(payload, expected_version):
    return save_canonical_json(ADVISEES_FILE, ADVISEES_OBJECT, payload, expected_version, normalize_advisees_payload)


def normalize_regular_events_payload(payload):
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")

    events = payload.get("events")
    if not isinstance(events, list):
        raise ValueError("events must be a list")

    normalized_events = []
    for index, event in enumerate(events, start=1):
        if not isinstance(event, dict):
            raise ValueError("each event must be an object")

        name = str(event.get("name") or "").strip()
        if not name:
            raise ValueError(f"event #{index} is missing name")

        category = str(event.get("category") or "").strip()
        if not category:
            raise ValueError(f"event #{index} is missing category")

        month = str(event.get("month") or "").strip()
        if not month:
            raise ValueError(f"event #{index} is missing month")

        normalized_events.append(
            {
                "id": str(event.get("id") or f"regular-event-{index:03d}"),
                "name": name,
                "category": category,
                "month": month,
                "due": str(event.get("due") or "").strip(),
                "description": str(event.get("description") or "").strip(),
                "link": str(event.get("link") or "").strip(),
                "related": str(event.get("related") or event.get("resource") or event.get("attachment") or "").strip(),
            }
        )

    payload["schemaVersion"] = int(payload.get("schemaVersion") or 1)
    payload["updatedAt"] = datetime.now(timezone.utc).isoformat()
    set_canonical_source(payload, "data/regular_event.json")
    payload.setdefault(
        "importSource",
        {
            "type": "csv",
            "value": "data/regular_event.csv",
            "note": "Imported from the legacy CSV import pipeline.",
        },
    )
    payload["events"] = normalized_events
    return payload


def load_regular_events():
    return json.loads(REGULAR_EVENTS_FILE.read_text(encoding="utf-8"))


def save_regular_events(payload, expected_version):
    return save_canonical_json(
        REGULAR_EVENTS_FILE,
        REGULAR_EVENTS_OBJECT,
        payload,
        expected_version,
        normalize_regular_events_payload,
    )


def split_tag_lines(value):
    if isinstance(value, list):
        parts = value
    else:
        parts = str(value or "").replace("，", ",").replace("、", ",").splitlines()
        parts = ",".join(parts).split(",")
    return [str(part).strip() for part in parts if str(part).strip()]


def alumni_submission_prefix():
    return f"{ALUMNI_STORAGE_PREFIX.rstrip('/')}/" if ALUMNI_STORAGE_PREFIX else ""


def alumni_local_root():
    return ROOT / "tmp" / ALUMNI_STORAGE_PREFIX


def alumni_local_file(object_name):
    return ROOT / "tmp" / object_name


def valid_alumni_object_name(object_name):
    object_name = str(object_name or "").strip().lstrip("/")
    prefix = alumni_submission_prefix()
    if not object_name or not object_name.startswith(prefix):
        raise ValueError("invalid alumni submission object name")
    return object_name


def parse_alumni_record(body, object_name):
    record = json.loads(body)
    if not isinstance(record, dict):
        raise ValueError("alumni submission must be an object")
    fields = record.get("fields") if isinstance(record.get("fields"), dict) else {}
    summary = {
        "objectName": object_name,
        "versionToken": canonical_etag(record),
        "submissionId": str(record.get("submissionId") or Path(object_name).stem),
        "submittedAt": str(record.get("submittedAt") or ""),
        "source": str(record.get("source") or ""),
        "status": str(record.get("status") or "new"),
        "adminTags": split_tag_lines(record.get("adminTags")),
        "adminNote": str(record.get("adminNote") or ""),
        "adminUpdatedAt": str(record.get("adminUpdatedAt") or ""),
        "fields": fields,
    }
    return summary


def list_alumni_submission_records():
    records = []
    if ALUMNI_STORAGE_BUCKET:
        try:
            bucket = storage.Client().bucket(ALUMNI_STORAGE_BUCKET)
            prefix = alumni_submission_prefix()
            for blob in bucket.list_blobs(prefix=prefix):
                if blob.name.endswith("/"):
                    continue
                blob.reload()
                records.append(parse_alumni_record(blob.download_as_text(encoding="utf-8"), blob.name))
        except Exception:
            pass

    if records:
        return sorted(records, key=lambda item: item.get("submittedAt") or item.get("objectName") or "", reverse=True)

    root = alumni_local_root()
    if not root.exists():
        return []
    for path in root.rglob("*.json"):
        body = path.read_text(encoding="utf-8")
        object_name = str(path.relative_to(ROOT / "tmp"))
        records.append(parse_alumni_record(body, object_name))
    return sorted(records, key=lambda item: item.get("submittedAt") or item.get("objectName") or "", reverse=True)


def load_alumni_submission(object_name):
    object_name = valid_alumni_object_name(object_name)
    if ALUMNI_STORAGE_BUCKET:
        blob = storage.Client().bucket(ALUMNI_STORAGE_BUCKET).blob(object_name)
        if not blob.exists():
            raise FileNotFoundError(f"遠端系友收件不存在：gs://{ALUMNI_STORAGE_BUCKET}/{object_name}")
        blob.reload()
        return parse_alumni_record(blob.download_as_text(encoding="utf-8"), object_name), int(blob.generation or 0)

    local_file = alumni_local_file(object_name)
    if not local_file.exists():
        raise FileNotFoundError(f"本機系友收件不存在：{local_file}")
    return parse_alumni_record(local_file.read_text(encoding="utf-8"), object_name), None


def normalize_alumni_submission_payload(payload):
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")

    fields = payload.get("fields")
    if not isinstance(fields, dict):
        raise ValueError("fields must be an object")

    name = str(fields.get("姓名") or "").strip()
    if not name:
        raise ValueError("fields must include 姓名")

    record = dict(payload)
    record["schemaVersion"] = int(record.get("schemaVersion") or 1)
    record["submissionId"] = str(record.get("submissionId") or f"alumni-{uuid.uuid4().hex[:12]}")
    record["submittedAt"] = str(record.get("submittedAt") or datetime.now(timezone.utc).isoformat())
    record["source"] = str(record.get("source") or "alumni_form.html")
    record["status"] = str(record.get("status") or "new").strip() or "new"
    record["adminTags"] = split_tag_lines(record.get("adminTags"))
    record["adminNote"] = str(record.get("adminNote") or "").strip()
    record["adminUpdatedAt"] = datetime.now(timezone.utc).isoformat()
    record["fields"] = fields
    return record


def save_alumni_submission(object_name, payload, expected_version):
    require_alumni_writable()
    object_name = valid_alumni_object_name(object_name)
    normalized = normalize_alumni_submission_payload(payload)
    body = json.dumps(normalized, ensure_ascii=False, indent=2) + "\n"
    current_version = None
    current_generation = 0

    try:
        current_record, current_generation = load_alumni_submission(object_name)
        current_version = str(current_record.get("versionToken") or "")
    except FileNotFoundError:
        current_generation = 0

    if current_version and normalize_if_match(expected_version) != current_version:
        raise VersionConflictError(current_version)

    if ALUMNI_STORAGE_BUCKET:
        blob = storage.Client().bucket(ALUMNI_STORAGE_BUCKET).blob(object_name)
        blob.cache_control = "no-cache"
        try:
            blob.upload_from_string(
                body,
                content_type="application/json; charset=utf-8",
                if_generation_match=current_generation,
            )
        except PreconditionFailed:
            latest_record, _generation = load_alumni_submission(object_name)
            raise VersionConflictError(str(latest_record.get("versionToken") or ""))
    else:
        local_file = alumni_local_file(object_name)
        local_file.parent.mkdir(parents=True, exist_ok=True)
        local_file.write_text(body, encoding="utf-8")

    return parse_alumni_record(body, object_name)


def delete_alumni_submission(object_name, expected_version):
    require_alumni_writable()
    object_name = valid_alumni_object_name(object_name)

    current_record, current_generation = load_alumni_submission(object_name)
    current_version = str(current_record.get("versionToken") or "")
    if current_version and normalize_if_match(expected_version) != current_version:
        raise VersionConflictError(current_version)

    if ALUMNI_STORAGE_BUCKET:
        blob = storage.Client().bucket(ALUMNI_STORAGE_BUCKET).blob(object_name)
        try:
            blob.delete(if_generation_match=current_generation)
        except PreconditionFailed:
            latest_record, _generation = load_alumni_submission(object_name)
            raise VersionConflictError(str(latest_record.get("versionToken") or ""))
    else:
        local_file = alumni_local_file(object_name)
        if not local_file.exists():
            raise FileNotFoundError(f"本機系友收件不存在：{local_file}")
        local_file.unlink()

    return {
        "objectName": object_name,
        "deleted": True,
    }


class CourseAdminHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def send_json(self, payload, status=200, extra_headers=None):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        for key, value in admin_headers().items():
            self.send_header(key, value)
        if extra_headers:
            for key, value in extra_headers.items():
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/":
            self.path = "/course_admin.html"
        if self.path == "/api/admin-state":
            try:
                refresh_remote_state(strict=False)
                self.send_json(admin_state_payload())
            except Exception as exc:
                self.send_json({"error": str(exc)}, status=500)
            return
        if self.path == "/api/courses":
            try:
                refresh_remote_state(strict=False)
                payload = load_courses()
                self.send_json(payload, extra_headers={"ETag": etag_header(payload)})
            except Exception as exc:
                self.send_json({"error": str(exc)}, status=500)
            return
        if self.path == "/api/advisees":
            try:
                refresh_remote_state(strict=False)
                payload = load_advisees()
                self.send_json(payload, extra_headers={"ETag": etag_header(payload)})
            except Exception as exc:
                self.send_json({"error": str(exc)}, status=500)
            return
        if self.path == "/api/regular-events":
            try:
                refresh_remote_state(strict=False)
                payload = load_regular_events()
                self.send_json(payload, extra_headers={"ETag": etag_header(payload)})
            except Exception as exc:
                self.send_json({"error": str(exc)}, status=500)
            return
        if self.path == "/api/alumni-submissions":
            try:
                refresh_remote_state(strict=False)
                payload = {
                    "schemaVersion": 1,
                    "updatedAt": datetime.now(timezone.utc).isoformat(),
                    "submissions": list_alumni_submission_records(),
                }
                self.send_json(payload, extra_headers={"ETag": etag_header(payload)})
            except Exception as exc:
                self.send_json({"error": str(exc)}, status=500)
            return
        super().do_GET()

    def do_PUT(self):
        if self.path not in {"/api/courses", "/api/advisees", "/api/regular-events"} and not self.path.startswith("/api/alumni-submissions/"):
            self.send_error(404)
            return

        try:
            refresh_remote_state(strict=False)
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            expected_version = self.headers.get("If-Match", "")
            if self.path == "/api/courses":
                saved = save_courses(payload, expected_version)
            elif self.path == "/api/advisees":
                saved = save_advisees(payload, expected_version)
            elif self.path == "/api/regular-events":
                saved = save_regular_events(payload, expected_version)
            else:
                object_name = unquote(self.path.removeprefix("/api/alumni-submissions/"))
                saved = save_alumni_submission(object_name, payload, expected_version)
            self.send_json(saved, extra_headers={"ETag": etag_header(saved)})
        except VersionConflictError as exc:
            self.send_json(
                {"error": str(exc), "currentVersion": exc.current_version},
                status=409,
                extra_headers={"ETag": f'"{exc.current_version}"'},
            )
        except ReadOnlyModeError as exc:
            self.send_json({"error": str(exc), "readOnly": True}, status=403)
        except Exception as exc:
            self.send_json({"error": str(exc)}, status=400)

    def do_DELETE(self):
        if not self.path.startswith("/api/alumni-submissions/"):
            self.send_error(404)
            return

        try:
            refresh_remote_state(strict=False)
            expected_version = self.headers.get("If-Match", "")
            object_name = unquote(self.path.removeprefix("/api/alumni-submissions/"))
            result = delete_alumni_submission(object_name, expected_version)
            self.send_json(result)
        except VersionConflictError as exc:
            self.send_json(
                {"error": str(exc), "currentVersion": exc.current_version},
                status=409,
                extra_headers={"ETag": f'"{exc.current_version}"'},
            )
        except ReadOnlyModeError as exc:
            self.send_json({"error": str(exc), "readOnly": True}, status=403)
        except FileNotFoundError as exc:
            self.send_json({"error": str(exc)}, status=404)
        except Exception as exc:
            self.send_json({"error": str(exc)}, status=400)


def main():
    try:
        refresh_remote_state(strict=True)
    except ReadOnlyModeError as exc:
        print(f"Local admin started in read-only mode: {exc}")
        if not DATA_FILE.exists():
            raise SystemExit(str(exc))

    server = ThreadingHTTPServer((HOST, PORT), CourseAdminHandler)
    url = f"http://{HOST}:{PORT}/"
    print(f"Course admin running at {url}")
    if ADMIN_RUNTIME["read_only"]:
        print(f"Read-only mode: {ADMIN_RUNTIME['reason']}")
    else:
        print(ADMIN_RUNTIME["reason"])
    print("Press Ctrl+C to stop.")
    try:
        webbrowser.open(url)
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping course admin.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
