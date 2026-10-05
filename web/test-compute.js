// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 bob3703
// Licensed under the Apache License, Version 2.0. See the LICENSE file for the full text.
/**
 * test-compute.js — Node.js ES module test for compute.js
 * Run: node test-compute.js  (requires package.json with "type":"module")
 */
import { readFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import {
  clamp, roundYuan, fmt, taxByTable, calcCumulativeTax,
  bonusSingleTax, monthlySpecial, createSession,
  computeMonth, computeYear, compareBonus,
  estimateAnnualSettlement, inverseGrossFromNet
} from './compute.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Load config
const CFG = JSON.parse(readFileSync(join(__dirname, '..', 'config.json'), 'utf-8'));

let failures = 0;

function assert(condition, msg) {
  if (condition) {
    console.log(`  PASS: ${msg}`);
  } else {
    console.log(`  FAIL: ${msg}`);
    failures++;
  }
}

function assertClose(actual, expected, tol, msg) {
  const ok = Math.abs(actual - expected) <= tol;
  if (ok) {
    console.log(`  PASS: ${msg} (actual=${fmt(actual)})`);
  } else {
    console.log(`  FAIL: ${msg} (expected≈${expected}, actual=${actual})`);
    failures++;
  }
}

// =====================================================================
// Test 1: Utility functions
// =====================================================================
console.log('\n=== Utility Functions ===');

assert(clamp(5, 1, 10) === 5, 'clamp(5,1,10)=5');
assert(clamp(0, 1, 10) === 1, 'clamp(0,1,10)=1');
assert(clamp(15, 1, 10) === 10, 'clamp(15,1,10)=10');

assert(roundYuan(2.5) === 3, 'roundYuan(2.5)=3');
assert(roundYuan(2.4) === 2, 'roundYuan(2.4)=2');
assert(roundYuan(2.49999) === 2, 'roundYuan(2.49999)=2');
assert(roundYuan(-0.5) === 0, 'roundYuan(-0.5)=0 (floor of 0)');

assert(fmt(1234.5) === '1234.50', 'fmt(1234.5)="1234.50"');

// Tax bracket test
const TB = CFG.tax_brackets.map(r => [r[0] === null ? Infinity : Number(r[0]), Number(r[1]), Number(r[2])]);
assert(taxByTable(0, TB) === 0, 'taxByTable(0)=0');
assert(taxByTable(36000, TB) === 36000 * 0.03 - 0, 'taxByTable(36000)=1080');
assertClose(taxByTable(100000, TB), 100000 * 0.10 - 2520, 0.01, 'taxByTable(100000)=7480');

// =====================================================================
// Test 2: Shanghai 2026 session + month 1
// =====================================================================
console.log('\n=== Shanghai 2026, salary=30000, housingPct=7, no special deductions ===');

const sess = createSession('shanghai', 2026, CFG);
assert(sess.city_name === '上海', 'city_name=上海');
assert(sess.year === 2026, 'year=2026');
assert(sess.pension_emp === 0.08, 'pension_emp=0.08');
assert(sess.housing_rate_min === 5, 'housing_rate_min=5');
assert(sess.housing_rate_max === 7, 'housing_rate_max=7');
assert(sess.extra_min === 1, 'extra_min=1');
assert(sess.extra_max === 5, 'extra_max=5');
assert(sess.taxFreeMonthly === 5000, 'taxFreeMonthly=5000');

// Period tests
const [hk1] = sess.periodFor(3);
assert(hk1 === 'h1', 'month 3 → h1');
const [hk2] = sess.periodFor(9);
assert(hk2 === 'h2', 'month 9 → h2');

// Social bounds month 1 (h1): [7460, 37302] for all
const [plo, phi, mlo, mhi, ulo, uhi] = sess.socialBounds(1);
assert(plo === 7460 && phi === 37302, 'h1 social bounds [7460,37302]');
assert(mlo === 7460 && mhi === 37302, 'h1 medical bounds same');
assert(ulo === 7460 && uhi === 37302, 'h1 unemployment bounds same');

// Housing bounds month 1: [2690, 37302]
const [hlo, hhi] = sess.housingBounds(1);
assert(hlo === 2690 && hhi === 37302, 'h1 housing bounds [2690,37302]');

// isProvisional for 2026 h1: should be false (no provisional flag)
assert(sess.isProvisional(3) === false, 'h1 not provisional');
// h2 has no provisional flag for shanghai 2026
assert(sess.isProvisional(9) === false, 'h2 shanghai 2026 not provisional');

// Compute month 1
const salary = 30000;
const specialItems = [];
const housingPct = 7;
const extraPct = 0;

const sbM1 = {
  pension: clamp(salary, plo, phi),
  medical: clamp(salary, mlo, mhi),
  unemployment: clamp(salary, ulo, uhi),
};
const hbM1 = clamp(salary, hlo, hhi);
const r1 = computeMonth(sess, 1, salary, sbM1, hbM1, specialItems, housingPct, extraPct, CFG);

console.log('\n  Month 1 result:', JSON.stringify(r1, null, 2).substring(0, 400), '...');

assert(r1.month_no === 1, 'month_no=1');
assert(r1.salary === 30000, 'salary=30000');
assert(r1.sb_p === 30000, 'sb_p=30000 (within bounds)');
assert(r1.sb_m === 30000, 'sb_m=30000');
assert(r1.sb_u === 30000, 'sb_u=30000');
assert(r1.housing_base === 30000, 'housing_base=30000 (within bounds)');

// pension_p = 30000 * 0.08 = 2400
assertClose(r1.pension_p, 2400, 0.01, 'pension_p=2400');
// medical_p = 30000 * 0.02 = 600
assertClose(r1.medical_p, 600, 0.01, 'medical_p=600');
// unemploy_p = 30000 * 0.005 = 150
assertClose(r1.unemploy_p, 150, 0.01, 'unemploy_p=150');
// housing_p = roundYuan(30000 * 7 / 100) = 2100
assert(r1.housing_p === 2100, 'housing_p=2100');
// extra_p = 0 (extra_pct=0)
assert(r1.extra_p === 0, 'extra_p=0');
// social_p_total = 2400 + 600 + 150 + 2100 + 0 = 5250
assertClose(r1.social_p_total, 5250, 0.01, 'social_p_total=5250');

// cum_taxable month 1 = 30000*1 - 5000*1 - 5250*1 - 0 = 19750
assertClose(r1.cum_taxable, 19750, 0.01, 'cum_taxable=19750');

// Tax: 19750 * 0.03 - 0 = 592.5
assertClose(r1.cum_tax, 592.5, 0.01, 'cum_tax=592.5');
// Month 1: prev_cum_taxable = 19750 - 30000 + 5000 + 5250 + 0 = 0
// prev_cum_tax = 0, month_tax = max(0, 592.5 - 0) = 592.5
assertClose(r1.month_tax, 592.5, 0.01, 'month_tax=592.5');

// net = 30000 - 5250 - 592.5 = 24157.5
assertClose(r1.net, 24157.5, 0.01, 'net=24157.5');

assert(r1.rate === 0.03, 'rate=0.03 (3% bracket)');
assert(r1.quick === 0, 'quick=0');

// Verify all expected keys exist
const expectedKeys = ['month_no','salary','sb_p','sb_m','sb_u','housing_base',
  'pension_p','medical_p','unemploy_p','housing_p','extra_p','social_p_total',
  'pension_o','medical_o','unemploy_o','injury_o','housing_o','extra_o','social_o_total',
  'cum_taxable','cum_tax','month_tax','rate','quick','net',
  'special_monthly','housing_pct','extra_pct'];
for (const k of expectedKeys) {
  assert(k in r1, `key "${k}" exists in result`);
}

// =====================================================================
// Test 3: Bonus comparison (100000 bonus)
// =====================================================================
console.log('\n=== Bonus Comparison: 100000 ===');

const bonusResult = compareBonus(salary, r1.social_p_total, 0, 100000, CFG);
console.log('  bonus:', JSON.stringify(bonusResult));

// salary_tax_a = calcCumulativeTax(30000*12 - 5000*12 - 5250*12 - 0)
//             = calcCumulativeTax(360000 - 60000 - 63000) = calcCumulativeTax(237000)
// 237000: falls in bracket [144000, 0.10, 2520] → 237000*0.10 - 2520 = 21180
// Wait, 237000 > 144000 and <= 300000: 0.20 - 16920 → 237000*0.20 - 16920 = 30480
assertClose(bonusResult.salaryTaxA, 30480, 0.01, 'salaryTaxA=30480 (bracket 20%-16920)');

// bonus_single_tax(100000, 30000, bonusBrackets, 5000)
// salary >= 5000, base=100000, avg=100000/12=8333.33
// avg <= 12000 → bracket [12000, 0.10, 210] → 100000*0.10 - 210 = 9790
assertClose(bonusResult.bonusTaxA, 9790, 0.01, 'bonusTaxA=9790');

assertClose(bonusResult.totalA, bonusResult.salaryTaxA + bonusResult.bonusTaxA, 0.01, 'totalA=sum');

// totalB: taxable_b = 360000 + 100000 - 60000 - 63000 = 337000
assertClose(bonusResult.taxableB, 337000, 0.01, 'taxableB=337000');
// 337000: bracket [420000, 0.25, 31920] → 337000*0.25 - 31920 = 52330
assertClose(bonusResult.totalB, 52330, 0.01, 'totalB=52330');

assert(bonusResult.totalA < bonusResult.totalB, 'Method A (separate) saves more tax');

// =====================================================================
// Test 4: Annual settlement
// =====================================================================
console.log('\n=== Annual Settlement ===');

const months12 = computeYear(sess, salary, specialItems, housingPct, extraPct, CFG);
assert(months12.length === 12, 'computeYear returns 12 months');

const settlement = estimateAnnualSettlement(months12, CFG, 0);
console.log('  settlement:', JSON.stringify(settlement));

// annual_taxable = 30000*12 - 60000 - social_total - 0
// social_p_total might vary per month due to half-year bounds
// For Shanghai 2026 h1: bounds [7460,37302], salary=30000 → sb=30000
// For Shanghai 2026 h2: bounds [7546,37731], salary=30000 → sb=30000
// Both cases: 30000 is within all bounds. Housing h1: [2690,37302], h2: [2740,37731] → 30000 within.
// So social_p_total = 5250 for all months.
// annual_gross = 360000, annual_contrib = 5250*12 = 63000
// annual_taxable = 360000 - 60000 - 63000 = 237000
assertClose(settlement.annualTaxable, 237000, 0.01, 'annualTaxable=237000');

// annual_settlement_tax: 237000*0.20 - 16920 = 30480
assertClose(settlement.annualSettlementTax, 30480, 0.01, 'annualSettlementTax=30480');

// withheld_tax = months12[11].cum_tax (month 12 cum_tax)
assertClose(settlement.withheldTax, months12[11].cum_tax, 0.01, 'withheldTax=cum_tax[12]');

// estimated_refund = withheld - settlement
assertClose(settlement.estimatedRefund, settlement.withheldTax - settlement.annualSettlementTax, 0.01, 'refund calc correct');

// =====================================================================
// Test 5: Inverse calculation (target net 20000/month)
// =====================================================================
console.log('\n=== Inverse: targetNet=20000 ===');

const inv = inverseGrossFromNet(sess, 20000, specialItems, housingPct, extraPct, CFG);
console.log(`  gross=${fmt(inv.gross)}, net_12m=${fmt(inv.net_12m)}, tax_12m=${fmt(inv.tax_12m)}`);

// Should be close to 20000*12 = 240000
assertClose(inv.net_12m, 240000, 1.0, 'net_12m ≈ 240000 (within 1 yuan tol)');
assert(inv.gross > 20000, 'gross > target net (expected due to deductions)');
assert(inv.gross < 30000, 'gross < 30000 (reasonable for 20000 net)');

// =====================================================================
// Test 6: Shenzhen (dict format social_base)
// =====================================================================
console.log('\n=== Shenzhen 2026 (dict social_base format) ===');

const sessSZ = createSession('shenzhen', 2026, CFG);
const [splo, sphl, smlo, smhl, suLo, suhi] = sessSZ.socialBounds(1);
// h1: pension [4775, 27549], medical [6727, 33633] (2026自然年度官方值), unemployment [2520, 44934]
assert(splo === 4775 && sphl === 27549, 'SZ pension bounds [4775,27549]');
assert(smlo === 6727 && smhl === 33633, 'SZ medical bounds 2026 [6727,33633]');
assert(suLo === 2520 && suhi === 44934, 'SZ unemployment bounds [2520,44934]');

// =====================================================================
// Test 7: Historical years 2023/2024 coverage (parity with income-calc)
// =====================================================================
console.log('\n=== 2023/2024 historical year coverage ===');

const CITY_CODES = ['shanghai', 'beijing', 'guangzhou', 'hangzhou', 'shenzhen', 'nanjing', 'hefei', 'wuhu'];
for (const code of CITY_CODES) {
  for (const y of ['2023', '2024', '2025', '2026']) {
    assert(!!CFG.cities[code].years[y], `${code} has year ${y}`);
  }
}

// Shanghai 2023/2024 — cross-checked against the official 历年对照表 in the calibration report
// (2023: 7310/36549, 2024: 7384/36921 are the H2 values of those social-insurance years).
const sh23 = CFG.cities.shanghai.years['2023'];
assert(sh23.h1.social_base[0] === 6520 && sh23.h1.social_base[1] === 34188, 'SH 2023 h1 social [6520,34188]');
assert(sh23.h2.social_base[0] === 7310 && sh23.h2.social_base[1] === 36549, 'SH 2023 h2 social [7310,36549]');
assert(sh23.h1.housing_base[0] === 2590 && sh23.h1.housing_base[1] === 34188, 'SH 2023 h1 housing [2590,34188]');
const sh24 = CFG.cities.shanghai.years['2024'];
assert(sh24.h1.social_base[0] === 7310 && sh24.h1.social_base[1] === 36549, 'SH 2024 h1 social [7310,36549]');
assert(sh24.h2.social_base[0] === 7384 && sh24.h2.social_base[1] === 36921, 'SH 2024 h2 social [7384,36921]');
assert(sh24.h2.housing_base[1] === 36921, 'SH 2024 h2 housing upper 36921');

// v3.1 补齐历史年度时的关键基数（部分断言已在 v3.3 按自然年度口径修正）
// Spot checks for the other 7 cities on 2023/2024 H1 lower bounds.
assert(CFG.cities.beijing.years['2023'].h1.social_base[0] === 5869, 'BJ 2023 h1 lower 5869');
assert(CFG.cities.beijing.years['2024'].h2.social_base[1] === 35283, 'BJ 2024 h2 upper 35283');
assert(CFG.cities.guangzhou.years['2023'].h1.social_base[0] === 4588, 'GZ 2023 h1 lower 4588');
assert(CFG.cities.hangzhou.years['2023'].h1.social_base[1] === 24060, 'HZ 2023 h1 upper 24060 (calendar year, not the 2022 lagged 22311)');
assert(CFG.cities.nanjing.years['2024'].h1.social_base[0] === 4879, 'NJ 2024 h1 lower 4879');
assert(CFG.cities.hefei.years['2024'].h2.social_base[1] === 21133, 'HF 2024 h2 upper 21133');
assert(CFG.cities.wuhu.years['2023'].h1.housing_base[0] === 1930, 'WH 2023 h1 housing lower 1930');

// Shenzhen 2023/2024: pension/unemployment follow the social-insurance year (from July),
// while medical follows the CALENDAR year per 深圳市医保局 notices.
const sz24 = CFG.cities.shenzhen.years['2024'];
assert(sz24.h1.social_base.pension[1] === 26421, 'SZ 2024 h1 pension upper 26421');
assert(sz24.h2.social_base.pension[0] === 3523, 'SZ 2024 h2 pension lower 3523');
assert(sz24.h1.social_base.medical[0] === 6475 && sz24.h1.social_base.medical[1] === 32376, 'SZ 2024 h1 medical [6475,32376]');
assert(sz24.h2.social_base.medical[0] === 6475 && sz24.h2.social_base.medical[1] === 32376, 'SZ 2024 h2 medical stays [6475,32376]');
const sz23 = CFG.cities.shenzhen.years['2023'];
assert(sz23.h1.social_base.medical[0] === 7778 && sz23.h2.social_base.medical[1] === 38892, 'SZ 2023 medical [7778,38892] both halves');

// 深圳医保自然年度口径：2025 全年 6733/33666（官方 2024-12-27 公告），不得沿用 2024 值
const sz25 = CFG.cities.shenzhen.years['2025'];
assert(sz25.h1.social_base.medical[0] === 6733 && sz25.h1.social_base.medical[1] === 33666, 'SZ 2025 h1 medical [6733,33666]');
assert(sz25.h2.social_base.medical[0] === 6733 && sz25.h2.social_base.medical[1] === 33666, 'SZ 2025 h2 medical [6733,33666]');
assert(sz25.h1.social_base.unemployment[1] === 43659, 'SZ 2025 h1 unemployment upper 43659');
assert(sz25.h1.housing_base[1] === 43659, 'SZ 2025 h1 housing upper 43659');

// Corrections to previously lagged rows (must match income-calc / official publications)
assert(CFG.cities.hangzhou.years['2025'].h1.social_base[1] === 25299, 'HZ 2025 h1 social upper 25299 (v3.3: H1 no longer lags one year)');
assert(CFG.cities.hangzhou.years['2025'].h1.housing_base[1] === 39530, 'HZ 2025 h1 housing upper 39530');
assert(CFG.cities.hangzhou.years['2025'].h2.housing_base[1] === 40694, 'HZ 2025 h2 housing upper 40694');
assert(CFG.cities.hangzhou.years['2026'].h1.housing_base[1] === 40694, 'HZ 2026 h1 housing upper 40694');
assert(CFG.cities.wuhu.years['2025'].h1.housing_base[1] === 25386, 'WH 2025 h1 housing upper 25386');

// A historical year must compute end-to-end (Shanghai 2023 H1, gross 20000, fund 7%)
// Expected M1: 五险一金 2100+1400=3500 / 个税 (20000-5000-3500)*3%=345 / 到手 16155
console.log('\n=== Historical-year full-year computation ===');
const sessSH23 = createSession('shanghai', 2023, CFG);
const m23 = computeYear(sessSH23, 20000, [], 7, 0, CFG);
assert(m23.length === 12, 'SH 2023 computes 12 months');
assertClose(m23[0].social_p_total, 3500, 0.005, 'SH 2023 M1 五险一金 = 3500');
assertClose(m23[0].month_tax, 345, 0.005, 'SH 2023 M1 个税 = 345');
assertClose(m23[0].net, 16155, 0.005, 'SH 2023 M1 到手 = 16155');
// H1/H2 of 2023 use different bounds (6520/34188 vs 7310/36549), and M7 has already
// crossed the 36000 cumulative threshold so it falls into the 10% bracket.
const [h1lo, h1hi] = sessSH23.socialBounds(1);
const [h2lo, h2hi] = sessSH23.socialBounds(7);
assert(h1lo === 6520 && h1hi === 34188, 'SH 2023 H1 bounds 6520/34188');
assert(h2lo === 7310 && h2hi === 36549, 'SH 2023 H2 bounds 7310/36549');
assertClose(m23[6].month_tax, 1150, 0.005, 'SH 2023 M7 个税 = 1150（累计预扣跨入 10% 档）');
assertClose(m23[6].net, 15350, 0.005, 'SH 2023 M7 到手 = 15350');

// =====================================================================
// Test 8: 2026 rows verified against official notices
// provisional semantics: true = 该半年度仍含沿用上一期的项（未全部公布）
// =====================================================================
console.log('\n=== 2026 official notice verification ===');

// Beijing: 人力社保局 2026-08-21 通告（社保 [7270,36348]）+ 公积金中心 2026-08-24 通知（[2540,36348]）
const bj26h2 = CFG.cities.beijing.years['2026'].h2;
assert(bj26h2.social_base[0] === 7270 && bj26h2.social_base[1] === 36348, 'BJ 2026 h2 social [7270,36348]');
assert(bj26h2.housing_base[0] === 2540 && bj26h2.housing_base[1] === 36348, 'BJ 2026 h2 housing [2540,36348]');
assert(!bj26h2.provisional, 'BJ 2026 h2 fully announced (2026-08-21 / 2026-08-24)');
assert(CFG.cities.beijing.years['2026'].verified_on === '2026-08-24', 'BJ 2026 verified_on is the announcement date');

// Nanjing: 南京公积金中心 2026-07-17 通知（上限 42400 = 2025 年在岗职工月均工资 3 倍，下限 2660）
// social: 江苏官方明确 2026 年 1 月起暂按 2025 年度标准执行 → 该半年度仍含沿用项
const nj26h2 = CFG.cities.nanjing.years['2026'].h2;
assert(nj26h2.housing_base[0] === 2660 && nj26h2.housing_base[1] === 42400, 'NJ 2026 h2 housing [2660,42400]');
assert(nj26h2.provisional === true, 'NJ 2026 h2 stays provisional (Jiangsu social carried over by official notice)');

// Hangzhou: 杭州公积金中心 2026-07-25 通知（上限 42151，杭州市区下限 2660，执行 2026-07-01至2027-06-30）
const hz26h2 = CFG.cities.hangzhou.years['2026'].h2;
assert(hz26h2.housing_base[0] === 2660 && hz26h2.housing_base[1] === 42151, 'HZ 2026 h2 housing [2660,42151]');
assert(hz26h2.provisional === true, 'HZ 2026 h2 stays provisional (Zhejiang social year not announced)');
// Hangzhou 2026 h1 still sits in the 2025 housing year
assert(CFG.cities.hangzhou.years['2026'].h1.housing_base[1] === 40694, 'HZ 2026 h1 housing upper 40694 (2025 year)');

// Guangzhou: 广州公积金中心 2026-07-06 通知（上限 41697，下限 2500）
const gz26h2 = CFG.cities.guangzhou.years['2026'].h2;
assert(gz26h2.housing_base[0] === 2500 && gz26h2.housing_base[1] === 41697, 'GZ 2026 h2 housing [2500,41697]');
assert(CFG.cities.guangzhou.years['2026'].h2.provisional === true, 'GZ 2026 h2 stays provisional (Guangdong social year not announced)');

// Anhui: 2026-09-07 五部门通知，社保基数 [4354,21772] 执行 2026 自然年度（全年统一，公布前暂按上期并补差）
for (const code of ['hefei', 'wuhu']) {
  for (const half of ['h1', 'h2']) {
    const y = CFG.cities[code].years['2026'][half];
    assert(y.social_base[0] === 4354 && y.social_base[1] === 21772, `${code} 2026 ${half} social [4354,21772] (Anhui calendar year)`);
    assert(JSON.stringify(CFG.cities[code].years['2026'].h1.social_base) === JSON.stringify(y.social_base),
      `${code} 2026 ${half} social identical across halves (calendar year)`);
  }
}
// Hefei: 合肥公积金中心 2026-06-29 通知（上限 31564，下限 2320）——社保与公积金均已公布，可去 provisional
const hf26h2 = CFG.cities.hefei.years['2026'].h2;
assert(hf26h2.housing_base[0] === 2320 && hf26h2.housing_base[1] === 31564, 'HF 2026 h2 housing [2320,31564]');
assert(!hf26h2.provisional, 'HF 2026 h2 fully announced (social 2026-09-07 + fund 2026-06-29)');
assert(!CFG.cities.hefei.years['2026'].h1.provisional, 'HF 2026 h1 fully announced');
// Wuhu fund 2026 upper limit not yet verified: keep the carried-over value flagged
assert(CFG.cities.wuhu.years['2026'].h2.provisional === true, 'WH 2026 h2 stays provisional (Wuhu fund notice not verified)');

// Guangzhou medical follows the calendar year (separate from the Guangdong pension cap),
// so Guangzhou must use the per-insurance object form like Shenzhen.
const gz26h1 = CFG.cities.guangzhou.years['2026'].h1.social_base;
assert(gz26h1.medical && gz26h1.medical[0] === 6234 && gz26h1.medical[1] === 31170,
  'GZ 2026 medical [6234,31170] split out as per-insurance');
assert(gz26h1.pension[0] === 5510 && gz26h1.pension[1] === 27549, 'GZ 2026 pension [5510,27549]');
assert(JSON.stringify(gz26h1.unemployment) === JSON.stringify(gz26h1.pension), 'GZ 2026 unemployment follows pension');
const gz25h1 = CFG.cities.guangzhou.years['2025'].h1.social_base;
assert(gz25h1.medical && gz25h1.medical[0] === 6236 && gz25h1.medical[1] === 31179, 'GZ 2025 medical [6236,31179]');
assert(gz25h1.pension[0] === 5500 && gz25h1.pension[1] === 27501, 'GZ 2025 h1 pension [5500,27501]');
// Medical stays identical across halves of the same calendar year (both 2025 and 2026)
for (const y of ['2025', '2026']) {
  const sb = CFG.cities.guangzhou.years[y];
  assert(JSON.stringify(sb.h1.social_base.medical) === JSON.stringify(sb.h2.social_base.medical),
    `GZ ${y} medical identical across halves (calendar year)`);
}

// Shenzhen medical calendar-year rule still holds after the Guangzhou change
for (const y of ['2023', '2024', '2025', '2026']) {
  const sz = CFG.cities.shenzhen.years[y];
  assert(JSON.stringify(sz.h1.social_base.medical) === JSON.stringify(sz.h2.social_base.medical),
    `SZ ${y} medical identical across halves (calendar year)`);
}

// =====================================================================
// Test 9: verified_on must be the real announcement date, and calendar-year
// provinces must not lag H1 by one period (Zhejiang finding)
// =====================================================================
console.log('\n=== Announcement dates and calendar-year halves ===');

const ANNOUNCED = {
  shanghai:  { '2023': '2023-06-28', '2024': '2024-07-31' },
  beijing:   { '2023': '2023-07-25', '2024': '2024-07-31' },
  guangzhou: { '2023': '2023-06-29', '2024': '2024-12-15', '2025': '2025-10-24' },
  shenzhen:  { '2023': '2023-06-29', '2024': '2024-12-15', '2025': '2025-10-24' },
  hangzhou:  { '2023': '2023-12-13', '2024': '2024-10-11', '2025': '2025-09-17' },
  nanjing:   { '2023': '2023-01-09', '2024': '2024-09-30' },
  hefei:     { '2023': '2023-08-17', '2024': '2024-08-21', '2025': '2025-09-19' },
  wuhu:      { '2023': '2023-08-17', '2024': '2024-08-21', '2025': '2025-09-19' },
};
for (const [code, years] of Object.entries(ANNOUNCED)) {
  for (const [year, date] of Object.entries(years)) {
    const row = CFG.cities[code].years[year];
    assert(!!row, `${code} has year ${year}`);
    assert(row.verified_on === date, `${code} ${year} verified_on = ${date} (announcement date)`);
    assert(row.verified_on !== '2026-10-04', `${code} ${year} verified_on is not the bare alignment date`);
  }
}

// Zhejiang / Jiangsu / Anhui set the province-wide base for the whole CALENDAR year, so the
// social-insurance bounds must be identical in H1 and H2 (income-calc lagged Hangzhou H1 by one year).
for (const code of ['hangzhou', 'nanjing', 'hefei', 'wuhu']) {
  for (const year of ['2023', '2024', '2025', '2026']) {
    const y = CFG.cities[code].years[year];
    assert(JSON.stringify(y.h1.social_base) === JSON.stringify(y.h2.social_base),
      `${code} ${year} social bounds equal in both halves (calendar-year province)`);
  }
}
// Hangzhou concrete values
assert(JSON.stringify(CFG.cities.hangzhou.years['2023'].h1.social_base) === '[4462,24060]', 'HZ 2023 h1 social [4462,24060]');
assert(JSON.stringify(CFG.cities.hangzhou.years['2024'].h1.social_base) === '[4812,24930]', 'HZ 2024 h1 social [4812,24930]');
assert(JSON.stringify(CFG.cities.hangzhou.years['2025'].h1.social_base) === '[4986,25299]', 'HZ 2025 h1 social [4986,25299]');
// Housing fund stays on the July year for these provinces, so H1 legitimately keeps the previous year
assert(CFG.cities.hangzhou.years['2025'].h1.housing_base[1] === 39530, 'HZ 2025 h1 housing stays on the 2024 fund year');
assert(CFG.cities.hangzhou.years['2025'].h2.housing_base[1] === 40694, 'HZ 2025 h2 housing upper 40694');

// Guangdong keeps the July social-insurance year, so H1 and H2 legitimately differ there
// (Guangzhou 2023/2024 still use the shared array form; 2025+ use the per-insurance object)
assert(JSON.stringify(CFG.cities.guangzhou.years['2023'].h1.social_base)
  !== JSON.stringify(CFG.cities.guangzhou.years['2023'].h2.social_base),
  'GZ 2023 bounds differ across halves (Guangdong July year)');
assert(JSON.stringify(CFG.cities.guangzhou.years['2024'].h1.social_base)
  !== JSON.stringify(CFG.cities.guangzhou.years['2024'].h2.social_base),
  'GZ 2024 bounds differ across halves (Guangdong July year)');

// =====================================================================
// Test 10: remaining 2025 announcement dates (v3.4 verification)
// =====================================================================
console.log('\n=== 2025 announcement dates ===');

// 上海：市人社局 2025-09-18 发布「本市调整 2025 年度社保缴费基数上下限」（上限 37302、下限 7460）
assert(CFG.cities.shanghai.years['2025'].verified_on === '2025-09-18', 'SH 2025 verified_on = 2025-09-18');
assert(JSON.stringify(CFG.cities.shanghai.years['2025'].h2.social_base) === '[7460,37302]', 'SH 2025 h2 social [7460,37302]');
// 北京：关于 2025 年度各项社会保险缴费工资基数上下限的通告（rsj.beijing.gov.cn 2025-09-18）
assert(CFG.cities.beijing.years['2025'].verified_on === '2025-09-18', 'BJ 2025 verified_on = 2025-09-18');
assert(JSON.stringify(CFG.cities.beijing.years['2025'].h2.social_base) === '[7162,35811]', 'BJ 2025 h2 social [7162,35811]');
// 江苏：苏人社发〔2025〕33号（2025-09-18，执行 2025 全年 [4952,24762]）
assert(CFG.cities.nanjing.years['2025'].verified_on === '2025-09-18', 'NJ 2025 verified_on = 2025-09-18');
for (const half of ['h1', 'h2']) {
  assert(JSON.stringify(CFG.cities.nanjing.years['2025'][half].social_base) === '[4952,24762]',
    `NJ 2025 ${half} social [4952,24762] (calendar year)`);
}
// No row may keep an alignment date any more
for (const [code, c] of Object.entries(CFG.cities)) {
  for (const [year, row] of Object.entries(c.years)) {
    assert(row.verified_on !== '2026-10-04', `${code} ${year} verified_on is a real announcement date`);
  }
}

// =====================================================================
// Test 11: user-declared contribution bases (v3.6 P0)
// Many employers declare the statutory lower bound instead of the real salary;
// computeYear() must then use that declared base (still clamped to the policy range).
// =====================================================================
console.log('\n=== Declared contribution bases ===');

const sessSH26 = createSession('shanghai', 2026, CFG);

// (a) No declared base keeps the historic behaviour: 30000 -> 5250 / tax 592.50 / net 24157.50
const plain = computeYear(sessSH26, 30000, [], 7, 0, CFG);
assertClose(plain[0].social_p_total, 5250, 0.005, 'SH 2026 M1 default 五险一金 = 5250');
assertClose(plain[0].net, 24157.50, 0.005, 'SH 2026 M1 default 到手 = 24157.50');

// (b) Declared at the statutory lower bounds (2026 H1 social 7460 / housing 2690)
const lowBase = computeYear(sessSH26, 30000, [], 7, 0, CFG, { social: [7460, 7546], housing: [2690, 2740] });
assertClose(lowBase[0].sb_p, 7460, 0.005, 'SH 2026 M1 declared social base = 7460');
assertClose(lowBase[0].housing_base, 2690, 0.005, 'SH 2026 M1 declared housing base = 2690');
// 596.80 + 149.20 + 37.30 + round(2690*7%)=188
assertClose(lowBase[0].social_p_total, 971.30, 0.005, 'SH 2026 M1 五险一金 at lower bounds = 971.30');
assertClose(lowBase[0].month_tax, 720.86, 0.01, 'SH 2026 M1 个税 = 720.86 (taxable 24028.70)');
assertClose(lowBase[0].net, 28307.84, 0.01, 'SH 2026 M1 到手 = 28307.84');
// The employer side must follow the same declared base (pension_org 16%)
assertClose(lowBase[0].pension_o, 1193.60, 0.005, 'SH 2026 M1 单位养老 = 7460*16% = 1193.60');

// (c) H2 switches to the 2026 H2 bounds once the declared base crosses them
assertClose(lowBase[6].sb_p, 7546, 0.005, 'SH 2026 M7 declared social base = 7546 (H2)');
assertClose(lowBase[6].housing_base, 2740, 0.005, 'SH 2026 M7 declared housing base = 2740 (H2)');

// (d) A declared base above the upper bound is still clamped (never exceeds policy max)
const highBase = computeYear(sessSH26, 30000, [], 7, 0, CFG, { social: [99999, 99999], housing: [50000, 50000] });
assertClose(highBase[0].sb_p, 37302, 0.005, 'SH 2026 M1 declared 99999 clamped to 37302');
assertClose(highBase[0].housing_base, 37302, 0.005, 'SH 2026 M1 declared housing 50000 clamped to 37302');
assertClose(highBase[0].social_p_total, 6527.71, 0.005, 'SH 2026 M1 五险一金 at upper cap = 6527.71');
assertClose(highBase[0].net, 22918.13, 0.01, 'SH 2026 M1 到手 at upper cap = 22918.13');

// (e) Only one of the two bases may be declared; the other follows the salary
const partial = computeYear(sessSH26, 30000, [], 7, 0, CFG, { housing: [2690, 2740] });
assertClose(partial[0].sb_p, 30000, 0.005, 'SH 2026 M1 social base follows salary when undeclared');
assertClose(partial[0].housing_base, 2690, 0.005, 'SH 2026 M1 housing base uses declared value');
// 3150 + 188 = 3338; taxable 30000-5000-3338 = 21662 -> 3% = 649.86; net = 30000-3338-649.86
assertClose(partial[0].social_p_total, 3338, 0.005, 'SH 2026 M1 五险一金 = 3338 (mixed)');
assertClose(partial[0].net, 26012.14, 0.01, 'SH 2026 M1 到手 = 26012.14 (mixed)');

// (f) Zero / empty entries mean "follow salary" so the UI can leave fields blank
const zeros = computeYear(sessSH26, 30000, [], 7, 0, CFG, { social: [0, 0], housing: [0, 0] });
assertClose(zeros[0].social_p_total, 5250, 0.005, 'SH 2026 M1 blank declared base behaves as default');
assertClose(zeros[6].social_p_total, 5250, 0.005, 'SH 2026 M7 blank declared base behaves as default');

// (g) The gross-for-net inverse must honour the same declared base
const invLow = inverseGrossFromNet(sessSH26, 25000, [], 7, 0, CFG, { social: [7460, 7546], housing: [2690, 2740] });
assertClose(invLow.net_12m, 25000 * 12, 12, 'inverse with declared base hits the 12-month target net');
assertClose(invLow.months[0].sb_p, 7460, 0.005, 'inverse keeps the declared base in its solution');
const invPlain = inverseGrossFromNet(sessSH26, 25000, [], 7, 0, CFG);
// Declaring the lower bound cuts the personal contribution, so cash net rises and the
// gross needed to hit the same net target drops (this is exactly the trap the tool must show)
assert(invLow.gross < invPlain.gross, 'declared lower base yields a higher net, so a lower gross suffices');

// =====================================================================
// Test 12: the engine inlined in index.html must not drift from compute.js
// (index.html is the shipped artifact; compute.js is the tested source)
// =====================================================================
console.log('\n=== Inlined engine drift guard ===');

const htmlPath = join(__dirname, 'index.html');
const html = readFileSync(htmlPath, 'utf-8');
const enginePath = join(__dirname, 'compute.js');
const engineSource = readFileSync(enginePath, 'utf-8').replace(/\r\n/g, '\n');
const OPEN_TAG = '<script id="compute-engine">';
const CLOSE_TAG = '</script>';

assert(html.includes(OPEN_TAG), 'index.html carries the <script id="compute-engine"> block');
const openAt = html.indexOf(OPEN_TAG);
const closeAt = html.indexOf(CLOSE_TAG, openAt + OPEN_TAG.length);
const inlinedEngine = html.slice(openAt + OPEN_TAG.length, closeAt).trim();
const expectedEngine = engineSource.split('\n')
  .filter((line) => !line.startsWith('import '))
  .map((line) => (line.startsWith('export ') ? line.slice('export '.length) : line))
  .join('\n').trim();
assert(inlinedEngine === expectedEngine,
  'index.html inlined engine is byte-identical to compute.js (run: node web/inline-compute.mjs)');
// The shipped artifact must stay newline-stable: web/inline-*.mjs normalise to LF, otherwise a
// build on a core.autocrlf machine leaves a mixed-ending index.html that git flags as modified
// even when nothing changed (which is exactly how the "stale embedded copy" class hides).
assert(!html.includes('\r'), 'index.html carries no CRLF (byte-stable shipped artifact)');
assert(inlinedEngine.includes('function declaredBase('), 'declaredBase() reached the inlined engine');
assert(!/cdn\.jsdelivr|unpkg\/sheetjs|xlsx\.full\.min\.js/i.test(html),
  'index.html still free of spreadsheet CDN dependencies');

// The declared-base inputs must accept statutory bounds such as 7460 / 2690 (a coarse
// step="100" makes those values natively :invalid in the browser).
const declaredInputs = html.match(/v-model\.number="params\.declared(?:Social|Housing)\d"[^>]*/g) || [];
assert(declaredInputs.length === 4, 'index.html exposes four declared-base inputs');
assert(declaredInputs.every((tag) => /step="1"/.test(tag)),
  'declared-base inputs use step="1" so statutory bounds stay valid');

// The monthly-salary UI must stay wired to the engine (guards the feature end to end).
assert(/v-model="params\.useMonthly"/.test(html), 'the UI exposes the 各月工资不同 toggle');
assert(/v-for="i in 12"/.test(html), 'the UI renders twelve monthly salary inputs');
assert(/computeYear\(session\.value,[\s\S]{0,220}?salaryList\.value\)/.test(html),
  'the Web UI feeds the monthly salary list into computeYear');

// =====================================================================
// Test 13: fixed medical top-up per month (Beijing 大额医疗互助 3 元/月)
// Beijing charges the employee 2% of the base PLUS 3 CNY per month; every other
// supported city has no personal fixed amount.
// =====================================================================
console.log('\n=== Fixed medical top-up (medical_fixed) ===');

assert(CFG.cities.beijing.social_rate.medical_fixed === 3, 'BJ config medical_fixed = 3');
for (const code of ['shanghai', 'guangzhou', 'hangzhou', 'shenzhen', 'nanjing', 'hefei', 'wuhu']) {
  assert((CFG.cities[code].social_rate.medical_fixed || 0) === 0, `${code} has no personal fixed amount`);
}

const sessBJ26f = createSession('beijing', 2026, CFG);
assert(sessBJ26f.medical_fixed === 3, 'session exposes medical_fixed = 3');
// Beijing 2026 H1 base 7460..36348? bounds matter only for the clamp; 30000 sits inside.
const bjRows = computeYear(sessBJ26f, 30000, [], 12, 0, CFG);
// pension 30000*8% = 2400; medical 30000*2% + 3 = 603; unemploy 30000*0.5% = 150; fund 30000*12% = 3600
assertClose(bjRows[0].medical_p, 603, 0.005, 'BJ M1 医疗 = 600 + 3 = 603');
assertClose(bjRows[0].social_p_total, 6753, 0.005, 'BJ M1 五险一金 = 6753（含 3 元定额）');
// taxable M1 = 30000 - 5000 - 6753 = 18247 -> 3% = 547.41; net = 30000 - 6753 - 547.41 = 22699.59
assertClose(bjRows[0].month_tax, 547.41, 0.01, 'BJ M1 个税 = 547.41');
assertClose(bjRows[0].net, 22699.59, 0.01, 'BJ M1 到手 = 22699.59');
// The fixed amount recurs every month, so M7 must carry it too.
assertClose(bjRows[6].medical_p, 603, 0.005, 'BJ M7 医疗 = 603 (fixed amount is monthly)');

// Shanghai must be untouched by the new field.
assert(sessSH26.medical_fixed === 0, 'SH session medical_fixed = 0');
assertClose(computeYear(sessSH26, 30000, [], 7, 0, CFG)[0].medical_p, 600, 0.005, 'SH M1 医疗 = 600 (no top-up)');

// =====================================================================
// Test 14: per-month gross salaries (the last income-calc feature gap)
// Shanghai 2026: H1 social [7460,37302] housing [2690,37302]; H2 [7546,37731] / [2740,37731].
// Employee rates 8% + 2% + 0.5% = 10.5%, housing 7%.
// =====================================================================
console.log('\n=== Per-month salary list ===');

const monthly = [20000, 20000, 20000, 20000, 20000, 60000, 20000, 20000, 20000, 20000, 20000, 20000];
const rowsM = computeYear(sessSH26, 20000, [], 7, 0, CFG, null, monthly);

// Hand-computed cumulative withholding:
// M1-M3: taxable 11500/month -> 3% -> 345 each, net 16155
assertClose(rowsM[0].net, 16155, 0.01, 'monthly M1 到手 = 16155');
// M4 pushes cumulative taxable to 46000 -> 10% bracket: 2080 - 1035 = 1045
assertClose(rowsM[3].month_tax, 1045, 0.01, 'monthly M4 个税 = 1045（跨入 10% 档）');
assertClose(rowsM[3].net, 15455, 0.01, 'monthly M4 到手 = 15455');
// M6 pays 60000 but the base caps at 37302: social 3916.71 + fund round(2611.14)=2611 = 6527.71
assertClose(rowsM[5].salary, 60000, 0.005, 'monthly M6 gross = 60000');
assertClose(rowsM[5].sb_p, 37302, 0.005, 'monthly M6 养老基数封顶 = 37302');
assertClose(rowsM[5].medical_p, 746.04, 0.005, 'monthly M6 医疗 = 37302*2% = 746.04');
assertClose(rowsM[5].social_p_total, 6527.71, 0.005, 'monthly M6 五险一金 = 6527.71');
assertClose(rowsM[5].month_tax, 4847.23, 0.01, 'monthly M6 个税 = 4847.23');
assertClose(rowsM[5].net, 48625.06, 0.01, 'monthly M6 到手 = 48625.06');
// M7 is in H2 (bounds rise) and still earns 20000 -> base unchanged, taxable +11500
assertClose(rowsM[6].sb_p, 20000, 0.005, 'monthly M7 base = 20000 under H2 bounds');
assertClose(rowsM[6].net, 15350, 0.01, 'monthly M7 到手 = 15350');

// A flat list must reproduce the single-salary behaviour exactly.
const rowsFlat = computeYear(sessSH26, 20000, [], 7, 0, CFG, null, new Array(12).fill(20000));
const rowsNone = computeYear(sessSH26, 20000, [], 7, 0, CFG);
assert(rowsFlat.every((r, i) => r.net === rowsNone[i].net),
  'a flat salary list is equivalent to omitting the list');

// The list and a declared base compose: declared wins for the base, the list for the gross.
const rowsBoth = computeYear(sessSH26, 20000, [], 7, 0, CFG,
  { social: [10000, 10000], housing: [10000, 10000] }, monthly);
assertClose(rowsBoth[5].salary, 60000, 0.005, 'compose: M6 gross still comes from the list');
assertClose(rowsBoth[5].sb_p, 10000, 0.005, 'compose: M6 base comes from the declared value');

// =====================================================================
// Summary
// =====================================================================
console.log('\n============================================');
if (failures > 0) {
  console.log(`  ${failures} ASSERTION(S) FAILED`);
  process.exit(1);
} else {
  console.log('  ALL TESTS PASSED');
  process.exit(0);
}
