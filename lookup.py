"""Build the same one-field price lookup used by the local web server."""
import argparse
import json
from pathlib import Path


def render(catalog):
    prices = {menu: row["unit_price"] for menu, row in catalog.items()}
    if any(type(price) is not int or price <= 0 for price in prices.values()):
        raise ValueError("기준표의 단가를 확인해 주세요.")
    template = Path(__file__).with_name("index.html").read_text(encoding="utf-8")
    data = json.dumps(prices, ensure_ascii=False).replace("<", r"\u003c")
    return template.replace("/*PRICE_TABLE*/{}", data)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="브라우저에서 바로 열 수 있는 메뉴 가격 조회 파일 생성")
    parser.add_argument("catalog", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.write_text(render(json.loads(args.catalog.read_text(encoding="utf-8"))), encoding="utf-8")
