"""Faculty routes mounted inside the existing Cloud Run admin application."""
import os
import re
import html
import hashlib
from io import BytesIO
from pathlib import Path

from flask import Blueprint, jsonify, request, send_from_directory
from PIL import Image, ImageOps, UnidentifiedImageError

from .model import encode, profile
from .store import CloudStore, Conflict, LocalStore, publish, save_draft

ROOT = Path(__file__).parent
MAX_PHOTO_BYTES = 8 * 1024 * 1024
MAX_PHOTO_EDGE = 1600


def register_faculty(app, require_admin, store=None):
    if store is None:
        if not os.environ.get("FACULTY_DRAFT_BUCKET"):
            return  # Existing deployment remains unchanged until explicitly configured.
        store = CloudStore(os.environ["FACULTY_DRAFT_BUCKET"], os.environ["DATA_BUCKET"],
                           os.environ.get("FACULTY_PUBLIC_PREFIX", "faculty-pilot/v1"))
    bp = Blueprint("faculty", __name__, url_prefix="/faculty")

    @bp.before_request
    def authorize():
        denied = require_admin()
        if denied:
            return denied
        if request.method in ("POST", "PUT"):
            # No CORS on admin routes. Cross-origin forms cannot set this header.
            is_photo_upload = request.endpoint == "faculty.upload_photo"
            if (request.headers.get("X-Faculty-Request") != "1" or
                    (not is_photo_upload and not request.is_json)):
                return jsonify(error="不允許的編輯請求"), 403

    @bp.after_request
    def headers(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' https: http:; connect-src 'self' https://storage.googleapis.com; "
            "frame-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'self'")
        return response

    @bp.errorhandler(Conflict)
    def conflict(exc):
        return jsonify(error=str(exc)), 409

    @bp.errorhandler(ValueError)
    def invalid(exc):
        return jsonify(error=str(exc)), 400

    @bp.get("/")
    def admin():
        return send_from_directory(ROOT / "web", "admin.html")

    @bp.get("/assets/<path:filename>")
    def assets(filename):
        return send_from_directory(ROOT / "web", filename)

    @bp.get("/api/draft")
    def draft():
        data, token = store.read("draft.json")
        current, published = store.read("public/current.json")
        return jsonify(data=data, version=token, publishedVersion=published, current=current)

    @bp.put("/api/draft")
    def update():
        data = request.get_json()
        save_draft(store, data["data"], str(data.get("version", "")))
        return draft()

    @bp.post("/api/publish")
    def release():
        data = request.get_json()
        publish(store, str(data.get("version", "")), str(data.get("publishedVersion", "")))
        return draft()

    @bp.post("/api/photo/<slug>")
    def upload_photo(slug):
        data, _ = store.read("draft.json")
        if not any(record["id"] == slug for record in (data or {}).get("records", [])):
            return jsonify(error="教師不存在"), 404
        uploaded = request.files.get("photo")
        if uploaded is None or not uploaded.filename:
            return jsonify(error="請選擇照片檔案"), 400
        if request.content_length and request.content_length > MAX_PHOTO_BYTES + 65536:
            return jsonify(error="照片不可超過 8 MB"), 413
        raw = uploaded.stream.read(MAX_PHOTO_BYTES + 1)
        if len(raw) > MAX_PHOTO_BYTES:
            return jsonify(error="照片不可超過 8 MB"), 413
        try:
            with Image.open(BytesIO(raw)) as source:
                source.verify()
            with Image.open(BytesIO(raw)) as source:
                if source.width * source.height > 40_000_000:
                    raise ValueError("照片像素過大")
                image = ImageOps.exif_transpose(source)
                image.thumbnail((MAX_PHOTO_EDGE, MAX_PHOTO_EDGE), Image.Resampling.LANCZOS)
                if image.mode in ("RGBA", "LA") or "transparency" in image.info:
                    rgba = image.convert("RGBA")
                    background = Image.new("RGB", rgba.size, "white")
                    background.paste(rgba, mask=rgba.getchannel("A"))
                    image = background
                else:
                    image = image.convert("RGB")
                output = BytesIO()
                image.save(output, format="JPEG", quality=90, optimize=True)
                width, height = image.size
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
            return jsonify(error="照片格式無法辨識，請使用 JPG、PNG 或 WebP"), 400
        body = output.getvalue()
        digest = hashlib.sha256(body).hexdigest()[:20]
        filename = f"{slug}-{digest}.jpg"
        url = store.upload_media(filename, body, "image/jpeg")
        if url.startswith("/"):
            url = request.host_url.rstrip("/") + url
        return jsonify(url=url, width=width, height=height)

    @bp.get("/api/preview/<slug>/<lang>")
    def preview_data(slug, lang):
        if lang not in ("zh", "en"):
            return jsonify(error="語言不存在"), 404
        data, _ = store.read("draft.json")
        for record in (data or {}).get("records", []):
            if record["id"] == slug:
                return jsonify(profile(record, lang))
        return jsonify(error="教師不存在"), 404

    @bp.get("/preview/")
    def preview_page():
        base = (f"https://storage.googleapis.com/{store.public_bucket}/{store.prefix}/"
                if isinstance(store, CloudStore) else "/faculty/feed/")
        page = (ROOT / "web/index.html").read_text()
        page = page.replace('<html lang=', '<html data-faculty-feed="' + html.escape(base, quote=True) + '" lang=', 1)
        return app.response_class(page, mimetype="text/html")

    @bp.get("/config.json")
    def config():
        base = (f"https://storage.googleapis.com/{store.public_bucket}/{store.prefix}/"
                if isinstance(store, CloudStore) else "/faculty/feed/")
        return jsonify(feed=base)

    @bp.get("/media/<filename>")
    def local_media(filename):
        if not isinstance(store, LocalStore):
            return jsonify(error="圖片請直接讀取儲存空間"), 404
        return send_from_directory(store.root / "public/media", filename)

    @bp.get("/feed/<path:key>")
    def local_feed(key):
        if not isinstance(store, LocalStore):
            return jsonify(error="公開資料請直接讀取儲存空間"), 404
        if not re.fullmatch(r"current\.json|releases/[a-f0-9]{64}/[a-z0-9.-]+\.json", key):
            return jsonify(error="找不到資料"), 404
        data, _ = store.read("public/" + key)
        if data is None:
            return jsonify(error="尚未發布"), 404
        return app.response_class(encode(data), mimetype="application/json")

    app.register_blueprint(bp)
