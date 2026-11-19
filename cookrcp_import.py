"""Import the ingredient and portion references from a COOKRCP01 CSV."""

import argparse
import csv
import json
import re
from html import unescape
from pathlib import Path

from catalog_import import key


SOURCE = "https://www.foodsafetykorea.go.kr/api/newDatasetDetail.do?svc_no=COOKRCP01"
COLUMNS = {"RCP_SEQ", "RCP_NM", "RCP_WAY2", "RCP_PAT2", "RCP_PARTS_DTLS"}
LEADING_PORTIONS = re.compile(r"^(?:\[\s*(\d+)\s*인분\s*\]|(?:재료\s*[:：]?\s*)?(\d+)\s*인분(?:\s*기준)?(?=\s|[:：]|$))")


def read_recipes(path):
    for encoding in ("utf-8-sig", "cp949"):
        try:
            with path.open(encoding=encoding, newline="") as stream:
                reader = csv.DictReader(stream)
                if not COLUMNS <= set(reader.fieldnames or []):
                    raise ValueError("COOKRCP01 CSV의 필수 열을 확인해 주세요.")
                return list(reader)
        except UnicodeDecodeError:
            continue
    raise ValueError("COOKRCP01 CSV를 UTF-8 또는 CP949로 저장해 주세요.")


def import_recipes(path):
    entries = {}
    ids = set()
    for row in read_recipes(path):
        fields = {column: (row[column] or "").strip() for column in COLUMNS}
        record_id, name = fields["RCP_SEQ"], fields["RCP_NM"]
        if not record_id.isascii() or not record_id.isdecimal() or not name or record_id in ids:
            raise ValueError(f"레시피 일련번호 또는 메뉴명을 확인해 주세요 ({record_id}).")
        ids.add(record_id)
        ingredients = unescape(fields["RCP_PARTS_DTLS"])
        ingredients = re.sub(r"<br\s*/?>", "\n", ingredients, flags=re.I)
        ingredients = re.sub(r"</?strong>", "", ingredients, flags=re.I).strip()
        portion = LEADING_PORTIONS.match(ingredients)
        portions = int(portion[1] or portion[2]) if portion else None
        entries.setdefault(key(name), []).append({
            "id": record_id, "name": name, "category": fields["RCP_PAT2"],
            "method": fields["RCP_WAY2"], "ingredients": ingredients, "servings": portions or None,
        })
    return {"source": SOURCE, "entries": dict(sorted(entries.items()))}


def write_index(output, data):
    entries = (f"    {json.dumps(name, ensure_ascii=False)}: {json.dumps(variants, ensure_ascii=False)}"
               for name, variants in data["entries"].items())
    with output.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(f'{{\n  "source": {json.dumps(data["source"])},\n  "entries": {{\n')
        stream.write(",\n".join(entries))
        stream.write("\n  }\n}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    write_index(args.output, import_recipes(args.csv))
