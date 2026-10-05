# Release 一键打包脚本 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用一个命令产出「下载即可一键运行」的 Release 资产（单文件 `.html` + 完整发行 `.zip`），供手动上传到 GitHub Releases 与 Gitee 发行版。

**Architecture:** Python 3 标准库零依赖的 `src/release.py` 承载全部逻辑：校验版本号 → （可选）复用 deploy-pages 发布门禁 → 生成 `dist/` 产物 → 打印上传步骤与 Release 文案模板。`release.bat` / `release.sh` 仅作一键入口把参数转发给 Python。所有纯逻辑（版本校验、命名、zip 成员收集、文案渲染）拆成可导入函数，配套 `src/test_release.py` 守卫（仿 `test_deploy_gate.py`）。

**Tech Stack:** Python 3（标准库：`re`/`os`/`shutil`/`zipfile`/`subprocess`/`sys`/`argparse`）、Windows cmd（`.bat`）、POSIX shell（`.sh`）、`git` CLI。

设计依据：[`docs/superpowers/specs/2026-10-05-release-packaging-design.md`](../specs/2026-10-05-release-packaging-design.md)

---

## 关键约定（贯穿所有任务）

- **产物文件名用正式名全角括号**：`工资计算器（中国）_<version>.html` / `工资计算器（中国）_<version>.zip`。
- **版本正则**：`^v\d+\.\d+(\.\d+)?$`（`vX.Y` 或 `vX.Y.Z`）。
- **`--fast`**：跳过重型发布门禁（node 内联校验 + 三套断言）；仍做版本校验与工作树脏检查。供测试与调试。
- **环境变量 `CSRELEASE_ALLOW_DIRTY=1`**：跳过「工作树必须已提交」检查（主要给自动化/测试子进程）。
- **退出码**：用法/版本非法 → `2`；脏树或门禁失败 → `1`；成功 → `0`。
- **版权头**：每个新 `.py` 顶部
  ```python
  # -*- coding: utf-8 -*-
  # SPDX-License-Identifier: Apache-2.0
  # Copyright 2026 bob3703
  # Licensed under the Apache License, Version 2.0. See the LICENSE file for the full text.
  ```
  注释/docstring 用英文。
- **执行前请 `cd` 到仓库根 `china-salary-calculator/`**；下方所有 `Run:` 命令均在仓根执行。

## File Structure

- Create `src/release.py` — 全部逻辑，纯函数 + `main()`。
- Create `src/test_release.py` — 单元 + 集成守卫。
- Create `release.bat` — Windows 入口。
- Create `release.sh` — POSIX 入口。
- Modify `.gitignore` — 追加 `dist/`。
- Modify `README.md` — 增补「📦 打包 Release 资产」。

---

## Task 1: 版本校验函数 + .gitignore

**Files:**
- Create: `src/release.py`
- Create: `src/test_release.py`
- Modify: `.gitignore`

- [ ] **Step 1: 写失败测试**（`src/test_release.py` 新建，仅先放版权头 + 版本校验用例）

```python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 bob3703
# Licensed under the Apache License, Version 2.0. See the LICENSE file for the full text.
"""test_release.py — guard for the one-click Release packaging script (src/release.py)."""
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
import release  # noqa: E402


def test_validate_version_accepts_semver_with_v():
    assert release.validate_version("v3.11")
    assert release.validate_version("v3.11.0")


def test_validate_version_rejects_bad_forms():
    for bad in ["3.11", "v3", "v3.11.0.1", "vX", "v", "", "v3.x", "v3.11-beta"]:
        assert not release.validate_version(bad), bad


def run_suite():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    fails = 0
    for fn in fns:
        try:
            fn()
            print("ok  " + fn.__name__)
        except AssertionError as e:
            fails += 1
            print("FAIL " + fn.__name__ + ": " + str(e))
    print("%d passed, %d failed" % (len(fns) - fails, fails))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(run_suite())
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python src/test_release.py`
Expected: FAIL / 报错 `ModuleNotFoundError: No module named 'release'`（release.py 尚不存在）

- [ ] **Step 3: 写最小实现**（新建 `src/release.py`）

