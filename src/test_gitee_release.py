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
