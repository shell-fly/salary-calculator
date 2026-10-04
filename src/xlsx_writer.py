# -*- coding: utf-8 -*-
"""
xlsx_writer.py — zero-dependency .xlsx (SpreadsheetML) writer.

Part of 工资计算器（中国）/ china-salary-calculator.

Why this exists: the Excel report used to need the optional `openpyxl` package, so a
machine without it could only export CSV. The Web UI had the mirrored problem — it had to
download SheetJS from a CDN, i.e. Excel export silently failed offline. This module writes a
real styled workbook using nothing but the standard library (`binascii.crc32` + `struct`), and
`web/xlsx-writer.js` is a line-for-line port so the CLI and the single-file Web UI produce
byte-identical reports. `src/test_xlsx_writer.py` enforces that promise.

Package layout (STORE-only zip, fixed order, fixed timestamps — required for byte equality):
  [Content_Types].xml  _rels/.rels  xl/workbook.xml  xl/_rels/workbook.xml.rels
  xl/styles.xml  xl/worksheets/sheetN.xml

Cell styles are a fixed palette (index == the number passed with each cell):
  0 default        1 header (bold, green fill, boxed)   2 title (large bold, merged band)
  3 money #,##0.00 4 percent 0.0%                       5 bordered label
  6 highlight (bold + soft green fill + money)
"""
import struct
from binascii import crc32

XML_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"

# Fixed DOS date/time (2020-01-01 00:00:00) so two runs, and two languages, agree byte for byte.
DOS_TIME = (0 << 11) | (0 << 5) | 0
DOS_DATE = (2020 - 1980) << 9 | 1 << 5 | 1

MONEY_FMT = "#,##0.00"
PERCENT_FMT = "0.0%"


def money(value):
    """Format a number for a money cell: plain digits, the #,##0.00 format adds separators."""
    return f"{value:.2f}"


def percent(value):
    """Format a ratio for a percent cell (0.0408 -> 4.1% once the 0.0% format is applied)."""
    return f"{value:.4f}"


def num(value):
    """Format an integer-ish count for a numeric cell."""
    return f"{value:.2f}"


def is_numeric(text):
    """A cell is numeric when it looks like a bare decimal literal (never with separators)."""
    body = text[1:] if text[:1] == "-" else text
    return bool(body) and all(ch.isdigit() or ch == "." for ch in body)


def col_letter(idx):
    """1-based column index -> spreadsheet letter (1 -> A, 27 -> AA)."""
    out = ""
    while idx > 0:
        idx, rem = divmod(idx - 1, 26)
        out = chr(65 + rem) + out
    return out


def _esc(text):
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def _pane_xml(freeze):
    """Freeze pane request for a top-left cell such as A2 / A3."""
    if not freeze:
        return ""
    col = freeze[:-1]
    row = freeze[len(col):]
    xsplit = 0
    for ch in col:
        xsplit = xsplit * 26 + (ord(ch) - 64)
    attrs = []
    if xsplit:
        attrs.append(f'xSplit="{xsplit}"')
    ysplit = int(row) - 1
    if ysplit:
        attrs.append(f'ySplit="{ysplit}"')
    state = "topRight" if ysplit == 0 else ("bottomLeft" if xsplit == 0 else "bottomRight")
    return (f'<sheetViews><sheetView workbookViewId="0"><pane {" ".join(attrs)} '
            f'topLeftCell="{freeze}" activePane="{state}" state="frozen"/>'
            f'</sheetView></sheetViews>')


