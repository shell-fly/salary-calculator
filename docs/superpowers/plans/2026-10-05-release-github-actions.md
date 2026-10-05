# GitHub Actions 自动 Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 推送 `v*` tag 后由 GitHub Actions 自动产出 `dist/` 并覆盖式发布到 GitHub Release 与（可选）Gitee 发行版。

**Architecture:** 三块增量：`src/release.py` 加 `--notes-file` 把 Release 文案写文件；新增 `src/gitee_release.py`（纯标准库 `urllib` 直连 Gitee v5 API，独立模块、软失败）；新增 `.github/workflows/release.yml`（内置 `gh` 建/覆盖 GitHub Release，调 `gitee_release.py` 发 Gitee，前置便宜的内联漂移检查替代重型门禁）。守卫测试扩 `src/test_release.py` 并新增 `src/test_gitee_release.py`。

**Tech Stack:** Python 3（`argparse`/`urllib.request`/`json`/`os`/`re`/`mimetypes`/`subprocess`）、GitHub Actions（`ubuntu-latest`、内置 `gh`、`GITHUB_TOKEN`）、Gitee API v5。

设计依据：[`docs/superpowers/specs/2026-10-05-release-github-actions-design.md`](../specs/2026-10-05-release-github-actions-design.md)（基线：同目录 `2026-10-05-release-packaging-design.md`）

---

## 关键约定（贯穿所有任务）

- **正式名全角括号**：标题用 `工资计算器（中国）`。
- **Gitee 凭据只走环境变量**：`GITEE_TOKEN` / `GITEE_OWNER` / `GITEE_REPO`，绝不出现在命令行参数或代码里。
- **软失败语义**：`gitee_release.py` 在无 token 时打印「跳过 Gitee」并以退出码 `0` 结束；网络/OBS/4xx 失败以非零码退出（由 workflow 步骤 `continue-on-error: true` 消化，不阻断 GitHub Release）。
- **base URL**：`https://gitee.com/api/v5`。
- **OBS 登记不确定点**：`upload_url` 返回 `{url, headers}`，PUT 二进制后是否需再调关联接口，官方文档未言明；本计划按「OBS 直传即登记（`x-obs-callback`），create 时带 `attach_names`/`attach_urls`」实现，验收靠 CI 首跑日志验证，必要时只调 `publish` 末尾。
- **退出码**：`release.py` 版本非法 `2`、脏树/门禁失败 `1`、成功 `0`；`gitee_release.py` 软失败非零、跳过/成功 `0`。
- **版权头**：新 `.py` 顶部 `# -*- coding: utf-8 -*-` / `# SPDX-License-Identifier: Apache-2.0` / `# Copyright 2026 bob3703` / Apache 提示行；注释/docstring 英文。
- **测试运行**：PowerShell 下先 `$env:PYTHONIOENCODING="utf-8"`；命令均在仓根 `china-salary-calculator/` 执行。

## File Structure

- Modify `src/release.py` — 加 `--notes-file`（仅 `main()` 参数与写文件）。
- Create `src/gitee_release.py` — Gitee 客户端：纯逻辑函数 + 薄网络函数 + CLI（`create`/`delete`/`publish`）。
- Create `src/test_gitee_release.py` — 纯逻辑单测（离线）+ 无 token 跳过用例；网络集成用例 `skipUnless`。
- Create `.github/workflows/release.yml` — tag 触发工作流。
- Modify `src/test_release.py` — `--notes-file` 用例 + `test_release_workflow_wired` 静态守卫。
- Modify `README.md` — 增补自动发布说明。

---

## Task 1: release.py 增加 --notes-file

**Files:**
- Modify: `src/release.py`（`main()` 末尾，`if __name__` 之前）
- Modify: `src/test_release.py`

- [ ] **Step 1: 写失败测试**（在 `src/test_release.py` 的 `def run_suite():` 之前追加）

