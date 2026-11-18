"""도와줘요 셰프님!의 오프라인 레시피 견적 계산."""
import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from statistics import median
from unicodedata import normalize


DATA_PATH = Path(__file__).with_name("data.json")


class MissingBasis(Exception):
    """An order cannot be priced with the available reference data."""


def _key(value):
    return "".join(normalize("NFC", value).split()).casefold()


def _nonnegative(value, label, *, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError(f"{label}은 숫자로 입력해주세요.")
    number = Decimal(str(value))
    if not number.is_finite() or number < 0 or (positive and number == 0):
        raise ValueError(f"{label}의 값을 확인해주세요.")
    return number


def _won(amount):
    return int(amount.to_integral_value(rounding=ROUND_HALF_UP))


def _family_items(prefix, ingredients):
    """Match the full ingredient prefix, preferring longer known tokens."""
    tokens = sorted(
        ((_key(token), entry) for token, entry in ingredients.items() if _key(token)),
        key=lambda pair: -len(pair[0]),
    )
    suffix_matches = {len(prefix): []}
    for start in range(len(prefix) - 1, -1, -1):
        for token, entry in tokens:
            end = start + len(token)
            if end in suffix_matches and prefix.startswith(token, start):
                suffix_matches[start] = [entry, *suffix_matches[end]]
                break
    if 0 not in suffix_matches:
        raise MissingBasis(f"메뉴의 재료 또는 지정 조건을 확인할 수 없습니다 ({prefix}).")
    items = {}
    for entry in suffix_matches[0]:
        if entry["item"] in items:
            raise MissingBasis(f"{entry['item']}의 사용량을 확인해주세요.")
        items[entry["item"]] = entry["grams"]
    return items


def _match(menu, data):
    name = _key(menu)
    for dish, details in data["recipes"].items():
        if _key(dish) == name:
            return details["family"], details["items"], "recipe"
    matches = [
        (len(suffix), family)
        for family, details in data["families"].items()
        for suffix in map(_key, (family, *details.get("aliases", [])))
        if suffix and name.endswith(suffix)
    ]
    if not matches:
        raise MissingBasis("비교할 조리 유형 또는 기준 레시피가 없습니다.")
    length = max(size for size, _ in matches)
    candidates = {family for size, family in matches if size == length}
    if len(candidates) != 1:
        raise MissingBasis("여러 조리 유형이 일치해 작업시간을 정할 수 없습니다.")
    return candidates.pop(), _family_items(name[:-length], data["ingredients"]), "family"


def _extra_item(extra, data):
    for item in data["prices"]:
        if _key(item) == _key(extra):
            return item
    for token, entry in data["ingredients"].items():
        if _key(token) == _key(extra):
            return entry["item"]
    raise MissingBasis(f"추가 재료의 단가를 확인할 수 없습니다 ({extra}).")


def estimate(menu, servings, *, extra=None, extra_grams=0, per_serving=False,
             containers=0, hourly=16000, markup=0.30, container_cost=300):
    """Return a won-denominated estimate or a review reason for an unpriced order."""
    if not isinstance(menu, str) or not menu.strip() or len(menu) > 200:
        raise ValueError("요리 이름을 1~200자로 입력해주세요.")
    if type(servings) is not int or servings < 1:
        raise ValueError("인분 수는 1 이상의 정수로 입력해주세요.")
    if type(containers) is not int or containers < 0:
        raise ValueError("용기 수는 0 이상의 정수로 입력해주세요.")
    if type(per_serving) is not bool:
        raise ValueError("추가량 적용 범위를 확인해주세요.")
    extra_grams = _nonnegative(extra_grams, "추가 중량")
    hourly = _nonnegative(hourly, "요리사 시급")
    markup = _nonnegative(markup, "재료비 가산율")
    container_cost = _nonnegative(container_cost, "용기 가격")
    if extra is not None and (not isinstance(extra, str) or not extra.strip()):
        raise ValueError("추가할 재료 이름을 입력해주세요.")
    if (extra is not None) != (extra_grams > 0):
        raise ValueError("추가 재료 이름과 추가 중량을 함께 입력해주세요.")

    data = json.loads(DATA_PATH.read_text(encoding="utf-8"), parse_float=Decimal)
    try:
        family_name, items, method = _match(menu, data)
        family = data["families"][family_name]
        # Named ingredients specify the full per-person amount when they overlap a base.
        quantities = {
            item: Decimal(str(grams)) * servings
            for item, grams in {**family["base"], **items}.items()
        }
        if extra is not None:
            item = _extra_item(extra, data)
            quantities[item] = quantities.get(item, 0) + extra_grams * (servings if per_serving else 1)

        lines = []
        for item, grams in quantities.items():
            price = data["prices"].get(item)
            if price is None or price <= 0:
                raise MissingBasis(f"재료 단가가 없습니다 ({item}).")
            lines.append({"item": item, "grams": float(grams), "unit_price": float(price),
                          "cost": _won(grams * price)})
        if not family["seasoning_samples"]:
            raise MissingBasis("조리 유형별 공통 양념비 자료가 없습니다.")
        seasoning = _won(median([Decimal(str(cost)) for cost in family["seasoning_samples"]]) * servings)
        lines.append({"item": "공통 양념", "grams": None, "unit_price": None, "cost": seasoning})
        batch_size = family["batch_size"]
        if type(batch_size) is not int or batch_size <= 0:
            raise MissingBasis("1회 조리 가능 인분 수가 없습니다.")
        batches = (servings + batch_size - 1) // batch_size
        minutes = (family["minutes_fixed"] + batches * family["minutes_batch"]
                   + containers * family.get("minutes_container", 0))
    except MissingBasis as exc:
        return {"status": "review", "menu": menu, "reason": str(exc)}
    except KeyError as exc:
        return {"status": "review", "menu": menu, "reason": f"계산에 필요한 기준 자료가 없습니다 ({exc.args[0]})."}

    food = sum(line["cost"] for line in lines)
    labor = _won(hourly * minutes / 60)
    markup_amount = _won(markup * food)
    packaging = _won(container_cost * containers)
    total = food + markup_amount + labor + packaging
    return {"status": "estimated", "menu": menu, "servings": servings, "method": method,
            "family": family_name, "food": food, "seasoning": seasoning, "minutes": float(minutes),
            "batches": batches, "labor": labor, "markup_amount": markup_amount,
            "packaging": packaging, "total": total,
            "per_person": _won(Decimal(total) / servings), "lines": lines}
