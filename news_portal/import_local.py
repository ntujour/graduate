"""Build the initial cloud news draft from current Chinese and English site JSON."""
import json
import re
from html import escape
from pathlib import Path


SERVICE_ROOT = Path(__file__).resolve().parents[1]


def main_site_root():
    """Locate the sibling main-site project in current and legacy workspaces."""
    candidates = (
        SERVICE_ROOT.parents[1] / "main-site",
        SERVICE_ROOT.parent,
    )
    for candidate in candidates:
        if (candidate / "public_html/data/news.json").is_file():
            return candidate
    raise FileNotFoundError("找不到 main-site 的消息匯入資料；請確認完整 ntujour workspace 結構")


def localized(visible=False, title="", tag="", excerpt="", body="", external=""):
    return {"visible": visible, "title": title or "", "tag": tag or "", "excerpt": excerpt or "",
            "bodyHtml": body or "", "externalUrl": external or ""}


def build_seed():
    root = main_site_root()
    zh_items = json.loads((root / "public_html/data/news.json").read_text())
    en_items = json.loads((root / "local_generator_app/generator/template/en/data/news.json").read_text())
    records = []
    for item in zh_items:
        records.append({
            "id": item["id"], "collection": "news", "date": item["date"], "image": item.get("image", ""),
            "pinned": bool(item.get("featured")),
            "locales": {
                "zh": localized(True, item.get("title"), "、".join(item.get("hashtags") or []),
                                item.get("excerpt"), item.get("content_html") or item.get("content"),
                                item.get("external_url", "")),
                "en": localized(),
            },
        })
    used = {r["id"] for r in records}
    for number, item in enumerate(en_items, 1):
        base = "en-" + item["date"] + "-" + re.sub(r"[^a-z0-9]+", "-", item["title"].lower()).strip("-")[:45]
        slug = base
        suffix = 2
        while slug in used:
            slug = f"{base}-{suffix}"
            suffix += 1
        used.add(slug)
        records.append({
            "id": slug, "collection": "news", "date": item["date"], "image": item.get("image", ""), "pinned": bool(item.get("pinned")),
            "locales": {
                "zh": localized(),
                "en": localized(True, item.get("title"), item.get("tag"), item.get("excerpt"),
                                f"<p>{escape(item.get('excerpt', ''))}</p>", item.get("url", "")),
            },
        })
    activity_items = json.loads((root / "public_html/data/activities.json").read_text())
    for item in activity_items:
        records.append({
            "id": item["id"], "collection": "activities", "date": item["date"],
            "image": item.get("image", ""), "pinned": bool(item.get("featured")),
            "gallery_images": item.get("gallery_images", []),
            "image_crop": item.get("image_crop", {}),
            "gallery_images_crop": item.get("gallery_images_crop", {}),
            "time": item.get("time", ""), "location": item.get("location", ""),
            "locales": {
                "zh": localized(True, item.get("title"), "、".join(item.get("hashtags") or []),
                                item.get("excerpt"), item.get("content_html") or item.get("content"),
                                item.get("external_url", "")),
                "en": localized(),
            },
        })
    return {"schemaVersion": 1, "records": records}


if __name__ == "__main__":
    print(json.dumps(build_seed(), ensure_ascii=False, indent=2))
