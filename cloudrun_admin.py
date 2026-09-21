import json
import os
from datetime import datetime, timezone
from pathlib import Path

from google.api_core.exceptions import PreconditionFailed
from google.auth.transport import requests as google_auth_requests
from flask import Flask, Response, jsonify, request, send_from_directory
from google.cloud import storage
from google.oauth2 import id_token

from course_admin import (
    canonical_etag,
    delete_alumni_submission,
    list_alumni_submission_records,
    etag_header,
    ReadOnlyModeError,
    VersionConflictError,
    normalize_advisees_payload,
    normalize_if_match,
    normalize_payload,
    normalize_regular_events_payload,
    save_alumni_submission,
)


ROOT = Path(__file__).resolve().parent
BUCKET_NAME = os.environ.get("DATA_BUCKET") or os.environ.get("COURSES_BUCKET", "")
COURSES_OBJECT = os.environ.get("COURSES_OBJECT", "data/courses.json")
ADVISEES_OBJECT = os.environ.get("ADVISEES_OBJECT", "data/advisees.json")
REGULAR_EVENTS_OBJECT = os.environ.get("REGULAR_EVENTS_OBJECT", "data/regular_event.json")
ADMIN_EMAILS = {
    email.strip().lower()
    for email in os.environ.get("ADMIN_EMAILS", "").split(",")
    if email.strip()
}
IAP_JWT_AUDIENCE = os.environ.get("IAP_JWT_AUDIENCE", "").strip()
IAP_JWT_HEADER = "X-Goog-IAP-JWT-Assertion"
IAP_ISSUER = "https://cloud.google.com/iap"
IAP_CERTS_URL = "https://www.gstatic.com/iap/verify/public_key"

app = Flask(__name__)


def get_blob(object_name):
    if not BUCKET_NAME:
        return None
    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)
    return bucket.blob(object_name)


def backup_object_name(object_name):
    base_name = Path(object_name).stem
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"backup/{base_name}-{timestamp}.json"


def backup_existing_blob(blob, object_name):
    if not blob or not blob.exists():
        return None
    backup_blob = blob.bucket.blob(backup_object_name(object_name))
    backup_blob.cache_control = "no-cache"
    backup_blob.upload_from_string(
        blob.download_as_bytes(),
        content_type=blob.content_type or "application/json; charset=utf-8",
    )
    return backup_blob.name


def current_object_version(object_name):
    blob = get_blob(object_name)
    if blob and blob.exists():
        blob.reload()
        payload = json.loads(blob.download_as_text(encoding="utf-8"))
        return canonical_etag(payload)

    local_file = ROOT / object_name
    if local_file.exists():
        payload = json.loads(local_file.read_text(encoding="utf-8"))
        return canonical_etag(payload)

    return None


def current_object_response(object_name):
    blob = get_blob(object_name)
    if blob and blob.exists():
        blob.reload()
        body = blob.download_as_text(encoding="utf-8")
        payload = json.loads(body)
        return Response(
            body,
            mimetype="application/json",
            headers={"ETag": etag_header(payload), "Cache-Control": "no-store"},
        )

    local_file = ROOT / object_name
    if local_file.exists():
        body = local_file.read_text(encoding="utf-8")
        payload = json.loads(body)
        return Response(
            body,
            mimetype="application/json",
            headers={"ETag": etag_header(payload), "Cache-Control": "no-store"},
        )

    return None


def save_object(object_name, payload, normalizer):
    blob = get_blob(object_name)
    current_version = None
    current_generation = 0
    if blob and blob.exists():
        blob.reload()
        current_payload = json.loads(blob.download_as_text(encoding="utf-8"))
        current_version = canonical_etag(current_payload)
        current_generation = int(blob.generation or 0)
    else:
        local_file = ROOT / object_name
        if local_file.exists():
            current_version = canonical_etag(json.loads(local_file.read_text(encoding="utf-8")))

    expected_version = normalize_if_match(request.headers.get("If-Match", ""))
    if current_version and expected_version != current_version:
        return jsonify(
            {
                "error": "資料已在另一個版本更新，請先重新載入最新資料再儲存。",
                "currentVersion": current_version,
            }
        ), 409, {"ETag": f'"{current_version}"'}

    normalized = normalizer(payload)
    body = json.dumps(normalized, ensure_ascii=False, indent=2) + "\n"

    blob = get_blob(object_name)
    if blob:
        backup_existing_blob(blob, object_name)
        blob.cache_control = "no-cache"
        try:
            blob.upload_from_string(
                body,
                content_type="application/json; charset=utf-8",
                if_generation_match=current_generation,
            )
        except PreconditionFailed:
            latest_version = current_object_version(object_name) or ""
            return jsonify(
                {
                    "error": "資料已在另一個版本更新，請先重新載入最新資料再儲存。",
                    "currentVersion": latest_version,
                }
            ), 409, {"ETag": f'"{latest_version}"'}
    else:
        local_file = ROOT / object_name
        local_file.parent.mkdir(parents=True, exist_ok=True)
        local_file.write_text(body, encoding="utf-8")

    return Response(body, mimetype="application/json", headers={"ETag": etag_header(normalized)})


