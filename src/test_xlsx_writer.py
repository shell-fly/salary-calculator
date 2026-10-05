# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 bob3703
# Licensed under the Apache License, Version 2.0. See the LICENSE file for the full text.
"""
test_xlsx_writer.py — contract tests for the zero-dependency .xlsx writer.

Run: python src/test_xlsx_writer.py

What it pins down:
1. the OOXML package layout Excel/WPS expect (STORE-zip, fixed order of parts);
2. that styles actually exist (header/title fills, money + percent number formats,
   freeze panes, auto filter, merged title cells) — the visual parity items that
   `income-calc` achieves through the third-party xlsx-js-style library;
3. byte-for-byte equality between the Python writer (src/xlsx_writer.py) and the
   JavaScript writer (web/xlsx-writer.js) for the same workbook definition, which is
   what lets the CLI and the single-file Web UI ship identical Excel reports without
   any third-party dependency.
"""
import io
import os
import subprocess
import sys
import zipfile
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from xlsx_writer import XlsxBook, money, percent  # noqa: E402

FAILURES = []


def check(cond, msg):
    print(("  PASS: " if cond else "  FAIL: ") + msg)
    if not cond:
        FAILURES.append(msg)


def sample_book():
    """The shared workbook definition also used by the Node side cross-check."""
    book = XlsxBook()
    book.add_sheet(
        "年度汇总",
        widths=[24, 20],
        rows=[
            [("上海 2025 年度工资测算", 2), ("", 0)],
            [("指标", 1), ("金额（元）", 1)],
            [("全年税前工资", 5), (money(240000.0), 3)],
            [("个人五险一金", 5), (money(42000.0), 3)],
            [("当月个税合计", 5), (money(9780.0), 3)],
            [("预计退税", 5), (money(0.0), 3)],
            [("全年实发到手", 6), (money(188220.0), 6)],
            [("实际税负率", 5), (percent(0.04075), 4)],
        ],
        merges=["A1:B1"],
        freeze="A3",
    )
    book.add_sheet(
        "逐月明细",
        widths=[8, 8, 14, 14, 14],
        rows=[
            [("月份", 1), ("半年度", 1), ("税前月薪", 1), ("五险一金_个人合计", 1), ("实发到手", 1)],
            [("1", 0), ("H1", 0), (money(20000.0), 3), (money(3500.0), 3), (money(16155.0), 3)],
            [("7", 0), ("H2", 0), (money(20000.0), 3), (money(3500.0), 3), (money(15350.0), 3)],
        ],
        freeze="A2",
        autofilter=True,
    )
    return book


print("=== package layout ===")
data = sample_book().to_bytes()
zf = zipfile.ZipFile(io.BytesIO(data))
names = zf.namelist()
check(names[0] == "[Content_Types].xml", "first part is [Content_Types].xml")
for required in ("_rels/.rels", "xl/workbook.xml", "xl/_rels/workbook.xml.rels",
                 "xl/styles.xml", "xl/worksheets/sheet1.xml", "xl/worksheets/sheet2.xml"):
    check(required in names, f"part present: {required}")
check(all(zf.getinfo(n).compress_type == zipfile.ZIP_STORED for n in names),
      "all parts stored uncompressed (no zlib dependency)")
check(all(zf.read(n) for n in names), "no empty parts")

print("\n=== xml is well formed ===")
parts = {}
for name in names:
    raw = zf.read(name)
    try:
        parts[name] = ET.fromstring(raw)
        ok = True
    except ET.ParseError as exc:  # pragma: no cover - failure path
        print(f"  parse error in {name}: {exc}")
        ok = False
    check(ok, f"well-formed xml: {name}")

print("\n=== workbook and styles ===")
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
wb = parts["xl/workbook.xml"]
sheet_names = [s.get("name") for s in wb.iter(f"{NS}sheet")]
check(sheet_names == ["年度汇总", "逐月明细"], f"sheet names/order {sheet_names}")
styles = zf.read("xl/styles.xml").decode("utf-8")
check("#,##0.00" in styles, "money number format #,##0.00 defined")
check("0.0%" in styles, "percent number format defined")
check(styles.count("<fill>") >= 3, "multiple fills (header/title highlighting)")
check("<b/>" in styles, "bold font for headers")
check(styles.count("<xf ") >= 6, "at least 6 cell formats (default/header/title/money/percent/text/highlight)")

print("\n=== sheet features ===")
s1 = zf.read("xl/worksheets/sheet1.xml").decode("utf-8")
check("<mergeCell ref=\"A1:B1\"" in s1, "summary sheet has a merged title row")
check('ySplit="2"' in s1 and "state=\"frozen\"" in s1, "summary sheet freezes the title + header rows")
check('t="inlineStr"' in s1 and "<is><t>全年实发到手" in s1, "summary sheet writes inline strings")
check('<v>188220.00</v>' in s1, "numbers land as numeric values, not text")
s2 = zf.read("xl/worksheets/sheet2.xml").decode("utf-8")
check("<autoFilter ref=" in s2, "monthly sheet has an auto filter")
check("<cols>" in s2 and "customWidth=\"1\"" in s2, "monthly sheet sets explicit column widths")

