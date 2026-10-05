# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 bob3703
# Licensed under the Apache License, Version 2.0. See the LICENSE file for the full text.
"""
test_cli_smoke.py — end-to-end guard for the interactive CLI (`run.bat` / `run.sh` entry 1).

Part of 工资计算器（中国）/ china-salary-calculator.

Why this exists: the engine had 367 assertions across the two languages, but nothing ever
drove `main()` itself. That blind spot hid a `KeyError: 'm'` in the 缴费基数核对 print
(`sb['m']` instead of `sb['medical']`) which was present since the initial commit and made
every CLI session die right after the first answer set. These checks feed real stdin, require
exit code 0 and pin the numbers of the declared-base feature, so both the crash class and the
new behaviour stay covered.

Run: python src/test_cli_smoke.py
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CLI = os.path.join(HERE, "salary_calculator.py")

FAILURES = []


def check(ok, msg, detail=""):
    if ok:
        print(f"  PASS: {msg}")
    else:
        print(f"  FAIL: {msg} {detail}")
        FAILURES.append(msg)


def run_cli(answers):
    """Drive the interactive CLI with a scripted stdin; return (returncode, stdout, stderr)."""
    env = os.environ.copy()
    # Force the child to emit UTF-8 regardless of the host console codepage. On a GBK/cp936
    # Windows console Python would otherwise encode the CLI's Chinese output as cp936 while the
    # parent decodes it as UTF-8 below, turning it into mojibake and failing the Chinese-substring
    # assertions even though the numbers still match (a false failure, not a real regression).
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        [sys.executable, CLI],
        input="\n".join(answers) + "\n",
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=HERE, env=env,
    )
    return proc.returncode, proc.stdout or "", proc.stderr or ""


# Common answer sheet:
# city(default 上海) year(default) 月薪 第几个月 12 月同薪? 公积金比例 补充公积金
HEAD = ["", "", "30000", "", "y", "7", "n"]
# 七项专项附加扣除全部不启用 → 年终奖 → 查看全年 → 汇算 → 不导出 → 不反推
TAIL = ["n"] * 7 + ["0", "y", "n", "0", "n"]

print("=== CLI: default behaviour (base follows the salary) ===")
code, out, err = run_cli(HEAD + ["n"] + TAIL)
check(code == 0, "default run exits 0", f"(code={code}, err={err[-300:]})")
check("Traceback" not in err, "default run raises no traceback", err[-300:])
check("按税前月薪" in out, "default run reports the salary as the contribution base")
check("5,250.00" in out, "default 五险一金 = 5,250.00")
check("24,157.50" in out, "default M1 到手 = 24,157.50")

print("\n=== CLI: declared base at the statutory lower bounds ===")
code, out, err = run_cli(HEAD + ["y", "7460", "", "2690", ""] + TAIL)
check(code == 0, "declared-lower run exits 0", f"(code={code}, err={err[-300:]})")
check("按单位申报基数" in out, "declared run labels the base as employer-declared")
check("7,460.00" in out, "declared social base 7,460.00 shown")
check("971.30" in out, "declared 五险一金 = 971.30")
check("28,307.84" in out, "declared M1 到手 = 28,307.84 (more cash, but a higher annual tax bill)")

print("\n=== CLI: declared base above the policy cap is clamped ===")
code, out, err = run_cli(HEAD + ["y", "99999", "", "50000", ""] + TAIL)
check(code == 0, "over-cap run exits 0", f"(code={code}, err={err[-300:]})")
check("已按上下限取限" in out, "over-cap base is reported as clamped")
check("37,302.00" in out, "over-cap base clamped to 37,302.00")
check("6,527.71" in out, "over-cap 五险一金 = 6,527.71")

print("\n=== CLI: inverse calculation honours the declared base ===")
# 反推路径：年终奖 0 → 不看全年 → 不看汇算 → 不导出 → 反推 y + 目标 25000
code, out, err = run_cli(HEAD + ["y", "7460", "", "2690", ""]
                         + ["n"] * 7 + ["0", "n", "n", "0", "y", "25000"])
check(code == 0, "inverse run exits 0", f"(code={code}, err={err[-300:]})")
check("反推结果" in out, "inverse result printed")
check("25,000" in out or "300,000" in out, "inverse reaches the requested take-home target")

print("\n=== CLI: Beijing fixed medical top-up (2% + 3 CNY/month) ===")
# city 2 = 北京, year default, 月薪 30000, 第 1 月, 公积金 12%, 无补充公积金, 无自定义基数
code, out, err = run_cli(["2", "", "30000", "", "y", "12", "n", "n"] + TAIL)
check(code == 0, "Beijing run exits 0", f"(code={code}, err={err[-300:]})")
check("603.00" in out, "Beijing 医疗个人 = 603.00（600 + 3 元定额）")
check("6,753.00" in out, "Beijing 五险一金个人合计 = 6,753.00")
check("22,699.59" in out, "Beijing M1 到手 = 22,699.59")
# Same numbers as web/test-compute.js Test 13: matching literals are the cross-engine proof.

print("\n=== CLI: per-month salary list (commission-style pay) ===")
# 上海 2026：M1-M5 = 20000，M6 = 60000（基数封顶 37302），M7-M12 = 20000；查看全年表
code, out, err = run_cli(["", "", "20000", "", "n"]
                         + ["20000"] * 5 + ["60000"] + ["20000"] * 6
                         + ["7", "n", "n"] + ["n"] * 7 + ["0", "y", "n", "0", "n"])
check(code == 0, "salary-list run exits 0", f"(code={code}, err={err[-300:]})")
check("Traceback" not in err, "salary-list run raises no traceback", err[-300:])
check("48,625.06" in out, "M6 到手 = 48,625.06（累计预扣按真实逐月收入）")
check("4,847.23" in out, "M6 本月个税 = 4,847.23（累计预扣按真实逐月收入）")
check("15,455.00" in out, "M4 到手 = 15,455.00（累计跨入 10% 档）")

print("\n============================================")
if FAILURES:
    print(f"  {len(FAILURES)} ASSERTION(S) FAILED")
    sys.exit(1)
print("  ALL TESTS PASSED")
sys.exit(0)
