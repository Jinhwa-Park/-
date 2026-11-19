"use strict";

const SeoulOffers = (() => {
  const portionFamilies = [
    "볶음밥", "비빔밥", "오므라이스", "카레라이스", "덮밥", "솥밥", "국밥", "리조또", "리소토",
    "스파게티", "파스타", "칼국수", "쌀국수", "콩국수", "국수", "냉면", "우동", "소바", "라멘",
    "라면", "짜장면", "짬뽕", "떡국", "만둣국", "만두국", "설렁탕", "육개장", "해장국", "곰탕",
    "찌개", "돈까스", "돈가스", "돈카츠", "샌드위치", "김밥", "버거"
  ];
  const referenceFamilies = ["그라탕", "나베", "전골", "찜", "볶음", "스테이크", "구이", "탕", "만두"];
  const families = [...portionFamilies, ...referenceFamilies].sort((a, b) => b.length - a.length);
  const ingredientGroups = [
    ["해산물", /해물|해산물|삼선|새우|가리비|게살|꽃게|오징어|낙지|주꾸미|문어|전복|조개|굴|연어|참치|고등어/],
    ["소고기", /소고기|쇠고기|한우|차돌|우삼겹|소불고기/],
    ["돼지고기", /돼지|제육|삼겹|햄|베이컨|스팸/],
    ["닭고기", /닭|치킨/],
    ["채소·버섯", /채소|야채|가지|시금치|버섯|나물|두부/],
  ];
  const conditional = /세트|정식|코스|추가|사리|한정|런치|디너|특대|곱빼기|(?:소|중|대)사이즈/;
  const saleUnit = /[\[(]?(\d+(?:[.,]\d+)?(?:[~～-]\d+(?:[.,]\d+)?)?(?:인분?|kg|ml|g|l|개|잔|팩|pcs|p))[)\]]?$/;
  const bands = [
    {label: "낮은 오퍼", min: -8, max: -4},
    {label: "기준가 근처", min: -2, max: 2},
    {label: "높은 오퍼", min: 4, max: 8}
  ];
  const own = (object, key) => Object.hasOwn(object, key) ? object[key] : undefined;
  const normalize = value => value.normalize("NFC").replace(/\s+/g, "").toLowerCase();
  const unitKey = value => normalize(value).replace(/인$/, "인분").replace(/[～-]/g, "~").replace(/,/g, ".");
  const familyOf = name => families.find(family => name.endsWith(family));
  const ingredientKinds = name => ingredientGroups.filter(([, pattern]) => pattern.test(name)).map(([label]) => label);

  function parts(value) {
    const full = normalize(value);
    const match = saleUnit.exec(full);
    return match ? {name: full.slice(0, match.index), unit: unitKey(match[1])} : {name: full, unit: null};
  }

  function similarity(query, name, family, ingredients) {
    const sharedFamily = Boolean(family && familyOf(name) === family);
    const contained = Math.min(query.length, name.length) >= 3 && (name.includes(query) || query.includes(name));
    if (!sharedFamily && !contained) return null;
    const core = sharedFamily ? query.slice(0, -family.length) : query;
    const otherCore = sharedFamily ? name.slice(0, -family.length) : name;
    const bigrams = new Set(Array.from({length: Math.max(0, core.length - 1)}, (_, i) => core.slice(i, i + 2)));
    const shared = [...bigrams].filter(piece => otherCore.includes(piece)).length;
    const overlap = bigrams.size ? shared / Math.max(bigrams.size, otherCore.length - 1) : 0;
    const ingredientsInCommon = ingredientKinds(otherCore).filter(ingredient => ingredients.includes(ingredient));
    return {
      sharedFamily,
      similarIngredients: ingredientsInCommon.length > 0,
      score: (sharedFamily ? 4 : 0) + (contained ? 2 : 0) + overlap * 3 + ingredientsInCommon.length * 3,
      reason: [sharedFamily ? `같은 요리 유형 (${family})` : "메뉴명 일부 일치", ...ingredientsInCommon].join(" · ")
    };
  }

  function find(data, query) {
    const {name, unit} = parts(query);
    if (!name) return {exact: null, references: [], similar: [], basis: null};
    const canonical = own(data.aliases, name) ?? name;
    const exact = own(data.menus, canonical) ?? null;
    const singleServing = !unit || unit === "1인분";
    const references = (exact?.references ?? []).filter(row => singleServing || unitKey(row.unit) === unit);
    const exactBaseline = singleServing && exact?.baseline ? references.find(row => row.row === exact.baseline.row) : null;
    const family = familyOf(canonical);
    const ingredients = ingredientKinds(family ? canonical.slice(0, -family.length) : canonical);
    const canEstimate = singleServing && portionFamilies.includes(family) &&
      canonical !== family && !conditional.test(canonical);
    const candidates = [];
    for (const [key, entry] of Object.entries(data.menus)) {
      if (key === canonical) continue;
      const match = similarity(canonical, key, family, ingredients);
      if (!match) continue;
      const display = entry.baseline ?? entry.references[0];
      candidates.push({key, name: entry.name, display, ...match,
        comparable: canEstimate && match.sharedFamily && key !== family && Boolean(entry.baseline) &&
          !conditional.test(key) && (!ingredients.length || match.similarIngredients)});
    }
    candidates.sort((a, b) => b.score - a.score || b.display.stores - a.display.stores || a.name.localeCompare(b.name, "ko"));
    const sources = exactBaseline ? [] : candidates.filter(row => row.comparable).slice(0, 3);
    const used = new Set((sources.length >= 2 ? sources : []).map(row => row.key));
    const ordered = [...candidates.filter(row => used.has(row.key)), ...candidates.filter(row => !used.has(row.key))];
    const similar = ordered.slice(0, 5).map(row => ({...row, used: used.has(row.key)}));
    let basis = null;
    if (exactBaseline) {
      basis = {kind: "exact", price: exactBaseline.price, reference: exactBaseline};
    } else if (used.size) {
      const amounts = sources.map(row => row.display.price).sort((a, b) => a - b);
      const price = Math.round((amounts[Math.floor((amounts.length - 1) / 2)] + amounts[Math.floor(amounts.length / 2)]) / 2);
      basis = {kind: "estimated", price, count: amounts.length};
    }
    return {exact, references, similar, basis};
  }

  function offers(total, random = Math.random) {
    const output = [];
    for (const {label, min, max} of bands) {
      const lower = Math.max(1, Math.ceil(total * (100 + min) / 100));
      const upper = Math.floor(total * (100 + max) / 100);
      if (lower > upper) return [];
      const step = Math.ceil(lower / 100) <= Math.floor(upper / 100) ? 100 : 1;
      const first = Math.ceil(lower / step);
      const last = Math.floor(upper / step);
      const price = (first + Math.floor(random() * (last - first + 1))) * step;
      output.push({label, price, change: (price - total) / total});
    }
    return output;
  }

  const positive = value => Number.isFinite(value) && value > 0;
  const positiveInteger = value => Number.isSafeInteger(value) && value > 0;

  function workCost(policy, minutes) {
    if (!positive(minutes)) return null;
    const labor = Math.round(minutes * policy.hourlyWon / 60);
    return Number.isSafeInteger(labor) ? {minutes, labor} : null;
  }

  function measuredWork(policy, servings, {prepMinutes, batchMinutes, servingsPerBatch} = {}) {
    if (!Number.isFinite(prepMinutes) || prepMinutes < 0 || !positive(batchMinutes) || !positiveInteger(servingsPerBatch)) {
      return null;
    }
    const batches = Math.ceil(servings / servingsPerBatch);
    const totals = workCost(policy, prepMinutes + batches * batchMinutes);
    return totals && {prepMinutes, batchMinutes, servingsPerBatch, batches, ...totals};
  }

  function adjustRecipe(recipe, base, policy, servings, inputs) {
    const work = measuredWork(policy, servings, inputs.work);
    const primaryIngredients = new Set(recipe.primaryIngredients);
    const lines = base.lines.map(line => {
      const purchase = primaryIngredients.has(line.item) && inputs.purchases && own(inputs.purchases, line.item);
      if (!Number.isSafeInteger(purchase?.price) || !positive(purchase.price) || !positive(purchase.usableAmount)) return line;
      const cost = Math.round(line.quantity * purchase.price / purchase.usableAmount);
      return Number.isSafeInteger(cost) ? {...line, cost, purchase} : line;
    });
    const food = lines.reduce((sum, line) => sum + line.cost, 0);
    const labor = work?.labor ?? base.labor;
    const markup_amount = food === base.food ? base.markup_amount : Math.round(food * policy.markup);
    const total = labor === null ? null : food + labor + markup_amount + base.packaging;
    const missingPurchases = recipe.primaryIngredients.filter(item => !lines.some(line => line.item === item && line.purchase));
    const missing = [...(work ? [] : ["직접 작업시간"]), ...missingPurchases.map(item => `${item} 매입가와 사용 가능량`),
      ...(inputs.confirmed === true ? [] : ["레시피 재료와 분량 확인"])];
    if (!Number.isSafeInteger(food) || (total !== null && !Number.isSafeInteger(total))) {
      return {breakdown: base, missing: ["계산 범위 안의 작업시간과 매입 정보"]};
    }
    return {breakdown: {...base, lines, food, labor, markup_amount, total, work,
      minutes: work?.minutes ?? base.minutes}, missing};
  }

  function quotePublicRecipe(records, policy, servings, inputs) {
    const record = inputs.publicRecipeId ? records.find(record => record.id === inputs.publicRecipeId) :
      records.length === 1 ? records[0] : null;
    if (!record) return {total: null, missing: ["견적에 사용할 식약처 레시피 선택"]};
    if (!record.ingredients) return {total: null, missing: ["원본에 빠진 재료와 분량 확인"]};

    const sourceServings = inputs.sourceServings ?? record.servings;
    const batchCost = inputs.batchCost;
    const work = inputs.directMinutes === undefined ? measuredWork(policy, servings, inputs.work) : workCost(policy, inputs.directMinutes);
    const missing = [];
    if (!positiveInteger(sourceServings)) missing.push("원본 분량의 인분");
    if (!positiveInteger(batchCost)) missing.push("해당 분량의 재료비");
    if (!work) missing.push("직접 작업시간");
    if (inputs.confirmed !== true) missing.push("레시피 재료와 분량 확인");

    const food = positiveInteger(sourceServings) && positiveInteger(batchCost) ? Math.round(batchCost * servings / sourceServings) : null;
    const markup = food === null ? null : Math.round(food * policy.markup);
    const total = food === null || !work ? null : food + markup + work.labor;
    if ((food !== null && !positiveInteger(food)) || (total !== null && !positiveInteger(total))) {
      return {total: null, missing: ["계산 범위 안의 재료비와 작업시간"]};
    }
    return {total, food, markup, work, missing};
  }

  function estimate(data, recipeData, query, servings, inputs = {}) {
    const market = find(data, query);
    const {name, unit} = parts(query);
    const menu = own(data.aliases, name) ?? name;
    const singleServing = !unit || unit === "1인분";
    const recipeId = recipeData && singleServing &&
      (own(recipeData.menus, name) ?? own(recipeData.menus, menu));
    const recipe = recipeId ? own(recipeData.recipes, recipeId) : null;
    const base = recipe?.quotes[servings - 1];
    const recipeQuote = base ? {recipe, ...adjustRecipe(recipe, base, recipeData.policy, servings, inputs)} : null;
    const publicIndex = recipeData?.public?.entries;
    const publicRecipes = (publicIndex && singleServing && (own(publicIndex, name) ?? own(publicIndex, menu))) || [];
    const publicQuote = !recipeQuote && publicRecipes.length ? quotePublicRecipe(publicRecipes, recipeData.policy, servings, inputs) : null;
    const marketTotal = market.basis ? market.basis.price * servings : null;
    const context = {market, marketTotal, recipeQuote, publicRecipes, publicQuote};
    if (market.basis?.kind === "exact") {
      return {...context, total: marketTotal, offerTotal: marketTotal, method: "market_exact"};
    }
    if (recipeQuote) {
      const total = recipeQuote.breakdown.total;
      return {...context, total, offerTotal: recipeQuote.missing.length ? null : total, method: "recipe"};
    }
    if (publicQuote) {
      const {total, missing} = publicQuote;
      return {...context, total, offerTotal: missing.length ? null : total, method: "public_recipe"};
    }
    if (marketTotal) {
      return {...context, total: marketTotal, offerTotal: null, method: "market_estimate"};
    }
    return {...context, total: null, offerTotal: null, method: "review"};
  }

  return {find, offers, estimate};
})();

if (typeof module !== "undefined" && module.exports) module.exports = SeoulOffers;
