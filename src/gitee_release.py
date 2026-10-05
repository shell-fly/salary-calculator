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


import argparse
import json
import mimetypes
import sys
import urllib.request


def _http_json(url, method="GET", data=None, headers=None, timeout=30):
    """Send a JSON request; return parsed JSON dict. data is a dict (form) or bytes."""
    hdrs = {"Accept": "application/json"}
    if headers:
        hdrs.update(headers)
    body = None
    if isinstance(data, dict):
        body = urllib.parse.urlencode(data).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/x-www-form-urlencoded")
    elif isinstance(data, (bytes, bytearray)):
        body = bytes(data)
    req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", "replace")
    return json.loads(raw) if raw.strip() else {}


def upload_asset(owner, repo, tag, token, local_path):
    """Upload one file to the tag's release via the OBS presigned url; return public url.

    NOTE: whether the attachment auto-registers after the OBS PUT (x-obs-callback) or
    needs an extra associate call is undocumented; here we PUT and rely on callback.
    Validated on first CI run — if the asset is missing, add the associate step here.
    """
    j = _http_json(build_api_url("releases/%s/upload_url" % tag, owner=owner, repo=repo)
                   + "?access_token=%s" % token)
    put_url, headers = select_upload_url(j)
    with open(local_path, "rb") as fh:
        blob = fh.read()
    headers = dict(headers)
    headers.setdefault("Content-Type",
                       mimetypes.guess_type(local_path)[0] or "application/octet-stream")
    req = urllib.request.Request(put_url, data=blob, headers=headers, method="PUT")
    urllib.request.urlopen(req, timeout=120).read()
    return public_asset_url(put_url)


def _env_creds():
    return (os.environ.get("GITEE_TOKEN"), os.environ.get("GITEE_OWNER"),
            os.environ.get("GITEE_REPO"))


def cmd_delete(args):
    token, owner, repo = _env_creds()
    if not token:
        print("跳过 Gitee：未配置 GITEE_TOKEN")
        return 0
    try:
        detail = _http_json(build_api_url("releases/tags/%s" % args.tag, owner=owner, repo=repo)
                            + "?access_token=%s" % token)
        rid = extract_release_id(detail)
        if rid is None:
            print("Gitee：未找到 tag %s 对应发行版，无需删除" % args.tag)
            return 0
        _http_json(build_api_url("releases/%s" % rid, owner=owner, repo=repo)
                   + "?access_token=%s" % token, method="DELETE")
        print("Gitee：已删除发行版 id=%s" % rid)
        return 0
    except Exception as e:  # soft-fail: CI step uses continue-on-error
        print("Gitee delete 失败（软处理）：%s" % e)
        return 1


def cmd_publish(args):
    token, owner, repo = _env_creds()
    if not token:
        print("跳过 Gitee：未配置 GITEE_TOKEN")
        return 0
    body = ""
    if args.notes_file and os.path.isfile(args.notes_file):
        body = open(args.notes_file, encoding="utf-8").read()
    try:
        _http_json(build_api_url("releases", owner=owner, repo=repo),
                   method="POST", data=create_payload(token, args.tag, args.title, body,
                                                       args.commitish))
        print("Gitee：已创建发行版 %s" % args.tag)
        for path in args.assets:
            url = upload_asset(owner, repo, args.tag, token, path)
            print("Gitee：已上传附件 %s -> %s" % (os.path.basename(path), url))
        return 0
    except Exception as e:
        print("Gitee publish 失败（软处理，GitHub Release 不受影响）：%s" % e)
        return 1


def main(argv=None):
    ap = argparse.ArgumentParser(prog="gitee_release", description="Publish to a Gitee 发行版 (env GITEE_TOKEN/OWNER/REPO).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    dp = sub.add_parser("delete", help="delete the release for a tag (overwrite support)")
    dp.add_argument("--tag", required=True)
    pp = sub.add_parser("publish", help="create release + upload assets")
    pp.add_argument("--tag", required=True)
    pp.add_argument("--title", required=True)
    pp.add_argument("--notes-file", dest="notes_file", default=None)
    pp.add_argument("--commitish", default="master")
    pp.add_argument("--assets", nargs="*", default=[])
    ns = ap.parse_args(argv)
    return cmd_delete(ns) if ns.cmd == "delete" else cmd_publish(ns)


if __name__ == "__main__":
    sys.exit(main())
