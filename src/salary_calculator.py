# -*- coding: utf-8 -*-
"""
China Salary Calculator (Mainland China · 8 cities · multi-year · half-year periods)
====================================================================================
Features:
  1) Five insurances + housing fund (per-city base upper/lower bounds + rates,
     employee and employer shares; half-year period switching)
  2) Individual income tax (cumulative withholding, threshold 5000 CNY/month,
     with special deductions — employee five-insurance/housing fund and
     supplementary housing fund — plus special additional deductions with
     optional start/end month)
  3) Supplementary housing fund (optional, city-specific range, employee share
     is tax-deductible)
  4) Annual once-off bonus: auto-compare separate taxation vs. combined with
     comprehensive income, recommend the tax-saving plan; handles salary<5000
     gap-fill per MOF/SAT rules
  5) Monthly take-home pay and clear itemized output
  6) Annual settlement (汇算清缴) refund/tax-due estimation
  7) Inverse calculation: binary-search gross salary from target net take-home
  8) Export the 12-month detail plus a yearly summary, policy bounds and the
     bonus comparison to CSV or a styled .xlsx — both zero-dependency (the
     workbook is written by `xlsx_writer.py`, no openpyxl required)

Usage: double-click run.bat, or run `python salary_calculator.py`.
Parameters (cities, years, half-year bases, tax brackets, etc.) are loaded
from `config.json` in the parent directory of this script.

Disclaimer: for demonstration only. The authoritative figures are those
published by the tax and social-security authorities.
"""

import os
import sys
import json
import math
import csv
import datetime

# The xlsx writer/report modules live next to this script; make the import work from any cwd.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xlsx_report import build_report  # noqa: E402


# =====================================================================
# 一、Config loading
# =====================================================================

def _script_dir():
    return os.path.dirname(os.path.abspath(__file__))


def _config_path():
    # config.json sits at the project root (parent of src/)
    return os.path.normpath(os.path.join(_script_dir(), "..", "config.json"))


def _load_config():
    with open(_config_path(), "r", encoding="utf-8") as f:
        return json.load(f)


CFG = _load_config()
DEFAULT_CITY = CFG["default_city"]
DEFAULT_YEAR = int(CFG["default_year"])


def _to_bracket(row):
    upper, rate, quick = row
    return (float("inf") if upper is None else float(upper), float(rate), float(quick))


TAX_BRACKETS = [_to_bracket(r) for r in CFG["tax_brackets"]]
BONUS_BRACKETS = [_to_bracket(r) for r in CFG["bonus_brackets"]]
TAX_FREE_MONTHLY = float(CFG["tax_free_monthly"])
SD = CFG["special_deductions"]


# =====================================================================
# 二、Session: per-city / per-year / per-month parameter resolver
# =====================================================================

def _normalize_social(spec):
    """Return dict with keys pension/medical/unemployment, each a [lo, hi] pair."""
    if isinstance(spec, list) and len(spec) == 2:
        return {"pension": spec, "medical": spec, "unemployment": spec}
    if isinstance(spec, dict):
        return {k: list(v) for k, v in spec.items()}
    raise ValueError("Invalid social_base spec")


class Session:
    """Resolved parameter set for a (city, year) combination."""

    def __init__(self, city_code=None, year=None):
        city_code = city_code or DEFAULT_CITY
        year = int(year or DEFAULT_YEAR)
        if city_code not in CFG["cities"]:
            raise ValueError(f"Unsupported city: {city_code}")
        city = CFG["cities"][city_code]
        years_map = {int(k): v for k, v in city["years"].items()}
        if year not in years_map:
            avail = sorted(years_map.keys())
            raise ValueError(f"City {city['name']} has no data for year {year}. Available: {avail}")
        y = years_map[year]

        self.city_code = city_code
        self.city_name = city["name"]
        self.year = year
        self.rent_deduction = float(city["rent_deduction"])
        self.housing_rate_min = int(city["housing_rate"][0])
        self.housing_rate_max = int(city["housing_rate"][1])
        self.housing_rate_default = self.housing_rate_max
        supp = city.get("supplemental_housing_rate", [0, 0])
        self.extra_min = int(supp[0])
        self.extra_max = int(supp[1])

        sr = city["social_rate"]
        self.pension_emp = float(sr["pension_emp"]);  self.pension_org = float(sr["pension_org"])
        self.medical_emp = float(sr["medical_emp"]);  self.medical_org = float(sr["medical_org"])
        self.unemploy_emp = float(sr["unemploy_emp"]); self.unemploy_org = float(sr["unemploy_org"])
        self.injury_org = float(sr.get("injury_org", 0.0))
        # Fixed monthly amount on top of the percentage (Beijing: 3 CNY 大额医疗互助)
        self.medical_fixed = float(sr.get("medical_fixed", 0.0))

        self._year_data = y

    def period_for(self, month):
        """Return (half_key 'h1'/'h2', period_dict) for the given month (1..12)."""
        m = int(month)
        if m <= self._year_data["h1"]["months"][1]:
            return "h1", self._year_data["h1"]
        return "h2", self._year_data["h2"]

    def social_bounds(self, month):
        """Return (pension_lo, pension_hi, medical_lo, medical_hi, unemp_lo, unemp_hi) for month."""
        _, p = self.period_for(month)
        s = _normalize_social(p["social_base"])
        return (s["pension"][0], s["pension"][1],
                s["medical"][0], s["medical"][1],
                s["unemployment"][0], s["unemployment"][1])

    def housing_bounds(self, month):
        _, p = self.period_for(month)
        return float(p["housing_base"][0]), float(p["housing_base"][1])

    def is_provisional(self, month):
        _, p = self.period_for(month)
        return bool(p.get("provisional", False))

    def summary_line(self):
        return (f"{self.city_name} {self.year} 年度（数据核实日期："
                f"{self._year_data.get('verified_on', '未知')}）")

    @property
    def verified_on(self):
        """Announcement/verification date of this year row."""
        return self._year_data.get("verified_on", "未知")


