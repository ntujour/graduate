import argparse
import csv
import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen


SEMESTER_RE = re.compile(r"^\d{3}-[12]$")


def read_csv_source(source):
    if source.startswith(("http://", "https://")):
        with urlopen(source, timeout=30) as response:
            text = response.read().decode("utf-8-sig")
        return text, {"type": "url", "value": source}

    path = Path(source)
    text = path.read_text(encoding="utf-8-sig")
    return text, {"type": "file", "value": str(path)}


def read_csv_rows(source):
    text, source_info = read_csv_source(source)
    reader = csv.DictReader(io.StringIO(text))
    return list(reader), reader.fieldnames or [], source_info


def parse_bool_flag(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def build_course(row, index, semesters, merge_row=None):
    merged = dict(merge_row or {})
    merged.update({key: value for key, value in row.items() if value not in (None, "")})

    sequence = str(merged.get("s") or index).strip()
    course = {
        "id": f"course-{int(sequence):03d}" if sequence.isdigit() else f"course-{index:03d}",
        "sequence": int(sequence) if sequence.isdigit() else index,
        "cname": (merged.get("cname") or "").strip(),
        "cname_en": (merged.get("cname_en") or "").strip(),
        "offer_by": (merged.get("offer_by") or "").strip(),
        "category": (merged.get("category") or "").strip(),
        "credit": int(str(merged.get("credit") or "0").strip() or 0),
        "last": (merged.get("last") or "").strip(),
        "period": (merged.get("period") or "").strip(),
        "active": (merged.get("active") or "").strip(),
        "info": (merged.get("info") or "").strip(),
        "skill": (merged.get("skill") or "").strip(),
        "description": (merged.get("description") or "").strip(),
        "offerings": {},
    }

    for semester in semesters:
        value = row.get(semester)
        if value in (None, "") and merge_row:
            value = merge_row.get(semester)
        course["offerings"][semester] = parse_bool_flag(value)

    return course


def build_payload(source, merge_missing=None):
    rows, fields, source_info = read_csv_rows(source)
    merge_by_name = {}
    merge_info = None

    if merge_missing:
        merge_rows, merge_fields, merge_source = read_csv_rows(merge_missing)
        merge_by_name = {
            (row.get("cname") or "").strip(): row
            for row in merge_rows
            if (row.get("cname") or "").strip()
        }
        fields = list(dict.fromkeys([*(fields or []), *(merge_fields or [])]))
        merge_info = merge_source

    semesters = [field for field in fields if SEMESTER_RE.match(field)]
    courses = []

    for index, row in enumerate(rows, start=1):
        name = (row.get("cname") or "").strip()
        if not name:
            continue
        courses.append(build_course(row, index, semesters, merge_by_name.get(name)))

    return {
        "schemaVersion": 1,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "source": {
            "type": "canonical-json",
            "value": "data/courses.json",
            "note": "Official source for public pages and admin edits. CSV files are import sources only.",
        },
        "importSource": source_info,
        "mergedMissingFrom": merge_info,
        "semesters": semesters,
        "courses": courses,
    }


def main():
    parser = argparse.ArgumentParser(description="Convert course CSV data to JSON.")
    parser.add_argument(
        "--source",
        default="data/courses.csv",
        help="CSV file path or published CSV URL.",
    )
    parser.add_argument(
        "--merge-missing",
        default=None,
        help="Optional CSV file used to preserve fields missing from the source, matched by cname.",
    )
    parser.add_argument(
        "--output",
        default="data/courses.json",
        help="JSON output path.",
    )
    args = parser.parse_args()

    payload = build_payload(args.source, args.merge_missing)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {output} with {len(payload['courses'])} courses.")


if __name__ == "__main__":
    main()
