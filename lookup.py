"""Build the same one-field price lookup used by the local web server."""
import argparse
import json
from pathlib import Path


def observations(workbook):
    from openpyxl import load_workbook
    from catalog_import import HEADERS, SHEET, key

    book = load_workbook(workbook, read_only=True, data_only=True)
    try:
        rows = book[SHEET].iter_rows(min_row=4, values_only=True)
        if tuple(next(rows)) != HEADERS:
            raise ValueError("판매규격별 가격 시트의 열 구성을 확인해 주세요.")
        menus = {}
        for name, size, portion, weight, count, _, price, store, *other in rows:
            if not name or type(price) is not int or price <= 0 or other[-1] != "포함":
                continue
            units = [str(portion or "인분 미표기")]
            units.extend(str(value) for value in (size, weight, count)
                         if value and value != "크기 미표기")
            record = [price, " · ".join(units), store or ""]
            matches = menus.setdefault(key(name), [])
            if record not in matches:
                matches.append(record)
        return menus
    finally:
        book.close()


def render(catalog, workbook=None):
    prices = {
        menu: {"price": row["unit_price"], "basis": row.get("basis", "인분 근거 미표기")}
        for menu, row in catalog.items()
    }
    if any(type(row["price"]) is not int or row["price"] <= 0 for row in prices.values()):
        raise ValueError("기준표의 단가를 확인해 주세요.")
    records = observations(workbook) if workbook else {}
    for name, rows in records.items():
        prices.setdefault(name, {})["observations"] = sorted(rows)
    template = Path(__file__).with_name("index.html").read_text(encoding="utf-8")
    data = json.dumps(prices, ensure_ascii=False).replace("<", r"\u003c")
    return template.replace("/*PRICE_TABLE*/{}", data)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="브라우저에서 바로 열 수 있는 메뉴 가격 조회 파일 생성")
    parser.add_argument("catalog", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--workbook", type=Path, help="판매 단위와 게시 가격이 들어 있는 원본 엑셀")
    args = parser.parse_args()
    args.output.write_text(render(json.loads(args.catalog.read_text(encoding="utf-8")), args.workbook), encoding="utf-8")
