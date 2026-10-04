# 工资计算器（中国）· 正式定名与文档口径设计

> 定稿日期：2026-10-04
> 状态：已确认（用户在三个候选名中选定方案 3）
> 关联文档：[`upgrade-changelog.md`](../../upgrade-changelog.md)、[`src-vs-github-repos-comparison.md`](../../src-vs-github-repos-comparison.md)、[`salary-calculator-calibration-report.md`](../../salary-calculator-calibration-report.md)

## 1. 定名结论

| 层 | 名称 | 说明 |
|---|---|---|
| 正式名（中文，唯一对外名） | **工资计算器（中国）** | 所有文档与界面展示一律以此为准 |
| 文档内简称 | **本工具** | 仅用于表格窄列与行文简洁，不作为名称使用 |
| 英文 / 代码层标识 | `china-salary-calculator` | 仓库与目录名，按既有规范取小写通用工程名，不套用「万」字辈谐音规则 |
| 主屏短名（PWA） | `工资计算器` | `manifest.webmanifest` 的 `short_name` 与 `apple-mobile-web-app-title`，受桌面/主屏标签长度限制 |

候选名评估（用户选定 3）：

1. `中国工资计算器 · China Salary Calculator`（品类描述名，改动最小）——未选；
2. `China Salary Calculator · 中国工资计算器`（沿用旧顺序）——未选；
3. **`工资计算器（中国）`（主名 + 括注地域）——已选**：主名更短，地域以括注呈现，避免"中国工资计算器"这种定语堆叠。

## 2. 落地范围

- **文档（三份）**：`docs/upgrade-changelog.md`、`docs/src-vs-github-repos-comparison.md`、`docs/salary-calculator-calibration-report.md`。
- **界面与入口展示名**：`README.md` 标题、`web/index.html` 的 `<title>` **与页面内可见标题头（正式名 + 根据配置动态生成的年度摘要）**、`web/manifest.webmanifest` 的 `name`、`run.bat` / `run.sh` 窗口标题与横幅、`deploy-pages.bat` / `deploy-pages.sh` 横幅、CLI 启动横幅（`src/salary_calculator.py`）。
- **不改**：docs 与源码文件名（避免破坏既有链接与 git 历史）、源码内英文注释与 docstring 中的 `china-salary-calculator` 工程标识、`docs/superpowers/` 下历史 spec/plan 的原文（仅加历史快照注记）。

## 3. 文档口径规则

1. **指代统一**：凡指代本项目处，旧称 `src` / `本地` / `china-salary-calculator`（作主语时）一律改为正式名或简称「本工具」；纯文件路径（如 `src/salary_calculator.py`）保持原样。
2. **历史快照保护**：v1 阶段的比对结论（如"仅上海单城市"、"建议做成参数表配置"）不改写正文，改为在篇首加「命名与版本口径」说明并指向升级后章节，已关闭的建议用删除线 + `→ 已落地` 标注。
3. **事实一致性**：文档中的代码行数、文件体积、能力清单等可核验事实须与仓库现状一致；本轮已修正的错误引用见第 5 节。

## 4. 产品定位（写入文档的对外口径）

在**准确性、功能、易用性**三个维度全面对等甚至超过 `income-calc`（五个对比仓库中综合实力最强者）。逐项达成情况见
[`src-vs-github-repos-comparison.md` 第十一章](../../src-vs-github-repos-comparison.md)：

- **准确性**：与 income-calc 并列第一，且在年终奖月度换算表口径、医保自然年度、自然年度省份的 H1 建模、2026 年度公告落实度与 Python/JS 双引擎交叉验证五项上更强；
- **功能**：income-calc 能力集已全部对等，另多出年终奖双方案对比、二分反推税前、单位用人成本、CSV 零依赖导出、零依赖 CLI、单文件离线 Web UI + PWA + 一键部署；
- **易用性**：零安装、`file://` 离线直开、免构建参数更新、移动端传文件即用，明显优于需 Node/pnpm 构建或依赖部署站点的 income-calc；
- ~~**唯一客观差距**：`config.json` 目前只有 2025/2026 两个社保年度（income-calc 另存 2023/2024），以及 Excel 导出样式丰富度，已列入待办。~~ → **年度差距已于同日 v3.1 关闭**（八城均覆盖 2023–2026），另修正了 6 处滞后错填；**v3.2 又逐城回到官方公告复核**，发现**深圳与广州医保均按自然年度**（`income-calc` 对深圳错用半年度切换、对广州直接将三险共用区间），本工具已改用官方值并在准确性上多项严格优于它（见对比文档第十一章与第十三章）。尚余差距：Excel 导出样式丰富度、广州 2023/2024 医保上下限未查到公告。

