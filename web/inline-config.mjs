// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 bob3703
// Licensed under the Apache License, Version 2.0. See the LICENSE file for the full text.
// web/inline-config.mjs — build helper: embed the root config.json into web/index.html
//
// The Web UI ships as a single self-contained file, so the parameter table lives twice:
// config.json (source of truth, used by the Python CLI and the Node tests) and an embedded
// `<script type="application/json" id="cfg-data">` block inside index.html. Run this after
// every config.json change to keep them identical:
//
//   node web/inline-config.mjs
//
// NOTE: the block is rewritten by index slicing (no String.replace replacement patterns),
// so `$&` / `$'` sequences inside the JSON can never be re-interpreted — same safety rule
// as inline-vue.mjs.
//
// Line endings are normalised to LF on purpose: the repository is often checked out with
// core.autocrlf=true, so config.json arrives as CRLF. Embedding it verbatim would make the
// shipped index.html depend on each developer's git config (and would leave it with mixed
// endings, which `git status` then reports as modified even when the content is unchanged).
import { readFileSync, writeFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const CONFIG_FILE = join(__dirname, '..', 'config.json');
const HTML_FILE = join(__dirname, 'index.html');

const toLf = (text) => text.replace(/\r\n/g, '\n');

const OPEN_TAG = '<script type="application/json" id="cfg-data">';
const CLOSE_TAG = '</script>';

const config = toLf(readFileSync(CONFIG_FILE, 'utf-8'));
if (config.toLowerCase().includes('</script')) {
  console.error('ERROR: config.json contains a closing script tag; refusing to embed.');
  process.exit(1);
}
JSON.parse(config); // fail fast on malformed JSON instead of writing a broken page

const html = toLf(readFileSync(HTML_FILE, 'utf-8'));
const start = html.indexOf(OPEN_TAG);
if (start < 0) {
  console.error('ERROR: cfg-data block not found in index.html.');
  process.exit(1);
}
const bodyStart = start + OPEN_TAG.length;
const end = html.indexOf(CLOSE_TAG, bodyStart);
if (end < 0) {
  console.error('ERROR: cfg-data block is not closed in index.html.');
  process.exit(1);
}

const rebuilt = html.slice(0, bodyStart) + '\n' + config.trimEnd() + '\n' + html.slice(end);
writeFileSync(HTML_FILE, rebuilt);

// Verify the embedded copy parses and equals the source of truth.
const embedded = JSON.parse(rebuilt.slice(rebuilt.indexOf(OPEN_TAG) + OPEN_TAG.length,
  rebuilt.indexOf(CLOSE_TAG, rebuilt.indexOf(OPEN_TAG))));
const same = JSON.stringify(embedded) === JSON.stringify(JSON.parse(config));
console.log('config embedded into index.html; identical to config.json:', same);
if (!same) {
  console.error('ERROR: embedded config does not match config.json.');
  process.exit(1);
}
