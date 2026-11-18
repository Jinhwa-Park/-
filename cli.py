import argparse
import json

from estimator import estimate


def main():
    parser = argparse.ArgumentParser(description="레시피 가격 측정기 · 예시 단가로 계산")
    parser.add_argument("menu", help="요리 이름")
    parser.add_argument("servings", type=int, help="인분 수")
    parser.add_argument("--extra", help="추가할 재료")
    parser.add_argument("--extra-grams", type=float, default=0, help="추가할 중량(g)")
    parser.add_argument("--per-serving", action="store_true", help="인분마다 추가")
    parser.add_argument("--containers", type=int, default=0, help="포장 용기 수")
    args = parser.parse_args()
    try:
        result = estimate(**vars(args))
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
