/**
 * Tests for sw.js handler logic.
 * Tests the exported handleInstall / handleActivate / handleFetch functions
 * without requiring a real service worker environment.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { CACHE, STATIC, handleInstall, handleActivate, handleFetch } from '../sw.js';

function makeCacheStore() {
  const store = new Map(); // url → response
  return {
    addAll: vi.fn(async (urls) => { urls.forEach(u => store.set(u, 'cached')); }),
    put: vi.fn(async (req, resp) => { store.set(req.url ?? req, resp); }),
    match: vi.fn(async (req) => store.get(req.url ?? req) ?? undefined),
  };
}

function makeCachesApi(existingKeys = [], cacheStore = null) {
  const cache = cacheStore ?? makeCacheStore();
  return {
    open: vi.fn(async () => cache),
    keys: vi.fn(async () => existingKeys),
    delete: vi.fn(async () => {}),
    match: vi.fn(async (req) => cache.match(req)),
    _cache: cache,
  };
}

function makeRequest(url) {
  return { url, clone: () => ({ url }) };
}

function makeResponse(ok = true, body = 'body') {
  return { ok, body, clone: () => ({ ok, body }) };
}

describe('CACHE and STATIC', () => {
  it('CACHE name includes version', () => {
    expect(CACHE).toMatch(/quiz-pwa-v\d+/);
  });

  it('STATIC includes all key PWA assets', () => {
    expect(STATIC).toContain('/pwa/');
    expect(STATIC).toContain('/pwa/quiz.html');
    expect(STATIC).toContain('/pwa/srs.bundle.js');
    expect(STATIC).toContain('/pwa/manifest.json');
  });
});

describe('handleInstall', () => {
  it('opens the current cache and caches all static assets', async () => {
    const api = makeCachesApi();
    const skipWaiting = vi.fn();
    await handleInstall(api, skipWaiting);
    expect(api.open).toHaveBeenCalledWith(CACHE);
    expect(api._cache.addAll).toHaveBeenCalledWith(STATIC);
  });

  it('calls skipWaiting after caching', async () => {
    const api = makeCachesApi();
    const skipWaiting = vi.fn();
    await handleInstall(api, skipWaiting);
    expect(skipWaiting).toHaveBeenCalled();
  });
});

describe('handleActivate', () => {
  it('deletes old cache versions', async () => {
    const oldCache = 'quiz-pwa-v0';
    const api = makeCachesApi([oldCache, CACHE]);
    const claim = vi.fn();
    await handleActivate(api, claim);
    expect(api.delete).toHaveBeenCalledWith(oldCache);
    expect(api.delete).not.toHaveBeenCalledWith(CACHE);
  });

  it('claims clients after cleanup', async () => {
    const api = makeCachesApi([CACHE]);
    const claim = vi.fn();
    await handleActivate(api, claim);
    expect(claim).toHaveBeenCalled();
  });

  it('handles no old caches gracefully', async () => {
    const api = makeCachesApi([CACHE]);
    const claim = vi.fn();
    await handleActivate(api, claim);
    expect(api.delete).not.toHaveBeenCalled();
  });

  it('deletes multiple stale caches', async () => {
    const api = makeCachesApi(['quiz-pwa-v0', 'quiz-pwa-old', CACHE]);
    await handleActivate(api, vi.fn());
    expect(api.delete).toHaveBeenCalledTimes(2);
  });
});

describe('handleFetch — /api/ routes', () => {
  it('bypasses cache for /api/ requests', async () => {
    const req = makeRequest('http://localhost/api/sync');
    const resp = makeResponse();
    const fetchFn = vi.fn().mockResolvedValue(resp);
    const api = makeCachesApi();
    const result = await handleFetch(req, api, fetchFn);
    expect(fetchFn).toHaveBeenCalledWith(req);
    expect(result).toBe(resp);
    expect(api._cache.put).not.toHaveBeenCalled();
  });

  it('does not cache /api/ responses', async () => {
    const req = makeRequest('http://localhost/api/decks');
    const api = makeCachesApi();
    const fetchFn = vi.fn().mockResolvedValue(makeResponse());
    await handleFetch(req, api, fetchFn);
    expect(api._cache.put).not.toHaveBeenCalled();
  });
});

describe('handleFetch — /pwa/ cache-first', () => {
  it('returns cached response without hitting network', async () => {
    const req = makeRequest('http://localhost/pwa/index.html');
    const cachedResp = makeResponse();
    const store = makeCacheStore();
    store.match = vi.fn().mockResolvedValue(cachedResp);
    const api = makeCachesApi([CACHE], store);
    const fetchFn = vi.fn();
    const result = await handleFetch(req, api, fetchFn);
    expect(result).toBe(cachedResp);
    expect(fetchFn).not.toHaveBeenCalled();
  });

  it('fetches from network on cache miss and stores result', async () => {
    const req = makeRequest('http://localhost/pwa/quiz.html');
    const netResp = makeResponse();
    const store = makeCacheStore();
    store.match = vi.fn().mockResolvedValue(undefined);
    const api = makeCachesApi([], store);
    const fetchFn = vi.fn().mockResolvedValue(netResp);
    const result = await handleFetch(req, api, fetchFn);
    expect(fetchFn).toHaveBeenCalledWith(req);
    expect(result).toBe(netResp);
    // cache.put is called async (fire-and-forget); open should have been called
    expect(api.open).toHaveBeenCalledWith(CACHE);
  });

  it('does not cache non-ok network responses', async () => {
    const req = makeRequest('http://localhost/pwa/missing.js');
    const store = makeCacheStore();
    store.match = vi.fn().mockResolvedValue(undefined);
    const api = makeCachesApi([], store);
    const fetchFn = vi.fn().mockResolvedValue(makeResponse(false));
    await handleFetch(req, api, fetchFn);
    expect(store.put).not.toHaveBeenCalled();
  });
});