# =====================================================================
# 三、Core computation
# =====================================================================

def round_yuan(v):
    """Round to the nearest yuan (half-up) for housing fund monthly amounts."""
    return math.floor(v + 0.5)


def clamp(v, lo, hi):
    return max(lo, min(v, hi))


def tax_by_table(taxable, table):
    if taxable <= 0:
        return 0.0
    for upper, rate, quick in table:
        if taxable <= upper:
            return taxable * rate - quick
    return 0.0


def calc_cumulative_tax(cum_taxable):
    return tax_by_table(cum_taxable, TAX_BRACKETS)


def bonus_single_tax(bonus, salary=5000.0):
    """
    Once-off bonus taxed separately:
      - If salary >= 5000: base = bonus
      - If salary <  5000: base = bonus - (5000 - salary)   (gap-fill)
    Then base/12 -> monthly bracket table. Tax = base * rate - quick.
    Policy: MOF & SAT Announcement No. 30 of 2023, extended to 2027-12-31.
    """
    if bonus <= 0:
        return 0.0
    base = bonus if salary >= TAX_FREE_MONTHLY else max(bonus - (TAX_FREE_MONTHLY - salary), 0.0)
    if base <= 0:
        return 0.0
    avg = base / 12.0
    for upper, rate, quick in BONUS_BRACKETS:
        if avg <= upper:
            return base * rate - quick
    return base * 0.45 - 181920


def monthly_special(month, items):
    """Sum of special additional deductions active in the given month.
    items: list of (key, amount_per_month, start_month, end_month)
    """
    total = 0.0
    for _, amt, s, e in items:
        if s <= month <= e:
            total += float(amt)
    return total


def compute_month(sess, month_no, salary, social_base_dict, housing_base,
                  special_items, housing_pct, extra_pct):
    """
    Compute month_no's detail under cumulative withholding.
    social_base_dict: {"pension": lo/hi-clamped, "medical": ..., "unemployment": ...}
    special_items: list of (key, amount, start_month, end_month)
    """
    sb_p = social_base_dict["pension"]
    sb_m = social_base_dict["medical"]
    sb_u = social_base_dict["unemployment"]

    # Five insurances (employee share)
    pension_p = sb_p * sess.pension_emp
    medical_p = sb_m * sess.medical_emp + sess.medical_fixed
    unemploy_p = sb_u * sess.unemploy_emp
    housing_p = round_yuan(housing_base * housing_pct / 100.0)
    extra_p = round_yuan(housing_base * extra_pct / 100.0) if extra_pct else 0.0
    social_p_total = pension_p + medical_p + unemploy_p + housing_p + extra_p

    # Five insurances (employer share)
    pension_o = sb_p * sess.pension_org
    medical_o = sb_m * sess.medical_org
    unemploy_o = sb_u * sess.unemploy_org
    injury_o = sb_p * sess.injury_org
    housing_o = round_yuan(housing_base * housing_pct / 100.0)
    extra_o = round_yuan(housing_base * extra_pct / 100.0) if extra_pct else 0.0
    social_o_total = pension_o + medical_o + unemploy_o + injury_o + housing_o + extra_o

    # Cumulative withholding IIT
    special_m = monthly_special(month_no, special_items)
    cum_income = salary * month_no
    cum_base = TAX_FREE_MONTHLY * month_no
    cum_social = social_p_total * month_no
    cum_special = special_m * month_no
    cum_taxable = cum_income - cum_base - cum_social - cum_special
    cum_tax = calc_cumulative_tax(cum_taxable)

    prev_cum_taxable = cum_taxable - salary + TAX_FREE_MONTHLY + social_p_total + special_m
    prev_cum_tax = calc_cumulative_tax(prev_cum_taxable)
    month_tax = max(0.0, cum_tax - prev_cum_tax)

    net = salary - social_p_total - month_tax

    rate, quick_d = 0.0, 0.0
    for upper, r, q in TAX_BRACKETS:
        if cum_taxable <= upper:
            rate, quick_d = r, q
            break

    return {
        "month_no": month_no, "salary": salary,
        "sb_p": sb_p, "sb_m": sb_m, "sb_u": sb_u, "housing_base": housing_base,
        "pension_p": pension_p, "medical_p": medical_p, "unemploy_p": unemploy_p,
        "housing_p": housing_p, "extra_p": extra_p, "social_p_total": social_p_total,
        "pension_o": pension_o, "medical_o": medical_o, "unemploy_o": unemploy_o,
        "injury_o": injury_o, "housing_o": housing_o, "extra_o": extra_o,
        "social_o_total": social_o_total,
        "cum_taxable": cum_taxable, "cum_tax": cum_tax, "month_tax": month_tax,
        "rate": rate, "quick": quick_d, "net": net,
        "special_monthly": special_m, "housing_pct": housing_pct, "extra_pct": extra_pct,
    }


