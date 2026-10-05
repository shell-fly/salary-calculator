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
