/**
 * Unit tests for SRSScheduler and classifyResponse.
 * Uses a fake DB to avoid IndexedDB dependency.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { SRSScheduler, classifyResponse, Rating } from '../srs.js';

// --- Fake in-memory DB ---

class FakeDB {
  constructor() { this._cards = {}; this._introducedToday = 0; }
  async getCard(key) { return this._cards[key] ?? null; }
  async saveCard(key, val) { this._cards[key] = val; }
  async countIntroducedToday() { return this._introducedToday; }
  setIntroducedToday(n) { this._introducedToday = n; }
}

const ITEM = 'test item';
const MODE = 'words';
const NOW = new Date('2024-01-01T12:00:00Z');

function makeScheduler(db, opts = {}) {
  return new SRSScheduler(db, {
    learningSteps: [1, 10],
    graduatedSteps: [1, 2],
    relearnSteps: [1],
    newCardsPerDay: 20,
    ...opts,
  });
}

// --- classifyResponse ---

describe('classifyResponse', () => {
  it('incorrect → Again', () => {
    expect(classifyResponse('words', 'hello world', 0, false)).toBe(Rating.Again);
  });
  it('fast correct → Easy', () => {
    // Base 1.5 + 2*0.30 + 10*0.05 = 2.6; response < 2.6 → Easy
    expect(classifyResponse('words', 'hello world', 1, true)).toBe(Rating.Easy);
  });
  it('medium correct → Good', () => {
    // easyT ≈ 2.6, hardT = 1.5 + 2*1.50 + 10*0.20 = 6.5
    expect(classifyResponse('words', 'hello world', 4, true)).toBe(Rating.Good);
  });
  it('slow correct → Hard', () => {
    expect(classifyResponse('words', 'hello world', 99, true)).toBe(Rating.Hard);
  });
  it('acronym mode uses word-count', () => {
    // acronym: n=2 words, easyT = 1.5 + 2*0.30 = 2.1
    expect(classifyResponse('acronym', 'hello world', 1, true)).toBe(Rating.Easy);
    expect(classifyResponse('acronym', 'hello world', 5, true)).toBe(Rating.Hard);
  });
  it('digits mode uses char-count', () => {
    // digits: n=3 chars, easyT = 1.5 + 3*0.40 = 2.7
    expect(classifyResponse('digits', '123', 1, true)).toBe(Rating.Easy);
    expect(classifyResponse('digits', '123', 20, true)).toBe(Rating.Hard);
  });
});

// --- New card ---

describe('new card initialisation', () => {
  it('first review creates learning state', async () => {
    const db = new FakeDB();
    const s = makeScheduler(db);
    await s.review(ITEM, MODE, 1, true, NOW);
    const raw = await db.getCard(await import('../itemKey.js').then(m => m.itemKey(ITEM)));
    const state = JSON.parse(raw);
    expect(state.learning_step).toBe(0);
    expect(state.graduated_step).toBeNull();
    expect(state.relearning_step).toBeNull();
    expect(state.introduced_date).toBe('2024-01-01');
  });
});

// --- Learning phase ---

describe('learning phase', () => {
  let db, s, key;
  beforeEach(async () => {
    db = new FakeDB();
    s = makeScheduler(db);
    key = await import('../itemKey.js').then(m => m.itemKey(ITEM));
  });

  it('correct at step 0 → step 1', async () => {
    // First review: creates new card at step 0
    await s.review(ITEM, MODE, 1, true, NOW);
    // Second review: advances step
    const t2 = new Date(NOW.getTime() + 2 * 60_000);
    await s.review(ITEM, MODE, 1, true, t2);
    const state = JSON.parse(await db.getCard(key));
    expect(state.learning_step).toBe(1);
  });

  it('incorrect resets to step 0', async () => {
    await s.review(ITEM, MODE, 1, true, NOW);
    const t2 = new Date(NOW.getTime() + 2 * 60_000);
    await s.review(ITEM, MODE, 1, true, t2);
    const t3 = new Date(NOW.getTime() + 15 * 60_000);
    await s.review(ITEM, MODE, 1, false, t3);
    const state = JSON.parse(await db.getCard(key));
    expect(state.learning_step).toBe(0);
  });

  it('completing all learning steps → graduated_step=0', async () => {
    // Steps [1,10]: need 2 correct reviews after creation
    await s.review(ITEM, MODE, 1, true, NOW);
    const t2 = new Date(NOW.getTime() + 2 * 60_000);
    await s.review(ITEM, MODE, 1, true, t2);
    const t3 = new Date(NOW.getTime() + 15 * 60_000);
    await s.review(ITEM, MODE, 1, true, t3);
    const state = JSON.parse(await db.getCard(key));
    expect(state.learning_step).toBeNull();
    expect(state.graduated_step).toBe(0);
  });
});

// --- Graduated phase ---

describe('graduated phase', () => {
  let db, s, key;

  async function advanceToGraduated() {
    db = new FakeDB();
    s = makeScheduler(db);
    key = await import('../itemKey.js').then(m => m.itemKey(ITEM));
    // 3 reviews to get through learning [1,10] steps
    await s.review(ITEM, MODE, 1, true, NOW);
    const t2 = new Date(NOW.getTime() + 2 * 60_000);
    await s.review(ITEM, MODE, 1, true, t2);
    const t3 = new Date(NOW.getTime() + 15 * 60_000);
    await s.review(ITEM, MODE, 1, true, t3);
  }

  it('correct at graduated step 0 → step 1', async () => {
    await advanceToGraduated();
    const t4 = new Date(NOW.getTime() + 26 * 3600_000);
    await s.review(ITEM, MODE, 1, true, t4);
    const state = JSON.parse(await db.getCard(key));
    expect(state.graduated_step).toBe(1);
  });

  it('completing all graduated steps → FSRS phase', async () => {
    await advanceToGraduated();
    // Steps [1,2]: need 2 correct graduated reviews
    const t4 = new Date(NOW.getTime() + 26 * 3600_000);
    await s.review(ITEM, MODE, 1, true, t4);
    const t5 = new Date(t4.getTime() + 49 * 3600_000);
    await s.review(ITEM, MODE, 1, true, t5);
    const state = JSON.parse(await db.getCard(key));
    expect(state.graduated_step).toBeNull();
    expect(state.fsrs).not.toBeNull();
  });

  it('incorrect at graduated → resets to step 0', async () => {
    await advanceToGraduated();
    const t4 = new Date(NOW.getTime() + 26 * 3600_000);
    await s.review(ITEM, MODE, 1, false, t4);
    const state = JSON.parse(await db.getCard(key));
    expect(state.graduated_step).toBe(0);
  });
});

// --- FSRS phase ---

describe('FSRS phase', () => {
  let db, s, key;

  async function advanceToFsrs() {
    db = new FakeDB();
    s = makeScheduler(db);
    key = await import('../itemKey.js').then(m => m.itemKey(ITEM));
    let t = NOW;
    // Through learning [1,10]
    await s.review(ITEM, MODE, 1, true, t); t = new Date(t.getTime() + 2*60_000);
    await s.review(ITEM, MODE, 1, true, t); t = new Date(t.getTime() + 15*60_000);
    await s.review(ITEM, MODE, 1, true, t); t = new Date(t.getTime() + 26*3600_000);
    // Through graduated [1,2]
    await s.review(ITEM, MODE, 1, true, t); t = new Date(t.getTime() + 49*3600_000);
    await s.review(ITEM, MODE, 1, true, t);
    return t;
  }

  it('correct FSRS review updates fsrs card', async () => {
    const t = await advanceToFsrs();
    const t2 = new Date(t.getTime() + 5 * 86_400_000);
    await s.review(ITEM, MODE, 1, true, t2);
    const state = JSON.parse(await db.getCard(key));
    expect(state.fsrs).not.toBeNull();
    const card = JSON.parse(state.fsrs);
    expect(card.stability).toBeGreaterThan(0);
    expect(state.relearning_step).toBeNull();
  });

  it('lapse triggers relearning_step=0', async () => {
    const t = await advanceToFsrs();
    const t2 = new Date(t.getTime() + 5 * 86_400_000);
    await s.review(ITEM, MODE, 1, false, t2);
    const state = JSON.parse(await db.getCard(key));
    expect(state.relearning_step).toBe(0);
  });
});

// --- Lapse forgiveness ---

describe('lapse forgiveness', () => {
  it('diffForgiveness=1.0 → difficulty unchanged', async () => {
    const db = new FakeDB();
    const s = makeScheduler(db, { difficultyForgiveness: 1.0, stabilityForgiveness: 1.0 });
    const key = await import('../itemKey.js').then(m => m.itemKey(ITEM));

    let t = NOW;
    await s.review(ITEM, MODE, 1, true, t); t = new Date(t.getTime() + 2*60_000);
    await s.review(ITEM, MODE, 1, true, t); t = new Date(t.getTime() + 15*60_000);
    await s.review(ITEM, MODE, 1, true, t); t = new Date(t.getTime() + 26*3600_000);
    await s.review(ITEM, MODE, 1, true, t); t = new Date(t.getTime() + 49*3600_000);
    await s.review(ITEM, MODE, 1, true, t);
    const preLapse = JSON.parse(JSON.parse(await db.getCard(key)).fsrs);

    t = new Date(t.getTime() + 5*86_400_000);
    await s.review(ITEM, MODE, 1, false, t);
    const postLapse = JSON.parse(JSON.parse(await db.getCard(key)).fsrs);

    // With forgiveness=1.0: difficulty = old + (new-old)*(1-1) = old
    expect(postLapse.difficulty).toBeCloseTo(preLapse.difficulty, 5);
    // Stability = old + (new-old)*(1-1) = old
    expect(postLapse.stability).toBeCloseTo(preLapse.stability, 5);
  });

  it('diffForgiveness=0.0 → full FSRS lapse applied', async () => {
    const db = new FakeDB();
    const s = makeScheduler(db, { difficultyForgiveness: 0.0, stabilityForgiveness: 0.0 });
    const key = await import('../itemKey.js').then(m => m.itemKey(ITEM));

    let t = NOW;
    await s.review(ITEM, MODE, 1, true, t); t = new Date(t.getTime() + 2*60_000);
    await s.review(ITEM, MODE, 1, true, t); t = new Date(t.getTime() + 15*60_000);
    await s.review(ITEM, MODE, 1, true, t); t = new Date(t.getTime() + 26*3600_000);
    await s.review(ITEM, MODE, 1, true, t); t = new Date(t.getTime() + 49*3600_000);
    await s.review(ITEM, MODE, 1, true, t);
    const preLapse = JSON.parse(JSON.parse(await db.getCard(key)).fsrs);

    t = new Date(t.getTime() + 5*86_400_000);
    await s.review(ITEM, MODE, 1, false, t);
    const postLapse = JSON.parse(JSON.parse(await db.getCard(key)).fsrs);

    // forgiveness=0 → FSRS values fully applied, stability should decrease
    expect(postLapse.stability).toBeLessThan(preLapse.stability);
    expect(postLapse.difficulty).toBeGreaterThanOrEqual(preLapse.difficulty);
  });
});

// --- Relearning phase ---

describe('relearning phase', () => {
  it('correct in relearning → exits relearning', async () => {
    const db = new FakeDB();
    const s = makeScheduler(db, { relearnSteps: [1] });
    const key = await import('../itemKey.js').then(m => m.itemKey(ITEM));

    let t = NOW;
    await s.review(ITEM, MODE, 1, true, t); t = new Date(t.getTime() + 2*60_000);
    await s.review(ITEM, MODE, 1, true, t); t = new Date(t.getTime() + 15*60_000);
    await s.review(ITEM, MODE, 1, true, t); t = new Date(t.getTime() + 26*3600_000);
    await s.review(ITEM, MODE, 1, true, t); t = new Date(t.getTime() + 49*3600_000);
    await s.review(ITEM, MODE, 1, true, t);

    // Lapse
    t = new Date(t.getTime() + 5*86_400_000);
    await s.review(ITEM, MODE, 1, false, t);
    let state = JSON.parse(await db.getCard(key));
    expect(state.relearning_step).toBe(0);

    // Correct relearn
    t = new Date(t.getTime() + 26*3600_000);
    await s.review(ITEM, MODE, 1, true, t);
    state = JSON.parse(await db.getCard(key));
    expect(state.relearning_step).toBeNull();
  });

  it('incorrect in relearning resets to step 0', async () => {
    const db = new FakeDB();
    const s = makeScheduler(db, { relearnSteps: [1, 3] });
    const key = await import('../itemKey.js').then(m => m.itemKey(ITEM));

    let t = NOW;
    await s.review(ITEM, MODE, 1, true, t); t = new Date(t.getTime() + 2*60_000);
    await s.review(ITEM, MODE, 1, true, t); t = new Date(t.getTime() + 15*60_000);
    await s.review(ITEM, MODE, 1, true, t); t = new Date(t.getTime() + 26*3600_000);
    await s.review(ITEM, MODE, 1, true, t); t = new Date(t.getTime() + 49*3600_000);
    await s.review(ITEM, MODE, 1, true, t);

    t = new Date(t.getTime() + 5*86_400_000);
    await s.review(ITEM, MODE, 1, false, t);
    t = new Date(t.getTime() + 26*3600_000);
    await s.review(ITEM, MODE, 1, true, t); // relearn step 0 → 1
    t = new Date(t.getTime() + 4*86_400_000);
    await s.review(ITEM, MODE, 1, false, t); // fail → reset to 0
    const state = JSON.parse(await db.getCard(key));
    expect(state.relearning_step).toBe(0);
  });
});

// --- Interval cap ---

describe('interval cap', () => {
  it('caps FSRS scheduled_days at maxIntervalDays', async () => {
    const db = new FakeDB();
    const s = makeScheduler(db, { maxIntervalDays: 1 });
    const key = await import('../itemKey.js').then(m => m.itemKey(ITEM));

    let t = NOW;
    await s.review(ITEM, MODE, 1, true, t); t = new Date(t.getTime() + 2*60_000);
    await s.review(ITEM, MODE, 1, true, t); t = new Date(t.getTime() + 15*60_000);
    await s.review(ITEM, MODE, 1, true, t); t = new Date(t.getTime() + 26*3600_000);
    await s.review(ITEM, MODE, 1, true, t); t = new Date(t.getTime() + 49*3600_000);
    await s.review(ITEM, MODE, 1, true, t);

    t = new Date(t.getTime() + 5*86_400_000);
    await s.review(ITEM, MODE, 1, true, t);
    const state = JSON.parse(await db.getCard(key));
    const card = JSON.parse(state.fsrs);
    expect(card.scheduled_days).toBeLessThanOrEqual(1);
  });
});

// --- getPhase ---

describe('getPhase', () => {
  it('null card → learning', async () => {
    const db = new FakeDB();
    const s = makeScheduler(db);
    expect(await s.getPhase(ITEM)).toBe('learning');
  });

  it('after first review → learning', async () => {
    const db = new FakeDB();
    const s = makeScheduler(db);
    await s.review(ITEM, MODE, 1, true, NOW);
    expect(await s.getPhase(ITEM)).toBe('learning');
  });
});

// --- getDueCount / getDueOrder ---

describe('getDueCount', () => {
  it('new unseen items within budget are due', async () => {
    const db = new FakeDB();
    const s = makeScheduler(db, { newCardsPerDay: 5 });
    const items = ['a', 'b', 'c'];
    const count = await s.getDueCount(items, NOW);
    expect(count).toBe(3);
  });

  it('items beyond budget are not due', async () => {
    const db = new FakeDB();
    const s = makeScheduler(db, { newCardsPerDay: 2 });
    const items = ['a', 'b', 'c'];
    const count = await s.getDueCount(items, NOW);
    expect(count).toBe(2);
  });
});
