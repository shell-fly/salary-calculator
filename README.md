# China Salary Calculator · 中国工资计算器

> 中国大陆 **8 城市 × 多年度 × 半年度** 的五险一金 + 个人所得税 + 年终奖 + 汇算清缴计算器。
> 提供 **命令行（CLI）** 与 **跨平台单文件 Web UI** 两种形态，开箱即用、零依赖。
>
> A Mainland-China salary calculator covering **8 cities × multiple years × half-year periods** —
> social insurance, housing fund, individual income tax (cumulative withholding), annual bonus and
> annual settlement. Ships in two forms: a **CLI** and a **cross-platform single-file Web UI**.

---

## ✨ 功能特性 / Features

- **五险一金**：按城市缴费基数上下限与比例计算个人 / 单位缴纳，支持半年度自动切换。
  Five insurances + housing fund with per-city base bounds and rates, auto half-year switching.
- **个人所得税（累计预扣法）**：7 级年度税率表、5000 元起征点、专项附加扣除（可设起止月）。
  IIT via cumulative withholding — 7 brackets, ¥5000 threshold, special additional deductions with month ranges.
- **补充公积金**：可选，城市区间约束，个人部分参与税前扣除。
  Optional supplementary housing fund (tax-deductible employee share).
- **年终奖双方案对比**：单独计税 vs 并入综合所得，自动推荐省税方案；月薪 < 5000 差额补足。
  Annual bonus: separate vs combined taxation auto-comparison with the tax-saving recommendation.
- **年度汇算清缴**：退税 / 补税估算。
  Annual settlement refund / additional-tax estimation.
- **二分反推税前**：由目标税后到手反推应发月薪。
  Inverse calculation: derive gross from a target net.
- **导出**：CSV（零依赖）/ Excel（可选）。
  Export to CSV (zero-dep) / Excel (optional).
- **8 城市 / 8 cities**：上海、北京、广州、杭州、深圳、南京、合肥、芜湖。

---

## 🚀 快速开始 / Quick Start

### 方式一：Web UI（推荐，免安装）/ Option 1: Web UI (recommended, no install)

直接用浏览器打开 `web/index.html` 即可，**无需安装任何东西**。

Open `web/index.html` directly in any browser — **nothing to install**.

| 平台 / Platform | 打开方式 / How to open |
|---|---|
| Windows | 双击 `run.bat` → 选 `2`；或直接双击 `web/index.html` |
| macOS / Linux | `bash run.sh` → 选 `2`；或用浏览器打开 `web/index.html` |
| Android | 把 `web/index.html` 传到手机，用 Chrome 打开（或 Termux 内 `bash run.sh`） |
| iPhone / iPad | 通过 AirDrop / 文件 App / iCloud 传输后用 Safari 打开 |

- 单文件自包含（约 215 KB），**离线可用**；参数改动实时刷新所有结果。
- 想更新城市/年度数据：点击页面「导入配置」选择外部 `config.json` 覆盖内嵌默认值。
- Self-contained single file (~215 KB), **works offline**; results update in real time as you edit inputs.
- To update city/year data: click "导入配置 / Import" and select an external `config.json`.

### 方式二：CLI（需 Python 3）/ Option 2: CLI (requires Python 3)

```bash
# Windows
run.bat            # 选 1，或：
python src/salary_calculator.py

# macOS / Linux
bash run.sh        # 选 1，或：
python3 src/salary_calculator.py
```

按交互提示依次选择城市、年度、月薪、公积金比例、专项附加扣除等，即可查看单月明细、
全年逐月、年终奖对比、汇算清缴、反推税前，并可选导出 CSV / Excel。

---

## ⚙️ 配置 / Configuration

所有参数集中在根目录 [`config.json`](config.json)（CLI 与 Web UI 共用同一份数据）：

- `cities`：8 城市逐年、逐半年度的社保/公积金基数上下限与费率；`_sources` 标注官方来源。
- `tax_brackets` / `bonus_brackets`：个税年度 7 级税率表、年终奖月度换算税率表。
- `special_deductions`：子女教育、继续教育、大病医疗、住房贷款利息、住房租金、赡养老人、3 岁以下婴幼儿照护。

**新增城市**：在 `cities` 下按上海模板追加一段。
**新增年度**：在对应城市 `years` 下追加 `"2027": { "verified_on": "...", "h1": {...}, "h2": {...} }`。

深圳的养老/医疗/失业三险基数区间不同，使用对象格式分别指定；其余城市用简写 `[lo, hi]`。

All parameters live in root [`config.json`](config.json), shared by CLI and Web UI. Add a city by
appending a block under `cities`; add a year under that city's `years`. Shenzhen uses per-insurance
base ranges (object form); other cities use the shared `[lo, hi]` shorthand.

---

## 📁 项目结构 / Project Layout

```
china-salary-calculator/
├── src/salary_calculator.py    # CLI 版（Python 3，零依赖 + 可选 openpyxl）
├── web/
│   ├── index.html              # Web UI 单文件（内嵌 Vue 3 + 计算引擎 + 配置）
│   ├── compute.js              # 计算引擎 JS 源（开发参考）
│   ├── test-compute.js         # Node.js 等价性测试（70+ 断言）
│   └── inline-vue.mjs          # 构建脚本：把 Vue 运行时内联进 index.html
├── config.json                 # 城市/年度/税率/专项附加参数（CLI 与 Web 共用）
├── run.bat                     # Windows 双菜单入口（CLI / Web）
├── run.sh                      # macOS / Linux / Termux 双菜单入口
└── docs/                       # 变更记录、口径比对、设计与实现文档
```

---

## 🧪 测试 / Testing

计算引擎的 JS 移植与 Python 版数值等价，可用 Node.js 回归：

```bash
cd web
node test-compute.js     # 70+ 断言，验证与 Python 结果一致
```

The JS engine is numerically equivalent to the Python CLI; run the Node regression above.

---

## 📚 文档 / Docs

- [`docs/upgrade-changelog.md`](docs/upgrade-changelog.md) — v1→v2→v3 升级变更说明 / changelog
- [`docs/salary-calculator-calibration-report.md`](docs/salary-calculator-calibration-report.md) — 与 GitHub 开源项目口径比对 / calibration report
- [`docs/src-vs-github-repos-comparison.md`](docs/src-vs-github-repos-comparison.md) — 详细代码对比 / detailed comparison

---

## ⚠️ 免责声明 / Disclaimer

本工具仅供演示与参考，**权威数值以税务局、社保及公积金管理部门公布为准**。
计算假设全年月薪不变；年终奖单独计税优惠政策执行期至 **2027-12-31**
（财政部 税务总局公告 2023 年第 30 号）。

For demonstration only. Authoritative figures are those published by the tax and social-security
authorizations. Calculations assume a constant monthly salary; the separate bonus-taxation policy
runs through **2027-12-31**.
