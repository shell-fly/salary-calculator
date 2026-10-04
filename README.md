# 工资计算器（中国） · China Salary Calculator

> 正式名 / Official name：**工资计算器（中国）**（英文与代码层仓库标识沿用通用工程名 `china-salary-calculator`）
> 定名说明 / Naming decision：[`docs/superpowers/specs/2026-10-04-product-naming-design.md`](docs/superpowers/specs/2026-10-04-product-naming-design.md)
>
> 定位 / Positioning：在**功能、易用性、准确性**上全面对等甚至超过 `income-calc`（详见
> [`docs/src-vs-github-repos-comparison.md`](docs/src-vs-github-repos-comparison.md) 第十一章）。
>
> 中国大陆 **8 城市 × 2023–2026 四个社保年度 × 半年度** 的五险一金 + 个人所得税 + 年终奖 + 汇算清缴计算器。
> 提供 **命令行（CLI）** 与 **跨平台单文件 Web UI** 两种形态，开箱即用、零依赖。
>
> A Mainland-China salary calculator covering **8 cities × 4 social-insurance years (2023–2026) ×
> half-year periods** —
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
- **四个社保年度 / 4 policy years**：2023–2026，每年分上半年/下半年两段基数，按月自动切换。

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

- 单文件自包含（约 224 KB），**离线可用**；参数改动实时刷新所有结果。
- 想更新城市/年度数据：点击页面「导入配置」选择外部 `config.json` 覆盖内嵌默认值。
- Self-contained single file (~224 KB), **works offline**; results update in real time as you edit inputs.
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

- `cities`：8 城市逐年、逐半年度的社保/公积金基数上下限与费率；`_sources` 标注官方来源与**公告日**（32 行 `verified_on` 全部为可查证的各地原始通知发布日期）。
- 自然年度省份（浙江 / 江苏 / 安徽）同一年度的上、下半年社保基数相同；广东按 7 月社保年度；深圳与广州的医保另按自然年度单列。
- Each calendar-year province (Zhejiang / Jiangsu / Anhui) keeps the same social-insurance bounds in both
  halves of a year; Guangdong switches in July, and Shenzhen/Guangzhou medical switch in January.
- `tax_brackets` / `bonus_brackets`：个税年度 7 级税率表、年终奖月度换算税率表。
- `special_deductions`：子女教育、继续教育、大病医疗、住房贷款利息、住房租金、赡养老人、3 岁以下婴幼儿照护。

**新增城市**：在 `cities` 下按上海模板追加一段。
**新增年度**：在对应城市 `years` 下追加 `"2027": { "verified_on": "...", "h1": {...}, "h2": {...} }`。

深圳的养老/医疗/失业三险基数区间不同，使用对象格式分别指定；其余城市用简写 `[lo, hi]`。
深圳与广州的**医保按自然年度**调整（非 7 月切换），且上下限与职保不同，故这两城单独指定 `medical` 区间，同年度上下半年相同。

⚠️ 改完 `config.json` 后，Web UI 内嵌的那一份需要重新内联才能生效：

```bash
node web/inline-config.mjs   # 把 config.json 写回 index.html 并校验一致
```

或直接在页面点「导入配置」选择 `config.json`（临时覆盖，不修改文件）。

All parameters live in root [`config.json`](config.json), shared by CLI and Web UI. Add a city by
appending a block under `cities`; add a year under that city's `years`. Shenzhen uses per-insurance
base ranges (object form), and the **medical** base in both Shenzhen and Guangzhou follows the calendar
year (same range in both halves); other cities use the shared `[lo, hi]` shorthand.
After editing `config.json`, run `node web/inline-config.mjs` to refresh the copy embedded in
`index.html` (or use the in-page "导入配置 / Import" button for a temporary override).

---

## 📁 项目结构 / Project Layout

```
china-salary-calculator/
├── src/salary_calculator.py    # CLI 版（Python 3，零依赖 + 可选 openpyxl）
├── web/
│   ├── index.html              # Web UI 单文件（内嵌 Vue 3 + 计算引擎 + 配置）
│   ├── compute.js              # 计算引擎 JS 源（开发参考）
│   ├── test-compute.js         # Node.js 等价性测试（316 条断言）
│   ├── inline-vue.mjs          # 构建脚本：把 Vue 运行时内联进 index.html
│   ├── inline-config.mjs       # 构建脚本：把 config.json 重新内联回 index.html
│   ├── manifest.webmanifest    # PWA 安装清单
│   ├── sw.js                   # 离线缓存 Service Worker
│   └── icons/                  # 应用图标（多尺寸 + maskable）
├── config.json                 # 8 城 × 2023–2026 参数（税率/专项附加，CLI 与 Web 共用）
├── run.bat                     # Windows 双菜单入口（CLI / Web）
├── run.sh                      # macOS / Linux / Termux 双菜单入口
├── deploy-pages.bat / .sh      # 一键发布前置检查（GitHub / Gitee Pages）
└── docs/                       # 定名说明、变更记录、口径比对、设计与实现文档
```

