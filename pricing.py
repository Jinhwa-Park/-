"""Quote one experimental order from the selected Gangnam catalog or a sourced recipe."""
import math
import unicodedata

from fried_rice import quote_recipe, shrimp_extra_cost, meat_extra_cost


def key(name):
    return "".join(unicodedata.normalize("NFC", name).split()).casefold()


def review(menu, reason, code="insufficient_basis"):
    return {"status": "review", "menu": menu, "reason": reason, "code": code}


def quote(menu, servings, *, catalog, extra=None, extra_grams=0, per_serving=False,
          containers=0, minimum_total=0):
    if not isinstance(menu, str) or not 1 <= len(menu.strip()) <= 200:
        raise ValueError("메뉴 이름을 1~200자로 입력해 주세요.")
    if type(servings) is not int or not 1 <= servings <= 100:
        raise ValueError("실험 인분 범위는 1~100입니다.")
    if type(containers) is not int or not 0 <= containers <= 100:
        raise ValueError("용기 수는 0~100 사이의 정수여야 합니다.")
    if type(extra_grams) not in (float, int) or not math.isfinite(extra_grams) or not 0 <= extra_grams <= 100000:
        raise ValueError("추가 중량 입력을 확인해 주세요.")
    if extra is not None and (not isinstance(extra, str) or not extra.strip()):
        raise ValueError("추가 재료 이름을 입력해 주세요.")
    if (extra is not None) != (extra_grams > 0) or type(per_serving) is not bool:
        raise ValueError("추가 재료와 중량을 함께 입력해 주세요.")
    if type(minimum_total) is not int or minimum_total < 0:
        raise ValueError("최소 주문 금액은 0 이상의 정수여야 합니다.")

    name = key(menu)
    if name in {"덮밥", "스테이크", "모둠해산물찜"}:
        return review(menu, "주재료를 알려주세요.", "clarification")
    record = catalog.get(name)
    if record is None:
        result = quote_recipe(menu, servings, extra=extra, extra_grams=extra_grams,
                              per_serving=per_serving, containers=containers)
    else:
        amount = extra_grams * (servings if per_serving else 1)
        adjustment = {"total": 0}
        if extra:
            adjustment = (shrimp_extra_cost(amount) if key(extra) in {"새우", "손질새우"}
                          else meat_extra_cost(extra, amount))
            if adjustment is None:
                return review(menu, "추가 요청에 맞는 재료 규격과 단가가 없습니다.")
        extra_cost = adjustment["total"]
        base = record["unit_price"] * servings
        packaging = containers * 300
        result = {"menu": menu, "servings": servings, "status": "estimated", "method": "catalog",
                  "base": base, "extra_cost": extra_cost, "packaging": packaging,
                  "total": base + extra_cost + packaging, "unit_price": record["unit_price"],
                  "basis": record["basis"], "rows": record["rows"], "stores": record.get("stores"),
                  "assumptions": ["지정 용기 1개당 300원. 별도 소분 작업시간은 미반영."]}
    if result["status"] == "estimated" and result["total"] < minimum_total:
        return review(menu, "설정한 최소 주문 금액보다 낮습니다.", "below_minimum")
    return result


def quote_interpreted(payload, *, catalog):
    """Consume the team's existing interpreter JSON; unresolved requests stay pending."""
    if not isinstance(payload, dict):
        raise ValueError("요청 해석 결과는 JSON 객체여야 합니다.")
    dishes = payload.get("dishes")
    if payload.get("questions") or payload.get("missing_rules") or not isinstance(dishes, list) or len(dishes) != 1:
        return review("", "확인 질문·가격 규칙 또는 단일 메뉴 확인이 필요합니다.")
    dish = dishes[0]
    if not isinstance(dish, dict):
        raise ValueError("요리 항목 형식을 확인해 주세요.")
    menu = dish.get("base_dish")
    if not menu or not dish.get("servings"):
        return review(menu, "메뉴와 인분을 확인해 주세요.", "clarification")
    mods = dish.get("modifications")
    if not isinstance(mods, list):
        return review(menu, "추가 요청 목록을 확인해 주세요.")
    additions = {}
    for mod in mods:
        if not isinstance(mod, dict) or mod.get("needs_resolution"):
            return review(menu, "해석 결과에 확인할 항목이 있습니다.")
        if ((mod.get("type"), mod.get("rule_id")) in {("seasoning", "R02"), ("keep", "R03")}
                and mod.get("price_effect") == "unchanged"):
            continue
        quantity = mod.get("quantity")
        if (mod.get("rule_id") == "R01" and mod.get("type") == "increase"
                and mod.get("price_effect") == "increase" and mod.get("quantity_meaning") == "additional"
                and mod.get("scope") in {"whole_order", "per_serving"} and mod.get("unit") in {"g", "kg"}
                and type(quantity) in {int, float} and 0 < quantity <= 100000
                and isinstance(mod.get("target"), str) and not additions):
            additions = dict(extra=mod["target"], extra_grams=quantity * (1000 if mod["unit"] == "kg" else 1),
                             per_serving=mod["scope"] == "per_serving")
            continue
        return review(menu, "해석된 요청에 적용할 확정 단가 또는 규칙이 필요합니다.")
    result = quote(menu, dish["servings"], catalog=catalog, **additions)
    result["modifications"] = mods
    return result
