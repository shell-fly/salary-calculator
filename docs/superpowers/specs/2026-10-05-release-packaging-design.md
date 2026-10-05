# 工资计算器（中国）· Release 一键打包脚本设计

> 定稿日期：2026-10-05
> 状态：待用户复核（方向三项 + 细节两项已经用户选定）
> 关联文档：[`2026-10-04-product-naming-design.md`](2026-10-04-product-naming-design.md)、[`../../upgrade-changelog.md`](../../upgrade-changelog.md)
> 关联脚本：`deploy-pages.bat` / `deploy-pages.sh`（复用其发布门禁）、`src/test_deploy_gate.py`（守卫范式参照）

## 1. 目标与范围

把「下载即可一键运行」的 Release 资产在一个命令内产好，供手动上传到 **GitHub Releases** 与 **Gitee 发行版**。定位与项目主轴一致：**参数可审计的准确 + 零安装离线可用**——不引入 `.exe`、不新增第三方依赖、不破坏既有内联一致性门禁。

- **做**：版本校验 → 复用发布门禁 → 生成 `dist/` 下的单文件 `.html` 与完整发行 `.zip` → 打印两平台手动上传步骤与可复制的 Release 文案模板。
- **不做**（本轮明确排除）：自动建 git tag、自动推远程、自动调 `gh`/Gitee OpenAPI 建线上 Release、生成 Windows `.exe`。这些留待后续，且需单独确认。

## 2. 决策记录（用户已选）

| 维度 | 选定 | 理由 |
|---|---|---|
| 版本号来源 | 命令行参数传入（`release.bat v3.11`） | 显式可控、最不易出错 |
| 自动化程度 | 纯本地打包 | 零 token 依赖，GitHub/Gitee 两平台对称适用 |
| 实现语言 | Python 核心 + `.bat`/`.sh` 一键入口 | 符合工程规范「脚本优选 Python」，易写守卫测试 |
| zip 粒度 | 完整发行包 | 解压后浏览器直开、run 菜单、PWA 全可用 |
| Release 文案 | 脚本打印可复制模板 | 减少用户手写成本 |

## 3. 新增与改动文件

| 文件 | 类型 | 说明 |
|---|---|---|
| `src/release.py` | 新增 | 核心逻辑，Python 3 标准库零依赖 |
| `release.bat` | 新增 | Windows 入口，仅 `chcp 65001` + 转发参数给 `python src\release.py` |
| `release.sh` | 新增 | macOS/Linux/Termux 入口，转发给 `python3 src/release.py` |
| `src/test_release.py` | 新增 | 发布脚本守卫（仿 `test_deploy_gate.py`） |
| `.gitignore` | 改动 | 追加 `dist/` |
| `README.md` | 改动 | 新增「📦 打包 Release 资产 / Release assets」小节 |

- 源码文件一律带既有版权头：`# SPDX-License-Identifier: Apache-2.0` / `# Copyright 2026 bob3703`，注释与 docstring 用英文（与 `salary_calculator.py`、`test_deploy_gate.py` 一致）。
- 展示名遵循定名规范：对外主名 **工资计算器（中国）**，工程标识 `china-salary-calculator`。

## 4. 接口与执行流程

```
release.bat v3.11              # Windows
bash release.sh v3.11          # macOS / Linux / Termux
```

1. **版本校验**：参数必须匹配 `^v\d+\.\d+(\.\d+)?$`（即 `vX.Y` 或 `vX.Y.Z`）。缺参或不合规 → 打印用法并以退出码 `2` 结束。
2. **工作树必须已提交**（沿用 deploy-pages「不代为提交」理念）：`git status --porcelain` 非空 → 列出脏文件、退出码 `1`、不产出。
3. **复用发布门禁**（与 deploy-pages 同一套检查，缺 `node`/`python` 时按现有脚本降级跳过并提示）：
   - `node web/inline-config.mjs`、`node web/inline-compute.mjs`、`node web/inline-xlsx.mjs`；
   - 内联漂移检查（跑完内联脚本后 `web/index.html` 若由干净变脏 → 失败）；
   - `node web/test-compute.js`（计算引擎断言）；
   - `python src/test_xlsx_writer.py`（Excel 契约）；
   - `python src/test_cli_smoke.py`（CLI 端到端冒烟）。
   - 任一步非零 → 停下、不清空/不写出半成品、退出码 `1`。
