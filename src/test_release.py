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
