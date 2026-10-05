# 工资计算器（中国）· GitHub Actions 自动 Release 设计

> 定稿日期：2026-10-05（v3，Gitee 由第三方 action 改为自研标准库模块 `src/gitee_release.py`；CI 直接跑、软失败）
> 状态：待用户复核
> 基线：本设计是对 [`2026-10-05-release-packaging-design.md`](2026-10-05-release-packaging-design.md)（本地一键打包 `src/release.py` + `release.bat/.sh`）的**增量扩展**，复用其打包逻辑，不重写。
> 关联：现有 Pages 工作流 `.github/workflows/deploy-pages.yml`（`actions/*@v4` 风格基线）

## 1. 目标与范围

把「打了 tag 就能自动出 Release」这一步也自动化：发布者只需 `git tag v3.11 && git push github v3.11`，GitHub Actions 自动产出 `dist/` 并**同时发布到 GitHub Release 与 Gitee 发行版**；同 tag 重跑自动覆盖。

- **做**：新增 tag 触发的 `release.yml`；给 `src/release.py` 增 `--notes-file`；新增 `src/gitee_release.py`（标准库直连 Gitee API）；CI 内用内置 `gh` 建/覆盖 GitHub Release、用 `gitee_release.py` 覆盖式发布 Gitee；补守卫测试与 README 说明。
- **不做**（本轮排除）：本地 `release.py --tag`、本地 `gh` 建草稿（受 ninesix-ai/shell-fly 身份冲突）、workflow_dispatch 手动入口、第三方 Gitee action。

## 2. 决策记录（用户已选）

| 维度 | 选定 | 理由 |
|---|---|---|
| 建 GitHub Release | CI 内**内置 `gh` + `secrets.GITHUB_TOKEN`** | 零第三方 action；runner token 天然对本仓有写权限，绕开本地 gh 身份冲突 |
| CI 验证强度 | **`--fast` 打包 + 独立「内联漂移检查」一步** | 提速，同时拦住「发布旧 index.html 副本」这一最大风险；不跑 379 断言等慢门禁 |
| 同 tag 重跑 | **自动覆盖**（GitHub clobber+edit；Gitee delete+create） | 免去手动删 |
| Gitee 发布 | **自研 `src/gitee_release.py`（标准库直连 API），独立模块** | 不引第三方 action；职责与 release.py 隔离、可独立测试 |
| Gitee 失败处理 | **软失败：跳过/失败均不阻断 GitHub Release**；首次靠 CI 日志调试 | 用户选「直接进 CI 调试」；网络集成测试默认 skip |
| 触发 / 形态 | **仅 `v*` tag 触发 · 直接正式发布** | tag 即定版 |

**为何弃用本地 gh**：本机 `gh` 登录账号为 `ninesix-ai`，与本仓 GitHub 远程 `shell-fly/salary-calculator` 不一致；CI runner 的 `gh` 用任务级 `GITHUB_TOKEN`，无此冲突。

## 3. 新增与改动文件

| 文件 | 类型 | 说明 |
|---|---|---|
| `.github/workflows/release.yml` | 新增 | tag `v*` 触发；漂移检查 → `--fast` 打包 → 建/覆盖 GitHub Release → 覆盖式发 Gitee |
| `src/release.py` | 改动 | 新增可选参数 `--notes-file PATH`（UTF-8 写文案到文件）；不改既有 stdout/门禁逻辑 |
| `src/gitee_release.py` | 新增 | 标准库（`urllib`）直连 Gitee v5 API：`create` / `delete` / 上传附件；CLI 子命令，缺 token 或非网络环境可安全退出 |
| `src/test_release.py` | 改动 | 增 `--notes-file` 写出断言 + workflow 静态守卫 |
| `src/test_gitee_release.py` | 新增 | 纯逻辑单测（端点/请求体/URL 解析）；网络集成用例默认 skip（需 `GITEE_TOKEN`+网络） |
| `README.md` | 改动 | 补 tag 自动发布（GitHub+Gitee）、同 tag 覆盖、`GITEE_TOKEN` 前提 |

