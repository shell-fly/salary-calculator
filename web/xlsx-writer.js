/**
 * xlsx-writer.js — zero-dependency .xlsx (SpreadsheetML) writer for the Web UI.
 *
 * Part of 工资计算器（中国）/ china-salary-calculator.
 *
 * This is a line-for-line port of `src/xlsx_writer.py`: the CLI and the single-file Web UI
 * must hand out the same styled workbook, and they must do it without any third-party
 * library. The old Web export pulled SheetJS from a CDN, so offline users were told to use
 * CSV instead; and the CLI Excel export silently disappeared unless `openpyxl` was installed.
 *
 * `src/test_xlsx_writer.py` asserts that both writers produce byte-identical output, which is
 * only possible because the zip is STORE-only, the timestamps are fixed, and every number is
 * serialised through money()/percent() instead of the language's default float formatting.
 *
 * Style indices (identical to the Python module):
 *   0 default  1 header  2 title  3 money #,##0.00  4 percent 0.0%  5 label  6 highlight
 */

const XML_NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main';

// Fixed DOS date/time (2020-01-01 00:00:00), shared with the Python writer.
const DOS_TIME = 0;
const DOS_DATE = ((2020 - 1980) << 9) | (1 << 5) | 1;

/** Format a number for a money cell: the #,##0.00 style adds the thousands separators. */
export const money = (value) => value.toFixed(2);
/** Format a ratio for a percent cell (0.0408 -> 4.1% under the 0.0% style). */
export const percent = (value) => value.toFixed(4);
/** Format a count for a numeric cell. */
export const num = (value) => value.toFixed(2);

/** A cell is numeric only when it is a bare decimal literal (never with separators). */
function isNumeric(text) {
  const body = text.startsWith('-') ? text.slice(1) : text;
  return body.length > 0 && /^[0-9.]+$/.test(body);
}

/** 1-based column index -> spreadsheet letter (1 -> A, 27 -> AA). */
function colLetter(idx) {
  let out = '';
  while (idx > 0) {
    const rem = (idx - 1) % 26;
    idx = Math.floor((idx - 1) / 26);
    out = String.fromCharCode(65 + rem) + out;
  }
  return out;
}

function esc(text) {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

/** Freeze-pane XML for a top-left cell such as A2 / A3. */
function paneXml(freeze) {
  if (!freeze) return '';
  const col = freeze.replace(/[0-9]/g, '');
  const row = col.length ? freeze.slice(col.length) : freeze;
  let xsplit = 0;
  for (const ch of col) xsplit = xsplit * 26 + (ch.charCodeAt(0) - 64);
  const ysplit = parseInt(row, 10) - 1;
  const attrs = [];
  if (xsplit) attrs.push(`xSplit="${xsplit}"`);
  if (ysplit) attrs.push(`ySplit="${ysplit}"`);
  const state = ysplit === 0 ? 'topRight' : (xsplit === 0 ? 'bottomLeft' : 'bottomRight');
  return `<sheetViews><sheetView workbookViewId="0"><pane ${attrs.join(' ')} ` +
    `topLeftCell="${freeze}" activePane="${state}" state="frozen"/>` +
    '</sheetView></sheetViews>';
}

function sheetXml(sheet) {
  const { rows, widths: cols } = sheet;
  const lastCol = rows.reduce((max, r) => Math.max(max, r.length), 1);
  const parts = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
    `<worksheet xmlns="${XML_NS}">`];
  parts.push(`<dimension ref="A1:${colLetter(lastCol)}${rows.length}"/>`);
  parts.push(paneXml(sheet.freeze));
  parts.push('<sheetFormatPr defaultRowHeight="15"/>');
  if (cols.length) {
    parts.push('<cols>' + cols.map((w, i) =>
      `<col min="${i + 1}" max="${i + 1}" width="${w}" customWidth="1"/>`).join('') + '</cols>');
  }
  const body = rows.map((row, index) => {
    const rIdx = index + 1;
    const cells = row.map((cell, cIndex) => {
      const [text, style] = cell;
      const ref = `${colLetter(cIndex + 1)}${rIdx}`;
      if (text === '') return `<c r="${ref}" s="${style}"/>`;
      if (isNumeric(text)) return `<c r="${ref}" s="${style}"><v>${text}</v></c>`;
      return `<c r="${ref}" s="${style}" t="inlineStr"><is><t>${esc(text)}</t></is></c>`;
    }).join('');
    let height = '';
    if (rIdx === 1 && sheet.titleRow) height = ' ht="30" customHeight="1"';
    else if (sheet.headerRow && rIdx === sheet.headerRow) height = ' ht="24" customHeight="1"';
    return `<row r="${rIdx}"${height}>${cells}</row>`;
  }).join('');
  parts.push(`<sheetData>${body}</sheetData>`);
  if (sheet.autofilter && rows.length) {
    parts.push(`<autoFilter ref="A1:${colLetter(rows[0].length)}${rows.length}"/>`);
  }
  if (sheet.merges.length) {
    parts.push(`<mergeCells count="${sheet.merges.length}">` +
      sheet.merges.map((m) => `<mergeCell ref="${m}"/>`).join('') + '</mergeCells>');
  }
  parts.push('</worksheet>');
  return parts.filter(Boolean).join('');
}

