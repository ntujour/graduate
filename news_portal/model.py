"""Validate bilingual news drafts and build immutable public releases."""
import hashlib
import json
import re
from urllib.parse import urlparse

import bleach

LANGUAGES = ("zh", "en")
COLLECTIONS = ("news", "activities")
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,95}$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TAGS = {"p", "br", "strong", "b", "em", "i", "u", "s", "a", "ul", "ol", "li",
        "h2", "h3", "h4", "h5", "h6", "blockquote", "hr", "sup", "sub", "span",
        "table", "thead", "tbody", "tr", "th", "td", "img", "code", "pre", "figure", "figcaption"}


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def version(value):
    return hashlib.sha256(encode(value)).hexdigest()


def clean_html(value):
    return bleach.clean(value, tags=TAGS, attributes={
        "a": ["href", "title", "target", "rel"], "img": ["src", "alt", "title"],
        "ol": ["start", "reversed"], "li": ["value"], "th": ["colspan", "rowspan"],
        "td": ["colspan", "rowspan"],
    }, protocols={"https", "http", "mailto"}, strip=True)


def checked_url(value):
    if not isinstance(value, str):
        raise ValueError("網址必須是文字")
    if value and not value.startswith("/"):
        parsed = urlparse(value)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("圖片與連結請使用完整網址或站內絕對路徑")
    return value


def validate(payload):
    if not isinstance(payload, dict) or payload.get("schemaVersion") != 1:
        raise ValueError("不支援的消息資料格式")
    records = payload.get("records")
    if not isinstance(records, list):
        raise ValueError("消息資料必須是清單")
    seen = set()
    for record in records:
        if not isinstance(record, dict) or not SLUG.fullmatch(str(record.get("id", ""))):
            raise ValueError("消息識別碼格式錯誤")
        if record["id"] in seen:
            raise ValueError("消息識別碼重複")
        seen.add(record["id"])
        collection = record.get("collection", "news")
        if collection not in COLLECTIONS:
            raise ValueError("資料類型必須是最新消息或活動資訊")
        if not DATE.fullmatch(str(record.get("date", ""))):
            raise ValueError("消息日期格式錯誤")
        if not isinstance(record.get("image"), str) or not isinstance(record.get("pinned"), bool):
            raise ValueError("圖片或置頂格式錯誤")
        checked_url(record["image"])
        if not isinstance(record.get("gallery_images", []), list):
            raise ValueError("相關照片格式錯誤")
        for gallery_image in record.get("gallery_images", []):
            checked_url(gallery_image)
        locales = record.get("locales", {})
        for lang in LANGUAGES:
            localized = locales.get(lang)
            if not isinstance(localized, dict) or not isinstance(localized.get("visible"), bool):
                raise ValueError("中英文顯示狀態格式錯誤")
            for key in ("title", "tag", "excerpt", "bodyHtml", "externalUrl"):
                if not isinstance(localized.get(key), str):
                    raise ValueError("中英文欄位格式錯誤")
            checked_url(localized["externalUrl"])
            if localized["visible"] and not localized["title"].strip():
                raise ValueError("要發布的語言必須填寫標題")
    return payload


def public_item(record, lang):
    localized = record["locales"][lang]
    return {
        "schemaVersion": 1, "id": record["id"], "lang": lang,
        "collection": record.get("collection", "news"), "date": record["date"],
        "image": record["image"], "pinned": record["pinned"],
        "gallery_images": record.get("gallery_images", []),
        "image_crop": record.get("image_crop", {}),
        "gallery_images_crop": record.get("gallery_images_crop", {}),
        "time": record.get("time", ""), "location": record.get("location", ""),
        "title": localized["title"], "tag": localized["tag"],
        "excerpt": localized["excerpt"], "externalUrl": localized["externalUrl"],
        "bodyHtml": clean_html(localized["bodyHtml"]),
    }


def release_files(payload):
    validate(payload)
    records = sorted(payload["records"], key=lambda r: (not r["pinned"], r["date"], r["id"]), reverse=False)
    result = {}
    for lang in LANGUAGES:
        for collection in COLLECTIONS:
            items = []
            visible = [r for r in records if r.get("collection", "news") == collection and r["locales"][lang]["visible"]]
            visible.sort(key=lambda r: (r["pinned"], r["date"], r["id"]), reverse=True)
            for record in visible:
                data = public_item(record, lang)
                result[f"{record['id']}.{lang}.json"] = data
                items.append({k: data[k] for k in ("id", "collection", "date", "title", "tag", "excerpt", "image", "pinned", "externalUrl")})
            result[f"index.{collection}.{lang}.json"] = {
                "schemaVersion": 1, "collection": collection, "lang": lang, "items": items,
            }
            # Preserve the original feed URL for existing news readers.
            if collection == "news":
                result[f"index.{lang}.json"] = {"schemaVersion": 1, "lang": lang, "items": items}
    release = version(result)
    return release, result
