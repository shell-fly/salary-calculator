# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 bob3703
# Licensed under the Apache License, Version 2.0. See the LICENSE file for the full text.
"""test_release.py — guard for the one-click Release packaging script (src/release.py)."""
import os
import re
import shutil
import subprocess
import sys
import zipfile

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


def _run_release(args, extra_env=None):
    env = dict(os.environ)
    env["CSRELEASE_ALLOW_DIRTY"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    if extra_env:
        env.update(extra_env)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    script = os.path.join(root, "src", "release.py")
    return subprocess.run([sys.executable, script] + args, cwd=root,
                          capture_output=True, text=True, env=env,
                          encoding="utf-8", errors="replace")


def test_fast_build_produces_dist_html_and_zip_byte_identical():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    html_name = "工资计算器（中国）_v9.9.9.html"
    zip_name = "工资计算器（中国）_v9.9.9.zip"
    dist = os.path.join(root, "dist")
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


def test_entry_scripts_forward_to_release_py_with_parity():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    bat = open(os.path.join(root, "release.bat"), encoding="utf-8").read()
    sh = open(os.path.join(root, "release.sh"), encoding="utf-8").read()
    assert "release.py" in bat and "%*" in bat
    assert "chcp 65001" in bat
    assert "release.py" in sh and '"$@"' in sh
    assert sh.startswith("#!/usr/bin/env bash")


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
    shutil.rmtree(os.path.join(root, "dist"), ignore_errors=True)
    r2 = _run_release(["v9.9.9", "--fast"])
    assert r2.returncode == 0, r2.stdout + r2.stderr
    assert not os.path.exists(nf)
    shutil.rmtree(os.path.join(root, "dist"), ignore_errors=True)


def test_release_workflow_wired():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    wf = os.path.join(root, ".github", "workflows", "release.yml")
    assert os.path.isfile(wf), "release.yml 不存在"
    txt = open(wf, encoding="utf-8").read()
    for needle in ["tags:", "'v*'", "node web/inline-config.mjs",
                   "git diff --exit-code -- web/index.html", "--fast",
                   "--notes-file", "gh release create", "--clobber",
                   "gitee_release.py publish", "continue-on-error",
                   "secrets.GITEE_TOKEN", "contents: write"]:
        assert needle in txt, "release.yml 缺少: " + needle


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
