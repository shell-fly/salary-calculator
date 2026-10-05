/**
 * xlsx-report.js — the four-sheet salary report shared by the Web UI.
 *
 * Part of 工资计算器（中国）/ china-salary-calculator.
 *
 * This is the workbook-level twin of `build_workbook()` in src/salary_calculator.py: same sheets,
 * same row order, same labels, same style indices. `web/xlsx-sample.mjs --report` rebuilds the
 * Shanghai 2023 case with the JS engine and `src/test_xlsx_writer.py` compares those bytes with
 * what the Python CLI produces, so "the CLI Excel" and "the Web Excel" are provably the same file
 * for the same inputs — with no third-party spreadsheet library anywhere.
 *
 * Sheet list (one more than income-calc, which has no annual-bonus feature at all):
 *   年度汇总 / 逐月明细 / 政策参数 / 年终奖对比
 */
import { XlsxBook, money, percent } from './xlsx-writer.js';

/**
 * The 25 report columns, in CSV/XLSX order. This is the single web-side definition (the CSV export
 * in index.html reuses it) and it must stay identical to `CSV_COLUMNS` in src/salary_calculator.py;
 * the byte-equality test catches any drift because the header row lands inside the workbook.
 */
export const DETAIL_COLS = [
  ['月份', 'month_no'], ['半年度', 'half'], ['税前月薪', 'salary'],
  ['养老基数', 'sb_p'], ['医疗基数', 'sb_m'], ['失业基数', 'sb_u'], ['公积金基数', 'housing_base'],
  ['养老_个人', 'pension_p'], ['医疗_个人', 'medical_p'], ['失业_个人', 'unemploy_p'],
  ['公积金_个人', 'housing_p'], ['补充公积金_个人', 'extra_p'], ['五险一金_个人合计', 'social_p_total'],
  ['养老_单位', 'pension_o'], ['医疗_单位', 'medical_o'], ['失业_单位', 'unemploy_o'],
  ['工伤_单位', 'injury_o'], ['公积金_单位', 'housing_o'], ['补充公积金_单位', 'extra_o'],
  ['五险一金_单位合计', 'social_o_total'],
  ['专项附加扣除_当月', 'special_monthly'],
  ['累计应纳税所得额', 'cum_taxable'], ['累计个税', 'cum_tax'],
  ['当月个税', 'month_tax'], ['实发到手', 'net'],
];

const pct = (value) => percent(value);

/**
 * @param {Object} ctx computed inputs; every field comes from the same engine the page shows.
 * @param {Array<Object>} ctx.months 12 monthly records from computeYear()
 * @param {Array<Array<string>>} ctx.detailCols [display, key] pairs, identical to CSV_COLS
 * @param {Array<Array<number>>} ctx.bounds [H1 bounds, H2 bounds], six social-insurance numbers each
 * @param {Array<Array<number>>} ctx.housingBounds [H1, H2] housing-fund bounds
 * @param {Object} ctx.rates employee/employer rates as fractions
 */