## 5. 本轮同时修正的事实性错误

| 位置 | 原表述 | 更正 |
|---|---|---|
| `upgrade-changelog.md` 第二章、第七章 | v1 配置"已备份至 `docs/config.v1.json.bak`" | 该文件从未存在且未被 git 跟踪；实际回退参考是仍留在仓根的 `shanghai_config.json`（v2 起代码不再读取） |
| `upgrade-changelog.md` 8.2 / 8.6 | 交付物未含 PWA 相关文件；限制项未含年度覆盖 | 补录 `manifest.webmanifest` / `sw.js` / `icons/` / `deploy-pages.*` / `.github/workflows/deploy-pages.yml`，新增 8.7 节 |
| `src-vs-github-repos-comparison.md` 10.3 | 把"PWA 离线缓存 + 添加到主屏"列为待改进 | 已落地，改为「已落地」并说明 `file://` 与 http(s) 双入口行为 |
| `salary-calculator-calibration-report.md` 第四章第 5 条 | 仍写"建议做成参数表配置" | 标注 v2 已落地并指向 changelog 对应章节 |
| `salary-calculator-calibration-report.md` 第一、五章 | 开源仓库与报告路径写作 `D:\STEM\Code\...` 绝对路径 | 改为工作区相对路径（该批仓库现与本仓同属 `ai-oss-tools/`） |

## 6. 验证

- `python -m py_compile src/salary_calculator.py` 通过；`src/salary_calculator.py` 仍为 833 行（文档所述行数不变）。
- `node web/test-compute.js`：全部断言通过（v3.1 后 157 → v3.2 后 191 → v3.3 后 277 → v3.4 后 316 条）。
- `manifest.webmanifest` JSON 可解析，`name` = 工资计算器（中国）。
- 浏览器端到端打开 `web/index.html`：`document.title` = 工资计算器（中国），Vue 正常渲染，控制台零消息，`file://` 下 SW 未注册且无报错；上海 2026 / 月薪 30000 / 公积金 7% → 第 1 月到手 24157.50、五险一金 5250.00，与 Python 口径一致。
- 文本一致性扫描：docs 与界面文件中已无"中国工资计算器 / 上海工资计算器"作项目名残留（`shanghai_config.json` 内部注释与历史 spec/plan 除外）。

## 7. 后续待办

1. ~~补录 2023/2024 两个社保年度到 `config.json`，以消除对 income-calc 的唯一覆盖差距~~ → **已完成**（同日 v3.1：八城 × 2023–2026，并修正 6 处滞后错填与深圳医保口径，见 changelog 第九章）；
2. Excel 导出样式增强（或把 SheetJS 内联以支持离线导出，代价是单文件体积增大）；
3. 若未来要并入「万」字辈产品家族，需重新走一次命名评估（语义覆盖、家族字辈、输入法歧义、撞名核验），本定名不预设该路径。
4. ~~（数据面新增待办）逐一回到官方公告核实其他城市医保是否也按自然年度调整，并把 `verified_on` 换成真实公告日~~ → **已全部完成**：医保按自然年度的是广东省内（深圳、广州，已改 per-insurance）；另发现**浙江社保也是自然年度，而 `income-calc` 把杭州 H1 滞后了一年**，已修正；**8 城 × 2023–2026 共 32 行的 `verified_on` 均为可查证的官方公告日**（无对齐日期残留），2026 年度已有 7 行去除 `provisional`。仅余三项确实找不到原文的近似/待定项（广州 2023/2024 医保上下限、广东 2026.7 职保新基数、芜湖 2026 公积金上限），见对比文档 14.4。
