# 工资计算器（中国） · China Salary Calculator

> 正式名 / Official name：**工资计算器（中国）**（英文与代码层仓库标识沿用通用工程名 `china-salary-calculator`）
> 定名说明 / Naming decision：[`docs/superpowers/specs/2026-10-04-product-naming-design.md`](docs/superpowers/specs/2026-10-04-product-naming-design.md)
>
> 定位 / Positioning：以**参数可审计的准确性 + 零安装离线可用**为主轴。
> `income-calc` 仅作参考基线而非行业标杆（依据与止损判据见
> [`income-calc-assessment.md`](income-calc-assessment.md)；逐项源码对比见
> [`docs/src-vs-github-repos-comparison.md`](docs/src-vs-github-repos-comparison.md) 第十一、十五章）。
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
- **可自定义申报基数**：单位按下限申报时，社保/公积金基数可分别指定（上/下半年各一组，留空即跟随月薪，填入后仍按政策区间限幅）。
  Declared contribution bases: many employers report the statutory lower bound instead of the real salary — override it per half-year, or leave it blank to follow the salary.
- **逐月不同薪资**：提成/发薪不均时可逐月录入 12 个月税前工资，累计预扣按真实逐月收入累加（留空即沿用税前月薪，填 0 表示该月无收入）。
  Per-month gross salaries: cumulative withholding is built from the real monthly income series, not `salary × months`.
- **个人所得税（累计预扣法）**：7 级年度税率表、5000 元起征点、专项附加扣除（可设起止月）。
  IIT via cumulative withholding — 7 brackets, ¥5000 threshold, special additional deductions with month ranges.
- **医疗固定附加费**：北京个人医保为“基数 × 2% + 3 元/月”（大额医疗费用互助资金），定额同样参与个税专项扣除；其余城市无个人按月定额。
  Fixed monthly medical top-up: Beijing employees pay 2% of the base plus ¥3/month; other supported cities have none.
- **补充公积金**：可选，城市区间约束，个人部分参与税前扣除。
  Optional supplementary housing fund (tax-deductible employee share).
- **年终奖双方案对比**：单独计税 vs 并入综合所得，自动推荐省税方案；月薪 < 5000 差额补足。
  Annual bonus: separate vs combined taxation auto-comparison with the tax-saving recommendation.
- **年度汇算清缴**：退税 / 补税估算。
  Annual settlement refund / additional-tax estimation.
- **二分反推税前**：由目标税后到手反推应发月薪。
  Inverse calculation: derive gross from a target net.
- **导出**：CSV 与带样式的 Excel（.xlsx），**两者均零第三方依赖**。
  CSV / styled .xlsx — both generated with no third-party library (no `openpyxl`, no CDN).
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

- 单文件自包含（约 258 KB），**离线可用**；参数改动实时刷新所有结果，CSV / Excel 导出也完全离线完成。
- 想更新城市/年度数据：点击页面「导入配置」选择外部 `config.json` 覆盖内嵌默认值。
- Self-contained single file (~258 KB), **works offline**; results update in real time as you edit
  inputs, and both the CSV and Excel exports work fully offline as well.
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

按交互提示依次选择城市、年度、月薪、公积金比例、申报基数（默认跟随月薪）、专项附加扣除等，
即可查看单月明细、全年逐月、年终奖对比、汇算清缴、反推税前，并可选导出 CSV / Excel。

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
个人医保另可带按月定额（`social_rate.medical_fixed`）：北京 3 元/月，其余城市 0。