```python
def test_notes_file_written_and_absent_without_flag():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    import shutil
    nf = os.path.join(root, "dist", "NOTES_T1.md")
    shutil.rmtree(os.path.join(root, "dist"), ignore_errors=True)
    r = _run_release(["v9.9.9", "--fast", "--notes-file", "dist/NOTES_T1.md"])
    assert r.returncode == 0, r.stdout + r.stderr
    assert os.path.isfile(nf)
    txt = open(nf, encoding="utf-8").read()
    assert "工资计算器（中国）v9.9.9" in txt
    assert "工资计算器（中国）_v9.9.9.html" in txt and "工资计算器（中国）_v9.9.9.zip" in txt
    # 省略 --notes-file 时不应写出该文件
    shutil.rmtree(os.path.join(root, "dist"), ignore_errors=True)
    r2 = _run_release(["v9.9.9", "--fast"])
    assert r2.returncode == 0, r2.stdout + r2.stderr
    assert not os.path.exists(nf)
    shutil.rmtree(os.path.join(root, "dist"), ignore_errors=True)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python src/test_release.py`
Expected: FAIL — `test_notes_file_written_and_absent_without_flag`（未知参数 `--notes-file`，argparse 报错 → returncode 2，断言 `== 0` 失败）

- [ ] **Step 3: 写实现**（`src/release.py` 内，`main()` 的 `--fast` 参数行之后加一个参数，并在 `build_dist` 调用之后、`return 0` 之前加写文件逻辑）

`main()` 里在 `ap.add_argument("--fast", ...)` 之后插入：

```python
    ap.add_argument("--notes-file", dest="notes_file", default=None,
                    help="also write the release notes to this file (used by CI)")
```

在 `html_name, zip_name = build_dist(root, ns.version)` 之后、`print("已产出 ...")` 之前插入：

```python
    if ns.notes_file:
        notes_path = ns.notes_file if os.path.isabs(ns.notes_file) else os.path.join(root, ns.notes_file)
        os.makedirs(os.path.dirname(notes_path), exist_ok=True)
        with open(notes_path, "w", encoding="utf-8") as fh:
            fh.write(render_release_notes(ns.version, html_name, zip_name))
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python src/test_release.py`
Expected: 全部 `ok`，末行 `... 0 failed`（含新用例）

- [ ] **Step 5: Commit**

```bash
git add src/release.py src/test_release.py
git commit -m "feat(release): add --notes-file to emit release notes for CI"
```

---

## Task 2: gitee_release.py 纯逻辑函数

**Files:**
- Create: `src/gitee_release.py`
- Create: `src/test_gitee_release.py`

- [ ] **Step 1: 写失败测试**（新建 `src/test_gitee_release.py`，仅放版权头 + 纯逻辑用例 + 复用式 run_suite）

```python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 bob3703
# Licensed under the Apache License, Version 2.0. See the LICENSE file for the full text.
"""test_gitee_release.py — offline guard for the pure logic of src/gitee_release.py.

Network integration is deliberately out of the default path: the upload_asset/attach
contract against the live Gitee API is validated on first CI run (see spec). Tests that
would require a token are guarded by skipUnless(GITEE_TOKEN).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gitee_release as gr  # noqa: E402


def test_build_api_url_and_base():
    assert gr.API_BASE == "https://gitee.com/api/v5"
    assert gr.build_api_url("releases", owner="o", repo="r") == \
        "https://gitee.com/api/v5/repos/o/r/releases"


def test_create_payload_fields():
    p = gr.create_payload(access_token="TK", tag_name="v1.2", name="T", body="B",
                          target_commitish="master")
    assert p == {"access_token": "TK", "tag_name": "v1.2", "name": "T", "body": "B",
                 "target_commitish": "master", "prerelease": "false"}


def test_select_upload_url_and_headers():
    j = {"url": "https://obs/x?sig=1", "headers": {"x-obs-acl": "publicread", "Content-Type": "application/octet-stream"}}
    url, headers = gr.select_upload_url(j)
    assert url == "https://obs/x?sig=1"
    assert headers["x-obs-acl"] == "publicread"


def test_public_asset_url_strips_signature_query():
    assert gr.public_asset_url("https://obs/x/a.zip?sig=1&a=2") == "https://obs/x/a.zip"


def test_extract_release_id_prefers_id_then_nested():
    assert gr.extract_release_id({"id": 5, "tag_name": "v1"}) == 5
    assert gr.extract_release_id({"release": {"id": 7}}) == 7
    assert gr.extract_release_id({"data": {"id": 9}}) == 9


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python src/test_gitee_release.py`
Expected: FAIL / `ModuleNotFoundError: No module named 'gitee_release'`