def declared_base(declared, salary, month):
    """
    Resolve one declared contribution base for a month.
    `declared` is a [h1, h2] pair; an empty/None/0 entry means "follow the salary".
    """
    if not declared:
        return salary
    value = declared[0 if month <= 6 else 1]
    try:
        value = float(value)
    except (TypeError, ValueError):
        return salary
    return value if value > 0 else salary


def compute_year(sess, salary, special_items, housing_pct, extra_pct, declared=None):
    """
    Run 12 months using each month's own half-year bounds. Returns list[dict].

    declared (optional): {"social": [h1, h2], "housing": [h1, h2]} contribution bases as
    actually declared by the employer. Many companies declare the statutory lower bound
    instead of the real salary, so the base must be overridable; it is still clamped to
    the policy range of the selected city/year/half.
    """
    results = []
    social_declared = (declared or {}).get("social")
    housing_declared = (declared or {}).get("housing")
    for m in range(1, 13):
        plo, phi, mlo, mhi, ulo, uhi = sess.social_bounds(m)
        hlo, hhi = sess.housing_bounds(m)
        s_base = declared_base(social_declared, salary, m)
        h_base = declared_base(housing_declared, salary, m)
        sb = {
            "pension": clamp(s_base, plo, phi),
            "medical": clamp(s_base, mlo, mhi),
            "unemployment": clamp(s_base, ulo, uhi),
        }
        hb = clamp(h_base, hlo, hhi)
        results.append(compute_month(sess, m, salary, sb, hb,
                                     special_items, housing_pct, extra_pct))
    return results


def compare_bonus(salary, social_p_monthly, special_monthly, bonus):
    annual_income = salary * 12
    annual_base = TAX_FREE_MONTHLY * 12
    annual_social = social_p_monthly * 12
    annual_special = special_monthly * 12

    salary_tax_a = calc_cumulative_tax(annual_income - annual_base - annual_social - annual_special)
    bonus_tax_a = bonus_single_tax(bonus, salary)
    total_a = salary_tax_a + bonus_tax_a

    taxable_b = annual_income + bonus - annual_base - annual_social - annual_special
    total_b = tax_by_table(taxable_b, TAX_BRACKETS)

    return total_a, total_b, salary_tax_a, bonus_tax_a, taxable_b


def estimate_annual_settlement(months_12, annual_medical=0.0):
    """
    Annual settlement (汇算清缴) estimation.
    months_12: list of 12 compute_month dicts.
    Returns (annual_taxable, annual_settlement_tax, withheld_tax, estimated_refund).
    estimated_refund > 0 means tax refund; < 0 means additional tax due.
    """
    annual_gross = sum(m["salary"] for m in months_12)
    annual_contrib = sum(m["social_p_total"] for m in months_12)
    annual_special = sum(m["special_monthly"] for m in months_12)
    annual_taxable = max(0.0, annual_gross - TAX_FREE_MONTHLY * 12
                         - annual_contrib - annual_special - max(0.0, annual_medical))
    annual_settlement_tax = calc_cumulative_tax(annual_taxable)
    withheld_tax = months_12[-1]["cum_tax"]
    estimated_refund = withheld_tax - annual_settlement_tax
    return annual_taxable, annual_settlement_tax, withheld_tax, estimated_refund


def inverse_gross_from_net(sess, target_net, special_items, housing_pct, extra_pct,
                           declared=None, tol=0.01, max_iter=120):
    """
    Binary-search gross monthly salary such that 12-month net take-home
    (sum of 12 months' net) matches target_net * 12 within tol.
    Returns dict with gross, net_12m, tax_12m, contrib_12m.
    """
    lo, hi = 0.0, 10_000_000.0
    target_total = target_net * 12.0
    last = None
    for _ in range(max_iter):
        mid = (lo + hi) / 2.0
        months = compute_year(sess, mid, special_items, housing_pct, extra_pct, declared)
        net_total = sum(m["net"] for m in months)
        last = (mid, months, net_total)
        if abs(net_total - target_total) <= tol:
            break
        if net_total < target_total:
            lo = mid
        else:
            hi = mid
    mid, months, net_total = last
    tax_total = months[-1]["cum_tax"]
    contrib_total = sum(m["social_p_total"] for m in months)
    return {
        "gross": mid, "net_12m": net_total, "tax_12m": tax_total,
        "contrib_12m": contrib_total, "months": months,
    }


# =====================================================================
# 四、CLI helpers
# =====================================================================

def ask_float(prompt, default=None, lo=None, hi=None):
    while True:
        s = input(prompt).strip()
        if not s and default is not None:
            return default
        try:
            v = float(s)
        except ValueError:
            print("  输入无效，请输入数字。")
            continue
        if lo is not None and v < lo:
            print(f"  数值不能小于 {lo}。")
            continue
        if hi is not None and v > hi:
            print(f"  数值不能大于 {hi}。")
            continue
        return v


def ask_int(prompt, default=None, lo=None, hi=None):
    while True:
        s = input(prompt).strip()
        if not s and default is not None:
            return default
        try:
            v = int(s)
        except ValueError:
            print("  输入无效，请输入整数。")
            continue
        if lo is not None and v < lo:
            print(f"  数值不能小于 {lo}。")
            continue
        if hi is not None and v > hi:
            print(f"  数值不能大于 {hi}。")
            continue
        return v


