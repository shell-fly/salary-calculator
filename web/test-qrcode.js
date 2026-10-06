// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 bob3703
// Licensed under the Apache License, Version 2.0. See the LICENSE file for the full text.
// web/test-qrcode.js — cross-checks web/qrcode.js against fixtures produced by the
// Python `qrcode` reference library (pip install qrcode). Every fixture pins one
// (payload, EC level, mask) and stores the full module matrix, so data placement,
// format-info BCH bits and mask application are all covered. Run: node web/test-qrcode.js

import { readFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import { qrMatrix } from './qrcode.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const fixtures = JSON.parse(readFileSync(join(__dirname, 'test-qrcode-fixtures.json'), 'utf-8'));

let pass = 0;
let fail = 0;

function matrixToString(modules) {
  return modules.map((row) => row.map((v) => (v ? '1' : '0')).join('')).join('\n');
}

// --- fixed-mask equality against the reference implementation ---
for (const fx of fixtures) {
  const name = `payload=${JSON.stringify(fx.payload.slice(0, 24))} ec=${fx.ec} mask=${fx.mask} v${fx.version}`;
  try {
    const { size, modules } = qrMatrix(fx.payload, { ec: fx.ec, mask: fx.mask });
    if (size !== fx.matrix.length) {
      console.error(`FAIL ${name}: size ${size} != ${fx.matrix.length}`);
      fail++;
      continue;
    }
    if (matrixToString(modules) !== fx.matrix.join('\n')) {
      console.error(`FAIL ${name}: module matrix differs from reference`);
      fail++;
      continue;
    }
    pass++;
  } catch (e) {
    console.error(`FAIL ${name}: threw ${e.message}`);
    fail++;
  }
}

// --- auto mask selection must land on one of the eight valid matrices ---
const autoSeen = new Set();
for (const fx of fixtures) {
  autoSeen.add(`${fx.payload}\u0000${fx.ec}`);
}
for (const key of autoSeen) {
  const nl = key.indexOf('\u0000');
  const payload = key.slice(0, nl);
  const ec = key.slice(nl + 1);
  const valid = new Set(
    fixtures.filter((f) => f.payload === payload && f.ec === ec).map((f) => f.matrix.join('\n')),
  );
  const name = `auto payload=${JSON.stringify(payload.slice(0, 24))} ec=${ec}`;
  try {
    const { modules } = qrMatrix(payload, { ec });
    if (!valid.has(matrixToString(modules))) {
      console.error(`FAIL ${name}: auto-mask matrix matches no reference mask`);
      fail++;
      continue;
    }
    pass++;
  } catch (e) {
    console.error(`FAIL ${name}: threw ${e.message}`);
    fail++;
  }
}

// --- rejection beyond capacity ---
try {
  qrMatrix('y'.repeat(79), { ec: 'L' });
  console.error('FAIL overlong payload should throw');
  fail++;
} catch {
  pass++;
}

console.log('============================================');
console.log(`PASS: ${pass}, FAIL: ${fail} (fixtures: ${fixtures.length})`);
if (fail > 0) process.exit(1);
console.log('ALL TESTS PASSED');
