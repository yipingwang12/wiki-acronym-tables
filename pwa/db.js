/**
 * IndexedDB wrapper for SRS state and deck cache.
 *
 * Exposes the interface expected by SRSScheduler (getCard/saveCard/countIntroducedToday)
 * plus helpers for sync (getAllCards/putCard) and deck caching (saveDeckCache/getDeckCache).
 */

const DB_NAME = 'quiz-srs';
const DB_VERSION = 1;

let _db = null;

/** Reset cached connection — for testing only. */
export function _resetDb() { _db = null; }

async function _open() {
  if (_db) return _db;
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = e => {
      const db = e.target.result;
      if (!db.objectStoreNames.contains('srs_state')) {
        db.createObjectStore('srs_state', { keyPath: 'item_key' });
      }
      if (!db.objectStoreNames.contains('deck_cache')) {
        db.createObjectStore('deck_cache', { keyPath: 'deck_id' });
      }
      if (!db.objectStoreNames.contains('deck_list_cache')) {
        db.createObjectStore('deck_list_cache', { keyPath: 'id' });
      }
    };
    req.onsuccess = e => { _db = e.target.result; resolve(_db); };
    req.onerror = e => reject(e.target.error);
  });
}

function _tx(storeName, mode, fn) {
  return _open().then(db => new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, mode);
    const store = tx.objectStore(storeName);
    const req = fn(store);
    req.onsuccess = e => resolve(e.target.result);
    req.onerror = e => reject(e.target.error);
  }));
}

// --- SRSScheduler interface ---

export async function getCard(key) {
  const row = await _tx('srs_state', 'readonly', s => s.get(key));
  return row?.card_json ?? null;
}

export async function saveCard(key, card_json) {
  const updated_at = new Date().toISOString();
  await _tx('srs_state', 'readwrite', s => s.put({ item_key: key, card_json, updated_at }));
}

export async function countIntroducedToday(now = new Date()) {
  const today = now.toISOString().slice(0, 10);
  return _open().then(db => new Promise((resolve, reject) => {
    const tx = db.transaction('srs_state', 'readonly');
    const req = tx.objectStore('srs_state').getAll();
    req.onsuccess = e => {
      const count = e.target.result.filter(r => {
        try { return JSON.parse(r.card_json).introduced_date === today; }
        catch { return false; }
      }).length;
      resolve(count);
    };
    req.onerror = e => reject(e.target.error);
  }));
}

// --- Sync helpers ---

export async function getAllCards() {
  return _open().then(db => new Promise((resolve, reject) => {
    const tx = db.transaction('srs_state', 'readonly');
    const req = tx.objectStore('srs_state').getAll();
    req.onsuccess = e => resolve(e.target.result);
    req.onerror = e => reject(e.target.error);
  }));
}

export async function putCard(item_key, card_json, updated_at) {
  await _tx('srs_state', 'readwrite', s => s.put({ item_key, card_json, updated_at }));
}

// --- Deck cache ---

export async function saveDeckCache(deck_id, data) {
  await _tx('deck_cache', 'readwrite', s =>
    s.put({ deck_id, data, cached_at: new Date().toISOString() })
  );
}

export async function getDeckCache(deck_id) {
  const row = await _tx('deck_cache', 'readonly', s => s.get(deck_id));
  return row?.data ?? null;
}

export async function saveDeckListCache(decks) {
  await _tx('deck_list_cache', 'readwrite', s =>
    s.put({ id: '__decks__', decks, cached_at: new Date().toISOString() })
  );
}

export async function getDeckListCache() {
  const row = await _tx('deck_list_cache', 'readonly', s => s.get('__decks__'));
  return row?.decks ?? null;
}
