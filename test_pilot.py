import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
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


class RecipeBrowserTests(unittest.TestCase):
    def test_browser_price_uses_existing_recipe_and_batch_calculation(self):
        from fried_rice import browser_recipes, quote_fried_rice

        data = browser_recipes()
        for menu in ("새우볶음밥", "새우계란볶음밥"):
            recipe = data["recipes"][data["menus"][menu]]
            for servings in (1, 3, 100):
                with self.subTest(menu=menu, servings=servings):
                    expected = quote_fried_rice(menu, servings)
                    result = recipe["quotes"][servings - 1]
                    self.assertEqual(result["total"], expected["total"])
                    self.assertEqual(result["lines"], expected["lines"])
                    self.assertEqual(result["minutes"], expected["minutes"])

    def test_new_recipes_have_priced_items_and_wait_for_work_time(self):
        from fried_rice import browser_recipes

        data = browser_recipes()
        menus = ("김치볶음밥", "스팸김치볶음밥", "참치볶음밥", "게살볶음밥", "된장찌개", "달걀국", "쇠고기미역국")
        for menu in menus:
            with self.subTest(menu=menu):
                recipe = data["recipes"][data["menus"][menu]]
                result = recipe["quotes"][0]
                self.assertIsNone(result["total"])
                self.assertIsNone(result["labor"])
                self.assertEqual(result["food"], sum(line["cost"] for line in result["lines"]))
                self.assertTrue(set(recipe["primaryIngredients"]) <= {line["item"] for line in result["lines"]})
                self.assertTrue(all(line["source"].startswith("https://") for line in result["lines"]))
        self.assertEqual(data["menus"]["달걀국"], data["menus"]["계란국"])
        self.assertEqual(quote("달걀국", 1, catalog={})["status"], "review")

    def test_public_csv_keeps_variants_and_only_prefills_explicit_batch_servings(self):
        from cookrcp_import import import_recipes

        csv = ('RCP_SEQ,RCP_NM,RCP_WAY2,RCP_PAT2,RCP_PARTS_DTLS,INFO_WGT,MANUAL01\n'
               '1,버섯 볶음,볶기,반찬,"[ 2인분 ]<br>버섯 50g, 간장 5g",200,조리법\n'
               '2,버섯볶음,굽기,반찬,버섯 70g. 소스는 5인분,200,조리법\n'
               '3,배추국,끓이기,국&찌개,,220,조리법\n')
        with TemporaryDirectory() as directory:
            path = Path(directory) / "COOKRCP01.csv"
            path.write_text(csv, encoding="utf-8-sig")
            entries = import_recipes(path)["entries"]
        variants = entries["버섯볶음"]
        self.assertEqual([variant["id"] for variant in variants], ["1", "2"])
        self.assertEqual([variant["servings"] for variant in variants], [2, None])
        self.assertIn("\n버섯 50g, 간장 5g", variants[0]["ingredients"])
        self.assertNotIn("MANUAL01", variants[0])
        self.assertEqual(entries["배추국"][0]["ingredients"], "")
