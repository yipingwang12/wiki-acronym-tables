/**
 * SRS scheduler. Port of srs.py.
 *
 * Uses ts-fsrs for FSRS-6 core; wraps it with the same custom
 * learning → graduated-ramp → FSRS → relearning state machine.
 *
 * FSRS weight parity: both Python fsrs==6.3.1 and ts-fsrs==5.3.2 share
 * identical default w[] vectors, verified at implementation time.
 *
 * Lapse stability divergence note: with default forgiveness params (1.0/1.0)
 * the raw FSRS lapse stability is fully overridden by _applyLapseForgiveness,
 * so any minor cross-library divergence in lapse stability is irrelevant.
 * Non-default forgiveness users should be aware of this.
 */

import { fsrs as createFsrs, createEmptyCard, Rating } from 'ts-fsrs';
import { itemKey } from './itemKey.js';

export { Rating };

// --- Rating thresholds (identical to srs.py) ---

const BASE = 1.5;
const WORDS_EASY = [0.30, 0.05];
const WORDS_HARD = [1.50, 0.20];
const TOKEN_EASY = { acronym: 0.30, digits: 0.40 };
const TOKEN_HARD = { acronym: 1.50, digits: 2.00 };

function thresholds(mode, itemText) {
  if (mode === 'words') {
    const words = itemText.split(/\s+/).filter(Boolean);
    const nW = words.length;
    const nC = words.reduce((s, w) => s + w.length, 0);
    return [
      BASE + nW * WORDS_EASY[0] + nC * WORDS_EASY[1],
      BASE + nW * WORDS_HARD[0] + nC * WORDS_HARD[1],
    ];
  }
  const n = mode === 'acronym'
    ? itemText.split(/\s+/).filter(Boolean).length
    : itemText.trim().length;
  return [BASE + n * TOKEN_EASY[mode], BASE + n * TOKEN_HARD[mode]];
}

export function classifyResponse(mode, itemText, responseSecs, correct) {
  if (!correct) return Rating.Again;
  const [easyT, hardT] = thresholds(mode, itemText);
  if (responseSecs < easyT) return Rating.Easy;
  if (responseSecs < hardT) return Rating.Good;
  return Rating.Hard;
}

// --- State envelope helpers ---

function loadState(cardJson) {
  const data = JSON.parse(cardJson);
  if ('learning_step' in data) {
    data.relearning_step    ??= null;
    data.relearn_step_due   ??= null;
    data.graduated_step     ??= null;
    data.graduated_step_due ??= null;
    return data;
  }
  // Legacy bare FSRS card JSON — treat as already in FSRS phase.
  return {
    fsrs: cardJson,
    learning_step: null,
    step_due: null,
    introduced_date: null,
    graduated_step: null,
    graduated_step_due: null,
    relearning_step: null,
    relearn_step_due: null,
  };
}

function addMinutes(date, minutes) {
  return new Date(date.getTime() + minutes * 60_000);
}

function addDays(date, days) {
  return new Date(date.getTime() + days * 86_400_000);
}

// --- SRSScheduler ---

export class SRSScheduler {
  /**
   * @param {object} db - IndexedDB wrapper with async getCard/saveCard/countIntroducedToday
   * @param {object} opts - SRS parameters (all optional, defaults match Python CLI defaults)
   */
  constructor(db, {
    desiredRetention = 0.9,
    maxIntervalDays = 365,
    learningSteps = [1, 10, 60, 360],      // minutes
    graduatedSteps = [1, 2, 3, 4, 5, 6, 7], // days
    newCardsPerDay = 20,
    relearnSteps = [1, 2, 3],               // days
    difficultyForgiveness = 1.0,
    stabilityForgiveness = 1.0,
  } = {}) {
    this._db = db;
    this._f = createFsrs({ enable_fuzz: false, request_retention: desiredRetention });
    this._maxIntervalDays = maxIntervalDays;
    this._steps = learningSteps;
    this._gradSteps = graduatedSteps;
    this._newPerDay = newCardsPerDay;
    this._relearnSteps = relearnSteps;
    this._diffForgiveness = difficultyForgiveness;
    this._stabForgiveness = stabilityForgiveness;
  }

  _capCard(card, now) {
    if (this._maxIntervalDays !== null) {
      const maxDue = addDays(now, this._maxIntervalDays);
      if (new Date(card.due) > maxDue) {
        card.due = maxDue.toISOString();
        card.scheduled_days = this._maxIntervalDays;
      }
    }
    return card;
  }

  _applyLapseForgiveness(card, oldStability, oldDifficulty, now) {
    card.difficulty = oldDifficulty + (card.difficulty - oldDifficulty) * (1 - this._diffForgiveness);
    const newStability = oldStability + (card.stability - oldStability) * (1 - this._stabForgiveness);
    card.stability = newStability;
    card.due = addDays(now, newStability).toISOString();
    card.scheduled_days = Math.max(1, Math.floor(newStability));
    card.state = 2; // State.Review — reset so FSRS treats next review correctly
    return card;
  }

