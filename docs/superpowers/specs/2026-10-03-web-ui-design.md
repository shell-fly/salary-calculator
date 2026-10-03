# China Salary Calculator — Web UI 设计规格

> 设计日期：2026-10-03  
> 状态：已确认  
> 作者：brainstorming session

## 1. 概述

为 china-salary-calculator 新增跨平台 Web UI，以单个 `web/index.html` 文件形式交付，内嵌 Vue 3 运行时 + 全部计算逻辑 + 样式。用户只需将文件发送到任意设备，用浏览器打开即可操作——无需安装 Python、Node.js 或任何运行时。

核心目标：
- 完整对标现有 Python CLI 的 7 大功能模块
- 实时联动：参数变化即时刷新全部结果
- 跨全平台：Windows / macOS / Linux / Android / iOS
- 零依赖：单文件自包含，离线可用

## 2. 文件结构

```
china-salary-calculator/
├── src/
│   └── salary_calculator.py      ← 保留，CLI 版
├── web/
│   └── index.html                ← 新增：单文件 Web UI
├── config.json                   ← 共享数据源（web 内嵌默认值 = 此文件内容）
├── shanghai_config.json          ← 保留
├── run.bat                       ← 修改：双菜单 [1] CLI [2] Web UI
├── run.sh                        ← 新增：macOS/Linux/Termux 一键入口
└── docs/
```

## 3. 技术栈

| 层 | 选型 | 说明 |
|----|------|------|
| 框架 | Vue 3 (runtime-only, ~130KB minified) | 内嵌在 HTML 的 `<script>` 标签中 |
| 状态 | `Vue.reactive` + `Vue.computed` | 响应式参数 → 自动重算 |
| 样式 | 原生 CSS（无框架） | 响应式，media query 断点 768px |
| 计算 | 原生 JS，从 Python 1:1 移植 | 与 CLI 版结果精度一致 |
| 导出 CSV | `Blob` + `<a download>` | 零依赖 |
| 导出 Excel | 动态加载 SheetJS CDN；离线降级提示 | 本地可选 |
| 配置导入 | `<input type="file">` + `FileReader` + deep merge | 覆盖内嵌默认值 |

## 4. UI 布局

### 4.1 PC / 平板（≥768px）

```
┌──────────────────────────────────────────────────────────┐
│  工具栏：[城市▼] [年度▼]    [导入配置] [导出CSV] [导出Excel] │
├────────────────────┬─────────────────────────────────────┤
│   参数面板 (38%)    │        结果面板 (62%)                │
│                    │  ┌─Tab─┬─Tab──┬─Tab───┬─Tab─┐       │
│  · 税前月薪        │  │月度 │全年  │年终奖 │汇算 │       │
│  · 月份            │  │明细 │逐月表│ 对比  │清缴 │       │
│  · 公积金比例      │  └─────┴──────┴───────┴─────┘       │
│  · 补充公积金      │                                     │
│                    │  [ 当前 Tab 的详情内容 ]              │
│  ── 专项附加扣除 ──│                                     │
│  ☑ 子女教育        │  ┌──────────────────────────┐       │
│  ☐ 住房租金        │  │ 反推区                    │       │
│  ☑ 赡养老人        │  │ 目标到手 → 反推税前        │       │
│  ...              │  └──────────────────────────┘       │
└────────────────────┴─────────────────────────────────────┘
```

### 4.2 手机端（<768px）

```
┌──────────────────────┐
│ [城市▼] [年度▼] [⚙]  │  ← 顶部栏
├──────────────────────┤
│ ▼ 参数区（可折叠）    │  ← 默认展开，可手动收起
├──────────────────────┤
│ [月度|全年|奖金|汇算] │  ← Tab 横滑
├──────────────────────┤
│   结果内容            │
├──────────────────────┤
│   反推区             │
└──────────────────────┘
```

要点：
- 手机端参数区可折叠，腾出屏幕空间给结果
- Tab 栏支持左右滑动
- 表格在手机端可横向滚动
- 所有金额数字右对齐

## 5. 数据流与状态管理

```
config.json (内嵌为 const CFG)
      │
      ▼
┌─────────────────────────────────────────────┐
│  应用状态 (Vue reactive)                      │
│                                             │
│  params: {                                  │
│    city, year, salary, month,               │
│    housingPct, extraPct, specialItems       │
│  }                                          │
│                                             │
│  computed:                                  │
│    session        → createSession()         │
│    months12       → computeYear()           │
│    monthDetail    → computeMonth()          │
│    bonusCompare   → compareBonus()          │
│    settlement     → estimateSettlement()    │
│    inverseResult  → inverseGross()（独立触发）│
└─────────────────────────────────────────────┘
      │
      ▼ 渲染
┌─────────────────┐
│  UI 组件 / Tab  │
└─────────────────┘
```

- 所有计算为 `computed`（派生状态），参数变即自动重算
- 反推模块用独立触发（debounce 500ms 或显式按钮），避免阻塞 UI
- `specialItems` 格式：`[{key, amount, startMonth, endMonth}]`

## 6. 功能模块详设

### 6.1 月度明细