- [ ] **Step 3: 写实现**（新建 `src/gitee_release.py` 的纯逻辑部分；本任务只到 `extract_release_id`，网络函数在 Task 3 追加）

```python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 bob3703
# Licensed under the Apache License, Version 2.0. See the LICENSE file for the full text.
"""gitee_release.py — publish Release assets to a Gitee 发行版 via Gitee API v5.

Stdlib only (urllib). Credentials come from env vars GITEE_TOKEN/GITEE_OWNER/GITEE_REPO
so a token never appears in argv or on disk. Designed to be soft-fail: CI wraps this in a
step with continue-on-error, so a Gitee hiccup never blocks the GitHub Release. The OBS
attach-registration contract is best-effort and validated on first CI run (see spec
docs/superpowers/specs/2026-10-05-release-github-actions-design.md).
"""
import os
import urllib.parse

API_BASE = "https://gitee.com/api/v5"


def build_api_url(path, owner=None, repo=None):
    """Compose a Gitee v5 URL. path is like 'releases' or 'releases/123'."""
    base = API_BASE
    if owner and repo:
        base = "%s/repos/%s/%s" % (base, owner, repo)
    return "%s/%s" % (base, path.strip("/"))


def create_payload(access_token, tag_name, name, body, target_commitish):
    """Build the POST body for creating a release."""
    return {
        "access_token": access_token,
        "tag_name": tag_name,
        "name": name,
        "body": body,
        "target_commitish": target_commitish,
        "prerelease": "false",
    }


def select_upload_url(upload_json):
    """From a upload_url response {url, headers} return (url, headers)."""
    return upload_json["url"], upload_json.get("headers", {})


def public_asset_url(obs_put_url):
    """Strip the signature query so the object is addressable as a public attachment."""
    return obs_put_url.split("?", 1)[0]


def extract_release_id(release_json):
    """Return the numeric release id from a Gitee release payload, tolerating a few shapes."""
    if not isinstance(release_json, dict):
        return None
    for key in ("id",):
        if key in release_json:
            return release_json[key]
    for wrap in ("release", "data"):
        inner = release_json.get(wrap)
        if isinstance(inner, dict) and "id" in inner:
            return inner["id"]
    return None


# --- network + CLI appended in Task 3 ---
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python src/test_gitee_release.py`
Expected: 5 tests `ok`（`Ran 5 tests ... OK`）

- [ ] **Step 5: Commit**

```bash
git add src/gitee_release.py src/test_gitee_release.py
git commit -m "feat(gitee): add pure-logic Gitee API helpers with offline unit tests"
```

---

## Task 3: gitee_release.py 网络调用与 CLI

**Files:**
- Modify: `src/gitee_release.py`（替换末尾 `# --- network + CLI appended in Task 3 ---` 占位注释）
- Modify: `src/test_gitee_release.py`

- [ ] **Step 1: 写失败测试**（在 `if __name__ == "__main__":` 之前追加无 token 跳过用例）

