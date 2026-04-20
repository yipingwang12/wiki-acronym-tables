/**
 * IndexedDB wrapper tests.
 * Uses fake-indexeddb for isolation — each test gets a fresh IDBFactory.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { IDBFactory } from 'fake-indexeddb';
import {
  _resetDb, getCard, saveCard, countIntroducedToday,
  getAllCards, putCard, saveDeckCache, getDeckCache,
  saveDeckListCache, getDeckListCache,
} from '../db.js';

beforeEach(() => {
  globalThis.indexedDB = new IDBFactory();
  _resetDb();
});

describe('getCard / saveCard', () => {
  it('returns null for unknown key', async () => {
    expect(await getCard('unknown')).toBeNull();
  });

  it('round-trips a card', async () => {
    const json = '{"learning_step":0}';
    await saveCard('key1', json);
    expect(await getCard('key1')).toBe(json);
  });

  it('overwrites on second save', async () => {
    await saveCard('k', '{"v":1}');
    await saveCard('k', '{"v":2}');
    expect(await getCard('k')).toBe('{"v":2}');
  });
});

describe('countIntroducedToday', () => {
  it('counts zero when empty', async () => {
    expect(await countIntroducedToday(new Date())).toBe(0);
  });

  it('counts cards introduced today', async () => {
    const today = new Date().toISOString().slice(0, 10);
    await saveCard('a', JSON.stringify({ learning_step: 0, introduced_date: today }));
    await saveCard('b', JSON.stringify({ learning_step: 0, introduced_date: today }));
    await saveCard('c', JSON.stringify({ learning_step: 0, introduced_date: '2000-01-01' }));
    expect(await countIntroducedToday(new Date())).toBe(2);
  });

  it('does not count cards introduced yesterday', async () => {
    const yesterday = new Date(Date.now() - 86_400_000).toISOString().slice(0, 10);
    await saveCard('x', JSON.stringify({ introduced_date: yesterday }));
    expect(await countIntroducedToday(new Date())).toBe(0);
  });
});

describe('getAllCards / putCard', () => {
  it('getAllCards returns empty when no cards', async () => {
    expect(await getAllCards()).toEqual([]);
  });

  it('getAllCards returns all entries with updated_at', async () => {
    await saveCard('a', '{"v":1}');
    await saveCard('b', '{"v":2}');
    const all = await getAllCards();
    expect(all).toHaveLength(2);
    expect(all.every(c => 'updated_at' in c)).toBe(true);
  });

  it('putCard stores explicit updated_at', async () => {
    const ts = '2024-01-01T00:00:00.000Z';
    await putCard('pk', '{"v":1}', ts);
    const all = await getAllCards();
    expect(all[0].updated_at).toBe(ts);
  });

  it('putCard overwrites existing entry', async () => {
    await putCard('pk', '{"v":1}', '2024-01-01T00:00:00.000Z');
    await putCard('pk', '{"v":2}', '2024-06-01T00:00:00.000Z');
    const all = await getAllCards();
    expect(all).toHaveLength(1);
    expect(all[0].card_json).toBe('{"v":2}');
  });

  it('saveCard sets updated_at automatically', async () => {
    await saveCard('k', '{}');
    const all = await getAllCards();
    expect(all[0].updated_at).toBeTruthy();
    expect(new Date(all[0].updated_at).getTime()).toBeGreaterThan(0);
  });
});

describe('deck cache', () => {
  it('getDeckCache returns null for unknown deck', async () => {
    expect(await getDeckCache('x')).toBeNull();
  });

  it('saveDeckCache / getDeckCache round-trips', async () => {
    const data = { items: ['a', 'b'], mode: 'words' };
    await saveDeckCache('d1', data);
    expect(await getDeckCache('d1')).toEqual(data);
  });

  it('deck list cache round-trips', async () => {
    const decks = [{ id: 'x', name: 'Test' }];
    await saveDeckListCache(decks);
    expect(await getDeckListCache()).toEqual(decks);
  });

  it('getDeckListCache returns null when empty', async () => {
    expect(await getDeckListCache()).toBeNull();
  });
});
