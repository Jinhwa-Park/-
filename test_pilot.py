import unittest
from pricing import quote, quote_interpreted


class PilotTests(unittest.TestCase):
    catalog = {"김치찌개": {"unit_price": 9000, "basis": "회귀시험용", "rows": [17]}}

    def test_catalog_priority_and_scale(self):
        result = quote("김치 찌개", 3, catalog=self.catalog, containers=3)
        self.assertEqual(result["total"], 27900)
        self.assertEqual(result["rows"], [17])

    def test_shrimp_scope(self):
        def total(per):
            return quote("김치찌개", 3, catalog=self.catalog, extra="새우", extra_grams=100,
                         per_serving=per)["total"] - 27000
        self.assertAlmostEqual(total(True), 3 * total(False), delta=2)

    def test_review_and_threshold(self):
        self.assertEqual(quote("덮밥", 2, catalog={})["code"], "clarification")
        self.assertEqual(quote("전복리조또", 1, catalog={})["status"], "review")
        self.assertEqual(quote("김치찌개", 1, catalog=self.catalog, minimum_total=12000)["code"], "below_minimum")
        self.assertEqual(quote("김치찌개", 1, catalog=self.catalog, extra="캐비아", extra_grams=20)["status"], "review")

    def test_interpreter(self):
        req = {"dishes": [{"base_dish": "김치찌개", "servings": 2, "modifications": []}]}
        self.assertEqual(quote_interpreted(req, catalog=self.catalog)["total"], 18000)
        mod = {"type":"seasoning", "price_effect":"unchanged", "rule_id":"R02"}
        req["dishes"][0]["modifications"].append(mod)
        self.assertEqual(quote_interpreted(req, catalog=self.catalog)["modifications"], [mod])
        mod["price_effect"] = "unresolved"
        self.assertEqual(quote_interpreted(req, catalog=self.catalog)["status"], "review")


class CatalogTests(unittest.TestCase):
    def test_sales_conditions_not_collapsed(self):
        from catalog_import import observation
        row = ["새우볶음밥", "크기 미표기", None, None, None, "새우볶음밥", 12000,
               "예시 매장", "서울 강남구 예시로 1", "일반 메뉴", "시험", "https://example.org",
               None, None, "포함"]
        self.assertTrue(observation(row, {"새우볶음밥"}))
        for column, value in [(2,"2인"), (3,"500g"), (5,"런치 새우볶음밥"), (5,"새우볶음밥 세트"), (14,"제외")]:
            with self.subTest(value=value):
                alternative = row.copy()
                alternative[column] = value
                self.assertIsNone(observation(alternative, {"새우볶음밥"}))
