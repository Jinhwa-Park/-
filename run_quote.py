import argparse
import json
from pathlib import Path

from pricing import quote, quote_interpreted


def main():
    parser = argparse.ArgumentParser(description="실험 견적 · 강남 기준가 및 출처가 있는 볶음밥")
    parser.add_argument("menu", nargs="?")
    parser.add_argument("servings", type=int, nargs="?")
    parser.add_argument("--catalog", type=Path)
    parser.add_argument("--request-json", type=Path, help="기존 해석기가 반환한 JSON")
    parser.add_argument("--extra")
    parser.add_argument("--extra-grams", type=float, default=0)
    parser.add_argument("--per-serving", action="store_true")
    parser.add_argument("--containers", type=int, default=0)
    parser.add_argument("--minimum-total", type=int, default=0)
    args = vars(parser.parse_args())
    try:
        path = args.pop("catalog")
        catalog = json.loads(path.read_text(encoding="utf-8")) if path else {}
        request = args.pop("request_json")
        if request:
            if any(args.values()):
                parser.error("--request-json 사용 시 주문 조건을 파일에만 지정해 주세요.")
            result = quote_interpreted(json.loads(request.read_text(encoding="utf-8")), catalog=catalog)
        else:
            result = quote(catalog=catalog, **args)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
