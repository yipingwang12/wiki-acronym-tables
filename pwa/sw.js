const CACHE = 'quiz-pwa-v1';

const STATIC = [
  '/pwa/',
  '/pwa/index.html',
  '/pwa/quiz.html',
  '/pwa/quiz.js',
  '/pwa/db.js',
  '/pwa/sync.js',
  '/pwa/srs.bundle.js',
  '/pwa/manifest.json',
  '/pwa/icon-192.png',
  '/pwa/icon-512.png',
];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll(STATIC)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  const { pathname } = new URL(e.request.url);

  // API calls: network-only, no caching.
  if (pathname.startsWith('/api/')) {
    e.respondWith(fetch(e.request));
    return;
  }

  // Static PWA assets: cache-first.
  e.respondWith(
    caches.match(e.request).then(cached => cached || fetch(e.request).then(resp => {
      if (resp.ok) {
        const clone = resp.clone();
        caches.open(CACHE).then(c => c.put(e.request, clone));
      }
      return resp;
    }))
  );
});
