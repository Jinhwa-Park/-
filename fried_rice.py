"""Source-backed recipe costing and compilation for the offline price page."""
import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from statistics import median
from unicodedata import normalize

DATA = json.loads(Path(__file__).with_name("fried_rice.json").read_text(encoding="utf-8"), parse_float=Decimal)
ADDITIONAL = json.loads(Path(__file__).with_name("recipes.json").read_text(encoding="utf-8"), parse_float=Decimal)
POLICY = DATA["policy"]
FRIED_RICE_IDS = ("registered_recipe", "inference")
RECIPES = {**{recipe_id: DATA[recipe_id] for recipe_id in FRIED_RICE_IDS}, **ADDITIONAL["recipes"]}
MENU_RECIPES = {menu: recipe_id for recipe_id, recipe in RECIPES.items() for menu in recipe["menus"]}
OFFERS = {**DATA["offers"], **ADDITIONAL["offers"]}


def won(value):
    return int(Decimal(value).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def cost(item, quantity):
    offer = OFFERS[item]
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


def quote_recipe(menu, servings, extra=None, extra_grams=0, per_serving=False, containers=0, *, holdout=False):
    name = "".join(normalize("NFC", menu).split())
    recipe_id = MENU_RECIPES.get(name)
    if recipe_id is None or (holdout and recipe_id not in FRIED_RICE_IDS):
        return {"status": "review", "menu": menu, "reason": "기준가 또는 검증 가능한 비교 레시피가 없습니다."}
    if holdout:
        recipe_id = "inference"
    inferred = recipe_id == "inference"
    recipe = RECIPES[recipe_id]
    quantities = {item: amount * servings for item, amount in recipe["per_serving"].items()}
    if extra:
        if "새우" not in quantities or "".join(extra.split()) not in {"새우", "손질새우"}:
            reason = ("이 레시피에서 지원하는 추가 재료는 손질 새우입니다." if "새우" in quantities
                      else "이 레시피의 추가 재료 견적은 확인이 필요합니다.")
            return {"status": "review", "menu": menu, "reason": reason}
        quantities["새우"] += Decimal(str(extra_grams)) * (servings if per_serving else 1)
    if inferred:
        samples = [sum(cost(item, q) for item, q in s["quantities"].items()) / s["recipe_servings"]
                   for s in recipe["seasoning_samples"]]
        seasoning = won(median(samples) * servings)
    else:
        quantities.update({item: amount * servings for item, amount in recipe["seasonings"].items()})
        seasoning = 0
    lines = [{"item": item, "quantity": float(q), "unit": OFFERS[item]["unit"],
              "cost": won(cost(item, q)), "source": OFFERS[item]["url"]} for item, q in quantities.items()]
    if inferred:
        lines.append({"item": "공통 양념", "cost": seasoning, "samples": len(samples)})
    food = sum(line["cost"] for line in lines)
    packaging = containers * POLICY["container_won"]
    markup = won(food * POLICY["markup"])
    result = {"menu": menu, "servings": servings, "method": "similar_recipe" if inferred else "recipe",
              "basis": recipe["name"], "lines": lines, "food": food, "markup_amount": markup, "packaging": packaging,
              "sources": [v for k, v in recipe.items() if k.endswith("url")]}
    if recipe_id not in FRIED_RICE_IDS:
        reason = "직접 작업시간을 입력한 뒤 레시피 견적을 확인해 주세요."
        return dict(result, status="review", reason=reason, minutes=None, labor=None, total=None,
                    assumptions=[recipe["assumptions"], ADDITIONAL["price_basis"]])

    batches = (servings + POLICY["servings_per_batch"] - 1) // POLICY["servings_per_batch"]
    minutes = POLICY["fixed_minutes"] + batches * POLICY["minutes_per_batch"] + containers * POLICY["minutes_per_container"]
    labor = won(Decimal(minutes) * POLICY["hourly_won"] / 60)
    return dict(result, status="estimated", minutes=minutes, labor=labor, total=food + labor + markup + packaging,
                assumptions=[recipe["assumptions"], DATA["labor_basis"], DATA["price_basis"]])


quote_fried_rice = quote_recipe


def browser_recipes():
    """Compile the existing recipe calculations for use in the offline price page."""
    recipes = {}
    for recipe_id, recipe in RECIPES.items():
        menu = recipe["menus"][0]
        quotes = [quote_recipe(menu, servings) for servings in range(1, 101)]
        details = quotes[0]
        amounts = ("food", "labor", "markup_amount", "minutes", "packaging", "total", "lines")
        sources = dict.fromkeys([*details["sources"],
                                 *(sample["url"] for sample in recipe.get("seasoning_samples", []))])
        recipes[recipe_id] = {
            "name": details["basis"],
            "method": details["method"],
            "primaryIngredients": recipe["primary_ingredients"],
            "assumptions": details["assumptions"],
            "sources": list(sources),
            "quotes": [{part: quote[part] for part in amounts} for quote in quotes],
        }
    packages = {**{item: {**offer, "date": DATA["accessed_on"]} for item, offer in DATA["offers"].items()},
                **{item: {**offer, "date": ADDITIONAL["accessed_on"]} for item, offer in ADDITIONAL["offers"].items()}}
    return {"date": DATA["accessed_on"], "menus": MENU_RECIPES, "packages": packages, "recipes": recipes,
            "policy": {"hourlyWon": POLICY["hourly_won"], "markup": float(POLICY["markup"])}}