def _sheet_xml(sheet):
    rows, cols = sheet["rows"], sheet["widths"]
    last_col = max((len(r) for r in rows), default=1)
    parts = [f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             f'<worksheet xmlns="{XML_NS}">']
    parts.append(f'<dimension ref="A1:{col_letter(last_col)}{len(rows)}"/>')
    parts.append(_pane_xml(sheet["freeze"]))
    parts.append('<sheetFormatPr defaultRowHeight="15"/>')
    if cols:
        parts.append("<cols>" + "".join(
            f'<col min="{i}" max="{i}" width="{w}" customWidth="1"/>'
            for i, w in enumerate(cols, start=1)) + "</cols>")
    body = []
    for r_idx, row in enumerate(rows, start=1):
        cells = []
        for c_idx, cell in enumerate(row, start=1):
            text, style = cell
            ref = f"{col_letter(c_idx)}{r_idx}"
            if text == "":
                cells.append(f'<c r="{ref}" s="{style}"/>')
            elif is_numeric(text):
                cells.append(f'<c r="{ref}" s="{style}"><v>{text}</v></c>')
            else:
                cells.append(f'<c r="{ref}" s="{style}" t="inlineStr"><is><t>'
                             f'{_esc(text)}</t></is></c>')
        height = ""
        if r_idx == 1 and sheet["title_row"]:
            height = ' ht="30" customHeight="1"'
        elif sheet["header_row"] and r_idx == sheet["header_row"]:
            height = ' ht="24" customHeight="1"'
        body.append(f'<row r="{r_idx}"{height}>' + "".join(cells) + "</row>")
    parts.append("<sheetData>" + "".join(body) + "</sheetData>")
    if sheet["autofilter"] and rows:
        parts.append(f'<autoFilter ref="A1:{col_letter(len(rows[0]))}{len(rows)}"/>')
    if sheet["merges"]:
        parts.append(f'<mergeCells count="{len(sheet["merges"])}">' +
                     "".join(f'<mergeCell ref="{m}"/>' for m in sheet["merges"]) +
                     "</mergeCells>")
    parts.append("</worksheet>")
    return "".join(p for p in parts if p)


_STYLES_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    f'<styleSheet xmlns="{XML_NS}">'
    '<numFmts count="2">'
    f'<numFmt numFmtId="164" formatCode="{MONEY_FMT}"/>'
    f'<numFmt numFmtId="165" formatCode="{PERCENT_FMT}"/>'
    '</numFmts>'
    '<fonts count="4">'
    '<font><sz val="11"/><name val="Microsoft YaHei"/><color rgb="FF34423D"/></font>'
    '<font><b/><sz val="11"/><name val="Microsoft YaHei"/><color rgb="FF245642"/></font>'
    '<font><b/><sz val="15"/><name val="Microsoft YaHei"/><color rgb="FF173F31"/></font>'
    '<font><b/><sz val="12"/><name val="Microsoft YaHei"/><color rgb="FF176C4E"/></font>'
    '</fonts>'
    '<fills count="5">'
    '<fill><patternFill patternType="none"/></fill>'
    '<fill><patternFill patternType="gray125"/></fill>'
    '<fill><patternFill patternType="solid"><fgColor rgb="FFEAF5F0"/><bgColor indexed="64"/></patternFill></fill>'
    '<fill><patternFill patternType="solid"><fgColor rgb="FFDDEFE7"/><bgColor indexed="64"/></patternFill></fill>'
    '<fill><patternFill patternType="solid"><fgColor rgb="FFF0F8F4"/><bgColor indexed="64"/></patternFill></fill>'
    '</fills>'
    '<borders count="3">'
    '<border><left/><right/><top/><bottom/><diagonal/></border>'
    '<border><left/><right/><top/><bottom style="thin"><color rgb="FFE4EAE7"/></bottom><diagonal/></border>'
    '<border><left/><right/><top style="thin"><color rgb="FFCFE1D9"/></top>'
    '<bottom style="thin"><color rgb="FFCFE1D9"/></bottom><diagonal/></border>'
    '</borders>'
    '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
    '<cellXfs count="7">'
    '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
    '<xf numFmtId="0" fontId="1" fillId="2" borderId="2" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center"/></xf>'
    '<xf numFmtId="0" fontId="2" fillId="3" borderId="0" xfId="0" applyFont="1" applyFill="1" applyAlignment="1"><alignment horizontal="center" vertical="center"/></xf>'
    '<xf numFmtId="164" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyBorder="1" applyAlignment="1"><alignment horizontal="right"/></xf>'
    '<xf numFmtId="165" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyBorder="1" applyAlignment="1"><alignment horizontal="right"/></xf>'
    '<xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1"/>'
    '<xf numFmtId="164" fontId="3" fillId="4" borderId="1" xfId="0" applyNumberFormat="1" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="right"/></xf>'
    '</cellXfs>'
    '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
    '</styleSheet>'
)


