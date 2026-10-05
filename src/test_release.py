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
