import json
import os
import uuid
import threading
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_from_directory
from werkzeug.exceptions import RequestEntityTooLarge
from google.cloud import storage


ROOT = Path(__file__).resolve().parent
ALUMNI_STORAGE_BACKEND = os.environ.get("ALUMNI_STORAGE_BACKEND", "gcs").strip().lower()
ALUMNI_STORAGE_BUCKET = os.environ.get("ALUMNI_STORAGE_BUCKET", "").strip()
ALUMNI_STORAGE_PREFIX = os.environ.get("ALUMNI_STORAGE_PREFIX", "alumni/raw-submissions").strip().strip("/")
ALUMNI_LOCAL_STORE = ROOT / "tmp"
ALUMNI_AIRTABLE_TOKEN = os.environ.get("ALUMNI_AIRTABLE_TOKEN", "").strip()
ALUMNI_AIRTABLE_BASE = os.environ.get("ALUMNI_AIRTABLE_BASE", "").strip()
ALUMNI_AIRTABLE_TABLE = os.environ.get("ALUMNI_AIRTABLE_TABLE", "").strip()
ALUMNI_ALLOWED_ORIGINS = {
    origin.strip()
    for origin in os.environ.get("ALUMNI_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
}
ALUMNI_MAX_REQUEST_BYTES = int(os.environ.get("ALUMNI_MAX_REQUEST_BYTES", str(64 * 1024)))
ALUMNI_RATE_LIMIT_PER_HOUR = int(os.environ.get("ALUMNI_RATE_LIMIT_PER_HOUR", "5"))
ALUMNI_RATE_WINDOW_SECONDS = 60 * 60
ALUMNI_FIELD_NAMES = {
    "姓名",
    "Email",
    "LinkedIn或個人首頁",
    "手機號碼",
    "Line ID",
    "還在聯絡的所友",
    "目前狀態",
    "現職職稱",
    "服務單位",
    "主要跑線",
    "所在城市",
    "所在國家 / 地區",
    "所在行業",
    "能提供的資源",
    "希望獲得的資源",
    "希望系上提供",
    "偏好聯絡方式",
    "其他聯絡方式",
    "非公開分享：學弟妹來信詢問職涯",
    "非公開分享：所友主動請所辦媒合時",
    "非公開分享：所上活動邀請（週年返校、座談）",
    "非公開分享：系所募款或捐款相關聯繫",
    "公開分享：預定按入學所級列出姓名",
    "公開分享：預定畢業所級與姓名",
    "公開分享：公司",
    "公開分享：職稱",
    "公開分享：E-mail",
    "公開分享：Line ID",
    "公開分享：LinkedIn",
    "公開分享：電話",
    "同意更新提醒",
    "給系上的話",
    # Legacy keys kept for compatibility with older drafts.
    "與系所關係",
    "入學年份 B__",
    "入學年份 R__",
    "入學年份 D__",
    "就讀學位",
    "Mentor 意願",
    "職涯諮詢意願",
    "大手牽小手",
    "可分享主題",
    "每季諮詢時間",
    "想串聯的人",
    "授權：學術合作",
}

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = ALUMNI_MAX_REQUEST_BYTES


class SubmissionRateLimiter:
    def __init__(self):
        self._lock = threading.Lock()
        self._submissions: dict[str, list[float]] = {}

    def allow(self, key: str, now: float) -> bool:
        with self._lock:
            recent = [timestamp for timestamp in self._submissions.get(key, []) if now - timestamp < ALUMNI_RATE_WINDOW_SECONDS]
            if len(recent) >= ALUMNI_RATE_LIMIT_PER_HOUR:
                self._submissions[key] = recent
                return False
            recent.append(now)
            self._submissions[key] = recent
            return True


submission_rate_limiter = SubmissionRateLimiter()


def configured_for_airtable():
    return bool(ALUMNI_AIRTABLE_TOKEN and ALUMNI_AIRTABLE_BASE and ALUMNI_AIRTABLE_TABLE)


def configured_for_gcs():
    return bool(ALUMNI_STORAGE_BUCKET)


def configured_backend():
    if ALUMNI_STORAGE_BACKEND == "airtable":
        return "airtable" if configured_for_airtable() else None
    if ALUMNI_STORAGE_BACKEND == "local":
        return "local"
    if ALUMNI_STORAGE_BACKEND in {"", "gcs"}:
        return "gcs" if configured_for_gcs() else None
    if configured_for_gcs():
        return "gcs"
    if configured_for_airtable():
        return "airtable"
    return None


def allowed_origin_for_request():
    origin = request.headers.get("Origin", "").strip()
    if not origin or not ALUMNI_ALLOWED_ORIGINS:
        return None
    return origin if origin in ALUMNI_ALLOWED_ORIGINS else None


def request_client_key():
    # Cloud Run appends the client address to the right of any caller-supplied
    # X-Forwarded-For values.  The left-most value is therefore untrusted and
    # must never be used as a rate-limit key.
    forwarded = [
        value.strip()
        for value in request.headers.get("X-Forwarded-For", "").split(",")
        if value.strip()
    ]
    return forwarded[-1] if forwarded else (request.remote_addr or "unknown")


def add_cors_headers(response):
    allowed_origin = allowed_origin_for_request()
    if allowed_origin:
        response.headers["Access-Control-Allow-Origin"] = allowed_origin
        response.headers["Vary"] = "Origin"
    response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Max-Age"] = "86400"
    return response


@app.errorhandler(RequestEntityTooLarge)
def request_too_large(_error):
    response = jsonify({"error": "送出資料過大。"})
    response.status_code = 413
    return add_cors_headers(response)


def sanitize_field_value(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, list):
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        return cleaned or None
    cleaned = str(value or "").strip()
    return cleaned or None


def sanitize_fields(raw_fields):
    if not isinstance(raw_fields, dict):
        raise ValueError("`fields` must be an object.")

    fields = {}
    for key in ALUMNI_FIELD_NAMES:
        cleaned = sanitize_field_value(raw_fields.get(key))
        if cleaned is not None:
            fields[key] = cleaned
    return fields


def validate_fields(fields):
    if not fields.get("姓名"):
        raise ValueError("缺少必填欄位：姓名")
    email = str(fields.get("Email") or "").strip()
    if email and "@" not in email:
        raise ValueError("缺少有效的 Email")


def build_submission_record(fields):
    now = datetime.now(timezone.utc)
    submission_id = f"alumni-{now.strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    return {
        "schemaVersion": 1,
        "submissionId": submission_id,
        "submittedAt": now.isoformat(),
        "source": "alumni_form.html",
        "status": "new",
        "fields": fields,
    }