- `src/gitee_release.py` 带既有 SPDX/Apache-2.0 版权头，英文注释。

## 4. 工作流设计（`release.yml`）

```
on:
  push:
    tags: ['v*']
permissions:
  contents: write
jobs:
  release:
    runs-on: ubuntu-latest
    env: { TAG: ${{ github.ref_name }} }
    steps:
      1) actions/checkout@v4
      2) actions/setup-node@v4 (node 20)          # 漂移检查需 node
      3) actions/setup-python@v5 (python 3.11)
      4) 内联漂移检查（便宜守卫，拦旧副本）:
         node web/inline-config.mjs
         node web/inline-compute.mjs
         node web/inline-xlsx.mjs
         git diff --exit-code -- web/index.html   # 变脏=交付旧副本 → 非零退出，终止发布
      5) 打包（--fast 提速）:
         python src/release.py "$TAG" --fast --notes-file dist/RELEASE_NOTES.md
      6) GitHub Release（内置 gh，任务级 GITHUB_TOKEN）:
         gh release create "$TAG" dist/*.html dist/*.zip \
           --title "工资计算器（中国）$TAG" --notes-file dist/RELEASE_NOTES.md \
         || { gh release upload "$TAG" dist/*.html dist/*.zip --clobber; \
              gh release edit   "$TAG" --title "工资计算器（中国）$TAG" --notes-file dist/RELEASE_NOTES.md; }
      7) Gitee 发布（软失败；缺 GITEE_TOKEN 直接跳过）:
         if: env.GITEE_TOKEN != ''
         continue-on-error: true
         run: |
           python src/gitee_release.py delete --tag "$TAG" || true      # 覆盖式：先删旧发行版（忽略不存在）
           python src/gitee_release.py publish --tag "$TAG" \
             --title "工资计算器（中国）$TAG" \
             --notes-file dist/RELEASE_NOTES.md \
             --assets dist/*.html dist/*.zip
         env: { GITEE_TOKEN: ${{ secrets.GITEE_TOKEN }},
                GITEE_OWNER: bob3703, GITEE_REPO: salary-calculator }
```

数据流：tag push → checkout → 装 node/python → 漂移检查 → `release.py --fast` 产 `dist/` → GitHub（create 或 clobber+edit）→ Gitee（`gitee_release.py` delete+publish，带两资产）。

## 5. `src/gitee_release.py` 契约

CLI：`gitee_release.py {create|delete|publish} ...`；base = `https://gitee.com/api/v5`；凭据走环境变量 `GITEE_TOKEN/GITEE_OWNER/GITEE_REPO`（不接命令行参数，杜绝泄露）。

已知端点（AtomGit/Gitee 同构，已核实存在；OBS 回调登记细节需 CI 首跑验证）：
- `POST /repos/{owner}/{repo}/releases`：建发行版（`access_token, tag_name, name, body, target_commitish`）。
- `GET /repos/{owner}/{repo}/releases/{tag}` / `DELETE /repos/{owner}/{repo}/releases/{id}`：查询/删除（delete 供覆盖式重跑）。
- `GET /repos/{owner}/{repo}/releases/{tag}/upload_url` → `{url, headers}`：**华为云 OBS 直传地址**；随后以 `PUT`（带返回的签名头）上传二进制。
- **不确定点**：OBS 直传成功后附件是否由 `x-obs-callback` 自动登记到发行版，还是需再调一次关联接口。公开文档未言明 → 该路径在**首次 CI 跑时靠日志验证**（用户已选「直接进 CI 调试」）；代码结构预留 `publish` = `create → 逐 asset upload_url+PUT → (必要时)attach 关联`，末步可按实测补。
- **软失败**：网络错误 / 4xx 非「已存在」/ OBS 失败 → 打印诊断到 stdout、以非零码退出；CI 步骤 `continue-on-error: true` 保证不阻断 GitHub Release。无 `GITEE_TOKEN` 时 `publish/delete` 打印「跳过 Gitee」并以 0 退出。