def ask_yn(prompt, default="n"):
    while True:
        s = input(prompt).strip().lower()
        if not s:
            return default == "y"
        if s in ("y", "yes", "是", "对"):
            return True
        if s in ("n", "no", "否", "不"):
            return False
        print("  请输入 y/n。")


def choose_city():
    codes = list(CFG["cities"].keys())
    print("\n可选城市：")
    for i, c in enumerate(codes, 1):
        print(f"  [{i}] {CFG['cities'][c]['name']} ({c})"
              + ("  ← 默认" if c == DEFAULT_CITY else ""))
    while True:
        s = input(f"请输入城市编号或代码（回车默认 {DEFAULT_CITY}）：").strip()
        if not s:
            return DEFAULT_CITY
        if s in CFG["cities"]:
            return s
        try:
            idx = int(s)
            if 1 <= idx <= len(codes):
                return codes[idx - 1]
        except ValueError:
            pass
        print("  输入无效，请重新输入。")


def choose_year(city_code):
    years = sorted(int(k) for k in CFG["cities"][city_code]["years"].keys())
    default = DEFAULT_YEAR if DEFAULT_YEAR in years else years[-1]
    print(f"\n{CFG['cities'][city_code]['name']} 可用年度：{', '.join(map(str, years))}")
    while True:
        s = input(f"请输入年度（回车默认 {default}）：").strip()
        if not s:
            return default
        try:
            y = int(s)
            if y in years:
                return y
        except ValueError:
            pass
        print("  输入无效，请从可用年度中选择。")


def collect_special_deductions(sess):
    print("\n================= 专项附加扣除（可选） =================")
    print("每项可指定生效起止月（默认 1~12，即全年生效）。")
    items = []
    notes = []
    RENT = sess.rent_deduction

    if ask_yn(f"子女教育扣除（每个 3 岁~博士阶段子女 {SD['child_edu']} 元/月）是否启用？ (y/n，默认 n): "):
        n = ask_int("  符合条件子女数：", default=1, lo=1, hi=20)
        s, e = ask_month_range()
        amt = float(SD["child_edu"]) * n
        items.append(("child_edu", amt, s, e))
        notes.append(f"子女教育 {n} 个 × {SD['child_edu']} = {amt:.0f} 元/月（{s}-{e}月）")

    if ask_yn(f"继续教育扣除（学历教育 {SD['continuing_edu']} 元/月；职业资格证书 3600 元/年）是否启用？ (y/n，默认 n): "):
        s, e = ask_month_range()
        items.append(("continuing_edu", float(SD["continuing_edu"]), s, e))
        notes.append(f"继续教育 {SD['continuing_edu']} 元/月（{s}-{e}月）")

    if ask_yn(f"大病医疗扣除（当年医保报销后自付超 {SD['medical_threshold']/10000:.1f} 万部分，限额 {SD['medical_annual_cap']/10000:.0f} 万/年）是否启用？ (y/n，默认 n): "):
        annual = ask_float("  请输入全年预计符合条件的自付金额（元，>15000 部分可扣，限额 80000）：",
                           default=0, lo=0, hi=1e9)
        yearly = min(max(annual - float(SD["medical_threshold"]), 0.0), float(SD["medical_annual_cap"]))
        s, e = ask_month_range()
        if yearly > 0:
            items.append(("medical", yearly / 12.0, s, e))
            notes.append(f"大病医疗全年 {yearly:.0f} 元，折合 {yearly/12.0:.0f} 元/月（{s}-{e}月）")

    if ask_yn(f"住房贷款利息扣除（首套房贷，{SD['mortgage_int']} 元/月）是否启用？ (y/n，默认 n): "):
        s, e = ask_month_range()
        items.append(("mortgage_int", float(SD["mortgage_int"]), s, e))
        notes.append(f"住房贷款利息 {SD['mortgage_int']} 元/月（{s}-{e}月）")

    if ask_yn(f"住房租金扣除（{sess.city_name} 按 {RENT:.0f} 元/月）是否启用？(与房贷利息二选一) (y/n，默认 n): "):
        s, e = ask_month_range()
        items.append(("rent", RENT, s, e))
        notes.append(f"住房租金 {RENT:.0f} 元/月（{s}-{e}月）")

    if ask_yn(f"赡养老人扣除（独生子女 {SD['elderly_only']} 元/月；非独生子女分摊≤{SD['elderly_share']} 元/月）是否启用？ (y/n，默认 n): "):
        s, e = ask_month_range()
        if ask_yn("    是否为独生子女？ (y/n，默认 y): ", default="y"):
            items.append(("elderly", float(SD["elderly_only"]), s, e))
            notes.append(f"赡养老人（独生子女）{SD['elderly_only']} 元/月（{s}-{e}月）")
        else:
            items.append(("elderly", float(SD["elderly_share"]), s, e))
            notes.append(f"赡养老人（非独生子女分摊）{SD['elderly_share']} 元/月（{s}-{e}月）")

    if ask_yn(f"3 岁以下婴幼儿照护扣除（每个婴幼儿 {SD['baby_care']} 元/月）是否启用？ (y/n，默认 n): "):
        n = ask_int("  符合条件的婴幼儿数：", default=1, lo=1, hi=20)
        s, e = ask_month_range()
        amt = float(SD["baby_care"]) * n
        items.append(("baby_care", amt, s, e))
        notes.append(f"婴幼儿照护 {n} 个 × {SD['baby_care']} = {amt:.0f} 元/月（{s}-{e}月）")

    print("------------------------------")
    if notes:
        print("已启用专项附加扣除：")
        for nd in notes:
            print(f"  · {nd}")
    else:
        print("未启用任何专项附加扣除。")
    return items


