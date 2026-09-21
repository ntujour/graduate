"""News routes mounted inside the existing Cloud Run admin application."""
import hashlib
import os
import re
from io import BytesIO
from pathlib import Path

from flask import Blueprint, jsonify, request, send_from_directory
from PIL import Image, ImageOps, UnidentifiedImageError

from .store import CloudStore, Conflict, LocalStore, publish, save_draft

ROOT = Path(__file__).parent
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_IMAGE_EDGE = 2400


def register_news(app, require_admin, store=None):
    if store is None:
        bucket = os.environ.get("NEWS_DRAFT_BUCKET") or os.environ.get("FACULTY_DRAFT_BUCKET")
        if not bucket:
            return
        store = CloudStore(bucket, os.environ["DATA_BUCKET"], os.environ.get("NEWS_PUBLIC_PREFIX", "news/v1"))
    bp = Blueprint("news_admin", __name__, url_prefix="/news-admin")

    @bp.before_request
    def authorize():
        denied = require_admin()
        if denied:
            return denied
        if request.method in ("POST", "PUT", "DELETE"):
            is_image = request.endpoint == "news_admin.upload_image"
            if request.headers.get("X-News-Request") != "1" or (not is_image and not request.is_json):
                return jsonify(error="不允許的編輯請求"), 403

    @bp.after_request
    def headers(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' https: http:; "
            "connect-src 'self' https://storage.googleapis.com; object-src 'none'; base-uri 'none'; "
            "frame-ancestors 'self'")
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
        return jsonify(data=data, version=token, current=current, publishedVersion=published)

    @bp.put("/api/draft")
    def update():
        body = request.get_json()
        save_draft(store, body["data"], str(body.get("version", "")))
        return draft()

    @bp.post("/api/publish")
    def release():
        body = request.get_json()
        publish(store, str(body.get("version", "")), str(body.get("publishedVersion", "")))
        return draft()

    @bp.post("/api/image/<slug>")
    def upload_image(slug):
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,95}", slug):
            return jsonify(error="消息識別碼格式錯誤"), 400
        uploaded = request.files.get("image")
        if uploaded is None or not uploaded.filename:
            return jsonify(error="請選擇圖片"), 400
        if request.content_length and request.content_length > MAX_IMAGE_BYTES + 65536:
            return jsonify(error="圖片不可超過 10 MB"), 413
        raw = uploaded.stream.read(MAX_IMAGE_BYTES + 1)
        if len(raw) > MAX_IMAGE_BYTES:
            return jsonify(error="圖片不可超過 10 MB"), 413
        try:
            with Image.open(BytesIO(raw)) as source:
                source.verify()
            with Image.open(BytesIO(raw)) as source:
                if source.width * source.height > 50_000_000:
                    raise ValueError("圖片像素過大")
                image = ImageOps.exif_transpose(source)
                image.thumbnail((MAX_IMAGE_EDGE, MAX_IMAGE_EDGE), Image.Resampling.LANCZOS)
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
            return jsonify(error="圖片格式無法辨識，請使用 JPG、PNG 或 WebP"), 400
        body = output.getvalue()
        filename = f"{slug}-{hashlib.sha256(body).hexdigest()[:20]}.jpg"
        url = store.upload_media(filename, body, "image/jpeg")
        return jsonify(url=url, width=width, height=height)

    @bp.get("/config.json")
    def config():
        base = (f"https://storage.googleapis.com/{store.public_bucket}/{store.prefix}/"
                if isinstance(store, CloudStore) else "/news-admin/feed/")
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
        return jsonify(data)

    app.register_blueprint(bp)