```python
def test_missing_token_skips_with_zero_exit(monkeypatch=None):
    import subprocess
    env = dict(os.environ)
    env.pop("GITEE_TOKEN", None)
    env["GITEE_OWNER"] = "o"; env["GITEE_REPO"] = "r"
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gitee_release.py")
    r = subprocess.run([sys.executable, path, "publish", "--tag", "v1", "--title", "T",
                        "--notes-file", "x", "--assets"],
                       capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "跳过" in r.stdout
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python src/test_gitee_release.py`
Expected: FAIL — `publish` 子命令尚不存在（argparse 报错 / returncode 非 0）

- [ ] **Step 3: 写实现**（把 `src/gitee_release.py` 末尾的 `# --- network + CLI appended in Task 3 ---` 整行替换为下列代码）

```python
import argparse
import json
import mimetypes
import sys
import urllib.request


def _http_json(url, method="GET", data=None, headers=None, timeout=30):
    """Send a JSON request; return parsed JSON dict. data is a dict (form) or bytes."""
    hdrs = {"Accept": "application/json"}
    if headers:
        hdrs.update(headers)
    body = None
    if isinstance(data, dict):
        body = urllib.parse.urlencode(data).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/x-www-form-urlencoded")
    elif isinstance(data, (bytes, bytearray)):
        body = bytes(data)
    req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", "replace")
    return json.loads(raw) if raw.strip() else {}


def upload_asset(owner, repo, tag, token, local_path):
    """Upload one file to the tag's release via the OBS presigned url; return public url.

    NOTE: whether the attachment auto-registers after the OBS PUT (x-obs-callback) or
    needs an extra associate call is undocumented; here we PUT and rely on callback.
    Validated on first CI run — if the asset is missing, add the associate step here.
    """
    j = _http_json(build_api_url("releases/%s/upload_url" % tag, owner=owner, repo=repo)
                   + "?access_token=%s" % token)
    put_url, headers = select_upload_url(j)
    with open(local_path, "rb") as fh:
        blob = fh.read()
    headers = dict(headers)
    headers.setdefault("Content-Type",
                       mimetypes.guess_type(local_path)[0] or "application/octet-stream")
    req = urllib.request.Request(put_url, data=blob, headers=headers, method="PUT")
    urllib.request.urlopen(req, timeout=120).read()
    return public_asset_url(put_url)


def _env_creds():
    return (os.environ.get("GITEE_TOKEN"), os.environ.get("GITEE_OWNER"),
            os.environ.get("GITEE_REPO"))


def cmd_delete(args):
    token, owner, repo = _env_creds()
    if not token:
        print("跳过 Gitee：未配置 GITEE_TOKEN")
        return 0
    try:
        detail = _http_json(build_api_url("releases/tags/%s" % args.tag, owner=owner, repo=repo)
                            + "?access_token=%s" % token)
        rid = extract_release_id(detail)
        if rid is None:
            print("Gitee：未找到 tag %s 对应发行版，无需删除" % args.tag)
            return 0
        _http_json(build_api_url("releases/%s" % rid, owner=owner, repo=repo)
                   + "?access_token=%s" % token, method="DELETE")
        print("Gitee：已删除发行版 id=%s" % rid)
        return 0
    except Exception as e:  # soft-fail: CI step uses continue-on-error
        print("Gitee delete 失败（软处理）：%s" % e)
        return 1


def cmd_publish(args):
    token, owner, repo = _env_creds()
    if not token:
        print("跳过 Gitee：未配置 GITEE_TOKEN")
        return 0
    body = ""
    if args.notes_file and os.path.isfile(args.notes_file):
        body = open(args.notes_file, encoding="utf-8").read()
    try:
        _http_json(build_api_url("releases", owner=owner, repo=repo),
                   method="POST", data=create_payload(token, args.tag, args.title, body,
                                                       args.commitish))
        print("Gitee：已创建发行版 %s" % args.tag)
        for path in args.assets:
            url = upload_asset(owner, repo, args.tag, token, path)
            print("Gitee：已上传附件 %s -> %s" % (os.path.basename(path), url))
        return 0
    except Exception as e:
        print("Gitee publish 失败（软处理，GitHub Release 不受影响）：%s" % e)
        return 1


def main(argv=None):
    ap = argparse.ArgumentParser(prog="gitee_release", description="Publish to a Gitee 发行版 (env GITEE_TOKEN/OWNER/REPO).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    dp = sub.add_parser("delete", help="delete the release for a tag (overwrite support)")
    dp.add_argument("--tag", required=True)
    pp = sub.add_parser("publish", help="create release + upload assets")
    pp.add_argument("--tag", required=True)
    pp.add_argument("--title", required=True)
    pp.add_argument("--notes-file", dest="notes_file", default=None)
    pp.add_argument("--commitish", default="master")
    pp.add_argument("--assets", nargs="*", default=[])
    ns = ap.parse_args(argv)
    return cmd_delete(ns) if ns.cmd == "delete" else cmd_publish(ns)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python src/test_gitee_release.py`
