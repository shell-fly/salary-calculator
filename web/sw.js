/* China Salary Calculator — Service Worker
 * Strategy: precache the self-contained app shell; cache-first at runtime with
 * a background refresh for navigations so the deployed PWA works fully offline
 * after the first visit. Bump VERSION on each release to bust stale caches.
 */
const VERSION = 'v3-pwa-5';
const CACHE = `salary-calc-${VERSION}`;

// App shell to precache. index.html is self-contained (Vue + engine + config inlined).
const PRECACHE = [
  './',
  './index.html',
  './manifest.webmanifest',
  './icons/icon-192.png',
  './icons/icon-512.png',
  './icons/maskable-512.png',
  './icons/apple-touch-icon.png',
  './icons/favicon-32.png',
  './icons/favicon-16.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(PRECACHE)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);
  // Only handle same-origin requests; let cross-origin (e.g. SheetJS CDN) pass through.
  if (url.origin !== self.location.origin) return;

  // Navigations: serve cached index.html (offline-first) but refresh in background.
  if (req.mode === 'navigate') {
    event.respondWith(
      caches.match('./index.html').then((cached) => {
        const network = fetch(req)
          .then((res) => {
            if (res && res.ok) {
              const clone = res.clone();
              caches.open(CACHE).then((c) => c.put('./index.html', clone));
            }
            return res;
          })
          .catch(() => cached || caches.match('./'));
        return cached || network;
      })
    );
    return;
  }

  // Other same-origin assets: cache-first, fall back to network and fill cache.
  event.respondWith(
    caches.match(req).then((cached) => {
      if (cached) return cached;
      return fetch(req).then((res) => {
        if (res && res.ok) {
          const clone = res.clone();
          caches.open(CACHE).then((c) => c.put(req, clone));
        }
        return res;
      });
    })
  );
});
