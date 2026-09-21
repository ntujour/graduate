"""One-time, non-overwriting import from source Markdown + generated English data.

Run with the pilot Python environment from graduate/: python -m faculty_portal.import_local
The ordinary site builder never imports or publishes this feed.
"""
import argparse
import copy
import hashlib
import html
import json
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import urljoin, unquote

from .model import clean_html, validate
from .store import LocalStore, publish, save_draft


def sections_html(sections):
    parts = []
    for section in sections:
        parts.append("<h2>" + html.escape(section.get("heading", "")) + "</h2>")
        if section.get("type") == "list":
            parts.append("<ul>" + "".join("<li>" + item + "</li>" for item in section.get("items", [])) + "</ul>")
        elif section.get("type") == "text":
            parts.append("<p>" + html.escape(section.get("content", "")) + "</p>")
        else:
            raise ValueError("Unknown English section type; refusing lossy conversion")
    return "\n".join(parts)


def absolute_links(body, base):
    def replace(match):
        attribute, quote, value = match.groups()
        return attribute + "=" + quote + html.escape(urljoin(base, html.unescape(value)), quote=True) + quote
    return re.sub(r'(href|src)=([\"\'])(.*?)\2', replace, body)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset-base", default="http://127.0.0.1:8766/faculty/media/")
    args = parser.parse_args()
    graduate = Path(__file__).resolve().parents[1]
    workspace_candidates = (graduate.parents[1] / "main-site", graduate.parent)
    workspace = next((path for path in workspace_candidates if (path / "local_generator_app").is_dir()), None)
    if workspace is None:
        raise SystemExit("找不到 main-site/local_generator_app；請確認完整 ntujour workspace 結構。")
    output = graduate / "output/faculty-pilot"
    if (output / "draft.json").exists():
        raise SystemExit("已有試作草稿；禁止再次匯入覆蓋編輯。")
    app_dir = workspace / "local_generator_app"
    sys.path.insert(0, str(app_dir))
    from generator import site_builder as builder
    builder.configure_paths(content_dir=app_dir / "content", output_dir=output / "import-render",
                            template_root=app_dir / "generator/template")
    items = builder.parse_content(app_dir / "content/faculty")
    expected = len(list((app_dir / "content/faculty").glob("*.md")))
    if len(items) != expected:
        raise RuntimeError("來源解析數量不符，停止匯入")
    builder.generate_en_site_data(items, output / "import-render")
    # Preserve exact source bytes independently of public sanitization/normalization.
    shutil.copytree(app_dir / "content/faculty", output / "import-originals/zh", dirs_exist_ok=True)
    shutil.copytree(app_dir / "generator/template/en/data", output / "import-originals/en", dirs_exist_ok=True)
    ftp = json.loads((app_dir / "data/ftp_settings.json").read_text())
    site_base = "https://homepage.ntu.edu.tw/~" + ftp["username"] + "/"
    records = []
    english_templates = {}
    for path in (app_dir / "generator/template/en/data/faculty").glob("*.json"):
        detail = json.loads(path.read_text())
        name_zh = builder.normalize_faculty_name_zh(detail.get("nameZh", ""))
        if name_zh:
            english_templates[name_zh] = (path.stem, detail)
    media = output / "public/media"
    media.mkdir(parents=True, exist_ok=True)
    for item in items:
        if item.get("category_key") == "staff":
            continue
        generated_slug = builder.english_faculty_slug(item)
        generated = json.loads((output / "import-render/en/data/faculty" / (generated_slug + ".json")).read_text())
        _, parsed_zh = builder.split_bilingual_faculty_name(item["name"])
        matched = english_templates.get(builder.normalize_faculty_name_zh(parsed_zh or item["name"]))
        slug, original_en = matched if matched else (generated_slug, generated)
        en = copy.deepcopy(original_en)
        # Preserve the established English identity/sections, including legacy slug
        # mismatches that the old generator can otherwise silently overlook.
        en["slug"] = slug
        en["contacts"] = generated.get("contacts", [])
        if item.get("title_en"):
            en["title"] = item["title_en"]
        if item.get("bio_en"):
            en["sections"] = builder.parse_markdown_to_sections(item["bio_en"])
        if item.get("journals_en"):
            section = {"heading": "Journals", "type": "list", "items": item["journals_en"]}
            sections = en.setdefault("sections", [])
            for i, old in enumerate(sections):
                if old.get("heading", "").strip().lower() == "journals":
                    sections[i] = section
                    break
            else:
                sections.append(section)
        if item.get("expertise_en"):
            en.setdefault("sidebar", {})["teachingField"] = item["expertise_en"]
        if item.get("research_en"):
            en.setdefault("sidebar", {})["researchInterests"] = item["research_en"]
        zh_url = urljoin(site_base, "faculty/" + builder.faculty_detail_slug(item) + ".html")
        en_url = urljoin(site_base, "en/faculty/" + slug + ".html")
        source_photo = unquote(str(item.get("photo", "")).lstrip("/"))
        photo = ""
        for photo_path in (app_dir / source_photo, workspace / "public_html" / source_photo):
            if photo_path.is_file():
                name = hashlib.sha256(photo_path.read_bytes()).hexdigest()[:20] + photo_path.suffix.lower()
                shutil.copy2(photo_path, media / name)
                photo = urljoin(args.asset_base, name)
                break
        if not photo and item.get("photo"):
            photo = urljoin(site_base, str(item["photo"]).lstrip("/"))
        zh_body = absolute_links(item["content_html"], zh_url)
        en_body = absolute_links(sections_html(en.get("sections", [])), en_url)
        sidebar = en.get("sidebar", {})
        if sidebar.get("researchInterests"):
            en_body += "<h2>Research Interests</h2><ul>" + "".join("<li>" + html.escape(t) + "</li>" for t in sidebar["researchInterests"]) + "</ul>"
        if sidebar.get("externalLinks"):
            en_body += "<h2>External Links</h2><ul>" + "".join('<li><a href="' + html.escape(urljoin(en_url, link["url"]), quote=True) + '">' + html.escape(link["text"]) + '</a></li>' for link in sidebar["externalLinks"]) + "</ul>"
        record = {
            "id": slug, "order": int(item.get("order", 999)), "category": item["category_key"],
            "additionalCategories": list(item.get("additional_category_keys") or []),
            "shared": {"photo": photo, **{k: str(item.get(k) or "") for k in ("email", "phone", "office", "website")}},
            "locales": {
                "zh": {"name": item["name"], "title": str(item.get("title") or ""),
                       "expertise": "、".join(item.get("expertise", [])) if isinstance(item.get("expertise"), list) else str(item.get("expertise") or ""),
                       "bodyHtml": clean_html(zh_body), "originalUrl": zh_url},
                "en": {"name": en["name"], "title": en.get("title", ""),
                       "expertise": "; ".join(en.get("sidebar", {}).get("teachingField", [])),
                       "bodyHtml": clean_html(en_body), "originalUrl": en_url},
            },
            "importSource": {"zh": copy.deepcopy(item), "en": en,
                             "zhHtmlBeforeSanitization": zh_body, "enHtmlBeforeSanitization": en_body},
        }
        records.append(record)
    # JSON round-trip converts source datetime objects without touching source files.
    payload = json.loads(json.dumps({"schemaVersion": 1, "records": records}, ensure_ascii=False, default=str))
    validate(payload)
    store = LocalStore(output)
    save_draft(store, payload, "0")
    _, token = store.read("draft.json")
    current = publish(store, token, "0")
    print(json.dumps({"teachers": len(records), "staffExcluded": len(items)-len(records), "release": current["release"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
