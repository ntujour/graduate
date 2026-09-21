"""One editable bilingual record; small public indexes and per-language profiles."""
import hashlib
import json
import re
from urllib.parse import urlparse

import bleach

LANGUAGES = ("zh", "en")
CATEGORIES = {
    "fulltime", "parttime", "practical", "former_practical",
    "honorary", "retired", "joint", "staff",
}
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,79}$")
TAGS = {"p", "br", "strong", "b", "em", "i", "u", "s", "a", "ul", "ol", "li",
        "h2", "h3", "h4", "h5", "h6", "blockquote", "hr", "sup", "sub", "span",
        "table", "thead", "tbody", "tr", "th", "td", "img", "code", "pre"}


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
    if value and (urlparse(value).scheme not in ("http", "https") or not urlparse(value).netloc):
        raise ValueError("照片與網站請使用完整 http／https 網址")
    return value


def validate(payload):
    if not isinstance(payload, dict) or payload.get("schemaVersion") != 1:
        raise ValueError("不支援的教師資料格式")
    records = payload.get("records")
    if not isinstance(records, list) or not records:
        raise ValueError("教師資料不能為空")
    seen = set()
    for record in records:
        if not isinstance(record, dict) or not SLUG.fullmatch(str(record.get("id", ""))):
            raise ValueError("教師識別碼格式錯誤")
        if record["id"] in seen:
            raise ValueError("教師識別碼重複")
        seen.add(record["id"])
        if not isinstance(record.get("order"), int) or record.get("category") not in CATEGORIES:
            raise ValueError("排序與分類格式錯誤")
        additional = record.get("additionalCategories", [])
        if (not isinstance(additional, list) or
                any(value not in CATEGORIES for value in additional) or
                len(additional) != len(set(additional)) or
                record["category"] in additional):
            raise ValueError("額外列入分類格式錯誤")
        shared = record.get("shared", {})
        for key in ("email", "phone", "office", "photo", "website"):
            if not isinstance(shared.get(key), str):
                raise ValueError("共用欄位格式錯誤")
        checked_url(shared["photo"])
        checked_url(shared["website"])
        for lang in LANGUAGES:
            localized = record.get("locales", {}).get(lang)
            if not isinstance(localized, dict):
                raise ValueError("中英文資料必須同時保留")
            for key in ("name", "title", "bodyHtml", "expertise", "originalUrl"):
                if not isinstance(localized.get(key), str):
                    raise ValueError("語言欄位格式錯誤")
            if not localized["name"].strip():
                raise ValueError("姓名不能為空")
            if "visible" in localized and not isinstance(localized["visible"], bool):
                raise ValueError("教師頁顯示狀態必須是勾選值")
            checked_url(localized["originalUrl"])
    return payload


def is_visible(record, lang):
    """Keep legacy drafts compatible while allowing each language to opt out."""
    value = record["locales"][lang].get("visible")
    if isinstance(value, bool):
        return value
    return lang == "zh" or record["category"] == "fulltime"


def category_memberships(record):
    return [record["category"], *record.get("additionalCategories", [])]


def validate_publishable(payload):
    validate(payload)
    for record in payload["records"]:
        visible_languages = [lang for lang in LANGUAGES if is_visible(record, lang)]
        if not visible_languages:
            continue
        if not record["shared"]["photo"].strip():
            raise ValueError(f"{record['id']} 已設為公開，請先上傳照片")
        for lang in visible_languages:
            if not record["locales"][lang]["title"].strip():
                raise ValueError(f"{record['id']} 已設為公開，請補上 {lang} 職稱")
    return payload


def profile(record, lang):
    localized = record["locales"][lang]
    return {
        "schemaVersion": 1, "id": record["id"], "lang": lang,
        "category": record["category"], "order": record["order"],
        "categories": category_memberships(record),
        **record["shared"], **{k: localized[k] for k in ("name", "title", "expertise", "originalUrl")},
        # Only the published representation is sanitized; originals stay intact in draft.
        "bodyHtml": clean_html(localized["bodyHtml"]),
    }


def release_files(payload):
    validate_publishable(payload)
    records = sorted(payload["records"], key=lambda r: (r["order"], r["id"]))
    result = {}
    for lang in LANGUAGES:
        items = []
        for record in records:
            if not is_visible(record, lang):
                continue
            data = profile(record, lang)
            result[f"{record['id']}.{lang}.json"] = data
            items.append({k: data[k] for k in ("id", "name", "title", "category", "categories", "order", "photo")})
        result[f"index.{lang}.json"] = {"schemaVersion": 1, "lang": lang, "items": items}
    # Hash final files, not private import metadata; unchanged public content keeps its URL.
    release = version(result)
    return release, result