## 6. `release.py` 的接口增量

- 新增 `--notes-file PATH`（可选）。成功产出 `dist/` 后，用现有 `render_release_notes(version, html_name, zip_name)` 的返回值以 UTF-8 写入 `PATH`（父目录不存在则先建）。未提供时行为完全不变。
- **不改**门禁/`--fast` 逻辑：漂移检查由 workflow 第 4 步独立承担，故 `--fast` 跳过 `run_gate` 不影响这道守卫。

## 7. 边界与错误处理

- **版本/tag 不合规**（如 `v3`）：`release.py` 退出码 2 → 步骤失败 → 不发布。
- **内联漂移**（step4 `git diff` 非零）：终止发布，提示「源文件改了忘重跑内联，先本地 `deploy-pages.bat check` 再打 tag」。
- **同 tag 重跑**：GitHub 走 clobber+edit（保留 Release 与下载数）；Gitee 走 delete+publish（重置该发行版）。
- **缺 `GITEE_TOKEN`**：step7 `if` 不成立 → 跳过；即使进入，`gitee_release.py` 亦以 0 退出。GitHub Release 不受影响。
- **Gitee 任何失败**：`continue-on-error: true` → 不使 job 失败；GitHub Release 已成功，日志明示 Gitee 部分未完成。
- **`dist/RELEASE_NOTES.md` 不误传**：GitHub 资产 glob 仅 `*.html`/`*.zip`。

## 8. 测试设计（先红后绿）

1. `src/test_release.py`：`--notes-file` 写出断言（内容含版本与两资产名）+ `test_release_workflow_wired`（静态读 `release.yml`，断言含 `tags: ['v*']`、漂移检查 `git diff --exit-code`、`--fast`、`--notes-file`、`gh release create`、`--clobber`、`gitee_release.py publish`、`continue-on-error`、`if: env.GITEE_TOKEN`、`contents: write`）。
2. `src/test_gitee_release.py`：纯逻辑用例（`build_api_url`、请求体字段、`select_upload_url` 解析 `{url,headers}`、无 token 退出 0）离线跑；网络集成用例用 `@skipUnless(os.getenv("GITEE_TOKEN"))` 默认跳过，不拖慢常规门禁。

## 9. 安全提示

- GitHub 侧 `contents: write` 用任务级 `GITHUB_TOKEN`，作用域仅本仓、单任务有效。
- Gitee 侧：`GITEE_TOKEN` 仅经 Secrets 注入、走环境变量、绝不明文入参/入库；建议只授 `projects` 最小权限。
- 弃用第三方 action（消除 `@master` 可变引用供应链风险），代价是自维护 OBS 直传契约。
- 推送本改动前建议先做一道 L3 深度安全审查（新 CI 写权限 + 自研外联代码 + Gitee token 路径）。

## 10. 验收标准

- 推合规 `v*` tag → Actions 跑漂移检查→打包→成功建/覆盖 GitHub Release（含 `.html`+`.zip`+文案）；配了 `GITEE_TOKEN` 时同步尝试覆盖式发 Gitee（首跑据日志验证 OBS 登记，必要时微调 `publish`）。
- 漂移/不合规版本/缺产物 → job 失败且不发布；Gitee 失败或缺 token → 跳过/软失败，GitHub 仍成功。
- `python src/test_release.py` 与 `python src/test_gitee_release.py` 全绿；省略 `--notes-file` 时本地一键脚本行为与上一版逐字节一致。
- README 增补到位（tag 自动发布、同 tag 覆盖、`GITEE_TOKEN` 前提与软失败语义）。
