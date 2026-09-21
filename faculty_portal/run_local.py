"""Run the EXISTING admin with the faculty module on loopback for verification."""
import os
from pathlib import Path

from cloudrun_admin import app, require_admin
from faculty_portal.routes import register_faculty
from faculty_portal.store import LocalStore

if os.environ.get("DATA_BUCKET") or os.environ.get("FACULTY_DRAFT_BUCKET"):
    raise RuntimeError("本機試作禁止使用雲端 bucket 環境變數")

register_faculty(app, require_admin, LocalStore(Path(__file__).parents[1] / "output/faculty-pilot"))

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8766, threaded=True)
