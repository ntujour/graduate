"""Run the news admin locally with disposable storage for browser checks."""
import os
import tempfile

from flask import Flask

from news_portal.import_local import build_seed
from news_portal.routes import register_news
from news_portal.store import LocalStore, save_draft

app = Flask(__name__)
root = os.environ.get("NEWS_LOCAL_STORE") or tempfile.mkdtemp(prefix="ntujour-news-")
store = LocalStore(root)
data, token = store.read("draft.json")
if data is None:
    save_draft(store, build_seed(), token)
register_news(app, lambda: None, store)

if __name__ == "__main__":
    app.run("127.0.0.1", int(os.environ.get("PORT", "5091")))
