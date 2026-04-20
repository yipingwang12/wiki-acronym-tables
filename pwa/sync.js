/**
 * SRS sync engine: pushes local IndexedDB state to /api/sync and merges server response.
 * Last-write-wins on updated_at.
 */

import { getAllCards, putCard } from './db.js';

export async function syncWithServer(serverUrl = '') {
  if (!navigator.onLine) return { synced: false, reason: 'offline' };

  try {
    const local = await getAllCards();
    const changes = local.map(c => ({
      item_key: c.item_key,
      card_json: c.card_json,
      updated_at: c.updated_at,
    }));

    const resp = await fetch(`${serverUrl}/api/sync`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ changes }),
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

    const { cards: serverCards } = await resp.json();

    const localMap = Object.fromEntries(local.map(c => [c.item_key, c]));
    for (const sc of serverCards) {
      const lc = localMap[sc.item_key];
      if (!lc || sc.updated_at > lc.updated_at) {
        await putCard(sc.item_key, sc.card_json, sc.updated_at);
      }
    }

    return { synced: true, count: serverCards.length };
  } catch (err) {
    return { synced: false, reason: err.message };
  }
}
