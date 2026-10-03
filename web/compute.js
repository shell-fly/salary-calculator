/**
 * compute.js — Core computation engine (JS port from salary_calculator.py)
 * China Salary Calculator: five insurances, housing fund, cumulative IIT,
 * bonus comparison, annual settlement, inverse calculation.
 */

// =====================================================================
// Utility Functions
// =====================================================================

/**
 * Clamp value between lo and hi.
 */
export function clamp(v, lo, hi) {
  return Math.max(lo, Math.min(v, hi));
}

/**
 * Round to nearest yuan (half-up). Must use Math.floor(v+0.5) exactly.
 */
export function roundYuan(v) {
  return Math.floor(v + 0.5);
}

/**
 * Format number to 2 decimal places as string.
 */
export function fmt(v) {
  return Number(v).toFixed(2);
}

/**
 * Convert a config bracket row [upper, rate, quick] to JS form.
 * upper=null means Infinity.
 */
function _toBracket(row) {
  return [
    row[0] === null ? Infinity : Number(row[0]),
    Number(row[1]),
    Number(row[2])
  ];
}

/**
 * Compute tax from taxable income using a bracket table.
 * table: array of [upper, rate, quick]
 */
export function taxByTable(taxable, table) {
  if (taxable <= 0) return 0.0;
  for (const [upper, rate, quick] of table) {
    if (taxable <= upper) {
      return taxable * rate - quick;
    }
  }
  return 0.0;
}

/**
 * Cumulative withholding tax using the annual 7-level tax bracket table.
 */
export function calcCumulativeTax(cumTaxable, taxBrackets) {
  return taxByTable(cumTaxable, taxBrackets);
}

/**
 * Once-off annual bonus taxed separately.
 * Handles salary < 5000 gap-fill per MOF/SAT rules.
 * Policy: 财政部 税务总局公告 2023年第30号, extended to 2027-12-31.
 */
export function bonusSingleTax(bonus, salary, bonusBrackets, taxFreeMonthly) {
  if (bonus <= 0) return 0.0;
  let base;
  if (salary >= taxFreeMonthly) {
    base = bonus;
  } else {
    base = Math.max(bonus - (taxFreeMonthly - salary), 0.0);
  }
  if (base <= 0) return 0.0;
  const avg = base / 12.0;
  for (const [upper, rate, quick] of bonusBrackets) {
    if (avg <= upper) {
      return base * rate - quick;
    }
  }
  // Fallthrough: highest bracket (45% - 181920)
  return base * 0.45 - 181920;
}

/**
 * Sum of special additional deductions active in a given month.
 * items: [{key, amount, startMonth, endMonth}]
 */
export function monthlySpecial(month, items) {
  let total = 0.0;
  for (const item of items) {
    if (item.startMonth <= month && month <= item.endMonth) {
      total += Number(item.amount);
    }
  }
  return total;
}

// =====================================================================
// Session Factory: per-city / per-year parameter resolver
// =====================================================================

/**
 * Normalize social_base spec: handles both [lo, hi] array and
 * {pension:[lo,hi], medical:[lo,hi], unemployment:[lo,hi]} dict format.
 */
function _normalizeSocial(spec) {
  if (Array.isArray(spec) && spec.length === 2) {
    return { pension: spec, medical: spec, unemployment: spec };
  }
  if (typeof spec === 'object' && spec !== null && !Array.isArray(spec)) {
    return {
      pension: [...spec.pension],
      medical: [...spec.medical],
      unemployment: [...spec.unemployment]
    };
  }
  throw new Error("Invalid social_base spec");
}

/**
 * Create a session object for a given city and year.
 * Returns an object with all rates, bounds, and helper methods.
 */
