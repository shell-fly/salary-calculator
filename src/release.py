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
import os
import re
import shutil
import subprocess
import sys
import zipfile

PRODUCT_NAME = "工资计算器（中国）"
VERSION_RE = re.compile(r"^v\d+\.\d+(\.\d+)?$")


def validate_version(version):
    """Return True if version matches vX.Y or vX.Y.Z."""
    return bool(VERSION_RE.match(version or ""))


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
    ap.add_argument("--notes-file", dest="notes_file", default=None,
                    help="also write the release notes to this file (used by CI)")
    ns = ap.parse_args(argv)
    if not validate_version(ns.version):
        print("用法: release <vX.Y|.Z>  (版本号须以 v 开头，如 v3.11)")
        sys.exit(2)
    root = repo_root()
    check_worktree_clean(root)
    if not ns.fast:
        run_gate(root)
    html_name, zip_name = build_dist(root, ns.version)
    if ns.notes_file:
        notes_path = ns.notes_file if os.path.isabs(ns.notes_file) else os.path.join(root, ns.notes_file)
        os.makedirs(os.path.dirname(notes_path), exist_ok=True)
        with open(notes_path, "w", encoding="utf-8") as fh:
            fh.write(render_release_notes(ns.version, html_name, zip_name))
    print("已产出 dist/%s 与 dist/%s" % (html_name, zip_name))
    print(render_release_notes(ns.version, html_name, zip_name))
    print(render_upload_steps(ns.version))
    return 0


if __name__ == "__main__":
    sys.exit(main())
