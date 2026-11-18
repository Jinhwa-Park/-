"""Source-backed offline costing for a small set of fried rice recipes."""
import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from statistics import median
from unicodedata import normalize

DATA = json.loads(Path(__file__).with_name("fried_rice.json").read_text(encoding="utf-8"), parse_float=Decimal)
POLICY = DATA["policy"]


def won(value):
    return int(Decimal(value).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def cost(item, quantity):
    offer = DATA["offers"][item]
    return Decimal(str(quantity)) * offer["won"] / offer["size"]


def extra_cost(item, grams):
    food = won(cost(item, grams))
    markup = won(food * POLICY["markup"])
    return {"food": food, "markup_amount": markup, "total": food + markup}


def shrimp_extra_cost(grams):
    return extra_cost("새우", grams)


def meat_extra_cost(target, grams):
    if "".join(target.split()) in {"돼지앞다리", "돼지앞다리살", "돼지고기앞다리", "돼지고기앞다리살", "한돈앞다리살"}:
        return extra_cost("돼지앞다리살", grams)
    return None


def quote_fried_rice(menu, servings, extra=None, extra_grams=0, per_serving=False, containers=0, *, holdout=False):
    name = "".join(normalize("NFC", menu).split())
    if name not in {"새우볶음밥", "중식새우볶음밥", "새우계란볶음밥", "새우달걀볶음밥"}:
        return {"status": "review", "menu": menu, "reason": "기준가 또는 검증 가능한 비교 레시피가 없습니다."}
    inferred = holdout or name in {"새우계란볶음밥", "새우달걀볶음밥"}
    recipe = DATA["inference" if inferred else "registered_recipe"]
    quantities = {item: amount * servings for item, amount in recipe["per_serving"].items()}
    if extra:
        if "".join(extra.split()) not in {"새우", "손질새우"}:
            return {"status": "review", "menu": menu, "reason": "이 레시피에서 지원하는 추가 재료는 손질 새우입니다."}
        quantities["새우"] += Decimal(str(extra_grams)) * (servings if per_serving else 1)
    if inferred:
        samples = [sum(cost(item, q) for item, q in s["quantities"].items()) / s["recipe_servings"]
                   for s in recipe["seasoning_samples"]]
        seasoning = won(median(samples) * servings)
    else:
        quantities.update({item: amount * servings for item, amount in recipe["seasonings"].items()})
        seasoning = 0
    lines = [{"item": item, "quantity": float(q), "unit": DATA["offers"][item]["unit"],
              "cost": won(cost(item, q)), "source": DATA["offers"][item]["url"]} for item, q in quantities.items()]
    if inferred:
        lines.append({"item": "공통 양념", "cost": seasoning, "samples": len(samples)})
    food = sum(line["cost"] for line in lines)
    batches = (servings + POLICY["servings_per_batch"] - 1) // POLICY["servings_per_batch"]
    minutes = POLICY["fixed_minutes"] + batches * POLICY["minutes_per_batch"] + containers * POLICY["minutes_per_container"]
    labor = won(Decimal(minutes) * POLICY["hourly_won"] / 60)
    packaging = containers * POLICY["container_won"]
    markup = won(food * POLICY["markup"])
    return {"menu": menu, "servings": servings, "status": "estimated", "method": "similar_recipe" if inferred else "recipe",
            "basis": recipe["name"], "lines": lines, "food": food, "labor": labor, "markup_amount": markup,
            "minutes": minutes, "packaging": packaging, "total": food + labor + markup + packaging,
            "sources": [v for k, v in recipe.items() if k.endswith("url")],
            "assumptions": [recipe["assumptions"], DATA["labor_basis"], DATA["price_basis"]]}
