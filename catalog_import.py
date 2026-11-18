"""Build a private restaurant-price lookup from the Gangnam menu workbook."""
import argparse
import hashlib
import json
import os
import re
import tempfile
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from statistics import median
from unicodedata import normalize


def key(value):
    return "".join(normalize("NFC", str(value or "")).lower().split())


# For unmarked portions, restrict the entire name to a generic preparation plus
# familiar ingredients. Shared dishes, brand names and unknown prefixes fall out.
SINGLE_DISHES = set("""
덮밥 볶음밥 비빔밥 솥밥 국밥 오므라이스 카레라이스 하이라이스 마파두부밥 짬뽕밥 짜장밥
리조또 리소토 파스타 스파게티 우동 소바 냉모밀 모밀국수 국수 칼국수 수제비 냉면 쫄면
라면 라멘 쌀국수 짜장면 자장면 짬뽕 탄탄면 마제소바 카레우동 온면 밀면 짜장 간짜장
설렁탕 갈비탕 해장국 육개장 곰탕 삼계탕 떡국 만둣국 만두국 순두부찌개 김치찌개 된장찌개
뚝배기불고기 돌솥밥 돌솥비빔밥 죽 돈까스 돈가스 돈카츠 함박스테이크 김밥
""".split())
PREFIXES = set("""
소고기 쇠고기 소불고기 불고기 돼지 돼지고기 제육 차돌 차돌박이 한우 우삼겹 떡갈비 닭 닭고기
닭갈비 치킨 닭가슴살 삼겹살 햄 베이컨 소시지 스팸 돼지국물 양지 사골 뼈 내장 선지 순대
해물 모둠해물 삼선 새우 칵테일새우 왕새우 대하 전복 조개 바지락 홍합 굴 백합 게살 꽃게
참치 연어 장어 낙지 문어 오징어 주꾸미 멸치 황태 명란 날치알 회 육회 모둠
고등어 버섯 표고 표고버섯 송이 양송이 트러플 능이 들깨 김치 묵은지 깍두기 깻잎 곤드레
나물 산채 야채 채소 계란 달걀 치즈 마늘 파 대파 고추 청양고추 꽈리고추 후추 고추장
된장 간장 미소 참깨 콩나물 숙주 두부 유부 어묵 가지 감자 고구마 단호박 김 미역 매생이
토마토 크림 로제 바질 페스토 오일 마요 마요네즈 카레 카레맛 짜장 김치제육 고추참치
물 비빔 잔치 메밀 얼큰 매운 매콤 직화 숯불 훈제 열무 냉 온 냉이 얼갈이 시래기
등심 안심 통등심 통안심 수제 손 전주 평양 함흥 경양식 옛날 양푼 돌솥 뚝배기
""".split())
# Explicit serving labels also allow some dishes usually sold for sharing.
EXPLICIT_DISHES = SINGLE_DISHES | set("""
전골 찌개 볶음 떡갈비 구이 수육 어묵 순대 스프 짜장 갈비찜 부대찌개 곱창전골
""".split())
EXCLUDED = re.compile(
    r"세트|셋트|set|추가|사리|옵션|토핑|사이드|코스|한상|한판|정식|무한|리필|"
    r"런치|디너|점심|저녁|해피아워|한정|특선|시그니처|대표|안주|후식|미니|곱빼기|"
    r"쟁반|스페셜|스페샬|오마카세|패밀리|커플|특대|왕곱|택일|선택"
)
ONE_SERVING = re.compile(r"[\(\[]?1인(?:분)?[\)\]]?")
HEADERS = (
    "대표 메뉴명", "크기 표기", "인분·주문조건", "중량·용량", "개수·수량", "판매 메뉴 원문",
    "게시 가격(원)", "매장", "주소", "표본", "출처", "원문 URL", "맛·제품·판매 형태",
    "매운맛 표기", "대표 가격표 포함 여부",
)
SHEET = "판매규격별 가격"


def generic_name(name, dishes):
    if not re.fullmatch("[가-힣]+", name) or EXCLUDED.search(name):
        return False
    reachable = {0}
    for index in range(len(name)):
        if index in reachable:
            if name[index:] in dishes:
                return True
            reachable.update(index + len(word) for word in PREFIXES if name.startswith(word, index))
    return False


def observation(row, names):
    (rep, size, portion, weight, count, raw, price, store, address, _sample, source, url,
     variant, _spice, included) = row
    if included != "포함" or rep not in names or not (raw and store and address and source and url):
        return None
    if type(price) is not int or price <= 0 or size != "크기 미표기" or weight or count or variant:
        return None
    if portion not in (None, "1인", "1인분"):
        return None
    name, original = key(rep), key(raw)
    if portion:
        original, labels = ONE_SERVING.subn("", original)
        if labels != 1:
            return None
    if original != name or not generic_name(name, EXPLICIT_DISHES if portion else SINGLE_DISHES):
        return None
    # One store and street number may be written with different floor details.
    road = re.search(r"(?:강남구)?([가-힣0-9·]+(?:로|길))\s*(\d+(?:-\d+)?)", str(address))
    location = key(road[1]) + ":" + road[2] if road else key(address)
    return name, (key(store), location), price, bool(portion)


def build(path):
    from openpyxl import load_workbook

    fingerprint = hashlib.sha256(path.read_bytes()).hexdigest()
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        names_sheet = workbook["메뉴 종류"]
        if next(names_sheet.iter_rows(min_row=4, max_row=4, values_only=True))[0] != "대표 메뉴명":
            raise ValueError("메뉴 종류 시트의 대표명 열을 확인해주세요.")
        names = {row[0] for row in names_sheet.iter_rows(min_row=5, values_only=True) if row[0]}
        rows = workbook[SHEET].iter_rows(min_row=4, values_only=True)
        if tuple(next(rows)) != HEADERS:
            raise ValueError("판매규격별 가격 시트 열 구성이 달라졌습니다.")
        observations = defaultdict(list)
        for number, row in enumerate(rows, start=5):
            accepted = observation(row, names)
            if accepted:
                name, store, price, explicit = accepted
                observations[name].append((number, store, price, explicit))
    finally:
        workbook.close()

    catalog = {}
    for name, group in sorted(observations.items()):
        store_prices = defaultdict(set)
        explicit, inferred = [], []
        for number, store, price, labeled in group:
            store_prices[store].add(price)
            (explicit if labeled else inferred).append(number)
        amounts = [median([Decimal(p) for p in prices]) for prices in store_prices.values()]
        unit_price = int(median(amounts).to_integral_value(rounding=ROUND_HALF_UP))
        basis = "1인분 명시" if not inferred else "통상 1인 단품으로 추정"
        if explicit and inferred:
            basis = "1인분 명시 및 통상 1인 단품 추정 혼합"
        catalog[name] = {
            "unit_price": unit_price, "basis": basis, "observations": len(group),
            "stores": len(store_prices), "rows": sorted(explicit + inferred),
            "explicit_rows": explicit, "inferred_rows": inferred, "source": path.name,
            "sheet": SHEET, "workbook_sha256": fingerprint,
        }
    return catalog


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workbook", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    catalog = build(args.workbook)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=args.output.parent, encoding="utf-8", delete=False) as tmp:
        temporary = Path(tmp.name)
        try:
            json.dump(catalog, tmp, ensure_ascii=False, indent=2)
            tmp.write("\n")
            tmp.close()
            os.replace(temporary, args.output)
        finally:
            temporary.unlink(missing_ok=True)
    print(f"{len(catalog)}개 메뉴, 판매 가격 {sum(entry['observations'] for entry in catalog.values())}행")


if __name__ == "__main__":
    main()