def ask_month_range():
    s = ask_int("  起始月（1~12，默认 1）：", default=1, lo=1, hi=12)
    e = ask_int("  结束月（1~12，默认 12）：", default=12, lo=1, hi=12)
    if e < s:
        s, e = e, s
    return s, e


# =====================================================================
# 五、Display
# =====================================================================

def fmt(v):
    return f"{v:,.2f}"


def show_monthly(sess, r, special_items):
    m, salary = r["month_no"], r["salary"]
    print("\n" + "=" * 68)
    print(f"    {sess.city_name} {sess.year} 工资计算器 —— 第 {m} 个月 (税前月薪 {fmt(salary)} 元)")
    print("=" * 68)

    hk, hp = sess.period_for(m)
    print(f"【适用半年度】{hk.upper()}（{hp['months'][0]}-{hp['months'][1]}月）"
          + ("  ⚠  provisional（暂未核实）" if hp.get("provisional") else ""))
    print(f"【缴费基数】社保 养老{fmt(r['sb_p'])} / 医疗{fmt(r['sb_m'])} / 失业{fmt(r['sb_u'])} 元/月")
    print(f"          公积金 {fmt(r['housing_base'])} 元/月")
    print(f"【公积金缴存比例】{r['housing_pct']}%（{sess.city_name} "
          f"{sess.housing_rate_min}~{sess.housing_rate_max}%）"
          + (f"  补充公积金 {r['extra_pct']}%（{sess.extra_min}~{sess.extra_max}%）"
             if r['extra_pct'] else "  未缴补充公积金"))

    print(f"\n【1. 五险一金（个人缴纳部分）】")
    print(f"  {'项目':<14}{'比例':>8}{'金额(元)':>14}")
    print(f"  {'养老保险':<14}{f'{sess.pension_emp*100:.0f}%':>8}{fmt(r['pension_p']):>14}")
    med_label = f"{sess.medical_emp*100:.0f}%" + (f"+{sess.medical_fixed:g}元" if sess.medical_fixed else "")
    print(f"  {'医疗保险(含生育)':<20}{med_label:>8}{fmt(r['medical_p']):>14}")
    print(f"  {'失业保险':<14}{f'{sess.unemploy_emp*100:.1f}%':>8}{fmt(r['unemploy_p']):>14}")
    hpct = str(r["housing_pct"]) + "%"
    epct = str(r["extra_pct"]) + "%" if r["extra_pct"] else ""
    print(f"  {'住房公积金':<14}{hpct:>8}{fmt(r['housing_p']):>14}")
    if r["extra_pct"]:
        print(f"  {'补充公积金':<14}{epct:>8}{fmt(r['extra_p']):>14}")
    print(f"  {'五项合计':<14}{'':>8}{fmt(r['social_p_total']):>14}")

    print(f"\n【2. 五险一金（单位缴纳部分，仅供参考）】")
    print(f"  {'项目':<14}{'比例':>8}{'金额(元)':>14}")
    print(f"  {'养老保险':<14}{f'{sess.pension_org*100:.0f}%':>8}{fmt(r['pension_o']):>14}")
    print(f"  {'医疗保险(含生育)':<20}{f'{sess.medical_org*100:.0f}%':>8}{fmt(r['medical_o']):>14}")
    print(f"  {'失业保险':<14}{f'{sess.unemploy_org*100:.1f}%':>8}{fmt(r['unemploy_o']):>14}")
    print(f"  {'工伤保险':<14}{f'{sess.injury_org*100:.2f}%':>8}{fmt(r['injury_o']):>14}")
    print(f"  {'住房公积金':<14}{hpct:>8}{fmt(r['housing_o']):>14}")
    if r["extra_pct"]:
        print(f"  {'补充公积金':<14}{epct:>8}{fmt(r['extra_o']):>14}")
    print(f"  {'单位合计':<14}{'':>8}{fmt(r['social_o_total']):>14}")

    print(f"\n【3. 个人所得税（累计预扣法，7 级年税率表）】")
    print(f"  专项扣除（个人五险一金+补充公积金）：{fmt(r['social_p_total'])} 元/月")
    print(f"  专项附加扣除（当月）：{fmt(r['special_monthly'])} 元/月")
    print(f"  累计应纳税所得额：{fmt(r['cum_taxable'])} 元")
    print(f"  适用预扣率：{r['rate']*100:.0f}%   速算扣除数：{fmt(r['quick'])} 元")
    print(f"  本年累计应预扣个税：{fmt(r['cum_tax'])} 元")
    print(f"  本月应预扣个税：{fmt(r['month_tax'])} 元")

    print(f"\n【4. 本月到手工资】")
    print(f"  应发工资：                        {fmt(salary)} 元")
    print(f"  - 五险一金 + 补充公积金（个人）   {fmt(r['social_p_total'])} 元")
    print(f"  - 个人所得税                      {fmt(r['month_tax'])} 元")
    print("  ─────────────────────────────────────")
    print(f"  = 实发到手：                      {fmt(r['net'])} 元")

    total_cost = salary + r["social_o_total"]
    print(f"\n【参考】单位每月综合用人成本 ≈ {fmt(total_cost)} 元"
          f"（工资 + 单位社保公积金 {fmt(r['social_o_total'])} 元）")
    print("=" * 68)


