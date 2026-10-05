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
