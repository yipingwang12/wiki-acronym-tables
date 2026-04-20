/**
 * Tests for sync.js.
 * Mocks fetch and db.js to avoid real network / IndexedDB.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock db.js before importing sync.js
vi.mock('../db.js', () => ({
  getAllCards: vi.fn(),
  putCard: vi.fn(),
}));

import { syncWithServer } from '../sync.js';
import { getAllCards, putCard } from '../db.js';

beforeEach(() => {
  vi.resetAllMocks();
  putCard.mockResolvedValue(undefined);
});

function mockFetch(cards, ok = true) {
  global.fetch = vi.fn().mockResolvedValue({
    ok,
    status: ok ? 200 : 500,
    json: () => Promise.resolve({ cards }),
  });
}

describe('syncWithServer', () => {
  it('returns offline when navigator.onLine is false', async () => {
    Object.defineProperty(navigator, 'onLine', { value: false, writable: true, configurable: true });
    const result = await syncWithServer('');
    expect(result.synced).toBe(false);
    expect(result.reason).toBe('offline');
    Object.defineProperty(navigator, 'onLine', { value: true, configurable: true });
  });

  it('sends local cards to server', async () => {
    const local = [{ item_key: 'k1', card_json: '{"v":1}', updated_at: '2024-01-01T00:00:00Z' }];
    getAllCards.mockResolvedValue(local);
    mockFetch([]);
    await syncWithServer('http://localhost:5001');
    expect(fetch).toHaveBeenCalledWith(
      'http://localhost:5001/api/sync',
      expect.objectContaining({ method: 'POST' })
    );
    const body = JSON.parse(fetch.mock.calls[0][1].body);
    expect(body.changes).toHaveLength(1);
    expect(body.changes[0].item_key).toBe('k1');
  });

  it('applies newer server cards to local DB', async () => {
    getAllCards.mockResolvedValue([
      { item_key: 'k1', card_json: '{"v":1}', updated_at: '2024-01-01T00:00:00Z' },
    ]);
    mockFetch([
      { item_key: 'k1', card_json: '{"v":99}', updated_at: '2024-06-01T00:00:00Z' },
    ]);
    await syncWithServer('');
    expect(putCard).toHaveBeenCalledWith('k1', '{"v":99}', '2024-06-01T00:00:00Z');
  });

  it('does not overwrite newer local card with older server card', async () => {
    getAllCards.mockResolvedValue([
      { item_key: 'k1', card_json: '{"v":5}', updated_at: '2024-06-01T00:00:00Z' },
    ]);
    mockFetch([
      { item_key: 'k1', card_json: '{"v":1}', updated_at: '2024-01-01T00:00:00Z' },
    ]);
    await syncWithServer('');
    expect(putCard).not.toHaveBeenCalled();
  });

  it('inserts new server cards that do not exist locally', async () => {
    getAllCards.mockResolvedValue([]);
    mockFetch([
      { item_key: 'new', card_json: '{"v":1}', updated_at: '2024-01-01T00:00:00Z' },
    ]);
    await syncWithServer('');
    expect(putCard).toHaveBeenCalledWith('new', '{"v":1}', '2024-01-01T00:00:00Z');
  });

  it('returns synced:true with card count on success', async () => {
    getAllCards.mockResolvedValue([]);
    mockFetch([{ item_key: 'a', card_json: '{}', updated_at: '2024-01-01T00:00:00Z' }]);
    const result = await syncWithServer('');
    expect(result.synced).toBe(true);
    expect(result.count).toBe(1);
  });

  it('returns synced:false on HTTP error', async () => {
    getAllCards.mockResolvedValue([]);
    mockFetch([], false);
    const result = await syncWithServer('');
    expect(result.synced).toBe(false);
    expect(result.reason).toContain('HTTP 500');
  });

  it('returns synced:false on network error', async () => {
    getAllCards.mockResolvedValue([]);
    global.fetch = vi.fn().mockRejectedValue(new Error('network fail'));
    const result = await syncWithServer('');
    expect(result.synced).toBe(false);
    expect(result.reason).toBe('network fail');
  });

  it('handles empty local and server state gracefully', async () => {
    getAllCards.mockResolvedValue([]);
    mockFetch([]);
    const result = await syncWithServer('');
    expect(result.synced).toBe(true);
    expect(result.count).toBe(0);
    expect(putCard).not.toHaveBeenCalled();
  });

  it('does not overwrite local card when timestamps are identical', async () => {
    // LWW uses strict >, so equal timestamps → server does not win
    const ts = '2024-03-01T12:00:00Z';
    getAllCards.mockResolvedValue([
      { item_key: 'k1', card_json: '{"local":true}', updated_at: ts },
    ]);
    mockFetch([{ item_key: 'k1', card_json: '{"local":false}', updated_at: ts }]);
    await syncWithServer('');
    expect(putCard).not.toHaveBeenCalled();
  });

  it('applies server cards for keys absent locally (other device reviews)', async () => {
    // Client only has k1; server returns k1 + k2 (reviewed on another device)
    getAllCards.mockResolvedValue([
      { item_key: 'k1', card_json: '{"v":1}', updated_at: '2024-01-01T00:00:00Z' },
    ]);
    mockFetch([
      { item_key: 'k1', card_json: '{"v":1}', updated_at: '2024-01-01T00:00:00Z' },
      { item_key: 'k2', card_json: '{"v":7}', updated_at: '2024-06-01T00:00:00Z' },
    ]);
    await syncWithServer('');
    expect(putCard).toHaveBeenCalledWith('k2', '{"v":7}', '2024-06-01T00:00:00Z');
    expect(putCard).toHaveBeenCalledTimes(1);
  });

  it('applies only newer cards when server returns a mix', async () => {
    getAllCards.mockResolvedValue([
      { item_key: 'old', card_json: '{"v":1}', updated_at: '2024-06-01T00:00:00Z' },
      { item_key: 'new', card_json: '{"v":1}', updated_at: '2024-01-01T00:00:00Z' },
    ]);
    mockFetch([
      { item_key: 'old', card_json: '{"v":2}', updated_at: '2024-01-01T00:00:00Z' }, // older → skip
      { item_key: 'new', card_json: '{"v":9}', updated_at: '2024-09-01T00:00:00Z' }, // newer → apply
    ]);
    await syncWithServer('');
    expect(putCard).toHaveBeenCalledTimes(1);
    expect(putCard).toHaveBeenCalledWith('new', '{"v":9}', '2024-09-01T00:00:00Z');
  });
});
