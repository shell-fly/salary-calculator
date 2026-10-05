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