- 顶部：城市/年度/半年度标签/缴费基数概要
- 表格 1：个人五险一金（项目/比例/金额）
- 表格 2：单位五险一金（默认折叠）
- 个税计算链路：逐步展示累计收入→减除→应纳税所得额→税率→税额
- 到手工资：大号高亮数字
- 单位综合用人成本：底部辅助

### 6.2 全年逐月表

- 12 行表格：月份/半年度/累计应纳税所得额/当月个税/实发到手
- 底部汇总：全年到手合计、全年个税合计、全年五险一金合计

### 6.3 年终奖对比

- 两张并排卡片展示方式 A（单独计税）vs 方式 B（并入综合所得）
- 高亮推荐方案 + 节省金额
- 月薪 < 5000 时显示差额补足说明

### 6.4 汇算清缴

- 计算链路逐行展示
- 最终结果：🟢 退税 ¥xxx 或 🔴 补税 ¥xxx 大卡片

### 6.5 反推税前

- 独立区域，输入目标到手金额
- 点击反推或 500ms debounce 触发
- 显示：税前月薪/全年到手/全年个税/全年五险一金
- 可一键回填到参数区

### 6.6 专项附加扣除

- 每项一行：开关 + 参数输入（人数/起止月份等）
- 7 项：子女教育、继续教育、大病医疗、房贷利息、住房租金、赡养老人、婴幼儿照护
- 房贷与租金互斥提示
- 城市相关的租金标准自动读取 config

### 6.7 导出

| 格式 | 实现 | 说明 |
|------|------|------|
| CSV | Blob 下载 | 列名/列序与 Python `CSV_COLUMNS` 完全一致 |
| Excel | 动态加载 SheetJS CDN | 离线时显示提示"请联网后重试或改用 CSV" |

## 7. 配置导入

- 工具栏「导入配置」按钮 → file input → FileReader → JSON.parse → deep merge 覆盖
- 成功后显示提示："已加载外部配置：{filename}（{N} 城市 / {年度范围}）"
- 导入后所有 computed 自动重算

## 8. 跨平台入口

| 平台 | 方式 |
|------|------|
| Windows | `run.bat` 双菜单；选 2 → `start web\index.html` |
| macOS | `run.sh`；`open web/index.html` |
| Linux | `run.sh`；`xdg-open web/index.html` |
| Android (Termux) | `run.sh`；`termux-open web/index.html` |
| Android (无 Termux) | 复制 `index.html` 到存储 → Chrome 打开 |
| iOS | AirDrop/文件App/iCloud → Safari 打开 |
| 在线部署 | Gitee Pages / GitHub Pages → 手机扫码访问 |

## 9. Python → JS 迁移映射

| Python | JS | 注意 |
|--------|-----|------|
| `Session` 类 | `createSession(cityCode, year)` | 索引逻辑保持 |
| `clamp(v, lo, hi)` | `clamp(v, lo, hi)` | — |
| `round_yuan(v)` | `roundYuan(v)` | `Math.floor(v + 0.5)` |
| `tax_by_table(taxable, table)` | `taxByTable(taxable, table)` | — |
| `compute_month(...)` | `computeMonth(...)` | 返回对象 key 一致 |
| `compute_year(...)` | `computeYear(...)` | — |
| `bonus_single_tax(bonus, salary)` | `bonusSingleTax(bonus, salary)` | — |
| `compare_bonus(...)` | `compareBonus(...)` | — |
| `estimate_annual_settlement(...)` | `estimateAnnualSettlement(...)` | — |
| `inverse_gross_from_net(...)` | `inverseGrossFromNet(...)` | 120 轮迭代上限 |
| `CSV_COLUMNS` | `CSV_COLUMNS` | 列名列序完全一致 |
| `config.json` 加载 | `const CFG = {...}` 内嵌 | FileReader 覆盖 |

精度保证：中间值 float64，渲染时 `.toFixed(2)`。

## 10. 验收标准

1. **等价性**：8 城市 × 2 年度 × 多种月薪档位，JS 结果与 Python CLI 完全一致（误差 < 0.01 元）
2. **跨平台**：Windows Edge、macOS Safari、iPhone Safari、Android Chrome 正确渲染和计算
3. **实时联动**：参数变化后所有 Tab < 50ms 刷新
4. **导出正确**：CSV 内容行列与 Python `export_csv` 一致
5. **离线可用**：无任何网络请求时全部功能正常（除 Excel 导出降级为提示）

## 11. 约束与决策记录

| 决策 | 选择 | 理由 |
|------|------|------|
| UI 类型 | 纯前端单 HTML | 唯一覆盖全平台含 iOS 的方案 |
| 框架 | Vue 3 内嵌 | 响应式计算链路天然匹配实时联动需求 |
| 配置策略 | 内嵌 + 可选外部导入 | 开箱即用且保留灵活性 |
| 功能范围 | 全部 7 模块 | 完整对标 CLI |
| 交互模式 | 实时联动 | 最流畅的用户体验 |
| 导出 Excel | 动态加载+降级 | 避免单文件膨胀 300KB+ |
| Python CLI | 保留共存 | 已有用户习惯，代码维护成本低 |
