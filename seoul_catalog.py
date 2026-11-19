"""Read the project's cross-checked Seoul market references and aliases."""
import re

from catalog_import import key


REFERENCE_SHEET = "메뉴별 참고가"
REFERENCE_HEADERS = (
    "대표 메뉴", "판매 규격", "판매 구성", "표본 유형", "참고가(원)",
    "매장 수", "최저(원)", "최고(원)", "자치구 수", "관측 자치구",
)
SERVING_UNITS = {"1인분": 0, "인분 미표기 (통상 1인 단품)": 1}
MEASURE = re.compile(r"\d+(?:[.,]\d+)?\s*(?:인분?|kg|g|ml|l|개|잔|팩|세트|p(?:cs)?)", re.I)
CONDITION = re.compile(r"세트|정식|추가|사리|런치|디너|점심|저녁|한정|곱빼기|특대")


def sheet_rows(book, name, required):
    rows = book[name].values
    header = next(rows, ())
    if any(header.count(column) != 1 for column in required):
        raise ValueError(f"'{name}' 시트의 열 구성을 확인해 주세요.")
    positions = [header.index(column) for column in required]
    for number, row in enumerate(rows, start=2):
        if any(value is not None for value in row):
            yield number, [row[index] if index < len(row) else None for index in positions]


def load_seoul(path):
    from openpyxl import load_workbook

    book = load_workbook(path, read_only=True, data_only=True)
    menus = {}
    alias_targets = {}
    try:
        for number, row in sheet_rows(book, REFERENCE_SHEET, REFERENCE_HEADERS):
            name, unit, composition, sample, price, stores, low, high, _, districts = row
            if (not all(isinstance(value, str) and value.strip()
                        for value in (name, unit, composition, sample, districts))
                    or any(type(value) is not int or value <= 0 for value in (price, stores, low, high))
                    or not low <= price <= high):
                raise ValueError(f"'{REFERENCE_SHEET}' 시트 {number}행에서 가격 근거를 확인해 주세요.")
            entry = menus.setdefault(key(name), {"name": name, "references": [], "baseline": None})
            entry["references"].append(dict(unit=unit, composition=composition, sample=sample,
                                             price=price, stores=stores, low=low, high=high,
                                             districts=districts, row=number))

        alias_columns = ("정제 대표명", "판매 메뉴 원문", "정제 판정", "판매 구성", "정제 판매 규격")
        for _, (name, raw, decision, composition, unit) in sheet_rows(book, "원문 대조", alias_columns):
            alias, canonical = key(raw), key(name)
            if not alias or not canonical:
                continue
            # Any competing interpretation of the raw name invalidates the alias.
            targets = alias_targets.setdefault(alias, set())
            if (decision == "집계" and composition == "단품" and canonical in menus
                    and unit in (*SERVING_UNITS, "판매량 미표기")
                    and not MEASURE.search(alias) and not CONDITION.search(alias)):
                targets.add(canonical)
            else:
                targets.add(None)
    finally:
        book.close()

    if not menus:
        raise ValueError("서울 가격표에 참고가가 없습니다.")
    for entry in menus.values():
        references = entry["references"]
        references.sort(key=lambda row: (row["sample"] != "일반 매장", row["composition"] != "단품",
                                         SERVING_UNITS.get(row["unit"], 2), -row["stores"], row["unit"]))
        entry["baseline"] = next((row for row in references if row["sample"] == "일반 매장"
                                  and row["composition"] == "단품" and row["unit"] in SERVING_UNITS
                                  and row["stores"] >= 2), None)
    aliases = {alias: next(iter(targets)) for alias, targets in alias_targets.items()
               if alias not in menus and len(targets) == 1 and None not in targets}
    return {"source": path.name, "menus": menus, "aliases": aliases}


def quote_catalog(data):
    """Adapt exact Seoul references to the existing order API schema."""
    catalog = {}
    for name, entry in data["menus"].items():
        reference = entry["baseline"]
        if reference:
            catalog[name] = dict(unit_price=reference["price"], basis=reference["unit"],
                                 rows=[reference["row"]], stores=reference["stores"],
                                 source=data["source"], sheet=REFERENCE_SHEET)
    for alias, canonical in data["aliases"].items():
        if canonical in catalog:
            catalog[alias] = catalog[canonical]
    return catalog
