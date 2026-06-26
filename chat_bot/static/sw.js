/* Service Worker PAPP EA — offline shell + cache statica.
   Regole: /api e /ws sempre dalla rete (dati live), statici cache-first,
   navigazione network-first con fallback offline. */
const CACHE = 'papp-ea-v1';
const ASSETS = [
  '/static/icon-192.png',
  '/static/icon-512.png',
  '/static/apple-touch-icon.png',
  '/manifest.webmanifest',
  '/static/offline.html',
];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(ASSETS)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);

  // Dati live: mai dalla cache
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/ws')) return;

  // Statici e manifest: cache-first con aggiornamento in background
  if (url.pathname.startsWith('/static/') || url.pathname === '/manifest.webmanifest') {
    e.respondWith(
      caches.match(req).then((cached) => {
        const fetchPromise = fetch(req).then((resp) => {
          const copy = resp.clone();
          caches.open(CACHE).then((c) => c.put(req, copy));
          return resp;
        }).catch(() => cached);
        return cached || fetchPromise;
      })
    );
    return;
  }

  // Navigazione (apertura pagina): rete prima, fallback offline
  if (req.mode === 'navigate') {
    e.respondWith(fetch(req).catch(() => caches.match('/static/offline.html')));
    return;
  }
});
