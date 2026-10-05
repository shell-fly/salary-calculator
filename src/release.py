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