Expected: 6 tests `ok`（新增的无 token 用例返回 0 且含「跳过」）

- [ ] **Step 5: Commit**

```bash
git add src/gitee_release.py src/test_gitee_release.py
git commit -m "feat(gitee): add network calls and publish/delete CLI with soft-fail"
```

---

## Task 4: release.yml 工作流 + 静态守卫

**Files:**
- Create: `.github/workflows/release.yml`
- Modify: `src/test_release.py`

- [ ] **Step 1: 写失败测试**（在 `src/test_release.py` 的 `def run_suite():` 之前追加）

```python
def test_release_workflow_wired():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    wf = os.path.join(root, ".github", "workflows", "release.yml")
    assert os.path.isfile(wf), "release.yml 不存在"
    txt = open(wf, encoding="utf-8").read()
    for needle in ["tags:", "'v*'", "node web/inline-config.mjs",
                   "git diff --exit-code -- web/index.html", "--fast",
                   "--notes-file", "gh release create", "--clobber",
                   "gitee_release.py publish", "continue-on-error",
                   "env.GITEE_TOKEN", "contents: write"]:
        assert needle in txt, "release.yml 缺少: " + needle
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python src/test_release.py`
Expected: FAIL — `release.yml 不存在`

- [ ] **Step 3: 写实现**（新建 `.github/workflows/release.yml`，完整内容）

```yaml
name: Release

# Tag-triggered auto-release: push a vX.Y[.Z] tag -> drift-check -> package ->
# GitHub Release (built-in gh) + optional Gitee 发行版 (soft-fail).
# Requires repo secret GITEE_TOKEN to publish to Gitee; absent = GitHub only.

on:
  push:
    tags: ['v*']

permissions:
  contents: write

jobs:
  release:
    runs-on: ubuntu-latest
    env:
      TAG: ${{ github.ref_name }}
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup node
        uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Setup python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Inline drift check
        run: |
          node web/inline-config.mjs
          node web/inline-compute.mjs
          node web/inline-xlsx.mjs
          if ! git diff --exit-code -- web/index.html; then
            echo "::error::内嵌副本漂移：源文件改了却未重跑内联。先本地跑 deploy-pages.bat check 再打 tag。"
            exit 1
          fi

      - name: Package dist (fast)
        run: python src/release.py "$TAG" --fast --notes-file dist/RELEASE_NOTES.md
        env:
          CSRELEASE_ALLOW_DIRTY: "1"

      - name: Publish GitHub Release (create or clobber-overwrite)
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          gh release create "$TAG" dist/*.html dist/*.zip \
            --title "工资计算器（中国）$TAG" --notes-file dist/RELEASE_NOTES.md \
          || { gh release upload "$TAG" dist/*.html dist/*.zip --clobber; \
               gh release edit "$TAG" --title "工资计算器（中国）$TAG" --notes-file dist/RELEASE_NOTES.md; }

      - name: Publish Gitee 发行版 (soft-fail)
        if: env.GITEE_TOKEN != ''
        continue-on-error: true
        env:
          GITEE_TOKEN: ${{ secrets.GITEE_TOKEN }}
          GITEE_OWNER: bob3703
          GITEE_REPO: salary-calculator
        run: |
          python src/gitee_release.py delete --tag "$TAG" || true
          python src/gitee_release.py publish --tag "$TAG" \
            --title "工资计算器（中国）$TAG" \
            --notes-file dist/RELEASE_NOTES.md \
            --assets dist/*.html dist/*.zip
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python src/test_release.py`
Expected: 全部 `ok`（含 `test_release_workflow_wired`）

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/release.yml src/test_release.py
git commit -m "ci(release): add tag-triggered GitHub Actions release workflow"
```

---

## Task 5: README 增补 + 全量回归

**Files:**
- Modify: `README.md`

- [ ] **Step 1: 在 README「📦 打包 Release 资产」小节末尾（那句 `--fast`/`.gitignore` 之后、其后的 `---` 之前）追加：**

```markdown