```python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 bob3703
# Licensed under the Apache License, Version 2.0. See the LICENSE file for the full text.
"""release.py — one-click packaging of Release assets for 工资计算器（中国）.

Produces dist/<product>_<version>.html (a byte-for-byte copy of web/index.html)
and dist/<product>_<version>.zip (a full portable bundle), then prints the manual
upload steps for GitHub Releases and Gitee 发行版 plus a ready-to-paste release note.
Stdlib only. See docs/superpowers/specs/2026-10-05-release-packaging-design.md.
"""
import re

PRODUCT_NAME = "工资计算器（中国）"
VERSION_RE = re.compile(r"^v\d+\.\d+(\.\d+)?$")


def validate_version(version):
    """Return True if version matches vX.Y or vX.Y.Z."""
    return bool(VERSION_RE.match(version or ""))
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python src/test_release.py`
Expected: `2 passed, 0 failed`，退出码 0

- [ ] **Step 5: 追加 .gitignore 的 dist/**

在 `.gitignore` 末尾（`.DS_Store` 之后）新增：

```
# Release packaging output
dist/
```

- [ ] **Step 6: 验证 gitignore 生效**

Run: `git check-ignore dist`
Expected: 输出 `dist`（命中忽略规则）

- [ ] **Step 7: Commit**

```bash
git add src/release.py src/test_release.py .gitignore
git commit -m "feat(release): add version validation and ignore dist/ output"
```

---

## Task 2: 产物命名 + zip 成员收集（纯逻辑）

**Files:**
- Modify: `src/release.py`
- Modify: `src/test_release.py`

- [ ] **Step 1: 写失败测试**（在 `run_suite` 之前追加）

```python
def test_build_names_use_product_and_version():
    html, zp = release.build_names("v3.11")
    assert html == "工资计算器（中国）_v3.11.html"
    assert zp == "工资计算器（中国）_v3.11.zip"


def test_collect_zip_members_has_required_and_excludes_dev():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    members = set(release.collect_zip_members(root))
    required = {"web/index.html", "web/manifest.webmanifest", "web/sw.js",
                "src/salary_calculator.py", "src/xlsx_writer.py", "src/xlsx_report.py",
                "config.json", "shanghai_config.json", "run.bat", "run.sh",
                "README.md", "LICENSE"}
    assert required <= members, required - members
    assert any(m.startswith("web/icons/") for m in members)
    forbidden_prefix = ("docs/", ".github/", "dist/", "src/test_", "web/inline-")
    forbidden_exact = {"web/compute.js", "web/test-compute.js", "web/package.json",
                       "web/gen-icons.ps1", "web/xlsx-sample.mjs"}
    for m in members:
        assert not m.startswith(forbidden_prefix), m
        assert m not in forbidden_exact, m
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python src/test_release.py`
Expected: FAIL `AttributeError: module 'release' has no attribute 'build_names'`

- [ ] **Step 3: 写实现**（在 `validate_version` 之后追加）

```python
# Root-level files shipped in the zip bundle.
ROOT_FILES = ["config.json", "shanghai_config.json", "run.bat", "run.sh",
              "README.md", "LICENSE"]
# web/ runtime files (exclude dev/build scripts).
WEB_FILES = ["web/index.html", "web/manifest.webmanifest", "web/sw.js"]
# src/ runtime modules (exclude tests).
SRC_FILES = ["src/salary_calculator.py", "src/xlsx_writer.py", "src/xlsx_report.py"]
WEB_ICON_DIR = "web/icons"


def build_names(version):
    """Return (html_name, zip_name) for a validated version string."""
    base = "%s_%s" % (PRODUCT_NAME, version)
    return base + ".html", base + ".zip"


def _posix(p):
    return p.replace(os.sep, "/")


def collect_zip_members(repo_root):
    """Return repo-root-relative POSIX paths to include in the release zip."""
    import os
    members = []
    for rel in ROOT_FILES + WEB_FILES + SRC_FILES:
        if os.path.isfile(os.path.join(repo_root, rel.replace("/", os.sep))):
            members.append(rel)
    icon_dir = os.path.join(repo_root, WEB_ICON_DIR.replace("/", os.sep))
    if os.path.isdir(icon_dir):
        for name in sorted(os.listdir(icon_dir)):
            full = os.path.join(icon_dir, name)
            if os.path.isfile(full):
                members.append(_posix(os.path.join(WEB_ICON_DIR, name)))
    return members
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python src/test_release.py`
Expected: `4 passed, 0 failed`

- [ ] **Step 5: Commit**

```bash
git add src/release.py src/test_release.py
git commit -m "feat(release): add product naming and zip member collection"
```

---

## Task 3: Release 文案与上传步骤渲染（纯逻辑）

**Files:**
- Modify: `src/release.py`
- Modify: `src/test_release.py`

- [ ] **Step 1: 写失败测试**（追加）

```python
def test_render_release_notes_contains_version_and_both_assets():
    txt = release.render_release_notes("v3.11", "工资计算器（中国）_v3.11.html",
                                       "工资计算器（中国）_v3.11.zip")
    assert "工资计算器（中国）v3.11" in txt
    assert "工资计算器（中国）_v3.11.html" in txt
    assert "工资计算器（中国）_v3.11.zip" in txt
    assert "Apache License 2.0" in txt or "Apache-2.0" in txt


def test_render_upload_steps_mentions_both_platforms():
    txt = release.render_upload_steps("v3.11")
    assert "GitHub" in txt and "Gitee" in txt
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python src/test_release.py`
Expected: FAIL `AttributeError: ... has no attribute 'render_release_notes'`

- [ ] **Step 3: 写实现**（追加）

```python
def render_release_notes(version, html_name, zip_name):
    """Return a paste-ready Release description (Chinese, matching README wording)."""
    return (
        "## 工资计算器（中国）%s\n\n"
        "8 城市 × 2023–2026 四个社保年度 × 半年度的五险一金 + 个税 + 年终奖 + 汇算清缴计算器。\n"
        "支持可自定义申报基数、逐月不同薪资、年终奖双方案对比、反推税前、CSV/Excel 导出（均零第三方依赖）。\n\n"
        "### 下载即用 / Get started\n"
        "1. **单文件免安装**：下载 `%s`，任意设备双击用浏览器打开即可，离线可用、零安装。\n"
        "2. **完整发行包**：下载并解压 `%s`，Windows 双击 `run.bat`、macOS/Linux 运行 `bash run.sh`（CLI 需 Python 3）。\n\n"
        "> 免责声明：本工具仅供演示与参考，权威数值以税务局、社保及公积金管理部门公布为准。\n"
        "> License：Apache License 2.0。\n"
    ) % (version, html_name, zip_name)


def render_upload_steps(version):
    """Return the manual upload instructions for GitHub Releases and Gitee."""
    return (
        "\n──────── 上传到 GitHub Releases ────────\n"
        "  1) 仓库页 → Releases → Draft a new release\n"
        "  2) Choose tag: 建议先 `git tag %s && git push github %s`（本脚本不代为打 tag）\n"
        "  3) 上传 dist/ 下的 .html 与 .zip 两个资产文件，粘贴 Release 文案，Publish\n"
        "\n──────── 上传到 Gitee 发行版 ────────\n"
        "  1) 仓库页 → 管理 → 发行版 → 新建发行版\n"
        "  2) 标签填 %s，上传 dist/ 下的 .html 与 .zip，保存发布\n"
    ) % (version, version, version)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python src/test_release.py`
Expected: `6 passed, 0 failed`

- [ ] **Step 5: Commit**

```bash
git add src/release.py src/test_release.py
git commit -m "feat(release): render release notes and upload steps"
```

---

## Task 4: 发布门禁封装 + 脏树检查 + dist 产出

**Files:**
- Modify: `src/release.py`
- Modify: `src/test_release.py`

- [ ] **Step 1: 写失败测试**（追加，用 `--fast` + 隔离 env 做端到端，只验证产物不跑重型门禁）

```python
import tempfile
import zipfile


def _run_release(args, extra_env=None):
    env = dict(os.environ)
    env["CSRELEASE_ALLOW_DIRTY"] = "1"
    if extra_env:
        env.update(extra_env)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    script = os.path.join(root, "src", "release.py")
    return subprocess.run([sys.executable, script] + args, cwd=root,
                          capture_output=True, text=True, env=env)


def test_fast_build_produces_dist_html_and_zip_byte_identical():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    html_name = "工资计算器（中国）_v9.9.9.html"
    zip_name = "工资计算器（中国）_v9.9.9.zip"
    dist = os.path.join(root, "dist")
    import shutil
    shutil.rmtree(dist, ignore_errors=True)
    r = _run_release(["v9.9.9", "--fast"])
    assert r.returncode == 0, r.stdout + r.stderr
    src_html = os.path.join(root, "web", "index.html")
    out_html = os.path.join(dist, html_name)
    with open(src_html, "rb") as a, open(out_html, "rb") as b:
        assert a.read() == b.read()
    assert os.path.isfile(os.path.join(dist, zip_name))
    with zipfile.ZipFile(os.path.join(dist, zip_name)) as z:
        names = set(z.namelist())
    assert "web/index.html" in names and "src/salary_calculator.py" in names
    shutil.rmtree(dist, ignore_errors=True)


def test_invalid_version_exits_two():
    r = _run_release(["3.11", "--fast"])
    assert r.returncode == 2, (r.returncode, r.stdout, r.stderr)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python src/test_release.py`
Expected: FAIL（release.py 无 `__main__`，returncode != 0）

- [ ] **Step 3: 写实现**（在 `src/release.py` 追加，含门禁、脏树、dist 与 main）

```python
import os
import shutil
import subprocess
import sys
import zipfile


def repo_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def check_worktree_clean(root):
    if os.environ.get("CSRELEASE_ALLOW_DIRTY") == "1":
        return
    r = subprocess.run(["git", "status", "--porcelain"], cwd=root,
                       capture_output=True, text=True)
    if r.stdout.strip():
        print("失败: 工作树有未提交改动，本脚本不代为提交。请先 git commit 或设 CSRELEASE_ALLOW_DIRTY=1。")
        for line in r.stdout.strip().splitlines():
            print("  ! " + line)
        sys.exit(1)


def run_gate(root):
    """Reuse the deploy-pages gate. Missing node/python are skipped like deploy scripts."""
    def _run(cmd):
        r = subprocess.run(cmd, cwd=root)
        if r.returncode != 0:
            print("失败: 门禁未通过 -> " + " ".join(cmd))
            sys.exit(1)

    def _has(exe):
        return shutil.which(exe) is not None

    html_was_clean = subprocess.run(["git", "diff", "--quiet", "--", "web/index.html"],
                                    cwd=root).returncode == 0
    if _has("node"):
        _run(["node", "web/inline-config.mjs"])
        _run(["node", "web/inline-compute.mjs"])
        _run(["node", "web/inline-xlsx.mjs"])
        if html_was_clean and subprocess.run(
                ["git", "diff", "--quiet", "--", "web/index.html"], cwd=root).returncode != 0:
            print("失败: 内嵌副本漂移，index.html 交付的是旧副本。请提交 web/index.html 后重试。")
            sys.exit(1)
        _run(["node", "web/test-compute.js"])
    else:
        print("! 未检测到 node，跳过内联/引擎门禁")
    py = "python" if _has("python") else ("python3" if _has("python3") else None)
    if py:
        _run([py, "src/test_xlsx_writer.py"])
        _run([py, "src/test_cli_smoke.py"])
    else:
        print("! 未检测到 python，跳过 xlsx/CLI 门禁")


def build_dist(root, version):
    html_name, zip_name = build_names(version)
    dist = os.path.join(root, "dist")
    shutil.rmtree(dist, ignore_errors=True)
    os.makedirs(dist, exist_ok=True)
    shutil.copyfile(os.path.join(root, "web", "index.html"),
                    os.path.join(dist, html_name))
    zip_path = os.path.join(dist, zip_name)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in sorted(collect_zip_members(root)):
            z.write(os.path.join(root, rel.replace("/", os.sep)), rel)
    return html_name, zip_name


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog="release", description="Package Release assets (see spec 2026-10-05).")
    ap.add_argument("version", help="release version, e.g. v3.11")
    ap.add_argument("--fast", action="store_true", help="skip heavy publish gate (dev/test only)")
    ns = ap.parse_args(argv)
    if not validate_version(ns.version):
        print("用法: release <vX.Y|.Z>  (版本号须以 v 开头，如 v3.11)")
        sys.exit(2)
    root = repo_root()
    check_worktree_clean(root)
    if not ns.fast:
        run_gate(root)
    html_name, zip_name = build_dist(root, ns.version)
    print("已产出 dist/%s 与 dist/%s" % (html_name, zip_name))
    print(render_release_notes(ns.version, html_name, zip_name))
    print(render_upload_steps(ns.version))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python src/test_release.py`
Expected: `8 passed, 0 failed`

- [ ] **Step 5: Commit**

```bash
git add src/release.py src/test_release.py
git commit -m "feat(release): add gate reuse, dist build and CLI entry"
```

---

## Task 5: .bat / .sh 一键入口 + 双入口一致性守卫

**Files:**
- Create: `release.bat`
- Create: `release.sh`
- Modify: `src/test_release.py`

- [ ] **Step 1: 写失败测试**（追加，防历史出现过的双入口漂移；至少都引用 release.py 与版本提示）

```python
def test_entry_scripts_reference_release_py_and_version():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    bat = open(os.path.join(root, "release.bat"), encoding="utf-8").read()
    sh = open(os.path.join(root, "release.sh"), encoding="utf-8").read()
    for txt, name in [(bat, "release.bat"), (sh, "release.sh")]:
        assert "release.py" in txt, name
        assert "65001" in txt or "#!/usr/bin/env bash" in txt, name
        assert "chcp 65001" in bat
        assert "--help" in bat or "release.py" in bat  # forwards args
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python src/test_release.py`
Expected: FAIL（release.bat / release.sh 不存在，FileNotFoundError）

- [ ] **Step 3: 写实现**（新建 `release.bat`）

```bat
@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
python src\release.py %*
if errorlevel 1 exit /b %ERRORLEVEL%
```

新建 `release.sh`：

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if command -v python3 >/dev/null 2>&1; then
  exec python3 src/release.py "$@"
else
  exec python src/release.py "$@"
fi
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python src/test_release.py`
Expected: `9 passed, 0 failed`

- [ ] **Step 5: 给 release.sh 加可执行位**（Windows 提交由 git 记录 mode）

Run: `git add release.bat release.sh; git update-index --chmod=+x release.sh`
Expected: 无报错

- [ ] **Step 6: Commit**

```bash
git add release.bat release.sh src/test_release.py
git commit -m "feat(release): add one-click .bat/.sh entry points with parity guard"
```

---

## Task 6: README 增补 + 全量回归

**Files:**
- Modify: `README.md`

- [ ] **Step 1: 在 README「🌐 部署为网址 & PWA 安装」小节之后新增一节**

````markdown
## 📦 打包 Release 资产 / Package Release Assets

一个命令产出可挂到 GitHub Releases / Gitee 发行版的「下载即运行」文件（纯本地，不代提交、不自动打 tag）：

```bash
# Windows
release.bat v3.11
# macOS / Linux / Termux
bash release.sh v3.11
```

产出到 `dist/`：
- `工资计算器（中国）_v3.11.html` — 单文件免安装，任意设备双击用浏览器打开即可（离线、零依赖）。
- `工资计算器（中国）_v3.11.zip` — 完整发行包（Web + CLI + 配置 + 运行脚本 + LICENSE）。

脚本会先复用发布门禁（内联一致性 + 计算引擎/Excel/CLI 断言），通过后打印两平台上传步骤与可直接粘贴的 Release 文案。加 `--fast` 可跳过重型门禁（仅供调试）。`dist/` 已被 `.gitignore` 忽略。
````

- [ ] **Step 2: 全量回归（发布物与被测引擎一致，确保没改坏既有门禁）**

Run（逐条执行，均期望全绿）：
```bash
python src/test_release.py
python src/test_deploy_gate.py
python src/test_xlsx_writer.py
python src/test_cli_smoke.py
```
Expected: 各自末尾 `0 failed`；`test_deploy_gate.py` 仍全绿（本改动未触碰 deploy-pages）。

- [ ] **Step 3: 手动 smoke（真实跑一次完整发布路径）**

Run: `python src/release.py v0.0.0 --fast`
Expected: `dist/` 下生成两个文件并打印文案；`git check-ignore dist` 命中（产物不入库）。
清理：`python -c "import shutil; shutil.rmtree('dist', ignore_errors=True)"`

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs(release): document one-click release packaging"
```

---

## Self-Review（作者自查，随计划交付）

- **Spec 覆盖**：版本校验(T1)、命名/zip 成员(T2)、文案模板(T3)、脏树+门禁+dist(T4)、双入口(T5)、README/回归(T6) → 覆盖 spec §3–§9。tag/远程/exe 属 spec §1 明确排除项，无对应任务=正确。
- **占位符**：无 TBD/“add error handling”；每个代码步都给完整代码。
- **类型/命名一致**：`validate_version` / `build_names` / `collect_zip_members` / `render_release_notes` / `render_upload_steps` / `run_gate` / `check_worktree_clean` / `build_dist` / `main` 在各任务间签名一致；`build_names` 返回 `(html_name, zip_name)` 与 T4 `build_dist` 解包一致；`collect_zip_members` 返回相对 POSIX 路径，T2 断言与 T4 zip 写入一致。
- **可测试性**：`--fast` + `CSRELEASE_ALLOW_DIRTY=1` 让集成测试不依赖 node、不因仓库存在未提交的 spec/plan 而误停；重型门禁仍在正常发布路径（不加 `--fast`）执行。