def show_bonus_compare(sess, salary, social_p_monthly, special_monthly, bonus):
    print("\n" + "=" * 68)
    print(f"  全年一次性奖金（年终奖）计税对比（{sess.city_name} {sess.year}，12 个月同薪）")
    print("  政策依据：财政部 税务总局公告 2023 年第 30 号，单独计税优惠延续至 2027-12-31")
    print("=" * 68)

    total_a, total_b, salary_tax_a, bonus_tax_a, taxable_b = \
        compare_bonus(salary, social_p_monthly, special_monthly, bonus)

    gap_fill_note = ""
    if salary < TAX_FREE_MONTHLY:
        gap_fill_note = f"（月薪 {fmt(salary)} < {int(TAX_FREE_MONTHLY)}，已按规则差额补足）"

    print(f"  年终奖金额：{fmt(bonus)} 元 {gap_fill_note}")
    print(f"\n  【方式 A · 单独计税】")
    print(f"    工资全年个税（累计预扣）：{fmt(salary_tax_a)} 元")
    print(f"    年终奖单独计税：{fmt(bonus_tax_a)} 元"
          f"（奖金/12={fmt(bonus/12)} → 查月度换算税率表）")
    print(f"    全年个税合计：{fmt(total_a)} 元")

    print(f"\n  【方式 B · 并入综合所得】")
    print(f"    全年综合所得：{fmt(salary*12 + bonus)} 元")
    print(f"    应纳税所得额（含年终奖）：{fmt(taxable_b)} 元")
    print(f"    全年个税合计：{fmt(total_b)} 元")

    better = "A（单独计税）" if total_a <= total_b else "B（并入综合所得）"
    diff = abs(total_a - total_b)
    print(f"\n  ★ 结论：方式{better}更省税，全年可少缴个税 ≈ {fmt(diff)} 元")
    print("=" * 68)


def show_yearly_table(sess, months_12):
    print("\n----- 全年逐月（累计预扣法） -----")
    print(f"{'月份':>5}{'半年度':>6}{'累计应纳税所得额':>18}{'本月个税':>14}{'实发到手':>14}")
    for r in months_12:
        hk, _ = sess.period_for(r["month_no"])
        print(f"{r['month_no']:>5}{hk.upper():>6}"
              f"{fmt(r['cum_taxable']):>18}{fmt(r['month_tax']):>14}{fmt(r['net']):>14}")
    r12 = months_12[-1]
    print(f"\n全年实发到手合计 ≈ {fmt(sum(m['net'] for m in months_12))} 元")
    print(f"全年缴纳个税合计 ≈ {fmt(r12['cum_tax'])} 元")
    print(f"全年五险一金（个人，含补充公积金）合计 ≈ {fmt(sum(m['social_p_total'] for m in months_12))} 元")


def show_settlement(sess, months_12, annual_medical=0.0):
    ann_taxable, ann_tax, withheld, refund = estimate_annual_settlement(months_12, annual_medical)
    print("\n" + "=" * 68)
    print(f"  年度汇算清缴退税估算（{sess.city_name} {sess.year}）")
    print("=" * 68)
    print(f"  全年综合所得收入额：{fmt(sum(m['salary'] for m in months_12))} 元")
    print(f"  减除费用（6 万/年）：{fmt(TAX_FREE_MONTHLY * 12)} 元")
    print(f"  全年专项扣除（五险一金个人）：{fmt(sum(m['social_p_total'] for m in months_12))} 元")
    print(f"  全年专项附加扣除：{fmt(sum(m['special_monthly'] for m in months_12))} 元")
    if annual_medical > 0:
        print(f"  大病医疗自付（年度）：{fmt(annual_medical)} 元")
    print(f"  年度应纳税所得额：{fmt(ann_taxable)} 元")
    print(f"  年度应纳个税：{fmt(ann_tax)} 元")
    print(f"  已预扣个税（12 月累计）：{fmt(withheld)} 元")
    if abs(refund) < 0.005:
        print(f"  ★ 预估退/补税额 ≈ 0 元（基本持平）")
    elif refund > 0:
        print(f"  ★ 预估退税额 ≈ {fmt(refund)} 元")
    else:
        print(f"  ★ 预估需补税额 ≈ {fmt(-refund)} 元")
    print("=" * 68)


# =====================================================================
# 六、Export
# =====================================================================

def _export_path(ext):
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(os.path.dirname(_config_path()),
                        f"salary_detail_{ts}.{ext}")


CSV_COLUMNS = [
    # (display_name, record_key)
    ("月份", "month_no"), ("半年度", "half"),
    ("税前月薪", "salary"),
    ("养老基数", "sb_p"), ("医疗基数", "sb_m"), ("失业基数", "sb_u"), ("公积金基数", "housing_base"),
    ("养老_个人", "pension_p"), ("医疗_个人", "medical_p"), ("失业_个人", "unemploy_p"),
    ("公积金_个人", "housing_p"), ("补充公积金_个人", "extra_p"), ("五险一金_个人合计", "social_p_total"),
    ("养老_单位", "pension_o"), ("医疗_单位", "medical_o"), ("失业_单位", "unemploy_o"),
    ("工伤_单位", "injury_o"), ("公积金_单位", "housing_o"), ("补充公积金_单位", "extra_o"),
    ("五险一金_单位合计", "social_o_total"),
    ("专项附加扣除_当月", "special_monthly"),
    ("累计应纳税所得额", "cum_taxable"), ("累计个税", "cum_tax"),
    ("当月个税", "month_tax"), ("实发到手", "net"),
]