**推 tag 自动发布（GitHub + Gitee）**：新增 `.github/workflows/release.yml`，推送形如 `v3.11` 的标签即自动跑内联漂移检查→打包→建/覆盖 GitHub Release；若仓库配置了 `GITEE_TOKEN` Secret，则同步覆盖式发布 Gitee 发行版（Gitee 步骤为软失败，不阻断 GitHub）。同标签重跑会覆盖资产。Gitee 未配 token 时仅发 GitHub。OBS 附件登记细节以首次 CI 运行日志为准（见 `docs/superpowers/specs/2026-10-05-release-github-actions-design.md`）。
```

- [ ] **Step 2: 全量回归（逐条执行，均期望全绿）**

Run:
```bash
python src/test_gitee_release.py
python src/test_release.py
python src/test_deploy_gate.py
python src/test_xlsx_writer.py
python src/test_cli_smoke.py
node web/test-compute.js
```
Expected: Python 各套末行 `0 failed`；unittest `OK`；node `exit 0`；`test_deploy_gate.py` 仍全绿（未触碰 deploy-pages）。

- [ ] **Step 3: 本地发布路径 smoke（--notes-file 生效，不联网）**

Run: `python src/release.py v0.0.0 --fast --notes-file dist/RELEASE_NOTES.md`（前置 `$env:CSRELEASE_ALLOW_DIRTY="1"`）
Expected: 退出码 0；`dist/RELEASE_NOTES.md` 存在且含 `工资计算器（中国）v0.0.0`；随后 `python -c "import shutil;shutil.rmtree('dist',ignore_errors=True)"` 清理，`git status --porcelain` 为空。

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs(release): document tag-triggered GitHub+Gitee auto-release"
```

---

## Self-Review（作者自查，随计划交付）

- **Spec 覆盖**：`--notes-file`(T1)、Gitee 纯逻辑(T2)、网络+CLI+软失败(T3)、workflow 漂移检查/gh/gitee 步骤(T4)、README(T5)、两份测试(T2/T3/T4) → 覆盖 spec §3–§10。排除项（`--tag`/本地 gh/dispatch/第三方 action）无对应任务=正确。
- **占位符**：网络实现给全代码；唯一「不确定点」以诚实注释标注为 best-effort + CI 首跑验证，非空实现。
- **一致性**：`API_BASE`、`build_api_url`、`create_payload`、`select_upload_url`、`public_asset_url`、`extract_release_id` 在 T2 定义、T3 使用签名一致；T3 CLI 参数（`--tag/--title/--notes-file/--commitish/--assets`）与 T4 workflow 调用一致；`CSRELEASE_ALLOW_DIRTY=1` 与 release.py 现有实现一致；`gitee_release.py publish/delete` 命名与 T4/T5 一致。
- **可测性**：纯逻辑离线测；网络集成不进默认门禁；无 token 用例可离线跑（断言跳过 + 退出 0）。真实 Gitee 联调靠 CI 首跑（用户已选）。

