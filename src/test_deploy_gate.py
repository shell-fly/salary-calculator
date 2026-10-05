# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 bob3703
# Licensed under the Apache License, Version 2.0. See the LICENSE file for the full text.
"""
test_deploy_gate.py — guard for the one-command deploy gate (deploy-pages.bat / deploy-pages.sh).

Part of 工资计算器（中国）/ china-salary-calculator.

Why this exists: `deploy-pages.bat` printed 失败 for every check yet still returned exit code 0,
because `exit /b 1` written *inside a parenthesized cmd block* loses its code (measured on this
machine: block-scoped exit -> 0, one-line nested block inside `else` -> 0, top-level single-line
exit -> 1). A gate that cannot fail is not a gate — `deploy-pages.bat && …` and any CI reading
its status would have shipped anyway. These checks reproduce the pitfall (a failing path must
exit non-zero), keep the new `check` mode side-effect free, and pin the .bat/.sh wording parity
that had silently diverged (the .sh still said 345/17 after the .bat moved on).

This suite is deliberately NOT wired into deploy-pages.bat/.sh: the gate would then launch
itself recursively. Children spawned here carry DEPLOY_GATE_NO_RECURSION=1 so that if someone
does add it later, the "run the real gate" cases downgrade to a skip instead of looping.

Run: python src/test_deploy_gate.py
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
BAT = os.path.join(REPO, "deploy-pages.bat")
SH = os.path.join(REPO, "deploy-pages.sh")

FAILURES = []


def check(ok, msg, detail=""):
    if ok:
        print(f"  PASS: {msg}")
    else:
        print(f"  FAIL: {msg} {detail}")
        FAILURES.append(msg)


def run(cmd, cwd, extra_env=None):
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["DEPLOY_GATE_NO_RECURSION"] = "1"
    if extra_env:
        env.update(extra_env)
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=env)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def find_bash():
    """Prefer Git Bash; the Windows system32 bash is the WSL launcher whose view of these
    Windows paths (and missing node/python) would make the gate results meaningless."""
    candidates = (r"D:\Program Files\Git\bin\bash.exe",
                  r"C:\Program Files\Git\bin\bash.exe",
                  shutil.which("bash"))
    for candidate in candidates:
        if not candidate or not os.path.exists(candidate):
            continue
        if "system32" in candidate.lower():
            continue
        return candidate
    return None


def lint_no_block_scoped_exit(path):
    """Return lines where `exit /b` sits inside a block — such exits lose their code in cmd."""
    offenders = []
    with open(path, encoding="utf-8", errors="replace") as handle:
        for number, line in enumerate(handle, 1):
            lowered = line.lower()
            if "exit /b" not in lowered:
                continue
            stripped = line.strip()
            if stripped.startswith(("rem ", "::")):
                continue
            indented = line[:1] in (" ", "\t")
            inline_group = re.search(r"\([^()]*exit\s+/b", lowered)
            if indented or inline_group:
                offenders.append(f"{os.path.basename(path)}:{number}: {stripped}")
    return offenders


def temp_git_repo(script_path):
    """A repo holding only the gate script, so step [1/5] must fail (and must report it as exit 1)."""
    workdir = tempfile.mkdtemp(prefix="deploy_gate_")
    try:
        shutil.copyfile(script_path, os.path.join(workdir, os.path.basename(script_path)))
        subprocess.run(["git", "init", "-q"], cwd=workdir, capture_output=True)
        return workdir
    except Exception:
        shutil.rmtree(workdir, ignore_errors=True)
        return None


def committed_temp_repo(script_path):
    """A temp repo with one committed file plus one uncommitted file, i.e. a dirty work tree."""
    workdir = temp_git_repo(script_path)
    if not workdir:
        return None
    with open(os.path.join(workdir, "seed.txt"), "w", encoding="utf-8") as handle:
        handle.write("seed\n")
    subprocess.run(["git", "add", "seed.txt"], cwd=workdir, capture_output=True)
    subprocess.run(["git", "-c", "user.email=t@example.com", "-c", "user.name=t",
                    "commit", "-q", "-m", "seed"], cwd=workdir, capture_output=True)
    with open(os.path.join(workdir, "uncommitted.txt"), "w", encoding="utf-8") as handle:
        handle.write("dirty\n")
    return workdir


def action_lines(text, pattern):
    """Lines that really execute something, ignoring echoes/rem comments used for help text."""
    hits = []
    for number, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        lowered = stripped.lower()
        if not lowered or lowered.startswith(("rem ", "::", "#")):
            continue
        first = lowered.split(" ")[0]
        if first in ("echo", "echo.", "printf") or lowered.startswith(("echo ", "rem", "::")):
            continue
        if re.search(pattern, lowered):
            hits.append(f"{number}: {stripped}")
    return hits


def git_head():
    proc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                          capture_output=True, text=True, encoding="utf-8")
    return proc.stdout.strip()


def porcelain(paths):
    proc = subprocess.run(["git", "status", "--porcelain"] + paths, cwd=REPO,
                          capture_output=True, text=True, encoding="utf-8")
    return proc.stdout.strip()


print("\n=== Gate shape: .bat must not rely on block-scoped exit codes ===")
for script in (BAT, SH):
    check(os.path.exists(script), f"{os.path.basename(script)} exists")
offenders = lint_no_block_scoped_exit(BAT) if os.path.exists(BAT) else ["file missing"]
check(not offenders, "no `exit /b` inside a cmd block (such exits return 0)",
      str(offenders[:3]))

# `something & goto :eof` leaves the previous errorlevel in place when it returns to the
# caller, so a skipped optional remote used to abort a publish that had already succeeded.
inline_jump = []
if os.path.exists(BAT):
    inline_jump = action_lines(open(BAT, encoding="utf-8", errors="replace").read(),
                               r"&\s*(goto|exit)\b")
check(not inline_jump, "no `& goto`/`& exit` inline groupings (they leak errorlevel)",
      str(inline_jump[:3]))

print("\n=== Gate wording: never quote a fact the gate did not measure ===")
if os.path.exists(BAT) and os.path.exists(SH):
    bat_text = open(BAT, encoding="utf-8", errors="replace").read()
    sh_text = open(SH, encoding="utf-8", errors="replace").read()
    # Assertion counts used to be printed here and went stale every time the suites grew
    # (345 -> 378 -> 379, and the .sh lagged behind the .bat). A gate must not report a number
    # it did not measure, so neither entry may hardcode one.
    hardcoded = [(name, match.group(0))
                 for name, text in (("deploy-pages.bat", bat_text), ("deploy-pages.sh", sh_text))
                 for match in re.finditer(r"\d{2,4}\s*条", text)]
    check(not hardcoded, "neither entry hardcodes an assertion count", str(hardcoded[:4]))
    for token in ("inline-config", "inline-compute", "inline-xlsx", "test-compute",
                  "test_xlsx_writer", "test_cli_smoke"):
        check(token in bat_text and token in sh_text, f"both entries run the {token} stage")
    check("check" in bat_text and "check" in sh_text, "both entries document the check mode")
    check("漂移" in bat_text and "漂移" in sh_text, "both entries guard the embedded-copy drift")

print("\n=== Publishing semantics: the script must never commit on your behalf ===")
if os.path.exists(BAT) and os.path.exists(SH):
    bat_text = open(BAT, encoding="utf-8", errors="replace").read()
    sh_text = open(SH, encoding="utf-8", errors="replace").read()
    # Help text may *mention* `git add -A`; only an executed line would re-create the
    # meaningless "chore(deploy): update Web UI / PWA assets" mega-commit.
    for name, text in (("deploy-pages.bat", bat_text), ("deploy-pages.sh", sh_text)):
        staging = action_lines(text, r"git\s+add\b")
        committing = action_lines(text, r"git\s+commit\b")
        check(not staging, f"{name} does not stage files itself", str(staging[:3]))
        check(not committing, f"{name} does not commit itself", str(committing[:3]))
        check("git status --porcelain" in text, f"{name} requires a committed work tree")
        check("publish" in text, f"{name} offers a non-interactive publish mode")
        check("已同步" in text, f"{name} skips pushing when already in sync")
    check("确认推送" in bat_text and "确认推送" in sh_text,
          "both entries ask for confirmation before pushing (default: cancel)")

print("\n=== Negative path: a failing gate must exit non-zero ===")
git_ok = subprocess.run(["git", "--version"], capture_output=True).returncode == 0
if os.name == "nt" and git_ok:
    workdir = temp_git_repo(BAT)
    if workdir:
        code, out = run([os.path.join(workdir, "deploy-pages.bat"), "check"], cwd=workdir)
        check(code == 1, "deploy-pages.bat check exits 1 when PWA files are missing",
              f"(got {code})")
        check("缺失" in out or "失败" in out, "the failure is also explained in the output")
        shutil.rmtree(workdir, ignore_errors=True)
    else:
        check(False, "could not build the temporary repo for the negative case")
else:
    print("  SKIP: .bat negative case needs Windows + git")

bash = find_bash()
if bash and git_ok:
    workdir = temp_git_repo(SH)
    if workdir:
        code, out = run([bash, "deploy-pages.sh", "check"], cwd=workdir)
        check(code == 1, "deploy-pages.sh check exits 1 when PWA files are missing",
              f"(got {code})")
        shutil.rmtree(workdir, ignore_errors=True)
    syntax = run([bash, "-n", SH], cwd=REPO)
    check(syntax[0] == 0, "deploy-pages.sh parses (bash -n)", syntax[1][-200:])
elif not bash:
    print("  SKIP: no bash available for the .sh cases")

print("\n=== A dirty work tree must block publishing, before any heavy test runs ===")
if git_ok:
    if os.name == "nt":
        workdir = committed_temp_repo(BAT)
        if workdir:
            code, out = run([os.path.join(workdir, "deploy-pages.bat"), "publish"], cwd=workdir)
            check(code == 1, "deploy-pages.bat publish refuses an uncommitted work tree",
                  f"(got {code})")
            check("不会代为提交" in out, "and says so without committing anything")
            check("[1/5]" not in out, "the pre-check stops before the slow suites")
            shutil.rmtree(workdir, ignore_errors=True)
    if bash:
        workdir = committed_temp_repo(SH)
        if workdir:
            code, out = run([bash, "deploy-pages.sh", "publish"], cwd=workdir)
            check(code == 1, "deploy-pages.sh publish refuses an uncommitted work tree",
                  f"(got {code})")
            check("不会代为提交" in out, "and says so without committing anything")
            shutil.rmtree(workdir, ignore_errors=True)

print("\n=== Positive path: check mode is a real gate and stays side-effect free ===")
if os.environ.get("DEPLOY_GATE_NO_RECURSION_CHILD") == "1":
    print("  SKIP: invoked from inside a gate run, not re-entering the gate")
else:
    head_before = git_head()
    dirty_before = porcelain(["--", "web/index.html", "config.json"])
    if os.name == "nt":
        code, out = run([BAT, "check"], cwd=REPO)
        check(code == 0, "deploy-pages.bat check passes on the committed tree",
              out[-400:])
        check("check 模式" in out and "不推送" in out, "check mode states that it does not push")
    code, out = run([bash, SH, "check"], cwd=REPO) if bash else (None, "")
    if bash:
        check(code == 0, "deploy-pages.sh check passes on the committed tree", out[-400:])
    check(git_head() == head_before, "no commit was created by check mode")
    check(porcelain(["--", "web/index.html", "config.json"]) == dirty_before,
          "check mode left the shipped files untouched (embedded copies already in sync)")

print("\n============================================")
if FAILURES:
    print(f"  {len(FAILURES)} ASSERTION(S) FAILED")
    sys.exit(1)
print("  ALL TESTS PASSED")
sys.exit(0)
