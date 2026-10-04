// web/inline-xlsx.mjs — build helper: inline the Excel writer + report builder into web/index.html
//
// The Web UI ships as one self-contained file, so the Excel layer exists twice: as ES modules
// (used by the Node tests and the cross-engine probe) and as classic scripts inside index.html.
// Run this after any change to web/xlsx-writer.js or web/xlsx-report.js:
//
//   node web/inline-xlsx.mjs
//
// The blocks are written by index slicing and a plain string removal of the `export ` keyword
// (never String.replace with a pattern containing $), so nothing in the source can be
// re-interpreted as a replacement pattern. `src/test_xlsx_writer.py` fails if the copies drift.
import { readFileSync, writeFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const HTML_FILE = join(__dirname, 'index.html');
const ANCHOR = '<!-- Vue Application -->';

// Order matters: the report builder uses the writer, so it must be injected after it.
const MODULES = [
  { file: 'xlsx-writer.js', id: 'xlsx-writer' },
  { file: 'xlsx-report.js', id: 'xlsx-report' },
];

let html = readFileSync(HTML_FILE, 'utf-8');

for (const { file, id } of MODULES) {
  const source = readFileSync(join(__dirname, file), 'utf-8');
  // Keep the code byte-identical except for ESM syntax: drop `export ` prefixes and the
  // `import ...` lines (the inlined blocks share globals, and index.html loads them as classic
  // scripts in the same order as the module graph).
  const body = source.split('\n')
    .filter((line) => !line.startsWith('import '))
    .map((line) => (line.startsWith('export ') ? line.slice('export '.length) : line))
    .join('\n');
  if (body.toLowerCase().includes('</script')) {
    console.error(`ERROR: ${file} contains a closing script tag; refusing to inline.`);
    process.exit(1);
  }
  const openTag = `<script id="${id}">`;
  const closeTag = '</script>';
  const start = html.indexOf(openTag);
  if (start >= 0) {
    const end = html.indexOf(closeTag, start + openTag.length);
    html = html.slice(0, start) + openTag + '\n' + body + html.slice(end);
  } else {
    if (!html.includes(ANCHOR)) {
      console.error('ERROR: could not find the "<!-- Vue Application -->" anchor in index.html.');
      process.exit(1);
    }
    html = html.replace(ANCHOR, `${openTag}\n${body}${closeTag}\n\n${ANCHOR}`);
  }
  const blocks = html.split(openTag).length - 1;
  const inlined = html.split(openTag)[1].split(closeTag, 1)[0];
  console.log(`${file} inlined (blocks = ${blocks}); body identical to source:`,
    inlined.trim() === body.trim());
  if (blocks !== 1 || inlined.trim() !== body.trim()) {
    console.error(`ERROR: inlined ${file} is missing or differs from its source.`);
    process.exit(1);
  }
}

writeFileSync(HTML_FILE, html);