const STYLES_XML = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
  `<styleSheet xmlns="${XML_NS}">` +
  '<numFmts count="2">' +
  '<numFmt numFmtId="164" formatCode="#,##0.00"/>' +
  '<numFmt numFmtId="165" formatCode="0.0%"/>' +
  '</numFmts>' +
  '<fonts count="4">' +
  '<font><sz val="11"/><name val="Microsoft YaHei"/><color rgb="FF34423D"/></font>' +
  '<font><b/><sz val="11"/><name val="Microsoft YaHei"/><color rgb="FF245642"/></font>' +
  '<font><b/><sz val="15"/><name val="Microsoft YaHei"/><color rgb="FF173F31"/></font>' +
  '<font><b/><sz val="12"/><name val="Microsoft YaHei"/><color rgb="FF176C4E"/></font>' +
  '</fonts>' +
  '<fills count="5">' +
  '<fill><patternFill patternType="none"/></fill>' +
  '<fill><patternFill patternType="gray125"/></fill>' +
  '<fill><patternFill patternType="solid"><fgColor rgb="FFEAF5F0"/><bgColor indexed="64"/></patternFill></fill>' +
  '<fill><patternFill patternType="solid"><fgColor rgb="FFDDEFE7"/><bgColor indexed="64"/></patternFill></fill>' +
  '<fill><patternFill patternType="solid"><fgColor rgb="FFF0F8F4"/><bgColor indexed="64"/></patternFill></fill>' +
  '</fills>' +
  '<borders count="3">' +
  '<border><left/><right/><top/><bottom/><diagonal/></border>' +
  '<border><left/><right/><top/><bottom style="thin"><color rgb="FFE4EAE7"/></bottom><diagonal/></border>' +
  '<border><left/><right/><top style="thin"><color rgb="FFCFE1D9"/></top>' +
  '<bottom style="thin"><color rgb="FFCFE1D9"/></bottom><diagonal/></border>' +
  '</borders>' +
  '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>' +
  '<cellXfs count="7">' +
  '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>' +
  '<xf numFmtId="0" fontId="1" fillId="2" borderId="2" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center"/></xf>' +
  '<xf numFmtId="0" fontId="2" fillId="3" borderId="0" xfId="0" applyFont="1" applyFill="1" applyAlignment="1"><alignment horizontal="center" vertical="center"/></xf>' +
  '<xf numFmtId="164" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyBorder="1" applyAlignment="1"><alignment horizontal="right"/></xf>' +
  '<xf numFmtId="165" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyBorder="1" applyAlignment="1"><alignment horizontal="right"/></xf>' +
  '<xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1"/>' +
  '<xf numFmtId="164" fontId="3" fillId="4" borderId="1" xfId="0" applyNumberFormat="1" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="right"/></xf>' +
  '</cellXfs>' +
  '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>' +
  '</styleSheet>';

function contentTypesXml(sheetCount) {
  let overrides = '';
  for (let i = 1; i <= sheetCount; i += 1) {
    overrides += `<Override PartName="/xl/worksheets/sheet${i}.xml" ContentType="application/vnd.` +
      'openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>';
  }
  return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">' +
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>' +
    '<Default Extension="xml" ContentType="application/xml"/>' +
    '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>' +
    '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>' +
    `${overrides}</Types>`;
}

const CRC_TABLE = (() => {
  const table = new Uint32Array(256);
  for (let n = 0; n < 256; n += 1) {
    let c = n;
    for (let k = 0; k < 8; k += 1) c = (c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1);
    table[n] = c >>> 0;
  }
  return table;
})();

function crc32(bytes) {
  let crc = 0xFFFFFFFF;
  for (const byte of bytes) crc = CRC_TABLE[(crc ^ byte) & 0xFF] ^ (crc >>> 8);
  return (crc ^ 0xFFFFFFFF) >>> 0;
}

