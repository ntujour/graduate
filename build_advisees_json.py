import argparse
import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen


DEFAULT_SOURCE = "data/advisees.csv"
DEFAULT_FULLTIME_ADVISORS = ["林麗雲", "洪貞玲", "林照真", "謝吉隆", "劉好迪", "蔡蕙如", "詹怡宜"]
DEFAULT_ADJUNCT_ADVISORS = ["李志德", "劉力仁", "梁玉芳", "方德琳", "王泰俐", "蕭富元", "鄭凱駿", "黃哲斌", "李雪莉", "陳順孝"]


def read_csv_source(source):
    if source.startswith(("http://", "https://")):
        with urlopen(source, timeout=30) as response:
            text = response.read().decode("utf-8-sig")
        return text, {"type": "url", "value": source}

    path = Path(source)
    return path.read_text(encoding="utf-8-sig"), {"type": "file", "value": str(path)}


def read_rows(source):
    text, source_info = read_csv_source(source)
    reader = csv.DictReader(io.StringIO(text))
    return list(reader), source_info


def infer_statuses(advisor, thesis_title):
    advisor = (advisor or "").strip()
    thesis_title = (thesis_title or "").strip()
    if not advisor:
        return {"advised": False, "proposal": False, "final": False}

    final = bool(thesis_title and thesis_title not in {"在學中", "休學"})
    return {
        "advised": True,
        "proposal": final,
        "final": final,
    }


def build_student(row, index):
    advisor = (row.get("指導老師") or "").strip()
    thesis_title = (row.get("論文題目") or "").strip()
    return {
        "id": f"advisee-{index:03d}",
        "cohort": (row.get("屆次") or "").strip(),
        "admissionYear": (row.get("入學年度") or "").strip(),
        "name": (row.get("學生姓名") or "").strip(),
        "thesisType": (row.get("論文類型") or "").strip(),
        "advisor": advisor,
        "thesisTitle": thesis_title,
        **infer_statuses(advisor, thesis_title),
        "job": (row.get("工作") or "").strip(),
        "workType": (row.get("類型") or "").strip(),
        "url": (row.get("url") or "").strip(),
    }


def build_payload(source):
    rows, source_info = read_rows(source)
    students = [
        build_student(row, index)
        for index, row in enumerate(rows, start=1)
        if (row.get("學生姓名") or "").strip()
    ]

    return {
        "schemaVersion": 1,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "source": {
            "type": "canonical-json",
            "value": "data/advisees.json",
            "note": "Official source for public pages and admin edits. Word and CSV files are import sources only.",
        },
        "importSource": source_info,
        "advisors": {
            "fulltime": DEFAULT_FULLTIME_ADVISORS,
            "adjunct": DEFAULT_ADJUNCT_ADVISORS,
        },
        "students": students,
    }


def main():
    parser = argparse.ArgumentParser(description="Convert advisee CSV data to JSON.")
    parser.add_argument("--source", default=DEFAULT_SOURCE, help="CSV file path or published CSV URL.")
    parser.add_argument("--output", default="data/advisees.json", help="JSON output path.")
    args = parser.parse_args()

    payload = build_payload(args.source)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {output} with {len(payload['students'])} students.")


if __name__ == "__main__":
    main()