⚙️ 导出无需任何第三方库：网页端不拉 CDN，命令行也不需 `pip install openpyxl`。
改过 `web/xlsx-writer.js` 或 `web/xlsx-report.js` 后需重跑：`node web/inline-xlsx.mjs`。
同理，改过计算引擎 `web/compute.js` 后需重跑：`node web/inline-compute.mjs`（仓内断言会拦住漂移）。

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
├── src/
│   ├── salary_calculator.py      # CLI 版（Python 3 标准库，零依赖）
│   ├── xlsx_writer.py            # 零依赖 .xlsx 写入器（表头样式/千分位/冻结/筛选）
│   ├── xlsx_report.py            # 四表报表（与 web/xlsx-report.js 逐字对应）
│   ├── test_xlsx_writer.py       # Excel 契约测试（含双引擎逐字节一致校验）
│   ├── test_cli_smoke.py         # CLI 端到端冒烟测试（脚本化 stdin 驱动完整 main()）
│   └── test_deploy_gate.py       # 发布门禁自身的守卫（失败必须非零退出、check 模式无副作用）
├── web/
│   ├── index.html                # Web UI 单文件（内嵌 Vue 3 + 计算引擎 + Excel 引擎 + 配置）
│   ├── compute.js                # 计算引擎 JS 源（开发参考）
│   ├── xlsx-writer.js            # Excel 写入器 JS 源（与 Python 版输出一致）
│   ├── xlsx-report.js            # 四表报表 JS 源（含 25 列定义）
│   ├── xlsx-sample.mjs           # 跨引擎探针：node web/xlsx-sample.mjs [--report]
│   ├── test-compute.js           # Node.js 等价性测试（379 条断言，含内联副本防漂移）
│   ├── inline-vue.mjs            # 构建脚本：内联 Vue 运行时
│   ├── inline-compute.mjs        # 构建脚本：将 compute.js 重新内联回 index.html
│   ├── inline-config.mjs         # 构建脚本：将 config.json 重新内联回 index.html
│   ├── inline-xlsx.mjs           # 构建脚本：将两个 Excel 模块重新内联回 index.html
│   ├── manifest.webmanifest      # PWA 安装清单
│   ├── sw.js                     # 离线缓存 Service Worker
│   └── icons/                    # 应用图标（多尺寸 + maskable）
├── config.json                   # 8 城 × 2023–2026 参数（税率/专项附加，CLI 与 Web 共用）
├── run.bat                       # Windows 双菜单入口（CLI / Web）
├── run.sh                        # macOS / Linux / Termux 双菜单入口
├── deploy-pages.bat / .sh        # 发布门禁：check 只校验 / publish 免交互推送 / 裸跑为确认制推送
└── docs/                         # 定名说明、变更记录、口径比对、设计与实现文档
```

---

## 🧪 测试 / Testing

计算引擎、Excel 引擎、CLI 入口与发布门禁脚本全部可回归验证，均不需联网（以下命令均在仓根目录执行）：

```bash
node web/test-compute.js            # 379 条断言：JS 与 Python 计算一致 + 内联副本未漂移
python src/test_xlsx_writer.py      # 51 条契约断言，含“CLI 与网页 Excel 逐字节一致”
python src/test_cli_smoke.py        # 26 条 CLI 端到端断言（驱动完整 main()，含申报基数、医疗定额、逐月薪资与反推）
python src/test_deploy_gate.py      # 37 条门禁守卫：检查失败必须非零退出、不代提交、check 模式零副作用
```

The JS engine is numerically equivalent to the Python CLI; the .xlsx writer is a byte-for-byte
port of its Python twin, and the contract test proves both produce the same workbook bytes.
The CLI smoke test drives the real interactive `main()` through scripted stdin, so an
entry-level crash cannot hide behind engine-only assertions. The gate test checks the gate
itself: a printed failure must actually produce a non-zero exit code (a cmd `exit /b` inside a
parenthesized block silently returns 0), and `check` mode must leave the repository untouched.

---

## 🌐 部署为网址 & PWA 安装 / Deploy & Install

把 Web UI 部署成网址后,手机/电脑可**扫码即用**并**安装为 App**(添加到主屏幕、离线可用)。

> ⚠️ PWA 安装/离线缓存依赖 Service Worker,**仅在 http(s) 部署下生效**;本地 `file://` 双击打开仍是完整单文件离线应用,只是不触发"安装"。

### 一键脚本 / One-click script

```bash
# Windows
 deploy-pages.bat            # 跑门禁 → 列出待推送提交 → 交互确认后推送（不会代为提交）
 deploy-pages.bat check      # 只跑门禁：不提交、不推送，无任何副作用（脏工作树也可跑）
 deploy-pages.bat publish    # 跑门禁后直接推送（免交互，供 CI 用）
 deploy-pages.bat gitee      # = publish gitee（可选 github / both，默认 both）

# macOS / Linux
 bash deploy-pages.sh                  # 同上，确认制
 bash deploy-pages.sh check            # 只校验
 bash deploy-pages.sh publish [both|gitee|github]
```

> **发布不会代你提交**：若工作树有未提交改动，`publish`/确认制会在跑重型测试**之前**直接停下并列出脏文件，
> 避开一个把真实变更抹平的 `chore(deploy): update Web UI / PWA assets` 大提交。
> 默认答非 `y` 即取消推送（非交互环境亦为取消，不会误推）。

> 门禁除内联副本一致性、三套断言外，还会检查**交付物漂移**：若 `index.html` 原本与已提交版本一致，
> 而重跑内联脚本后它变了，说明仓里交付旧副本（改了源文件却忘跑内联），门禁直接非零退出。

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
- [`docs/src-vs-github-repos-comparison.md`](docs/src-vs-github-repos-comparison.md) — 逐仓源码级对比：第十一章记分表、第十五章品类基线复核（含已校正的落后项）/ per-repo source-level comparison (scoring in ch.11, category-baseline re-audit in ch.15)
- [`docs/gitee-repos-comparison.md`](docs/gitee-repos-comparison.md) — Gitee（码云）同类开源项目调研与生态对比 / Gitee-side landscape survey & positioning
- [`income-calc-assessment.md`](income-calc-assessment.md) — `income-calc` 优劣势与商业价值评估（含“为何不应继续以它作对标 KPI”的依据与止损判据）/ benchmark & commercial-value assessment

---

## ⚠️ 免责声明 / Disclaimer

本工具仅供演示与参考，**权威数值以税务局、社保及公积金管理部门公布为准**。
计算假设全年月薪不变；年终奖单独计税优惠政策执行期至 **2027-12-31**
（财政部 税务总局公告 2023 年第 30 号）。

For demonstration only. Authoritative figures are those published by the tax and social-security
authorizations. Calculations assume a constant monthly salary; the separate bonus-taxation policy
runs through **2027-12-31**.
