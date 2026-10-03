// web/inline-vue.mjs (one-time build helper)
import { readFileSync, writeFileSync } from 'fs';
const html = readFileSync('web/index.html', 'utf-8');
const vue = readFileSync('web/vue.global.prod.js', 'utf-8');
const inlined = html.replace(
  /<script src="https:\/\/unpkg\.com\/vue@3\/dist\/vue\.global\.prod\.js"><\/script>/,
  `<script>/* Vue 3 runtime - inlined for offline use */\n${vue}\n</script>`
);
if (inlined === html) {
  console.error('ERROR: Pattern not found! Check the CDN script tag in index.html.');
  process.exit(1);
}
writeFileSync('web/index.html', inlined);
console.log('Vue inlined successfully. File size:', (inlined.length / 1024).toFixed(1), 'KB');
