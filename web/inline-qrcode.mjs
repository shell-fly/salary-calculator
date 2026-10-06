// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 bob3703
// Licensed under the Apache License, Version 2.0. See the LICENSE file for the full text.
// web/inline-qrcode.mjs — build helper: inline the QR encoder into web/index.html
//
// Same pattern as inline-compute.mjs: the QR encoder exists twice (ES module for the
// Node test, classic script inside index.html). Run after any change to web/qrcode.js:
//
//   node web/inline-qrcode.mjs
//
// The block is rewritten by index slicing and a plain string removal of the `export `
// keyword (never String.replace with a pattern containing $), so nothing in the source
// can be re-interpreted as a replacement pattern. Normalised to LF for byte stability.
import { readFileSync, writeFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const HTML_FILE = join(__dirname, 'index.html');
const SOURCE_FILE = join(__dirname, 'qrcode.js');
const MARKER = '<!-- Inline QR encoder (from qrcode.js, export keyword removed) -->';
const OPEN = '<script id="qrcode-encoder">';
const CLOSE = '</script>';

const toLf = (text) => text.replace(/\r\n/g, '\n');

const source = toLf(readFileSync(SOURCE_FILE, 'utf-8'));
// Keep the code byte-identical except for ESM syntax: drop `export ` prefixes and any
// `import ...` line (index.html loads the block as a classic script).
const body = source.split('\n')
  .filter((line) => !line.startsWith('import '))
  .map((line) => (line.startsWith('export ') ? line.slice('export '.length) : line))
  .join('\n');
if (body.toLowerCase().includes('</script')) {
  console.error('ERROR: qrcode.js contains a closing script tag; refusing to inline.');
  process.exit(1);
}

let html = toLf(readFileSync(HTML_FILE, 'utf-8'));
const marker = html.indexOf(MARKER);
if (marker < 0) {
  console.error('ERROR: could not find the inline qrcode-encoder marker in index.html.');
  process.exit(1);
}
let start = html.indexOf(OPEN, marker);
let openLength = OPEN.length;
if (start < 0) {
  start = html.indexOf('<script>', marker);
  openLength = '<script>'.length;
}
if (start < 0 || start - marker > MARKER.length + 40) {
  console.error('ERROR: no <script> block right after the qrcode-encoder marker in index.html.');
  process.exit(1);
}
const end = html.indexOf(CLOSE, start + openLength);
html = html.slice(0, start) + OPEN + '\n' + body + html.slice(end);

writeFileSync(HTML_FILE, html);

const blocks = html.split(OPEN).length - 1;
const inlined = html.split(OPEN)[1].split(CLOSE, 1)[0];
console.log(`qrcode.js inlined (blocks = ${blocks}); body identical to source:`,
  inlined.trim() === body.trim());
if (blocks !== 1 || inlined.trim() !== body.trim()) {
  console.error('ERROR: inlined QR encoder is missing or differs from qrcode.js.');
  process.exit(1);
}
