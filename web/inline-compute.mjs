// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 bob3703
// Licensed under the Apache License, Version 2.0. See the LICENSE file for the full text.
// web/inline-compute.mjs — build helper: inline the calculation engine into web/index.html
//
// The Web UI ships as one self-contained file, so the engine exists twice: as an ES module
// (`web/compute.js`, used by the Node tests and the cross-engine probe) and as a classic
// script inside index.html. Run this after any change to web/compute.js:
//
//   node web/inline-compute.mjs
//
// The block is rewritten by index slicing and a plain string removal of the `export ` keyword
// (never String.replace with a pattern containing $), so nothing in the source can be
// re-interpreted as a replacement pattern — same safety rule as inline-xlsx.mjs.
// `web/test-compute.js` fails if the two copies drift.
//
// Everything is normalised to LF so the shipped index.html is byte-stable whatever
// core.autocrlf says on the machine that built it.
import { readFileSync, writeFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const HTML_FILE = join(__dirname, 'index.html');
const SOURCE_FILE = join(__dirname, 'compute.js');
const MARKER = '<!-- Inline Compute Engine (from compute.js, export keywords removed) -->';
const OPEN = '<script id="compute-engine">';
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
  console.error('ERROR: compute.js contains a closing script tag; refusing to inline.');
  process.exit(1);
}

let html = toLf(readFileSync(HTML_FILE, 'utf-8'));
const marker = html.indexOf(MARKER);
if (marker < 0) {
  console.error('ERROR: could not find the inline compute-engine marker in index.html.');
  process.exit(1);
}
// Accept the legacy bare `<script>` tag once, then normalise it to the identified form.
let start = html.indexOf(OPEN, marker);
let openLength = OPEN.length;
if (start < 0) {
  start = html.indexOf('<script>', marker);
  openLength = '<script>'.length;
}
if (start < 0 || start - marker > MARKER.length + 40) {
  console.error('ERROR: no <script> block right after the compute-engine marker in index.html.');
  process.exit(1);
}
const end = html.indexOf(CLOSE, start + openLength);
html = html.slice(0, start) + OPEN + '\n' + body + html.slice(end);

writeFileSync(HTML_FILE, html);

const blocks = html.split(OPEN).length - 1;
const inlined = html.split(OPEN)[1].split(CLOSE, 1)[0];
console.log(`compute.js inlined (blocks = ${blocks}); body identical to source:`,
  inlined.trim() === body.trim());
if (blocks !== 1 || inlined.trim() !== body.trim()) {
  console.error('ERROR: inlined engine is missing or differs from compute.js.');
  process.exit(1);
}