print("\n=== cross-engine byte equality (Python vs Node) ===")
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
node_script = os.path.join(root_dir, "web", "xlsx-writer.js")
probe_script = os.path.join(root_dir, "web", "xlsx-sample.mjs")
check(os.path.exists(node_script), "web/xlsx-writer.js exists")
check(os.path.exists(probe_script), "web/xlsx-sample.mjs exists")
if os.path.exists(node_script) and os.path.exists(probe_script):
    probe = subprocess.run(["node", "web/xlsx-sample.mjs"], cwd=root_dir, capture_output=True)
    check(probe.returncode == 0,
          f"node writer ran (stderr: {probe.stderr.decode('utf-8', 'replace')[:200]})")
    if probe.returncode == 0:
        check(probe.stdout == data,
              f"Node and Python writers emit identical bytes "
              f"({len(probe.stdout)} vs {len(data)})")

print("\n=== real report: CLI workbook vs Node --report ===")
import importlib.util  # noqa: E402

spec = importlib.util.spec_from_file_location(
    "salary_calculator", os.path.join(root_dir, "src", "salary_calculator.py"))
sc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sc)

sess = sc.Session("shanghai", 2023)
months_12 = sc.compute_year(sess, 20000, [], 7, 0)
real = sc.build_workbook(sess, months_12, annual_medical=0.0, bonus=100000,
                         housing_pct=7, extra_pct=0).to_bytes()
rz = zipfile.ZipFile(io.BytesIO(real))
real_names = rz.namelist()
check(all(f"xl/worksheets/sheet{i}.xml" in real_names for i in range(1, 5)),
      "real workbook contains four worksheets")
wb_xml = rz.read("xl/workbook.xml").decode("utf-8")
for sheet_name in ["年度汇总", "逐月明细", "政策参数", "年终奖对比"]:
    check(f'name="{sheet_name}"' in wb_xml, f"sheet present: {sheet_name}")
check("推荐方案" in rz.read("xl/worksheets/sheet4.xml").decode("utf-8"),
      "bonus sheet carries the recommendation row")
check("<is><t>全年税前工资</t></is>" in rz.read("xl/worksheets/sheet1.xml").decode("utf-8"),
      "summary sheet starts with the annual gross row")
# The styling that income-calc only gets via xlsx-js-style has to be present in the raw XML too.
real_s1 = rz.read("xl/worksheets/sheet1.xml").decode("utf-8")
check('ySplit="2"' in real_s1 and 'state="frozen"' in real_s1,
      "real summary sheet freezes title + header")
check('<mergeCell ref="A1:B1"/>' in real_s1, "real summary sheet merges the title band")
real_s2 = rz.read("xl/worksheets/sheet2.xml").decode("utf-8")
check('<autoFilter ref="A1:Y13"/>' in real_s2, "real detail sheet filters all 25 columns")
check('t="inlineStr"' in real_s2 and 'month_no' not in real_s2,
      "detail sheet writes labels, not internal keys")
check(rz.read("xl/styles.xml").decode("utf-8").count('numFmtId="164"') >= 2,
      "money format is referenced by the cell styles actually used")

report_probe = subprocess.run(["node", "web/xlsx-sample.mjs", "--report"],
                              cwd=root_dir, capture_output=True)
check(report_probe.returncode == 0,
      f"node report probe ran (stderr: {report_probe.stderr.decode('utf-8', 'replace')[:220]})")
if report_probe.returncode == 0:
    check(report_probe.stdout == real,
          f"CLI Excel and Web Excel are the same file ({len(report_probe.stdout)} vs {len(real)} bytes)")

print("\n=== in-page copies never drift ===")
html = open(os.path.join(root_dir, "web", "index.html"), encoding="utf-8").read()


def normalise(text):
    """Keep code lines only, without ESM keywords — what the inliner is allowed to change."""
    keep = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("//", "*", "/*", "*/")):
            continue
        if stripped.startswith("import "):
            continue
        keep.append(line.replace("export ", ""))
    return "\n".join(keep)


check("window.XLSX" not in html and "cdn.jsdelivr.net" not in html,
      "index.html no longer pulls a spreadsheet library from a CDN")
for module_file, block_id in (("xlsx-writer.js", "xlsx-writer"), ("xlsx-report.js", "xlsx-report")):
    marker = f'<script id="{block_id}">'
    check(marker in html, f"index.html carries the inlined {module_file}")
    source = open(os.path.join(root_dir, "web", module_file), encoding="utf-8").read()
    if marker in html:
        inlined = html.split(marker, 1)[1].split("</script>", 1)[0]
        check(normalise(inlined) == normalise(source), f"inlined {module_file} matches its source")

print("\n============================================")
if FAILURES:
    print(f"  {len(FAILURES)} ASSERTION(S) FAILED")
    sys.exit(1)
print("  ALL TESTS PASSED")