export function buildReport(ctx) {
  const { months, detailCols, cityName, year, verifiedOn } = ctx;
  const sum = (key) => months.reduce((acc, m) => acc + (m[key] || 0), 0);
  const annualGross = sum('salary');
  const annualContrib = sum('social_p_total');
  const annualNet = sum('net');
  const annualSpecial = sum('special_monthly');
  const annualOrg = sum('social_o_total');
  const withheld = months[months.length - 1].cum_tax;

  // 年度汇总（与 CLI 的 estimate_annual_settlement 同口径）
  const taxFreeYear = ctx.taxFreeMonthly * 12;
  const annualTaxable = Math.max(0, annualGross - taxFreeYear - annualContrib - annualSpecial
    - Math.max(0, ctx.annualMedical || 0));
  const settlementTax = ctx.cumulativeTax(annualTaxable);
  const refund = withheld - settlementTax;
  const title = `${cityName} ${year} 年度工资测算`;

  const summary = [
    [[title, 2], ['', 0]],
    [['指标', 1], ['金额（元）', 1]],
    [['全年税前工资', 5], [money(annualGross), 3]],
    [['五险一金合计（个人）', 5], [money(annualContrib), 3]],
    [['专项附加扣除合计', 5], [money(annualSpecial), 3]],
    [['大病医疗扣除（限 8 万）', 5], [money(Math.max(0, ctx.annualMedical || 0)), 3]],
    [['已预扣个税合计', 5], [money(withheld), 3]],
    [['汇算应纳个税', 5], [money(settlementTax), 3]],
    [[refund >= 0 ? '预计退税' : '预计补税', 5], [money(Math.abs(refund)), 3]],
    [['全年应纳税所得额', 5], [money(annualTaxable), 3]],
    [['全年实发到手', 6], [money(annualNet), 6]],
    [['月均实发到手', 5], [money(annualNet / 12), 3]],
    [['五险一金合计（单位）', 5], [money(annualOrg), 3]],
    [['单位全年用工成本', 5], [money(annualGross + annualOrg), 3]],
    [['实际税负率', 5], [annualGross ? pct(settlementTax / annualGross) : pct(0), 4]],
  ];

  const book = new XlsxBook();
  book.addSheet('年度汇总', {
    rows: summary, widths: [26, 20], merges: ['A1:B1'],
    freeze: 'A3', titleRow: true, headerRow: 2,
  });

  // 逐月明细（列与 CSV 导出完全一致）
  const detail = [detailCols.map(([name]) => [name, 1])];
  for (const record of months) {
    const row = { ...record, half: record.month_no <= 6 ? 'H1' : 'H2' };
    detail.push(detailCols.map(([, key]) =>
      (key === 'month_no' || key === 'half')
        ? [String(row[key]), 0]
        : [money(Number(row[key])), 3]));
  }
  book.addSheet('逐月明细', {
    rows: detail, widths: [8, 8, 12, ...Array(22).fill(13)],
    freeze: 'A2', autofilter: true, headerRow: 1,
  });

  // 政策参数
  const [h1, h2] = ctx.bounds;
  const [hp1, hp2] = ctx.housingBounds;
  const money6 = (vals) => vals.map((v) => [money(v), 3]);
  const r = ctx.rates;
  const pad = (row) => row.concat(Array(9 - row.length).fill(['', 0]));
  // Beijing adds a flat 3 CNY/month on top of the 2% employee medical rate; show both.
  const medPersonal = pct(r.medical_emp) + (r.medical_fixed ? ` + ${r.medical_fixed} 元/月` : '');
  const policy = [
    pad([[`${cityName} ${year} 年度参数（核实：${verifiedOn}）`, 2]]),
    [['期间', 1], ['养老下限', 1], ['养老上限', 1], ['医疗下限', 1], ['医疗上限', 1],
      ['失业下限', 1], ['失业上限', 1], ['公积金下限', 1], ['公积金上限', 1]],
    [['1–6 月', 5], ...money6(h1), [money(hp1[0]), 3], [money(hp1[1]), 3]],
    [['7–12 月', 5], ...money6(h2), [money(hp2[0]), 3], [money(hp2[1]), 3]],
    Array(9).fill(['', 0]),
    pad([['缴费比例', 1], ['个人', 1], ['单位', 1]]),
    pad([['养老保险', 5], [pct(r.pension_emp), 4], [pct(r.pension_org), 4]]),
    pad([['医疗保险', 5], [medPersonal, 4], [pct(r.medical_org), 4]]),
    pad([['失业保险', 5], [pct(r.unemploy_emp), 4], [pct(r.unemploy_org), 4]]),
    pad([['工伤保险', 5], ['—', 5], [pct(r.injury_org), 4]]),
    pad([['住房公积金（本次选用）', 5], [pct(ctx.housingPct / 100), 4], [pct(ctx.housingPct / 100), 4]]),
    pad([['补充公积金（本次选用）', 5], [pct(ctx.extraPct / 100), 4], [pct(ctx.extraPct / 100), 4]]),
    pad([['城市允许区间', 5], [`${ctx.housingRange[0]}%–${ctx.housingRange[1]}%`, 5],
      [`补充 ${ctx.supplementRange[0]}%–${ctx.supplementRange[1]}%`, 5]]),
  ];
  book.addSheet('政策参数', {
    rows: policy, widths: [22, 14, 14, 14, 14, 14, 14, 14, 14],
    merges: ['A1:I1'], freeze: 'A3', titleRow: true, headerRow: 2,
  });

  // 年终奖双方案对比
  const bonus = ctx.bonus || 0;
  let bonusRows;
  if (bonus > 0) {
    const m0 = months[0];
    // ctx.compareBonus returns {totalA, totalB, bonusTax}; the CLI wrapper returns the same keys.
    const cmp = ctx.compareBonus(m0.salary, m0.social_p_total, m0.special_monthly, bonus);
    const totalA = cmp.totalA;
    const totalB = cmp.totalB;
    const bonusTax = cmp.bonusTax;
    bonusRows = [
      [['年终奖双方案对比', 2], ['', 0]],
      [['项目', 1], ['金额（元）', 1]],
      [['年终奖金额', 5], [money(bonus), 3]],
      [['方案A·单独计税（工资+奖金合计纳税）', 5], [money(totalA), 3]],
      [['  其中奖金部分个税', 5], [money(bonusTax), 3]],
      [['方案B·并入综合所得（合计纳税）', 5], [money(totalB), 3]],
      [['推荐方案', 6],
        [`方案${totalA <= totalB ? 'A（单独计税）' : 'B（并入综合所得）'}`, 6]],
      [['节税金额', 6], [money(Math.abs(totalB - totalA)), 6]],
    ];
  } else {
    bonusRows = [
      [['年终奖双方案对比', 2], ['', 0]],
      [['项目', 1], ['说明', 1]],
      [['本次测算', 5], ['未填写年终奖，无方案对比；输入年终奖后重新导出即可生成', 5]],
    ];
  }
  book.addSheet('年终奖对比', {
    rows: bonusRows, widths: [34, 26], merges: ['A1:B1'],
    freeze: 'A3', titleRow: true, headerRow: 2,
  });

  return book;
}