  async review(itemText, mode, responseSecs, correct, now = new Date()) {
    const key = await itemKey(itemText);
    const rating = classifyResponse(mode, itemText, responseSecs, correct);
    const raw = await this._db.getCard(key);

    if (raw === null) {
      const state = {
        fsrs: null,
        learning_step: 0,
        step_due: addMinutes(now, this._steps[0]).toISOString(),
        introduced_date: now.toISOString().slice(0, 10),
        graduated_step: null,
        graduated_step_due: null,
        relearning_step: null,
        relearn_step_due: null,
      };
      await this._db.saveCard(key, JSON.stringify(state));
      return rating;
    }

    const state = loadState(raw);

    if (state.learning_step !== null) {
      const step = state.learning_step;
      if (!correct) {
        state.learning_step = 0;
        state.step_due = addMinutes(now, this._steps[0]).toISOString();
      } else {
        const next = step + 1;
        if (next >= this._steps.length) {
          state.learning_step = null;
          state.step_due = null;
          state.graduated_step = 0;
          state.graduated_step_due = addDays(now, this._gradSteps[0]).toISOString();
        } else {
          state.learning_step = next;
          state.step_due = addMinutes(now, this._steps[next]).toISOString();
        }
      }

    } else if (state.graduated_step !== null) {
      const step = state.graduated_step;
      if (!correct) {
        state.graduated_step = 0;
        state.graduated_step_due = addDays(now, this._gradSteps[0]).toISOString();
      } else {
        const next = step + 1;
        if (next >= this._gradSteps.length) {
          // Hand off to FSRS: initialise a fresh card and review it once.
          let card = createEmptyCard(now);
          const result = this._f.repeat(card, now);
          card = this._capCard(result[rating].card, now);
          state.fsrs = JSON.stringify(card);
          state.graduated_step = null;
          state.graduated_step_due = null;
        } else {
          state.graduated_step = next;
          state.graduated_step_due = addDays(now, this._gradSteps[next]).toISOString();
        }
      }

    } else if (state.relearning_step !== null) {
      const step = state.relearning_step;
      if (!correct) {
        state.relearning_step = 0;
        state.relearn_step_due = addDays(now, this._relearnSteps[0]).toISOString();
      } else {
        const next = step + 1;
        if (next >= this._relearnSteps.length) {
          state.relearning_step = null;
          state.relearn_step_due = null;
        } else {
          state.relearning_step = next;
          state.relearn_step_due = addDays(now, this._relearnSteps[next]).toISOString();
        }
      }

    } else {
      let card = JSON.parse(state.fsrs);
      if (rating === Rating.Again) {
        const oldStability = card.stability;
        const oldDifficulty = card.difficulty;
        const result = this._f.repeat(card, now);
        card = result[Rating.Again].card;
        card = this._applyLapseForgiveness(card, oldStability, oldDifficulty, now);
        card = this._capCard(card, now);
        state.fsrs = JSON.stringify(card);
        state.relearning_step = 0;
        state.relearn_step_due = addDays(now, this._relearnSteps[0]).toISOString();
      } else {
        const result = this._f.repeat(card, now);
        card = this._capCard(result[rating].card, now);
        state.fsrs = JSON.stringify(card);
      }
    }

    await this._db.saveCard(key, JSON.stringify(state));
    return rating;
  }

  async _classifyItems(itemTexts, now = new Date()) {
    const newBudget = Math.max(0, this._newPerDay - await this._db.countIntroducedToday(now));
    const nowMs = now.getTime();

    const newDue = [];
    const learningDue = [];    // [overdueMs, idx]
    const fsrsDue = [];        // [dueMsRelativeToNow, idx]  — negative = overdue
    const learningFuture = []; // [dueDate, idx]
    const fsrsFuture = [];     // [dueDate, idx]
    const newFuture = [];

    for (let idx = 0; idx < itemTexts.length; idx++) {
      const key = await itemKey(itemTexts[idx]);
      const raw = await this._db.getCard(key);

      if (raw === null) {
        if (newDue.length < newBudget) newDue.push(idx);
        else newFuture.push(idx);
        continue;
      }

      const state = loadState(raw);

      if (state.learning_step !== null) {
        const due = new Date(state.step_due);
        if (due <= now) learningDue.push([nowMs - due.getTime(), idx]);
        else learningFuture.push([due.getTime(), idx]);

      } else if (state.graduated_step !== null) {
        const due = new Date(state.graduated_step_due);
        if (due <= now) learningDue.push([nowMs - due.getTime(), idx]);
        else learningFuture.push([due.getTime(), idx]);

      } else if (state.relearning_step !== null) {
        const due = new Date(state.relearn_step_due);
        if (due <= now) learningDue.push([nowMs - due.getTime(), idx]);
        else learningFuture.push([due.getTime(), idx]);

      } else {
        const cardDue = new Date(JSON.parse(state.fsrs).due);
        if (cardDue <= now) fsrsDue.push([cardDue.getTime() - nowMs, idx]);
        else fsrsFuture.push([cardDue.getTime(), idx]);
      }
    }

    // Most overdue first in both buckets.
    learningDue.sort((a, b) => b[0] - a[0]);  // descending overdue ms
    fsrsDue.sort((a, b) => a[0] - b[0]);       // ascending (most negative = most overdue) first
    learningFuture.sort((a, b) => a[0] - b[0]);
    fsrsFuture.sort((a, b) => a[0] - b[0]);

    const dueCount = newDue.length + learningDue.length + fsrsDue.length;
    const order = [
      ...newDue,
      ...learningDue.map(([, i]) => i),
      ...fsrsDue.map(([, i]) => i),
      ...learningFuture.map(([, i]) => i),
      ...fsrsFuture.map(([, i]) => i),
      ...newFuture,
    ];
    return [order, dueCount];
  }

  async getPhase(itemText) {
    const key = await itemKey(itemText);
    const raw = await this._db.getCard(key);
    if (raw === null) return 'learning';
    const state = loadState(raw);
    if (state.learning_step !== null) return 'learning';
    if (state.graduated_step !== null) return 'graduated';
    if (state.relearning_step !== null) return 'relearning';
    return 'review';
  }

  async getDueOrder(itemTexts, now = new Date()) {
    return (await this._classifyItems(itemTexts, now))[0];
  }

  async getDueCount(itemTexts, now = new Date()) {
    return (await this._classifyItems(itemTexts, now))[1];
  }
}