def _row_from_record(sess, r):
    hk, _ = sess.period_for(r["month_no"])
    row = dict(r)
    row["half"] = hk.upper()
    return {display: row.get(key, "") for display, key in CSV_COLUMNS}


def export_csv(sess, months_12, path=None):
    path = path or _export_path("csv")
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[k for k, _ in CSV_COLUMNS])
        w.writeheader()
        for r in months_12:
            w.writerow(_row_from_record(sess, r))
    return path


def build_workbook(sess, months_12, annual_medical=0.0, bonus=0.0,
                   housing_pct=0, extra_pct=0):
    """
    Collect the CLI's computed values into the shared report context.

    The workbook itself is assembled by `xlsx_report.build_report()`, the Python twin of
    `web/xlsx-report.js`, on top of the byte-identical writer port (`xlsx_writer.py` vs
    `web/xlsx-writer.js`); `src/test_xlsx_writer.py` proves that a CLI export and a browser
    export of the same inputs are the same file, byte for byte.
    """
    def bonus_summary(salary, social_p_monthly, special_monthly, bonus_amount):
        """Adapt compare_bonus() to the {totalA, totalB, bonusTax} shape the report expects."""
        total_a, total_b, _, bonus_tax_a, _ = compare_bonus(
            salary, social_p_monthly, special_monthly, bonus_amount)
        return {"totalA": total_a, "totalB": total_b, "bonusTax": bonus_tax_a}

    return build_report({
        "months": months_12,
        "detail_cols": CSV_COLUMNS,
        "city_name": sess.city_name,
        "year": sess.year,
        "verified_on": sess.verified_on,
        "bounds": [list(sess.social_bounds(1)), list(sess.social_bounds(7))],
        "housing_bounds": [list(sess.housing_bounds(1)), list(sess.housing_bounds(7))],
        "rates": {"pension_emp": sess.pension_emp, "pension_org": sess.pension_org,
                  "medical_emp": sess.medical_emp, "medical_org": sess.medical_org,
                  "medical_fixed": sess.medical_fixed,
                  "unemploy_emp": sess.unemploy_emp, "unemploy_org": sess.unemploy_org,
                  "injury_org": sess.injury_org},
        "housing_pct": housing_pct,
        "extra_pct": extra_pct,
        "housing_range": [sess.housing_rate_min, sess.housing_rate_max],
        "supplement_range": [sess.extra_min, sess.extra_max],
        "tax_free_monthly": TAX_FREE_MONTHLY,
        "annual_medical": annual_medical,
        "bonus": bonus,
        "cumulative_tax": calc_cumulative_tax,
        "compare_bonus": bonus_summary,
    })


def export_xlsx(sess, months_12, path=None, annual_medical=0.0, bonus=0.0,
                housing_pct=0, extra_pct=0):
    """Write the styled four-sheet workbook with no third-party dependency."""
    path = path or _export_path("xlsx")
    build_workbook(sess, months_12, annual_medical, bonus, housing_pct, extra_pct).save(path)
    return path


# =====================================================================
# 七、Main
# =====================================================================