function u16(value) { return [value & 0xFF, (value >>> 8) & 0xFF]; }
function u32(value) { return [value & 0xFF, (value >>> 8) & 0xFF, (value >>> 16) & 0xFF, (value >>> 24) & 0xFF]; }

/** STORE-only zip built by hand, matching the Python writer byte for byte. */
function zip(parts) {
  const body = [];
  const central = [];
  let offset = 0;
  for (const [name, text] of parts) {
    const nameBytes = new TextEncoder().encode(name);
    const payload = new TextEncoder().encode(text);
    const crc = crc32(payload);
    const local = [
      ...u32(0x04034B50), ...u16(20), ...u16(0), ...u16(0), ...u16(DOS_TIME), ...u16(DOS_DATE),
      ...u32(crc), ...u32(payload.length), ...u32(payload.length), ...u16(nameBytes.length), ...u16(0),
    ];
    const entry = Uint8Array.from([...local, ...nameBytes, ...payload]);
    body.push(entry);
    central.push(Uint8Array.from([
      ...u32(0x02014B50), ...u16(20), ...u16(20), ...u16(0), ...u16(0), ...u16(DOS_TIME), ...u16(DOS_DATE),
      ...u32(crc), ...u32(payload.length), ...u32(payload.length), ...u16(nameBytes.length),
      ...u16(0), ...u16(0), ...u16(0), ...u16(0), ...u32(0x20), ...u32(offset),
      ...nameBytes,
    ]));
    offset += entry.length;
  }
  const directory = central.length ? Uint8Array.from([].concat(...central.map((c) => Array.from(c)))) : new Uint8Array();
  const end = Uint8Array.from([
    ...u32(0x06054B50), ...u16(0), ...u16(0), ...u16(parts.length), ...u16(parts.length),
    ...u32(directory.length), ...u32(offset), ...u16(0),
  ]);
  const total = body.reduce((sum, part) => sum + part.length, 0) + directory.length + end.length;
  const out = new Uint8Array(total);
  let cursor = 0;
  for (const part of body) { out.set(part, cursor); cursor += part.length; }
  out.set(directory, cursor); cursor += directory.length;
  out.set(end, cursor);
  return out;
}

export class XlsxBook {
  constructor() {
    this.sheets = [];
  }

  addSheet(name, { rows, widths = [], merges = [], freeze = null, autofilter = false,
    titleRow = false, headerRow = null } = {}) {
    this.sheets.push({
      name, rows, widths: [...widths], merges: [...merges], freeze,
      autofilter: Boolean(autofilter), titleRow: Boolean(titleRow), headerRow,
    });
    return this;
  }

  workbookXml() {
    const sheets = this.sheets.map((s, i) =>
      `<sheet name="${esc(s.name)}" sheetId="${i + 1}" r:id="rId${i + 1}"/>`).join('');
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
      `<workbook xmlns="${XML_NS}" ` +
      'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">' +
      `<sheets>${sheets}</sheets><calcPr calcId="0"/></workbook>`;
  }

  workbookRelsXml() {
    let rels = '';
    for (let i = 1; i <= this.sheets.length; i += 1) {
      rels += `<Relationship Id="rId${i}" Type="${XML_NS}/worksheet" Target="worksheets/sheet${i}.xml"/>`;
    }
    const styles = `<Relationship Id="rId${this.sheets.length + 1}" ` +
      `Type="${XML_NS}/styles" Target="styles.xml"/>`;
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
      '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' +
      `${rels}${styles}</Relationships>`;
  }

  toBytes() {
    if (!this.sheets.length) throw new Error('refusing to write a workbook without sheets');
    const parts = [
      ['[Content_Types].xml', contentTypesXml(this.sheets.length)],
      ['_rels/.rels', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' +
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" ' +
        'Target="xl/workbook.xml"/></Relationships>'],
      ['xl/workbook.xml', this.workbookXml()],
      ['xl/_rels/workbook.xml.rels', this.workbookRelsXml()],
      ['xl/styles.xml', STYLES_XML],
    ];
    this.sheets.forEach((sheet, i) => parts.push([`xl/worksheets/sheet${i + 1}.xml`, sheetXml(sheet)]));
    return zip(parts);
  }

  /** Trigger a browser download of the finished workbook. */
  download(filename) {
    const bytes = this.toBytes();
    const url = URL.createObjectURL(new Blob([bytes], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    }));
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    return bytes.length;
  }
}