def _content_types_xml(sheet_count):
    overrides = "".join(
        f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.'
        f'openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for i in range(1, sheet_count + 1))
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
            + overrides + '</Types>')


def _zip(parts):
    """STORE-only zip built by hand: parts is an ordered list of (name, bytes)."""
    out, central, offset = [], [], 0
    for name, payload in parts:
        crc = crc32(payload) & 0xFFFFFFFF
        local = struct.pack("<IHHHHHIIIHH", 0x04034B50, 20, 0, 0, DOS_TIME, DOS_DATE,
                            crc, len(payload), len(payload), len(name), 0)
        out.append(local + name.encode("utf-8") + payload)
        central.append(struct.pack("<IHHHHHHIIIHHHHHII", 0x02014B50, 20, 20, 0, 0, DOS_TIME,
                                   DOS_DATE, crc, len(payload), len(payload), len(name),
                                   0, 0, 0, 0, 0x20, offset)
                       + name.encode("utf-8"))
        offset += len(out[-1])
    body = b"".join(out)
    directory = b"".join(central)
    end = struct.pack("<IHHHHIIH", 0x06054B50, 0, 0, len(parts), len(parts),
                      len(directory), len(body), 0)
    return body + directory + end


class XlsxBook:
    """Collect styled sheets and serialise them as an .xlsx byte string."""

    def __init__(self):
        self.sheets = []

    def add_sheet(self, name, rows, widths=None, merges=None, freeze=None,
                  autofilter=False, title_row=False, header_row=None):
        self.sheets.append({
            "name": name, "rows": rows, "widths": list(widths or []),
            "merges": list(merges or []), "freeze": freeze,
            "autofilter": bool(autofilter), "title_row": bool(title_row),
            "header_row": header_row,
        })
        return self

    def _workbook_xml(self):
        sheets = "".join(
            f'<sheet name="{_esc(s["name"])}" sheetId="{i}" r:id="rId{i}"/>'
            for i, s in enumerate(self.sheets, start=1))
        return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                f'<workbook xmlns="{XML_NS}" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                f'<sheets>{sheets}</sheets><calcPr calcId="0"/></workbook>')

    def _workbook_rels_xml(self):
        rels = "".join(
            f'<Relationship Id="rId{i}" Type="{XML_NS}/worksheet" Target="worksheets/sheet{i}.xml"/>'
            for i in range(1, len(self.sheets) + 1))
        styles = (f'<Relationship Id="rId{len(self.sheets) + 1}" '
                  f'Type="{XML_NS}/styles" Target="styles.xml"/>')
        return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                f'{rels}{styles}</Relationships>')

    def to_bytes(self):
        if not self.sheets:
            raise ValueError("refusing to write a workbook without sheets")
        parts = [
            ("[Content_Types].xml", _content_types_xml(len(self.sheets)).encode("utf-8")),
            ("_rels/.rels", ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                             '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                             '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
                             'Target="xl/workbook.xml"/></Relationships>').encode("utf-8")),
            ("xl/workbook.xml", self._workbook_xml().encode("utf-8")),
            ("xl/_rels/workbook.xml.rels", self._workbook_rels_xml().encode("utf-8")),
            ("xl/styles.xml", _STYLES_XML.encode("utf-8")),
        ]
        for i, sheet in enumerate(self.sheets, start=1):
            parts.append((f"xl/worksheets/sheet{i}.xml", _sheet_xml(sheet).encode("utf-8")))
        return _zip(parts)

    def save(self, path):
        with open(path, "wb") as handle:
            handle.write(self.to_bytes())
        return path