export function createSession(cityCode, year, CFG) {
  const taxBrackets = CFG.tax_brackets.map(_toBracket);
  const bonusBrackets = CFG.bonus_brackets.map(_toBracket);
  const taxFreeMonthly = Number(CFG.tax_free_monthly);

  cityCode = cityCode || CFG.default_city;
  year = year ? Number(year) : Number(CFG.default_year);

  if (!(cityCode in CFG.cities)) {
    throw new Error(`Unsupported city: ${cityCode}`);
  }
  const city = CFG.cities[cityCode];

  // Build years map with numeric keys
  const yearsMap = {};
  for (const [k, v] of Object.entries(city.years)) {
    yearsMap[Number(k)] = v;
  }
  if (!(year in yearsMap)) {
    const avail = Object.keys(yearsMap).map(Number).sort((a, b) => a - b);
    throw new Error(`City ${city.name} has no data for year ${year}. Available: ${avail}`);
  }
  const y = yearsMap[year];

  const supp = city.supplemental_housing_rate || [0, 0];

  const sess = {
    city_code: cityCode,
    city_name: city.name,
    year: year,
    rent_deduction: Number(city.rent_deduction),
    housing_rate_min: Number(city.housing_rate[0]),
    housing_rate_max: Number(city.housing_rate[1]),
    housing_rate_default: Number(city.housing_rate[1]),
    extra_min: Number(supp[0]),
    extra_max: Number(supp[1]),

    pension_emp: Number(city.social_rate.pension_emp),
    pension_org: Number(city.social_rate.pension_org),
    medical_emp: Number(city.social_rate.medical_emp),
    medical_org: Number(city.social_rate.medical_org),
    unemploy_emp: Number(city.social_rate.unemploy_emp),
    unemploy_org: Number(city.social_rate.unemploy_org),
    injury_org: Number(city.social_rate.injury_org || 0),

    taxBrackets,
    bonusBrackets,
    taxFreeMonthly,

    _yearData: y,

    /**
     * Return ['h1'|'h2', periodData] for the given month (1..12).
     */
    periodFor(month) {
      const m = Number(month);
      if (m <= y.h1.months[1]) {
        return ['h1', y.h1];
      }
      return ['h2', y.h2];
    },

    /**
     * Return [pensionLo, pensionHi, medicalLo, medicalHi, unempLo, unempHi].
     */
    socialBounds(month) {
      const [, p] = this.periodFor(month);
      const s = _normalizeSocial(p.social_base);
      return [
        Number(s.pension[0]), Number(s.pension[1]),
        Number(s.medical[0]), Number(s.medical[1]),
        Number(s.unemployment[0]), Number(s.unemployment[1])
      ];
    },

    /**
     * Return [housingLo, housingHi] for the given month.
     */
    housingBounds(month) {
      const [, p] = this.periodFor(month);
      return [Number(p.housing_base[0]), Number(p.housing_base[1])];
    },

    /**
     * Whether the period data is provisional (not yet officially verified).
     */
    isProvisional(month) {
      const [, p] = this.periodFor(month);
      return Boolean(p.provisional || false);
    }
  };

  return sess;
}

// =====================================================================
// Core Computation
// =====================================================================

/**
 * Compute a single month's detail under cumulative withholding.
 * socialBaseDict: {pension: clamped_value, medical: clamped_value, unemployment: clamped_value}
 * specialItems: [{key, amount, startMonth, endMonth}]
 */
export function computeMonth(sess, monthNo, salary, socialBaseDict, housingBase,
  specialItems, housingPct, extraPct, CFG) {
  const taxFreeMonthly = sess.taxFreeMonthly;

  const sbP = socialBaseDict.pension;
  const sbM = socialBaseDict.medical;
  const sbU = socialBaseDict.unemployment;

  // Five insurances (employee share)
  const pensionP = sbP * sess.pension_emp;
  const medicalP = sbM * sess.medical_emp;
  const unemployP = sbU * sess.unemploy_emp;
  const housingP = roundYuan(housingBase * housingPct / 100.0);
  const extraP = extraPct ? roundYuan(housingBase * extraPct / 100.0) : 0.0;
  const socialPTotal = pensionP + medicalP + unemployP + housingP + extraP;

  // Five insurances (employer share)
  const pensionO = sbP * sess.pension_org;
  const medicalO = sbM * sess.medical_org;
  const unemployO = sbU * sess.unemploy_org;
  const injuryO = sbP * sess.injury_org;
  const housingO = roundYuan(housingBase * housingPct / 100.0);
  const extraO = extraPct ? roundYuan(housingBase * extraPct / 100.0) : 0.0;
  const socialOTotal = pensionO + medicalO + unemployO + injuryO + housingO + extraO;

  // Cumulative withholding IIT
  const specialMonthly = monthlySpecial(monthNo, specialItems);
  const cumIncome = salary * monthNo;
  const cumBase = taxFreeMonthly * monthNo;
  const cumSocial = socialPTotal * monthNo;
  const cumSpecial = specialMonthly * monthNo;
  const cumTaxable = cumIncome - cumBase - cumSocial - cumSpecial;
  const cumTax = calcCumulativeTax(cumTaxable, sess.taxBrackets);

  const prevCumTaxable = cumTaxable - salary + taxFreeMonthly + socialPTotal + specialMonthly;
  const prevCumTax = calcCumulativeTax(prevCumTaxable, sess.taxBrackets);
  const monthTax = Math.max(0.0, cumTax - prevCumTax);

  const net = salary - socialPTotal - monthTax;

  let rate = 0.0, quick = 0.0;
  for (const [upper, r, q] of sess.taxBrackets) {
    if (cumTaxable <= upper) {
      rate = r;
      quick = q;
      break;
    }
  }

  return {
    month_no: monthNo, salary: salary,
    sb_p: sbP, sb_m: sbM, sb_u: sbU, housing_base: housingBase,
    pension_p: pensionP, medical_p: medicalP, unemploy_p: unemployP,
    housing_p: housingP, extra_p: extraP, social_p_total: socialPTotal,
    pension_o: pensionO, medical_o: medicalO, unemploy_o: unemployO,
    injury_o: injuryO, housing_o: housingO, extra_o: extraO,
    social_o_total: socialOTotal,
    cum_taxable: cumTaxable, cum_tax: cumTax, month_tax: monthTax,
    rate: rate, quick: quick, net: net,
    special_monthly: specialMonthly, housing_pct: housingPct, extra_pct: extraPct,
  };
}

