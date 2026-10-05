// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 bob3703
// Licensed under the Apache License, Version 2.0. See the LICENSE file for the full text.
/**
 * xlsx-sample.mjs — cross-engine probe for web/xlsx-writer.js.
 *
 * Run: node web/xlsx-sample.mjs > sample.xlsx
 *
 * It builds exactly the workbook defined in `sample_book()` inside
 * `src/test_xlsx_writer.py`. The contract test pipes both outputs and requires the bytes to
 * match, which is what proves the CLI (src/xlsx_writer.py) and the Web UI (this writer, inlined
 * into index.html) hand out the same styled report without any third-party library.
 */
import { pathToFileURL } from 'node:url';
import { readFileSync } from 'node:fs';
import { XlsxBook, money, percent } from './xlsx-writer.js';
import { buildReport, DETAIL_COLS } from './xlsx-report.js';
import { createSession, computeYear, compareBonus, calcCumulativeTax } from './compute.js';

export function sampleBook() {
  const book = new XlsxBook();
  book.addSheet('年度汇总', {
    widths: [24, 20],
    merges: ['A1:B1'],
    freeze: 'A3',
    rows: [
      [['上海 2025 年度工资测算', 2], ['', 0]],
      [['指标', 1], ['金额（元）', 1]],
      [['全年税前工资', 5], [money(240000), 3]],
      [['个人五险一金', 5], [money(42000), 3]],
      [['当月个税合计', 5], [money(9780), 3]],
      [['预计退税', 5], [money(0), 3]],
      [['全年实发到手', 6], [money(188220), 6]],
      [['实际税负率', 5], [percent(0.04075), 4]],
    ],
  });
  book.addSheet('逐月明细', {
    widths: [8, 8, 14, 14, 14],
    freeze: 'A2',
    autofilter: true,
    rows: [
      [['月份', 1], ['半年度', 1], ['税前月薪', 1], ['五险一金_个人合计', 1], ['实发到手', 1]],
      [['1', 0], ['H1', 0], [money(20000), 3], [money(3500), 3], [money(16155), 3]],
      [['7', 0], ['H2', 0], [money(20000), 3], [money(3500), 3], [money(15350), 3]],
    ],
  });
  return book;
}

/**
 * The real report for the same inputs the CLI test uses: 上海 2023, 月薪 20000, 公积金 7%,
 * 年终奖 100000, no serious-medical deduction. Both engines compute the numbers themselves; equal
 * bytes therefore also prove the engines agree on every figure that lands in the workbook.
 */
export function reportBytes() {
  const CFG = JSON.parse(readFileSync(new URL('../config.json', import.meta.url), 'utf-8'));
  const sess = createSession('shanghai', 2023, CFG);
  const months = computeYear(sess, 20000, [], 7, 0, CFG);
  const book = buildReport({
    months,
    detailCols: DETAIL_COLS,
    cityName: sess.city_name,
    year: sess.year,
    verifiedOn: sess._yearData.verified_on,
    bounds: [sess.socialBounds(1), sess.socialBounds(7)],
    housingBounds: [sess.housingBounds(1), sess.housingBounds(7)],
    rates: {
      pension_emp: sess.pension_emp, pension_org: sess.pension_org,
      medical_emp: sess.medical_emp, medical_org: sess.medical_org,
      medical_fixed: sess.medical_fixed,
      unemploy_emp: sess.unemploy_emp, unemploy_org: sess.unemploy_org,
      injury_org: sess.injury_org,
    },
    housingPct: 7,
    extraPct: 0,
    housingRange: [sess.housing_rate_min, sess.housing_rate_max],
    supplementRange: [sess.extra_min, sess.extra_max],
    taxFreeMonthly: sess.taxFreeMonthly,
    annualMedical: 0,
    bonus: 100000,
    cumulativeTax: (taxable) => calcCumulativeTax(taxable, sess.taxBrackets),
    compareBonus: (salary, socialP, specialM, bonusAmt) => {
      const r = compareBonus(salary, socialP, specialM, bonusAmt, CFG);
      return { totalA: r.totalA, totalB: r.totalB, bonusTax: r.bonusTaxA };
    },
  });
  return Buffer.from(book.toBytes());
}

// Only write bytes to stdout when executed directly (not when imported by a test).
if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  process.stdout.write(process.argv.includes('--report') ? reportBytes() : Buffer.from(sampleBook().toBytes()));
}