def main():
    print("=" * 68)
    print("  工资计算器（中国） · 8 城市 · 多年度 · 半年度")
    print(f"  默认城市：{CFG['cities'][DEFAULT_CITY]['name']}  默认年度：{DEFAULT_YEAR}")
    print(f"  数据来源：config.json（{len(CFG['cities'])} 城市 · 年度 {min(int(k) for k in CFG['cities'][DEFAULT_CITY]['years'])}-{max(int(k) for k in CFG['cities'][DEFAULT_CITY]['years'])} · 含上/下半年基数）")
    print("=" * 68)

    city_code = choose_city()
    year = choose_year(city_code)
    sess = Session(city_code, year)
    print(f"\n已选择：{sess.summary_line()}")

    salary = ask_float("\n请输入税前月薪（元）：", lo=0, hi=10_000_000)
    if salary <= 0:
        print("月薪必须大于 0。")
        sys.exit(0)

    month_no = ask_int("\n这是年度内第几个月的工资？（1~12，默认 1）：", default=1, lo=1, hi=12)

    print(f"\n【公积金】{sess.city_name} {year} 年度缴存比例区间为 "
          f"{sess.housing_rate_min}%~{sess.housing_rate_max}%（整数值）"
          + (f"；叠加补充公积金最高可达 {sess.housing_rate_max}+{sess.extra_max}"
             f"={sess.housing_rate_max+sess.extra_max}%。" if sess.extra_max else "。"))
    housing_pct = ask_int(f"  个人/单位缴存比例（%，{sess.housing_rate_min}~{sess.housing_rate_max}，"
                          f"默认 {sess.housing_rate_default}）：",
                          default=sess.housing_rate_default,
                          lo=sess.housing_rate_min, hi=sess.housing_rate_max)

    if sess.extra_max > 0:
        if ask_yn(f"  是否缴纳补充住房公积金（可选 {sess.extra_min}%~{sess.extra_max}%，默认不缴）？ (y/n，默认 n): "):
            extra_pct = ask_int(f"    个人/单位补充公积金比例（%，{sess.extra_min}~{sess.extra_max}，"
                                f"默认 {sess.extra_max}）：",
                                default=sess.extra_max, lo=sess.extra_min, hi=sess.extra_max)
        else:
            extra_pct = 0
    else:
        extra_pct = 0

    # Declared contribution bases (many employers declare the statutory lower bound, not
    # the real salary; that changes both the take-home cash and the withheld tax)
    declared = None
    if ask_yn("\n【申报基数】默认按税前月薪作为缴费基数，是否改为单位实际申报的基数？ (y/n，默认 n): "):
        p_lo, p_hi, _, _, _, _ = sess.social_bounds(1)
        h_lo, h_hi = sess.housing_bounds(1)
        print(f"  提示：留空或 0 表示跟随月薪 {fmt(salary)} 元；填写后仍会被限制在该年度政策区间内。")
        s1 = ask_float(f"  上半年社保申报基数（元，参考区间 {fmt(p_lo)}~{fmt(p_hi)}）：",
                       default=0, lo=0, hi=10_000_000)
        s2 = ask_float(f"  下半年社保申报基数（元，默认同上）：", default=s1, lo=0, hi=10_000_000)
        f1 = ask_float(f"  上半年公积金缴存基数（元，参考区间 {fmt(h_lo)}~{fmt(h_hi)}）：",
                       default=0, lo=0, hi=10_000_000)
        f2 = ask_float(f"  下半年公积金缴存基数（元，默认同上）：", default=f1, lo=0, hi=10_000_000)
        if max(s1, s2, f1, f2) > 0:
            declared = {"social": [s1, s2], "housing": [f1, f2]}
        else:
            print("  四项均为 0，按默认（跟随月薪）处理。")

    special_items = collect_special_deductions(sess)

    # Compute single month using that month's half-year bounds
    plo, phi, mlo, mhi, ulo, uhi = sess.social_bounds(month_no)
    hlo, hhi = sess.housing_bounds(month_no)
    s_base = declared_base((declared or {}).get("social"), salary, month_no)
    h_base = declared_base((declared or {}).get("housing"), salary, month_no)
    sb = {"pension": clamp(s_base, plo, phi),
          "medical": clamp(s_base, mlo, mhi),
          "unemployment": clamp(s_base, ulo, uhi)}
    hb = clamp(h_base, hlo, hhi)
    r = compute_month(sess, month_no, salary, sb, hb, special_items, housing_pct, extra_pct)

    src = "单位申报基数" if declared else "税前月薪"
    capped = "" if (s_base == sb["pension"] and s_base == sb["medical"]
                    and s_base == sb["unemployment"] and h_base == hb) else "（超出政策区间，已按上下限取限）"
    print(f"\n【缴费基数核对】按{src}：社保 养老{fmt(sb['pension'])}/医疗{fmt(sb['medical'])}/"
          f"失业{fmt(sb['unemployment'])} 元/月；公积金 {fmt(hb)} 元/月{capped}")

    show_monthly(sess, r, special_items)

    # Bonus
    bonus_q = ask_float("\n是否有全年一次性奖金（年终奖）？有请输入金额，没有输入 0（元）：",
                        default=0, lo=0, hi=100_000_000)
    special_m_for_bonus = monthly_special(month_no, special_items)
    if bonus_q > 0:
        show_bonus_compare(sess, salary, r["social_p_total"], special_m_for_bonus, bonus_q)

    # Full year
    months_12 = compute_year(sess, salary, special_items, housing_pct, extra_pct, declared)
    if ask_yn("\n是否查看全年 1~12 月逐月个税与到手工资演化？ (y/n，默认 n): "):
        show_yearly_table(sess, months_12)

    # Annual settlement
    annual_medical = 0.0
    for k, amt, s, e in special_items:
        if k == "medical":
            annual_medical += amt * (e - s + 1)
    if ask_yn("\n是否查看年度汇算清缴退税估算？ (y/n，默认 n): "):
        show_settlement(sess, months_12, annual_medical)

    # Export
    choice = ask_int("\n是否导出全年逐月明细？[1] CSV  [2] Excel(.xlsx)  [3] 都要  [0] 不导出（默认 0）：",
                     default=0, lo=0, hi=3)
    if choice in (1, 3):
        p = export_csv(sess, months_12)
        print(f"  已导出 CSV：{p}")
    if choice in (2, 3):
        p = export_xlsx(sess, months_12, annual_medical=annual_medical, bonus=bonus_q,
                        housing_pct=housing_pct, extra_pct=extra_pct)
        print(f"  已导出 Excel（四个工作表：年度汇总/逐月明细/政策参数/年终奖对比）：{p}")

    # Inverse
    if ask_yn("\n是否使用【二分反推税前月薪】（已知目标税后，反推应发）？ (y/n，默认 n): "):
        target = ask_float("  请输入目标月均到手工资（元）：", lo=0, hi=10_000_000)
        res = inverse_gross_from_net(sess, target, special_items, housing_pct, extra_pct, declared)
        print(f"\n  反推结果：税前月薪 ≈ {fmt(res['gross'])} 元")
        print(f"  对应全年到手合计 ≈ {fmt(res['net_12m'])} 元（目标 {fmt(target*12)} 元）")
        print(f"  全年五险一金（个人）≈ {fmt(res['contrib_12m'])} 元")
        print(f"  全年个税合计 ≈ {fmt(res['tax_12m'])} 元")

    print("\n计算完成。说明：房贷利息与住房租金不得同时享受；年终奖单独计税优惠"
          "延续至 2027-12-31；本结果按假设全年月薪不变测算，实际以税务/社保核定为准。\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n已退出。")
        sys.exit(0)
