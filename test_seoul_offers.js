const assert = require("node:assert/strict");
const test = require("node:test");
const {find, offers, estimate} = require("./seoul_offers.js");

const reference = (price, row, properties = {}) => ({
  price, row, unit: "인분 미표기 (통상 1인 단품)", composition: "단품", sample: "일반 매장",
  stores: 3, districts: "강남구", ...properties
});

const item = (name, baseline, references = [baseline]) => ({name, baseline, references});
const shrimp = reference(12000, 2);
const kimchi = reference(12900, 3, {unit: "1.5인분", stores: 1});
const data = JSON.parse(JSON.stringify({
  aliases: {해우볶음밥: "새우볶음밥"},
  menus: {
    새우볶음밥: item("새우볶음밥", shrimp, [shrimp, reference(8000, 4, {sample: "착한가격업소"})]),
    해물볶음밥: item("해물볶음밥", reference(13000, 5)),
    게살볶음밥: item("게살볶음밥", reference(14000, 6)),
    닭고기볶음밥: item("닭고기볶음밥", reference(9000, 7)),
    새우덮밥: item("새우덮밥", reference(22000, 8)),
    김치찜: item("김치찜", null, [kimchi]),
    모츠나베: item("모츠나베", null, [reference(25000, 9, {unit: "2인분"})]),
  }
}));
const recipeData = {
  menus: {새우볶음밥: "rice", 새우계란볶음밥: "rice"},
  policy: {hourlyWon: 16000, markup: 0.30},
  recipes: {rice: {primaryIngredients: ["새우"], quotes: [1, 2, 3].map(servings => {
    const minutes = servings <= 2 ? 20 : 28;
    const food = 6000 * servings;
    const labor = Math.round(minutes * 16000 / 60);
    const markup_amount = food * 0.30;
    return {minutes, food, labor, markup_amount, packaging: 0, total: food + labor + markup_amount,
      lines: [{item: "새우", quantity: 80 * servings, cost: 4000 * servings},
        {item: "쌀", quantity: 80 * servings, cost: 2000 * servings}]};
  })}},
};

test("exact reference, normalized names and aliases take precedence over comparisons", () => {
  for (const name of ["새우 볶음밥", "해우볶음밥", "새우볶음밥".normalize("NFD"),
    "새우볶음밥 1인분", "새우볶음밥(1인)", "해우볶음밥 1인분"]) {
    const result = find(data, name);
    assert.equal(result.basis.kind, "exact");
    assert.equal(result.basis.reference, result.references[0]);
    assert.equal(result.basis.price, 12000);
    assert.ok(result.similar.length && result.similar.every(row => !row.used));
  }
});

test("an estimate uses distinct menus of the same type and similar ingredients", () => {
  const result = find(data, "가리비볶음밥");
  assert.deepEqual(result.basis, {kind: "estimated", price: 13000, count: 3});
  assert.deepEqual(result.similar.filter(row => row.used).map(row => row.display.price).sort(), [12000, 13000, 14000]);
  assert.equal(find(data, "돼지볶음밥").basis, null);
  assert.equal(find(data, "볶음밥").basis, null);
});

test("posted prices and related menus remain visible for unsupported serving sizes", () => {
  const kimchiResult = find(data, "김치찜 (1.5인분)");
  assert.equal(kimchiResult.references[0].price, 12900);
  assert.equal(kimchiResult.basis, null);
  assert.equal(find(data, "새우볶음밥 2인분").basis, null);
  const nabeResult = find(data, "밀푀유나베");
  assert.equal(nabeResult.similar[0].name, "모츠나베");
  assert.equal(nabeResult.basis, null);
});

test("three random prices stay in disjoint percentage bands after rounding", () => {
  const bands = [[-8, -4], [-2, 2], [4, 8]];
  for (const total of [101, 12000, 24501, 36000]) {
    for (const value of [0, 0.5, 0.999999]) {
      let draws = 0;
      const result = offers(total, () => { draws += 1; return value; });
      assert.equal(draws, 3);
      assert.equal(new Set(result.map(offer => offer.price)).size, 3);
      result.forEach((offer, i) => {
        const [min, max] = bands[i];
        assert.ok(offer.change * 100 >= min && offer.change * 100 <= max);
      });
    }
  }
});