/**
 * Run 12 months using each month's own half-year bounds. Returns array of 12 dicts.
 */
export function computeYear(sess, salary, specialItems, housingPct, extraPct, CFG) {
  const results = [];
  for (let m = 1; m <= 12; m++) {
    const [plo, phi, mlo, mhi, ulo, uhi] = sess.socialBounds(m);
    const [hlo, hhi] = sess.housingBounds(m);
    const sb = {
      pension: clamp(salary, plo, phi),
      medical: clamp(salary, mlo, mhi),
      unemployment: clamp(salary, ulo, uhi),
    };
    const hb = clamp(salary, hlo, hhi);
    results.push(computeMonth(sess, m, salary, sb, hb, specialItems, housingPct, extraPct, CFG));
  }
  return results;
}

// =====================================================================
// Bonus Comparison / Annual Settlement / Inverse Calculation
// =====================================================================

/**
 * Compare bonus taxation methods: A (separate) vs B (combined).
 * Returns {totalA, totalB, salaryTaxA, bonusTaxA, taxableB}.
 */
export function compareBonus(salary, socialPMonthly, specialMonthly, bonus, CFG) {
  const taxFreeMonthly = Number(CFG.tax_free_monthly);
  const taxBrackets = CFG.tax_brackets.map(_toBracket);
  const bonusBrackets = CFG.bonus_brackets.map(_toBracket);

  const annualIncome = salary * 12;
  const annualBase = taxFreeMonthly * 12;
  const annualSocial = socialPMonthly * 12;
  const annualSpecial = specialMonthly * 12;

  const salaryTaxA = calcCumulativeTax(
    annualIncome - annualBase - annualSocial - annualSpecial, taxBrackets
  );
  const bonusTaxA = bonusSingleTax(bonus, salary, bonusBrackets, taxFreeMonthly);
  const totalA = salaryTaxA + bonusTaxA;

  const taxableB = annualIncome + bonus - annualBase - annualSocial - annualSpecial;
  const totalB = taxByTable(taxableB, taxBrackets);

  return { totalA, totalB, salaryTaxA, bonusTaxA, taxableB };
}

/**
 * Annual settlement (汇算清缴) refund/tax-due estimation.
 * months12: array of 12 computeMonth result dicts.
 * Returns {annualTaxable, annualSettlementTax, withheldTax, estimatedRefund}.
 * estimatedRefund > 0 means refund; < 0 means additional tax due.
 */
export function estimateAnnualSettlement(months12, CFG, annualMedical = 0.0) {
  const taxFreeMonthly = Number(CFG.tax_free_monthly);
  const taxBrackets = CFG.tax_brackets.map(_toBracket);

  const annualGross = months12.reduce((s, m) => s + m.salary, 0);
  const annualContrib = months12.reduce((s, m) => s + m.social_p_total, 0);
  const annualSpecial = months12.reduce((s, m) => s + m.special_monthly, 0);
  const annualTaxable = Math.max(0.0,
    annualGross - taxFreeMonthly * 12 - annualContrib - annualSpecial - Math.max(0.0, annualMedical)
  );
  const annualSettlementTax = calcCumulativeTax(annualTaxable, taxBrackets);
  const withheldTax = months12[months12.length - 1].cum_tax;
  const estimatedRefund = withheldTax - annualSettlementTax;

  return { annualTaxable, annualSettlementTax, withheldTax, estimatedRefund };
}

/**
 * Binary-search gross monthly salary such that 12-month net total
 * matches targetNet * 12 within tol.
 * Returns {gross, net_12m, tax_12m, contrib_12m, months}.
 */
export function inverseGrossFromNet(sess, targetNet, specialItems, housingPct, extraPct,
  CFG, tol = 0.01, maxIter = 120) {
  let lo = 0.0, hi = 10_000_000.0;
  const targetTotal = targetNet * 12.0;
  let last = null;

  for (let i = 0; i < maxIter; i++) {
    const mid = (lo + hi) / 2.0;
    const months = computeYear(sess, mid, specialItems, housingPct, extraPct, CFG);
    const netTotal = months.reduce((s, m) => s + m.net, 0);
    last = { mid, months, netTotal };

    if (Math.abs(netTotal - targetTotal) <= tol) break;
    if (netTotal < targetTotal) {
      lo = mid;
    } else {
      hi = mid;
    }
  }

  const { mid, months, netTotal } = last;
  const taxTotal = months[months.length - 1].cum_tax;
  const contribTotal = months.reduce((s, m) => s + m.social_p_total, 0);

  return {
    gross: mid, net_12m: netTotal, tax_12m: taxTotal,
    contrib_12m: contribTotal, months: months,
  };
}