---

## 🧪 测试 / Testing

计算引擎的 JS 移植与 Python 版数值等价，可用 Node.js 回归：

```bash
cd web
node test-compute.js     # 316 条断言，验证与 Python 结果一致
```

The JS engine is numerically equivalent to the Python CLI; run the Node regression above.

---

## 🌐 部署为网址 & PWA 安装 / Deploy & Install

把 Web UI 部署成网址后,手机/电脑可**扫码即用**并**安装为 App**(添加到主屏幕、离线可用)。

> ⚠️ PWA 安装/离线缓存依赖 Service Worker,**仅在 http(s) 部署下生效**;本地 `file://` 双击打开仍是完整单文件离线应用,只是不触发"安装"。

### 一键脚本 / One-click script

```bash
# Windows
 deploy-pages.bat            # 或指定远程: deploy-pages.bat gitee / github

# macOS / Linux
 bash deploy-pages.sh       # 可选参数: gitee | github | both
```

脚本会校验 PWA 文件、提交并推送到已配置的远程,然后打印各平台的启用步骤。

### GitHub Pages（自动部署）

1. 仓库已内置 [`.github/workflows/deploy-pages.yml`](.github/workflows/deploy-pages.yml)，自动发布 `web/` 目录。
2. 一次性开启：Settings → Pages → Source 选 **GitHub Actions**。
3. 推送到 main/master 后，Actions 自动部署，访问 `https://<用户名>.github.io/<仓库名>/`。

### Gitee Pages（国内访问快）

1. 需先完成**实名认证**。
2. 仓库页 → Services → **Gitee Pages** → 启用；部署分支选 master/main，**目录填 `web`** → 启动。
3. 访问控制台给出的 `https://<用户名>.gitee.io/<仓库名>/`。（更新内容后需手动点"更新"重新发布。）

### 安装为 App / Install

浏览器打开部署后的网址 →
- **安卓 Chrome**：地址栏右侧"安装"图标，或菜单 → "安装应用/添加到主屏幕"。
- **iOS Safari**：分享 → "添加到主屏幕"。
- **桌面 Chrome/Edge**：地址栏右侧安装图标。
安装后独立窗口启动、离线可用、带应用图标。

Deploy the site (one-click script or GitHub/Gitee Pages), then open the URL and use the browser's
"Install / Add to Home Screen" to get a standalone, offline-capable app icon. PWA install requires
http(s); opening `index.html` via `file://` still works as a full offline single file.

---

## 📚 文档 / Docs

- [`docs/superpowers/specs/2026-10-04-product-naming-design.md`](docs/superpowers/specs/2026-10-04-product-naming-design.md) — 正式定名与文档口径 / product naming decision
- [`docs/upgrade-changelog.md`](docs/upgrade-changelog.md) — v1→v2→v3 升级变更说明 / changelog
- [`docs/salary-calculator-calibration-report.md`](docs/salary-calculator-calibration-report.md) — 与 GitHub 开源项目口径比对 / calibration report
- [`docs/src-vs-github-repos-comparison.md`](docs/src-vs-github-repos-comparison.md) — 详细代码对比，含对 `income-calc` 的功能/易用性/准确性对等与超越总评 / detailed comparison incl. parity & superiority vs `income-calc`
- [`docs/gitee-repos-comparison.md`](docs/gitee-repos-comparison.md) — Gitee（码云）同类开源项目调研与生态对比 / Gitee-side landscape survey & positioning

---

## ⚠️ 免责声明 / Disclaimer

本工具仅供演示与参考，**权威数值以税务局、社保及公积金管理部门公布为准**。
计算假设全年月薪不变；年终奖单独计税优惠政策执行期至 **2027-12-31**
（财政部 税务总局公告 2023 年第 30 号）。

For demonstration only. Authoritative figures are those published by the tax and social-security
authorizations. Calculations assume a constant monthly salary; the separate bonus-taxation policy
runs through **2027-12-31**.