test("exact market and recipe calculations can be compared without combining them", () => {
  for (const name of ["새우 볶음밥", "새우볶음밥 1인분", "해우볶음밥"]) {
    const result = estimate(data, recipeData, name, 3);
    assert.equal(result.method, "market_exact");
    assert.equal(result.total, 36000);
    assert.equal(result.offerTotal, 36000);
    assert.equal(result.recipeQuote.breakdown.total, 30867);
  }
});

test("default recipes and similar menu prices are visible without generating offers", () => {
  const result = estimate(data, recipeData, "새우 계란 볶음밥", 3);
  assert.equal(result.method, "recipe");
  assert.equal(result.total, 30867);
  assert.equal(result.marketTotal, 39000);
  assert.equal(result.offerTotal, null);
  assert.equal(estimate(data, recipeData, "새우계란볶음밥 500g", 3).method, "review");
  const similar = estimate(data, recipeData, "가리비볶음밥", 1);
  assert.equal(similar.method, "market_estimate");
  assert.equal(similar.offerTotal, null);
  assert.equal(estimate(data, recipeData, "밀푀유나베", 1).method, "review");
});

test("measured batches and usable purchase weight update the estimate before checking offer eligibility", () => {
  const work = {prepMinutes: 6, batchMinutes: 4, servingsPerBatch: 2};
  const purchases = {새우: {price: 10000, usableAmount: 400}};
  const preview = estimate(data, recipeData, "새우계란볶음밥", 3, {work, purchases});
  const result = estimate(data, recipeData, "새우계란볶음밥", 3, {work, purchases, confirmed: true});
  assert.equal(preview.offerTotal, null);
  assert.equal(preview.total, result.total);
  assert.deepEqual(result.recipeQuote.missing, []);
  const {minutes, labor, food, markup_amount, lines} = result.recipeQuote.breakdown;
  assert.deepEqual([minutes, labor, food, markup_amount], [14, 3733, 12000, 3600]);
  assert.equal(lines[0].cost, 6000);
  assert.equal(result.offerTotal, 19333);
  assert.equal(offers(result.offerTotal).length, 3);

  const invalid = estimate(data, recipeData, "새우계란볶음밥", 3,
    {work, purchases: {새우: {price: 10000, usableAmount: 0}}, confirmed: true});
  assert.equal(invalid.offerTotal, null);
  assert.equal(invalid.recipeQuote.breakdown.food, 18000);
  const exact = estimate(data, recipeData, "새우볶음밥 1인분", 3, {work, purchases, confirmed: true});
  assert.equal(exact.recipeQuote.breakdown.total, 19333);
  assert.equal(exact.offerTotal, 36000);
});

test("a recipe without default labor shows materials and only prices the order after work is entered", () => {
  const base = {lines: [{item: "달걀", quantity: 3, cost: 1200}], food: 1200, labor: null,
    markup_amount: 360, packaging: 0, minutes: null, total: null};
  const recipes = {menus: {달걀국: "egg"}, policy: recipeData.policy,
    recipes: {egg: {primaryIngredients: ["달걀"], quotes: [null, base]}}};
  const work = {prepMinutes: 5, batchMinutes: 4, servingsPerBatch: 4};
  const purchases = {달걀: {price: 3600, usableAmount: 10}};
  const display = estimate(data, recipes, "달걀국", 2, {purchases, confirmed: true});
  assert.equal(display.recipeQuote.breakdown.food, 1080);
  assert.equal(display.total, null);
  assert.equal(display.offerTotal, null);
  const ready = estimate(data, recipes, "달걀국", 2, {work, purchases, confirmed: true});
  assert.equal(ready.total, 3804);
  assert.equal(ready.offerTotal, 3804);
});
