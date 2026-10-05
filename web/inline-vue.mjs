// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 bob3703
// Licensed under the Apache License, Version 2.0. See the LICENSE file for the full text.
// web/inline-vue.mjs — build helper: inline Vue 3 runtime into index.html for offline use
//
// Usage:
//   1. Download vue.global.prod.js to web/vue.global.prod.js
//   2. node web/inline-vue.mjs
//
// IMPORTANT: We MUST use a function replacer, NOT a replacement string.
// Vue's minified source contains sequences like `$&`, `$'`, `` $` `` which
// String.prototype.replace would otherwise interpret as special replacement
// patterns, corrupting the output (e.g. re-inserting the matched CDN tag and
// producing a premature </script> that breaks the inline <script> block).
import { readFileSync, writeFileSync } from 'fs';

const CDN_TAG = '<script src="https://unpkg.com/vue@3/dist/vue.global.prod.js"></script>';
const VUE_FILE = 'web/vue.global.prod.js';
const HTML_FILE = 'web/index.html';

let html = readFileSync(HTML_FILE, 'utf-8');
const vue = readFileSync(VUE_FILE, 'utf-8');

if (!html.includes(CDN_TAG)) {
  console.error('ERROR: CDN script tag not found in index.html. Is it already inlined?');
  process.exit(1);
}

// Belt-and-suspenders: also escape any literal </script in the Vue source so the
// HTML parser can never see a premature closing tag. In a JS string context `\/`
// is just `/`, so runtime semantics are unchanged.
const vueSafe = vue.replace(/<\/script/gi, '<\\/script');

// Function replacer: the returned string is used verbatim, no $-pattern expansion.
const inlined = html.replace(CDN_TAG, () =>
  '<script>/* Vue 3 runtime - inlined for offline use */\n' + vueSafe + '\n</script>'
);

writeFileSync(HTML_FILE, inlined);

// Verify: exactly one opening <script> for Vue and its matching </script>,
// and no stray </script> inside the Vue payload.
const openCount = (inlined.match(/<script/g) || []).length;
const closeCount = (inlined.match(/<\/script>/g) || []).length;
console.log('Vue inlined. File size:', (inlined.length / 1024).toFixed(1), 'KB');
console.log('Total <script tags:', openCount, '| </script> tags:', closeCount);
if (openCount !== closeCount) {
  console.error('WARNING: unbalanced script tags!');
  process.exit(1);
}