4. **产出 `dist/`**（先清理旧的 `dist/` 再写；仅在门禁全通过后写）：
   - `dist/工资计算器（中国）_v3.11.html` ← **逐字节复制** `web/index.html`（不改内容，避免触发内联漂移门禁；版本只体现在文件名）。
   - `dist/工资计算器（中国）_v3.11.zip` ← 完整发行包，成员见 §5。
5. **打印后续动作**：GitHub Releases / Gitee 发行版上传步骤 + §6 的 Release 文案模板。

## 5. zip 完整发行包成员

保留目录结构，解压后即可用（根 `run.bat` / `run.sh` 打开 `web/index.html`；CLI 走 `src/salary_calculator.py`）：

- `web/` 整站的**运行所需**：`index.html`、`manifest.webmanifest`、`sw.js`、`icons/`（全尺寸图标）。
  - **排除**开发/构建脚本：`compute.js`、`xlsx-writer.js`、`xlsx-report.js`、`inline-*.mjs`、`xlsx-sample.mjs`、`test-compute.js`、`gen-icons.ps1`、`package.json`（这些是仓内开发用，不进发行包以免体积与混淆）。
- `src/` 运行所需：`salary_calculator.py`、`xlsx_writer.py`、`xlsx_report.py`。
  - **排除** `test_*.py`（测试不属于发行物）。
- 根级：`config.json`、`shanghai_config.json`、`run.bat`、`run.sh`、`README.md`、`LICENSE`。
- 打包用标准库 `zipfile`，UTF-8 文件名；不写入 `.git`、`docs/`、`dist/`、`.github/`。

## 6. Release 文案模板（脚本打印，供复制）

标题：`工资计算器（中国）v3.11`。正文包含：功能亮点摘要（沿用 README「✨ 功能特性」要点）、两种下载方式的说明——
1. **单文件免安装**：下载 `工资计算器（中国）_v3.11.html`，任意设备双击用浏览器打开即可（离线、零安装）；
2. **完整发行包**：下载并解压 `工资计算器（中国）_v3.11.zip`，Windows 双击 `run.bat`、macOS/Linux `bash run.sh`（CLI 需 Python 3）。
末尾附免责声明（权威数值以税务局/社保/公积金部门公布为准）与 Apache-2.0 许可提示。

## 7. 关键取舍

- **不向 `index.html` 注入版本号**：注入会破坏内联一致性、触发 `test_deploy_gate` 漂移检查失败；版本仅出现在文件名与 Release 标题。
- **.html 只取单文件**：已验证 `web/index.html` 零外部 http(s) 引用、自包含（258 KB），双击即可跑；图标/sw/manifest 只进 zip（本地 `file://` 双击不依赖 PWA）。
- **不建 tag、不推远程、不代提交**：与 deploy-pages 保持一致，交接动作留给用户显式执行。
- **`dist/` 不入库**：`.gitignore` 追加，产物为一次性交付物。

## 8. 测试设计（`src/test_release.py`，先红后绿）

以 `subprocess` 调用 `src/release.py`（子进程带隔离环境变量，避免误跑重型门禁：提供 `--fast` 仅供测试与调试跳过门禁；正常发布路径不加即跑全门禁）。断言：

1. 版本格式校验：`v3.11`、`v3.11.0` 通过；`3.11`、`v3`、`v3.11.0.1`、`vX`、空参 → 非零退出且打印用法。
2. 脏工作树 / 门禁失败时：非零退出，且 **不写出 `dist/` 半成品**（校验产物目录状态）。
3. `--fast` 成功路径：`dist/` 下生成正确命名的 `.html` 与 `.zip`；`.html` 与 `web/index.html` 逐字节一致。
4. zip 成员齐全性：含 `web/index.html`、`src/salary_calculator.py`、`config.json`、`run.bat`、`run.sh`、`LICENSE`；**不含** `docs/`、`.github/`、`inline-*.mjs`、`test_*.py`。
5. `dist/` 命中 `.gitignore`（`git check-ignore dist` 返回成功）。
6. `.bat` 与 `.sh` 文案/用法一致（防止历史上出现过的双入口漂移）。

## 9. 验收标准

- `release.bat v3.11`（或 `bash release.sh v3.11`）在干净工作树、门禁全绿时，产出 `dist/` 下正确命名的 `.html` + `.zip`，并打印上传步骤与文案模板，退出码 0。
- 任一门禁/校验失败时非零退出，不留半成品。
- `python src/test_release.py` 全绿；不改坏 `deploy-pages` 及其 `test_deploy_gate.py`。
- 新文件版权头/英文注释/命名口径合规；README 增补说明。
