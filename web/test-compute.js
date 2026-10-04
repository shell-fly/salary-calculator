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

// Spot checks for the other 7 cities on 2023/2024 H1 lower bounds.
assert(CFG.cities.beijing.years['2023'].h1.social_base[0] === 5869, 'BJ 2023 h1 lower 5869');
assert(CFG.cities.beijing.years['2024'].h2.social_base[1] === 35283, 'BJ 2024 h2 upper 35283');
assert(CFG.cities.guangzhou.years['2023'].h1.social_base[0] === 4588, 'GZ 2023 h1 lower 4588');
assert(CFG.cities.hangzhou.years['2023'].h1.social_base[1] === 22311, 'HZ 2023 h1 upper 22311');
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
assert(CFG.cities.hangzhou.years['2025'].h1.social_base[1] === 24930, 'HZ 2025 h1 social upper 24930');
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
