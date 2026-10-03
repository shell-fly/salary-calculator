# china-salary-calculator 升级变更说明

- 升级日期：2026-09-16
- 升级前版本：v1（上海 2026 单城市单年度，`shanghai_config.json`）
- 升级后版本：v2（8 城市 × 多年度 × 半年度 + 全套高级功能，`config.json`）

---

## 一、新增能力

### 1.1 多城市支持（8 城）
沪 / 京 / 穗 / 杭 / 深 / 宁 / 合 / 芜（shanghai / beijing / guangzhou / hangzhou / shenzhen / nanjing / hefei / wuhu）。数据来源对齐 `income-calc` 的 `cityPolicies.ts`（已验证 2025/2026 与官方一致）。

### 1.2 多年度 × 半年度切换
每个城市支持 2025 / 2026 两个社保年度，每年度分上半年（H1，1-6 月）与下半年（H2，7-12 月）两段基数。CLI 入口选择城市与年度后，程序按月份自动切换对应半年度的社保/公积金基数上下限。

### 1.3 深圳 per-insurance 基数独立
深圳的养老/医疗/失业三险基数区间互不相同（如 H2：养老 4775~27549、医疗 6733~33666、失业 2520~44934），config.json 使用对象格式分别指定；其余 7 城使用简写 `[lo, hi]` 共享。

### 1.4 专项附加扣除支持起止月
每项专项附加扣除可指定生效区间（start_month..end_month，默认 1~12 全年），程序按当月是否落在区间内累加。

### 1.5 年终奖月薪<5000 差额补足
对齐 `salary` 的 `award.ts`：当月薪 < 5000 时，年终奖计税基数 = 年终奖 − (5000 − 月薪)；月薪 ≥ 5000 时基数 = 年终奖。

### 1.6 年度汇算清缴退税估算
对齐 `income-calc` 的 `estimatedRefund`：按全年综合所得重算年度应纳税额，与 12 月累计预扣对比，给出退税/补税估算。

### 1.7 二分反推税前月薪
已知目标月均到手工资，用二分法反推应发月薪（容差 0.01 元，最多 120 轮）。

### 1.8 全年逐月明细导出
- **CSV**：零依赖，UTF-8 with BOM（Excel 直接打开不乱码），25 列 × 12 行。
- **Excel (.xlsx)**：可选 `openpyxl`（未装时自动回退 CSV 并提示），首行冻结、金额列千分位格式、列宽自适应。

---

## 二、配置迁移（v1 → v2）

| v1 文件 | v2 文件 | 说明 |
|---|---|---|
| `shanghai_config.json`（已备份至 `docs/config.v1.json.bak`） | `config.json`（根目录） | 结构完全重构，不向下兼容 |
| `src/salary_calculator.py` 中 `CFG["social_base"]["lower"]` 等 | `Session` 类按 (city, year, month) 动态解析 | 旧全局常量改为会话级 |

### 新 config.json 顶层结构

```json
{
  "_comment": "...",
  "_sources": { ... },
  "default_city": "shanghai",
  "default_year": 2026,
  "cities": {
    "<city_code>": {
      "name": "中文名",
      "rent_deduction": 1500,
      "housing_rate": [5, 7],
      "supplemental_housing_rate": [1, 5],
      "social_rate": { "pension_emp": ..., "pension_org": ..., ... },
      "years": {
        "2025": {
          "verified_on": "YYYY-MM-DD",
          "h1": { "months": [1, 6],  "social_base": [lo, hi], "housing_base": [lo, hi] },
          "h2": { "months": [7, 12], "social_base": [lo, hi], "housing_base": [lo, hi] }
        },
        "2026": { ... }
      }
    },
    ...
  },
  "tax_brackets": [ ... 7 级年表，全局统一 ... ],
  "bonus_brackets": [ ... 月度换算表，全局统一 ... ],
  "tax_free_monthly": 5000,
  "special_deductions": { ... }
}
```

### 深圳 per-insurance 写法

```json
"h2": {
  "months": [7, 12],
  "social_base": {
    "pension": [4775, 27549],
    "medical": [6733, 33666],
    "unemployment": [2520, 44934]
  },
  "housing_base": [2520, 44934]
}
```

### 如何新增城市
在 `cities` 下追加一段，参考上海模板填入 `name` / `rent_deduction` / `housing_rate` / `supplemental_housing_rate` / `social_rate` / `years`。

### 如何新增年度
在对应城市 `years` 下追加 `"2027": { "verified_on": "...", "h1": {...}, "h2": {...} }`。

---

## 三、依赖

- **必需**：Python 3 标准库（os / sys / json / math / csv / datetime）—— 零外部依赖。
- **可选**：`openpyxl`（用于 Excel 导出；未安装时自动回退到 CSV）。

```bash
pip install openpyxl   # 可选
```

---

## 四、CLI 主流程（v2）

1. 打印版本信息（含默认城市/年度）
2. 选城市（默认上海，回车跳过）
3. 选年度（默认 2026，回车跳过；列出可用年度）
4. 输入税前月薪
5. 选月份（1~12，默认 1；用于半年度基数自动切换）
6. 公积金比例（按城市区间约束）
7. 补充公积金（按城市区间约束）
8. 专项附加扣除（逐项询问 + 起止月，默认 1~12）
9. 计算单月明细 + 展示
10. 年终奖输入 + 双方案对比（含月薪<5000 差额补足）
11. 全年 12 月逐月表（控制台）
12. 年度汇算退税估算
13. 导出 CSV / Excel 询问
14. 二分反推税前月薪（已知目标税后）

---

## 五、数值回归验证

升级后已用以下用例回归，全部通过：

| # | 场景 | 关键结果 |
|---|---|---|
| 1 | 上海 2026 H2，月薪 20000，公积金 7%，无补充/无专项 | 五险一金 3500 / 个税 345 / 到手 16155（与 v1 一致） |
| 2 | 上海 2026 H2，月薪 50000（封顶） | 社保基数 37731 / 公积金基数 37731 |
| 3 | 上海 2026 H2，月薪 5000（保底） | 社保基数 7546 |
| 4 | 年终奖 10 万（月薪 3 万） | A 方案 40270 < B 方案 52330，推荐 A |
| 5 | 月薪<5000 差额补足（月薪 3000，奖金 6 万） | 税额 5590 < 5790（方向正确） |
| 6 | 反推回归（target=16155 → gross=20000） | 误差 < 0.001 |
| 7 | 8 城 × 2026 全部加载 | 全部成功 |
| 8 | 上海 2025 H2 加载 | 基数 7460/37302（与官方一致） |
| 9 | CSV 导出 | 13 行 × 25 列，UTF-8 BOM，Excel 直接打开不乱码 |

---

## 六、已知限制

- 不做 GUI / Web（保留 CLI 形态）。
- 不做多语言（保持中文 CLI + 英文注释）。
- 不做城市参数自动抓取（参数仍手工录入 JSON）。
- 不引入 pandas 等重依赖（保持零依赖 + 可选 openpyxl）。
- 反推税前月薪假设全年月薪不变，且使用实际 H1/H2 混合基数；如目标 net 对应 gross 跨越 H1/H2 基数切换点，结果仍正确（因正算路径与反推路径使用同一套 `compute_year`）。

---

## 七、回退

- 旧版配置备份：`docs/config.v1.json.bak`（即 `shanghai_config.json`）。
- 旧版 Python 脚本未保留（v2 已完全重写）；如需回退，可基于 `docs/config.v1.json.bak` + v1 源码重新搭建。
- 任何阶段可通过 `git` 回滚。

*（内容由 AI 生成，仅供参考）*
