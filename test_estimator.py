"""Regression checks for the offline Korean recipe price estimator."""

import json
import math
import unittest
from pathlib import Path
from statistics import median

from estimator import estimate


DATA = json.loads(Path(__file__).with_name("data.json").read_text(encoding="utf-8"))


class EstimatorTests(unittest.TestCase):
    def quote(self, menu, servings, **options):
        quote = estimate(menu, servings, **options)
        self.assertEqual(quote["status"], "estimated", quote)
        return quote

    def test_inferred_price_uses_shrimp_in_place_of_beef(self):
        family = DATA["families"][DATA["recipes"]["소고기볶음밥"]["family"]]
        shrimp = DATA["ingredients"]["새우"]
        prices = DATA["prices"]
        base_food = sum(grams * prices[item] for item, grams in family["base"].items())
        food_per_serving = (
            base_food
            + shrimp["grams"] * prices[shrimp["item"]]
            + median(family["seasoning_samples"])
        )
        exact = self.quote("소고기볶음밥", 3)
        inferred = self.quote("새우볶음밥", 3)
        self.assertNotEqual(exact["method"], inferred["method"])
        self.assertAlmostEqual(inferred["food"], 3 * food_per_serving, delta=1)

    def test_extra_grams_can_apply_once_or_to_each_serving(self):
        shrimp_price = DATA["prices"][DATA["ingredients"]["새우"]["item"]]
        original = self.quote("새우볶음밥", 3)
        extra = {"extra": "새우", "extra_grams": 100}
        once = self.quote("새우볶음밥", 3, **extra)
        each = self.quote("새우볶음밥", 3, per_serving=True, **extra)
        self.assertAlmostEqual(once["food"] - original["food"], 100 * shrimp_price, delta=1)
        self.assertAlmostEqual(each["food"] - original["food"], 300 * shrimp_price, delta=1)

    def test_batch_capacity_controls_cooking_time(self):
        family = DATA["families"][DATA["recipes"]["소고기볶음밥"]["family"]]
        batch = family["batch_size"]
        for servings in (1, batch, batch + 1):
            with self.subTest(servings=servings):
                quote = self.quote("새우볶음밥", servings)
                expected = family["minutes_fixed"] + math.ceil(servings / batch) * family["minutes_batch"]
                self.assertEqual(quote["minutes"], expected)

    def test_quote_breakdown_with_custom_rates(self):
        quote = self.quote("들깨크림수제비", 3, containers=3, container_cost=375, markup=0.25, hourly=12000)
        self.assertEqual(quote["packaging"], 1125)
        self.assertEqual(quote["labor"], quote["minutes"] * 200)
        self.assertAlmostEqual(quote["total"], quote["food"] * 1.25 + quote["labor"] + 1125, delta=2)

    def test_unpriced_ingredient_does_not_get_partial_quote(self):
        for menu in ("전복리조또", "전복새우볶음밥", "어느식당시그니처"):
            with self.subTest(menu=menu):
                result = estimate(menu, 3)
                self.assertEqual(result["status"], "review")
                self.assertIsNone(result.get("total"))


if __name__ == "__main__":
    unittest.main()
