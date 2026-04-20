export const CACHE = 'quiz-pwa-v1';

export const STATIC = [
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

export async function handleInstall(cachesApi, skipWaiting) {
  const c = await cachesApi.open(CACHE);
  await c.addAll(STATIC);
  await skipWaiting();
}

export async function handleActivate(cachesApi, claim) {
  const keys = await cachesApi.keys();
  await Promise.all(keys.filter(k => k !== CACHE).map(k => cachesApi.delete(k)));
  await claim();
}

export async function handleFetch(request, cachesApi, fetchFn) {
  const { pathname } = new URL(request.url);
  if (pathname.startsWith('/api/')) {
    return fetchFn(request);
  }
  const cached = await cachesApi.match(request);
  if (cached) return cached;
  const resp = await fetchFn(request);
  if (resp.ok) {
    const clone = resp.clone();
    cachesApi.open(CACHE).then(c => c.put(request, clone));
  }
  return resp;
}

// Service worker registration — only runs in SW context (self is defined)
if (typeof self !== 'undefined' && typeof caches !== 'undefined') {
  self.addEventListener('install', e => e.waitUntil(handleInstall(caches, () => self.skipWaiting())));
  self.addEventListener('activate', e => e.waitUntil(handleActivate(caches, () => self.clients.claim())));
  self.addEventListener('fetch', e => e.respondWith(handleFetch(e.request, caches, fetch)));
}