def authenticated_email():
    """Return the email from a valid IAP-signed assertion, or ``None``.

    ``X-Goog-Authenticated-User-Email`` is deliberately not read here: a caller
    that bypasses IAP can forge that unsigned compatibility header. IAP's signed
    JWT proves both the identity and that the assertion was issued for this
    Cloud Run service.
    """
    assertion = request.headers.get(IAP_JWT_HEADER, "").strip()
    if not assertion or not IAP_JWT_AUDIENCE:
        return None
    try:
        claims = id_token.verify_token(
            assertion,
            google_auth_requests.Request(),
            audience=IAP_JWT_AUDIENCE,
            certs_url=IAP_CERTS_URL,
        )
    except Exception:
        app.logger.warning("Rejected request with an invalid IAP assertion.")
        return None

    if claims.get("iss") != IAP_ISSUER:
        app.logger.warning("Rejected request with an unexpected IAP issuer.")
        return None
    email = claims.get("email")
    subject = claims.get("sub")
    if not isinstance(email, str) or not email.strip() or not isinstance(subject, str) or not subject:
        app.logger.warning("Rejected IAP assertion without an email and subject.")
        return None
    return email.strip().lower()


def require_admin():
    if not ADMIN_EMAILS:
        app.logger.error("ADMIN_EMAILS is not configured; denying all admin requests.")
        return jsonify({"error": "Forbidden"}), 403
    email = authenticated_email()
    if email in ADMIN_EMAILS:
        return None
    return jsonify({"error": "Forbidden"}), 403


@app.get("/")
def index():
    denied = require_admin()
    if denied:
        return denied
    return send_from_directory(ROOT, "course_admin.html")


@app.get("/api/admin-state")
def admin_state():
    denied = require_admin()
    if denied:
        return denied
    configured = bool(BUCKET_NAME)
    alumni_configured = bool(os.environ.get("ALUMNI_STORAGE_BUCKET", "").strip())
    return jsonify({
        "readOnly": not configured,
        "reason": "" if configured else "未設定雲端資料 bucket",
        "remoteConfigured": configured,
        "lastSyncAt": None,
        "alumniReadOnly": not alumni_configured,
        "alumniReason": "" if alumni_configured else "未設定系友資料 bucket",
    })


@app.get("/courses-data.js")
def courses_data_js():
    return send_from_directory(ROOT, "courses-data.js")


@app.get("/advisees-data.js")
def advisees_data_js():
    return send_from_directory(ROOT, "advisees-data.js")


@app.get("/api/courses")
def get_courses():
    denied = require_admin()
    if denied:
        return denied
    response = current_object_response(COURSES_OBJECT)
    if response:
        return response
    return jsonify({"error": f"{COURSES_OBJECT} not found"}), 404


@app.put("/api/courses")
def put_courses():
    denied = require_admin()
    if denied:
        return denied

    payload = request.get_json(force=True)
    return save_object(COURSES_OBJECT, payload, normalize_payload)


@app.get("/api/advisees")
def get_advisees():
    denied = require_admin()
    if denied:
        return denied
    response = current_object_response(ADVISEES_OBJECT)
    if response:
        return response
    return jsonify({"error": f"{ADVISEES_OBJECT} not found"}), 404


@app.put("/api/advisees")
def put_advisees():
    denied = require_admin()
    if denied:
        return denied

    payload = request.get_json(force=True)
    return save_object(ADVISEES_OBJECT, payload, normalize_advisees_payload)


@app.get("/api/regular-events")
def get_regular_events():
    denied = require_admin()
    if denied:
        return denied
    response = current_object_response(REGULAR_EVENTS_OBJECT)
    if response:
        return response
    return jsonify({"error": f"{REGULAR_EVENTS_OBJECT} not found"}), 404


@app.put("/api/regular-events")
def put_regular_events():
    denied = require_admin()
    if denied:
        return denied

    payload = request.get_json(force=True)
    return save_object(REGULAR_EVENTS_OBJECT, payload, normalize_regular_events_payload)


@app.get("/api/alumni-submissions")
def get_alumni_submissions():
    denied = require_admin()
    if denied:
        return denied
    try:
        payload = {
            "schemaVersion": 1,
            "updatedAt": datetime.now(timezone.utc).isoformat(),
            "submissions": list_alumni_submission_records(),
        }
        return Response(
            json.dumps(payload, ensure_ascii=False),
            mimetype="application/json",
            headers={"ETag": etag_header(payload), "Cache-Control": "no-store"},
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.put("/api/alumni-submissions/<path:object_name>")
def put_alumni_submission(object_name):
    denied = require_admin()
    if denied:
        return denied

    payload = request.get_json(force=True)
    expected_version = normalize_if_match(request.headers.get("If-Match", ""))
    try:
        saved = save_alumni_submission(object_name, payload, expected_version)
        return Response(
            json.dumps(saved, ensure_ascii=False),
            mimetype="application/json",
            headers={"ETag": etag_header(saved), "Cache-Control": "no-store"},
        )
    except VersionConflictError as exc:
        return jsonify({"error": str(exc), "currentVersion": exc.current_version}), 409
    except ReadOnlyModeError as exc:
        return jsonify({"error": str(exc), "readOnly": True}), 403
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.delete("/api/alumni-submissions/<path:object_name>")
def remove_alumni_submission(object_name):
    denied = require_admin()
    if denied:
        return denied

    expected_version = normalize_if_match(request.headers.get("If-Match", ""))
    try:
        deleted = delete_alumni_submission(object_name, expected_version)
        return jsonify(deleted)
    except VersionConflictError as exc:
        return jsonify({"error": str(exc), "currentVersion": exc.current_version}), 409
    except ReadOnlyModeError as exc:
        return jsonify({"error": str(exc), "readOnly": True}), 403
    except FileNotFoundError as exc:
        return jsonify({"error": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


from faculty_portal.routes import register_faculty
register_faculty(app, require_admin)
from news_portal.routes import register_news
register_news(app, require_admin)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
