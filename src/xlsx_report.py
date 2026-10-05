# -*- coding: utf-8 -*-
"""
xlsx_report.py — the four-sheet salary report, Python twin of web/xlsx-report.js.

Part of 工资计算器（中国）/ china-salary-calculator.

Both implementations build the workbook from a plain `ctx` mapping so that the CLI
(`build_workbook()` in salary_calculator.py) and the single-file Web UI produce the *same
bytes* for the same inputs. `src/test_xlsx_writer.py` proves it by comparing the CLI workbook
against `node web/xlsx-sample.mjs --report`.

Sheets: 年度汇总 / 逐月明细 / 政策参数 / 年终奖对比 — one more than income-calc, which has no
annual-bonus feature at all.

`ctx` keys:
  months (list of compute_month dicts), detail_cols ([(display, key), ...]),
  city_name, year, verified_on, bounds ([H1, H2] six numbers each),
  housing_bounds ([H1, H2] pairs), rates (dict of fractions), housing_pct, extra_pct,
  housing_range, supplement_range, tax_free_monthly, annual_medical, bonus,
  cumulative_tax (callable), compare_bonus (callable -> {totalA, totalB, bonusTax})
"""
from xlsx_writer import XlsxBook, money, percent


def build_report(ctx):
    """Assemble the styled four-sheet workbook described by `ctx`."""
    months = ctx["months"]
    detail_cols = ctx["detail_cols"]

    def total(key):
        return sum(m.get(key, 0) or 0 for m in months)

    annual_gross = total("salary")
    annual_contrib = total("social_p_total")
    annual_net = total("net")
    annual_special = total("special_monthly")
    annual_org = total("social_o_total")
    withheld = months[-1]["cum_tax"]

    # 年度汇总（与 estimate_annual_settlement 同口径）
    tax_free_year = ctx["tax_free_monthly"] * 12
    annual_medical = max(0.0, ctx.get("annual_medical", 0.0))
    annual_taxable = max(0.0, annual_gross - tax_free_year - annual_contrib
                         - annual_special - annual_medical)
    settlement_tax = ctx["cumulative_tax"](annual_taxable)
    refund = withheld - settlement_tax
    title = f"{ctx['city_name']} {ctx['year']} 年度工资测算"

    summary = [
        [(title, 2), ("", 0)],
        [("指标", 1), ("金额（元）", 1)],
        [("全年税前工资", 5), (money(annual_gross), 3)],
        [("五险一金合计（个人）", 5), (money(annual_contrib), 3)],
        [("专项附加扣除合计", 5), (money(annual_special), 3)],
        [("大病医疗扣除（限 8 万）", 5), (money(annual_medical), 3)],
        [("已预扣个税合计", 5), (money(withheld), 3)],
        [("汇算应纳个税", 5), (money(settlement_tax), 3)],
        [("预计退税" if refund >= 0 else "预计补税", 5), (money(abs(refund)), 3)],
        [("全年应纳税所得额", 5), (money(annual_taxable), 3)],
        [("全年实发到手", 6), (money(annual_net), 6)],
        [("月均实发到手", 5), (money(annual_net / 12), 3)],
        [("五险一金合计（单位）", 5), (money(annual_org), 3)],
        [("单位全年用工成本", 5), (money(annual_gross + annual_org), 3)],
        [("实际税负率", 5),
         (percent(settlement_tax / annual_gross) if annual_gross else percent(0), 4)],
    ]

    book = XlsxBook()
    book.add_sheet("年度汇总", rows=summary, widths=[26, 20], merges=["A1:B1"],
                   freeze="A3", title_row=True, header_row=2)

    # 逐月明细（列定义与 CSV 导出完全一致）
    detail = [[(name, 1) for name, _ in detail_cols]]
    for record in months:
        row = dict(record)
        row["half"] = "H1" if record["month_no"] <= 6 else "H2"
        cells = []
        for display, key in detail_cols:
            value = row.get(key, "")
            if key in ("month_no", "half"):
                cells.append((str(value), 0))
            else:
                cells.append((money(float(value)), 3))
        detail.append(cells)
    book.add_sheet("逐月明细", rows=detail, widths=[8, 8, 12] + [13] * 22,
                   freeze="A2", autofilter=True, header_row=1)

    # 政策参数
    h1, h2 = ctx["bounds"]
    hp1, hp2 = ctx["housing_bounds"]
    rates = ctx["rates"]
    housing_pct = ctx["housing_pct"]
    extra_pct = ctx["extra_pct"]

    def pad(row):
        return row + [("", 0)] * (9 - len(row))

    blank9 = [("", 0)] * 9
    # Beijing adds a flat 3 CNY/month on top of the 2% employee medical rate; show both.
    med_personal = percent(rates["medical_emp"])
    if rates.get("medical_fixed", 0):
        med_personal += f" + {rates['medical_fixed']:g} 元/月"
    policy = [
        pad([(f"{ctx['city_name']} {ctx['year']} 年度参数（核实：{ctx['verified_on']}）", 2)]),
        [("期间", 1), ("养老下限", 1), ("养老上限", 1), ("医疗下限", 1), ("医疗上限", 1),
         ("失业下限", 1), ("失业上限", 1), ("公积金下限", 1), ("公积金上限", 1)],
        [("1–6 月", 5)] + [(money(v), 3) for v in h1] + [(money(hp1[0]), 3), (money(hp1[1]), 3)],
        [("7–12 月", 5)] + [(money(v), 3) for v in h2] + [(money(hp2[0]), 3), (money(hp2[1]), 3)],
        blank9,
        pad([("缴费比例", 1), ("个人", 1), ("单位", 1)]),
        pad([("养老保险", 5), (percent(rates["pension_emp"]), 4), (percent(rates["pension_org"]), 4)]),
        pad([("医疗保险", 5), (med_personal, 4), (percent(rates["medical_org"]), 4)]),
        pad([("失业保险", 5), (percent(rates["unemploy_emp"]), 4), (percent(rates["unemploy_org"]), 4)]),
        pad([("工伤保险", 5), ("—", 5), (percent(rates["injury_org"]), 4)]),
        pad([("住房公积金（本次选用）", 5), (percent(housing_pct / 100), 4), (percent(housing_pct / 100), 4)]),
        pad([("补充公积金（本次选用）", 5), (percent(extra_pct / 100), 4), (percent(extra_pct / 100), 4)]),
        pad([("城市允许区间", 5),
             (f"{ctx['housing_range'][0]}%–{ctx['housing_range'][1]}%", 5),
             (f"补充 {ctx['supplement_range'][0]}%–{ctx['supplement_range'][1]}%", 5)]),
    ]
    book.add_sheet("政策参数", rows=policy, widths=[22, 14, 14, 14, 14, 14, 14, 14, 14],
                   merges=["A1:I1"], freeze="A3", title_row=True, header_row=2)

    # 年终奖双方案对比
    bonus = ctx.get("bonus", 0) or 0
    if bonus > 0:
        m0 = months[0]
        cmp_result = ctx["compare_bonus"](m0["salary"], m0["social_p_total"],
                                          m0["special_monthly"], bonus)
        total_a, total_b, bonus_tax = cmp_result["totalA"], cmp_result["totalB"], cmp_result["bonusTax"]
        bonus_rows = [
            [("年终奖双方案对比", 2), ("", 0)],
            [("项目", 1), ("金额（元）", 1)],
            [("年终奖金额", 5), (money(bonus), 3)],
            [("方案A·单独计税（工资+奖金合计纳税）", 5), (money(total_a), 3)],
            [("  其中奖金部分个税", 5), (money(bonus_tax), 3)],
            [("方案B·并入综合所得（合计纳税）", 5), (money(total_b), 3)],
            [("推荐方案", 6),
             (f"方案{'A（单独计税）' if total_a <= total_b else 'B（并入综合所得）'}", 6)],
            [("节税金额", 6), (money(abs(total_b - total_a)), 6)],
        ]
    else:
        bonus_rows = [
            [("年终奖双方案对比", 2), ("", 0)],
            [("项目", 1), ("说明", 1)],
            [("本次测算", 5), ("未填写年终奖，无方案对比；输入年终奖后重新导出即可生成", 5)],
        ]
    book.add_sheet("年终奖对比", rows=bonus_rows, widths=[34, 26], merges=["A1:B1"],
                   freeze="A3", title_row=True, header_row=2)
    return book
