"""FSRS-based spaced repetition with length-scaled latency thresholds."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from fsrs import Card, Rating, Scheduler, State

from .logger import QuizLogger, item_key as make_item_key

_BASE = 1.5  # fixed orienting + submit time (seconds)

# words mode: (per_word_rate, per_char_rate)
_WORDS_EASY = (0.30, 0.05)
_WORDS_HARD = (1.50, 0.20)

# acronym / digits: per_token_rate
_TOKEN_EASY = {'acronym': 0.30, 'digits': 0.40}
_TOKEN_HARD = {'acronym': 1.50, 'digits': 2.00}


def _thresholds(mode: str, item_text: str) -> tuple[float, float]:
    if mode == 'words':
        words = item_text.split()
        n_w, n_c = len(words), sum(len(w) for w in words)
        return (
            _BASE + n_w * _WORDS_EASY[0] + n_c * _WORDS_EASY[1],
            _BASE + n_w * _WORDS_HARD[0] + n_c * _WORDS_HARD[1],
        )
    n = len(item_text.split()) if mode == 'acronym' else len(item_text.strip())
    return (
        _BASE + n * _TOKEN_EASY[mode],
        _BASE + n * _TOKEN_HARD[mode],
    )


def classify_response(mode: str, item_text: str, response_secs: float, correct: bool) -> Rating:
    if not correct:
        return Rating.Again
    easy_t, hard_t = _thresholds(mode, item_text)
    if response_secs < easy_t:
        return Rating.Easy
    if response_secs < hard_t:
        return Rating.Good
    return Rating.Hard


def _load_state(card_json: str) -> dict:
    """Parse card_json, upgrading legacy bare-FSRS format to state envelope."""
    data = json.loads(card_json)
    if 'learning_step' in data:
        data.setdefault('relearning_step', None)
        data.setdefault('relearn_step_due', None)
        return data
    # Legacy format: raw FSRS card JSON — treat as already graduated.
    return {
        'fsrs': card_json,
        'learning_step': None,
        'step_due': None,
        'introduced_date': None,
        'relearning_step': None,
        'relearn_step_due': None,
    }


class SRSScheduler:
    def __init__(
        self,
        logger: QuizLogger,
        desired_retention: float = 0.9,
        max_interval_days: int | None = 365,
        learning_steps: list[int] | None = None,   # minutes
        new_cards_per_day: int = 20,
        relearn_steps: list[int] | None = None,    # days
        difficulty_forgiveness: float = 1.0,       # 1.0 = no difficulty increase on lapse
        stability_forgiveness: float = 1.0,        # 1.0 = no stability drop on lapse
    ) -> None:
        self._logger = logger
        self._scheduler = Scheduler(desired_retention=desired_retention)
        self._max_interval_days = max_interval_days
        self._steps = learning_steps if learning_steps is not None else [1, 10]
        self._new_per_day = new_cards_per_day
        self._relearn_steps = relearn_steps if relearn_steps is not None else [1, 2, 3]
        self._difficulty_forgiveness = difficulty_forgiveness
        self._stability_forgiveness = stability_forgiveness

    def _cap_card(self, card: Card) -> Card:
        if self._max_interval_days is not None:
            max_due = datetime.now(timezone.utc) + timedelta(days=self._max_interval_days)
            if card.due > max_due:
                card.due = max_due
                card.scheduled_days = self._max_interval_days
        return card

    def _apply_lapse_forgiveness(self, card: Card, old_stability: float, old_difficulty: float) -> Card:
        now = datetime.now(timezone.utc)
        card.difficulty = old_difficulty + (card.difficulty - old_difficulty) * (1 - self._difficulty_forgiveness)
        new_stability = old_stability + (card.stability - old_stability) * (1 - self._stability_forgiveness)
        card.stability = new_stability
        card.due = now + timedelta(days=new_stability)
        card.scheduled_days = max(1, int(new_stability))
        # Reset to Review so FSRS treats the next real review correctly.
        card.state = State.Review
        return card

    def review(self, item_text: str, mode: str, response_secs: float, correct: bool) -> Rating:
        now = datetime.now(timezone.utc)
        key = make_item_key(item_text)
        rating = classify_response(mode, item_text, response_secs, correct)
        raw = self._logger.get_card(key)

        if raw is None:
            if not self._steps:
                # No learning phase — graduate immediately on first review.
                card = Card()
                card, _ = self._scheduler.review_card(card, rating)
                card = self._cap_card(card)
                state = {
                    'fsrs': card.to_json(),
                    'learning_step': None,
                    'step_due': None,
                    'introduced_date': now.date().isoformat(),
                    'relearning_step': None,
                    'relearn_step_due': None,
                }
            else:
                state = {
                    'fsrs': None,
                    'learning_step': 0,
                    'step_due': (now + timedelta(minutes=self._steps[0])).isoformat(),
                    'introduced_date': now.date().isoformat(),
                    'relearning_step': None,
                    'relearn_step_due': None,
                }
            self._logger.save_card(key, json.dumps(state))
            return rating

        state = _load_state(raw)

        if state['learning_step'] is not None:
            step = state['learning_step']
            if not correct:
                state['learning_step'] = 0
                state['step_due'] = (now + timedelta(minutes=self._steps[0])).isoformat()
            else:
                next_step = step + 1
                if next_step >= len(self._steps):
                    card = Card()
                    card, _ = self._scheduler.review_card(card, rating)
                    card = self._cap_card(card)
                    state['fsrs'] = card.to_json()
                    state['learning_step'] = None
                    state['step_due'] = None
                else:
                    state['learning_step'] = next_step
                    state['step_due'] = (now + timedelta(minutes=self._steps[next_step])).isoformat()

        elif state['relearning_step'] is not None:
            step = state['relearning_step']
            if not correct:
                state['relearning_step'] = 0
                state['relearn_step_due'] = (now + timedelta(days=self._relearn_steps[0])).isoformat()
            else:
                next_step = step + 1
                if next_step >= len(self._relearn_steps):
                    state['relearning_step'] = None
                    state['relearn_step_due'] = None
                else:
                    state['relearning_step'] = next_step
                    state['relearn_step_due'] = (now + timedelta(days=self._relearn_steps[next_step])).isoformat()

        else:
            card = Card.from_json(state['fsrs'])
            if rating == Rating.Again:
                old_stability = card.stability
                old_difficulty = card.difficulty
                card, _ = self._scheduler.review_card(card, rating)
                card = self._apply_lapse_forgiveness(card, old_stability, old_difficulty)
                card = self._cap_card(card)
                state['fsrs'] = card.to_json()
                state['relearning_step'] = 0
                state['relearn_step_due'] = (now + timedelta(days=self._relearn_steps[0])).isoformat()
            else:
                card, _ = self._scheduler.review_card(card, rating)
                card = self._cap_card(card)
                state['fsrs'] = card.to_json()

        self._logger.save_card(key, json.dumps(state))
        return rating

    def _classify_items(self, item_texts: list[str]) -> tuple[list[int], int]:
        """Sort items into due/future buckets; return (ordered_indices, due_count)."""
        now = datetime.now(timezone.utc)
        new_budget = max(0, self._new_per_day - self._logger.count_introduced_today())

        new_due: list[int] = []
        learning_due: list[tuple[float, int]] = []    # (overdue_secs, idx)
        fsrs_due: list[tuple[float, int]] = []         # (due_secs negative, idx)
        learning_future: list[tuple[datetime, int]] = []
        fsrs_future: list[tuple[datetime, int]] = []
        new_future: list[int] = []

        for idx, text in enumerate(item_texts):
            raw = self._logger.get_card(make_item_key(text))
            if raw is None:
                if len(new_due) < new_budget:
                    new_due.append(idx)
                else:
                    new_future.append(idx)
                continue
            state = _load_state(raw)

            # Determine the active step due time (learning or relearning).
            if state['learning_step'] is not None:
                step_due = datetime.fromisoformat(state['step_due'])
                if step_due <= now:
                    learning_due.append(((now - step_due).total_seconds(), idx))
                else:
                    learning_future.append((step_due, idx))
            elif state['relearning_step'] is not None:
                step_due = datetime.fromisoformat(state['relearn_step_due'])
                if step_due <= now:
                    learning_due.append(((now - step_due).total_seconds(), idx))
                else:
                    learning_future.append((step_due, idx))
            else:
                card = Card.from_json(state['fsrs'])
                if card.due <= now:
                    fsrs_due.append(((card.due - now).total_seconds(), idx))
                else:
                    fsrs_future.append((card.due, idx))

        learning_due.sort(key=lambda x: -x[0])
        fsrs_due.sort(key=lambda x: x[0])
        learning_future.sort(key=lambda x: x[0])
        fsrs_future.sort(key=lambda x: x[0])

        due_count = len(new_due) + len(learning_due) + len(fsrs_due)
        order = (
            new_due
            + [idx for _, idx in learning_due]
            + [idx for _, idx in fsrs_due]
            + [idx for _, idx in learning_future]
            + [idx for _, idx in fsrs_future]
            + new_future
        )
        return order, due_count

    def get_phase(self, item_text: str) -> str:
        """Return 'learning', 'relearning', or 'review' for the current card state."""
        raw = self._logger.get_card(make_item_key(item_text))
        if raw is None:
            return 'learning'
        state = _load_state(raw)
        if state['learning_step'] is not None:
            return 'learning'
        if state['relearning_step'] is not None:
            return 'relearning'
        return 'review'

    def get_due_order(self, item_texts: list[str]) -> list[int]:
        return self._classify_items(item_texts)[0]

    def get_due_count(self, item_texts: list[str]) -> int:
        return self._classify_items(item_texts)[1]