def submission_object_name(record):
    submitted_at = datetime.fromisoformat(record["submittedAt"])
    return (
        f"{ALUMNI_STORAGE_PREFIX}/"
        f"{submitted_at.strftime('%Y/%m/%d')}/"
        f"{record['submissionId']}.json"
    )


def submission_body(record):
    return json.dumps(record, ensure_ascii=False, indent=2) + "\n"


def write_submission_to_gcs(record):
    bucket = storage.Client().bucket(ALUMNI_STORAGE_BUCKET)
    object_name = submission_object_name(record)
    blob = bucket.blob(object_name)
    blob.cache_control = "no-store"
    blob.upload_from_string(
        submission_body(record),
        content_type="application/json; charset=utf-8",
    )
    return {"recordId": record["submissionId"], "objectName": object_name}


def write_submission_to_local(record):
    object_name = submission_object_name(record)
    path = ALUMNI_LOCAL_STORE / object_name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(submission_body(record), encoding="utf-8")
    return {"recordId": record["submissionId"], "objectName": str(path.relative_to(ROOT))}


def airtable_endpoint():
    base = urllib.parse.quote(ALUMNI_AIRTABLE_BASE, safe="")
    table = urllib.parse.quote(ALUMNI_AIRTABLE_TABLE, safe="")
    return f"https://api.airtable.com/v0/{base}/{table}"


def submit_to_airtable(fields):
    body = json.dumps({"fields": fields}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        airtable_endpoint(),
        data=body,
        headers={
            "Authorization": f"Bearer {ALUMNI_AIRTABLE_TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return payload, response.status
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(detail or f"Airtable request failed with status {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(str(exc.reason or exc)) from exc


def store_submission(fields):
    record = build_submission_record(fields)
    backend = configured_backend()
    if backend == "gcs":
        if not configured_for_gcs():
            raise RuntimeError("ALUMNI_STORAGE_BUCKET is not configured on the server.")
        return write_submission_to_gcs(record)
    if backend == "airtable":
        airtable_response, _status = submit_to_airtable(fields)
        return {"recordId": airtable_response.get("id", ""), "objectName": ""}
    if backend == "local":
        return write_submission_to_local(record)
    raise RuntimeError("No alumni storage backend is configured.")


@app.get("/")
def alumni_form_root():
    return send_from_directory(ROOT, "alumni_form.html")


@app.get("/alumni_form.html")
def alumni_form_page():
    return send_from_directory(ROOT, "alumni_form.html")


@app.get("/healthz")
def healthz():
    return jsonify(
        {
            "ok": True,
            "backend": configured_backend(),
            "gcsConfigured": configured_for_gcs(),
            "airtableConfigured": configured_for_airtable(),
        }
    )


@app.route("/api/alumni-submissions", methods=["OPTIONS", "POST"])
def alumni_submissions():
    allowed_origin = allowed_origin_for_request()
    if request.method == "OPTIONS":
        if allowed_origin is None:
            return jsonify({"error": "Origin not allowed."}), 403
        response = Response(status=204)
        return add_cors_headers(response)

    if allowed_origin is None:
        response = jsonify({"error": "Origin not allowed."})
        response.status_code = 403
        return add_cors_headers(response)
    # Origin is a browser/CORS boundary only.  It is not an abuse-control
    # identity, because non-browser callers can forge it; rate limiting uses
    # the Cloud Run-provided client address instead.
    if not submission_rate_limiter.allow(request_client_key(), datetime.now(timezone.utc).timestamp()):
        response = jsonify({"error": "送出次數過於頻繁，請稍後再試。"})
        response.status_code = 429
        return add_cors_headers(response)

    try:
        payload = request.get_json(force=True) or {}
        raw_fields = payload.get("fields", payload)
        fields = sanitize_fields(raw_fields)
        validate_fields(fields)
        stored = store_submission(fields)
        response = jsonify({"ok": True, **stored})
        response.status_code = 200
    except ValueError as exc:
        response = jsonify({"error": str(exc)})
        response.status_code = 400
    except RuntimeError:
        response = jsonify({"error": "送出失敗，請稍後再試。"})
        response.status_code = 502

    return add_cors_headers(response)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
