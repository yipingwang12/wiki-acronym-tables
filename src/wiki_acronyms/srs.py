"""FSRS-based spaced repetition with length-scaled latency thresholds."""

from __future__ import annotations

from fsrs import Card, Rating, Scheduler

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


class SRSScheduler:
    def __init__(self, logger: QuizLogger, desired_retention: float = 0.9) -> None:
        self._logger = logger
        self._scheduler = Scheduler(desired_retention=desired_retention)

    def review(self, item_text: str, mode: str, response_secs: float, correct: bool) -> Rating:
        key = make_item_key(item_text)
        rating = classify_response(mode, item_text, response_secs, correct)
        card_json = self._logger.get_card(key)
        card = Card.from_json(card_json) if card_json else Card()
        card, _ = self._scheduler.review_card(card, rating)
        self._logger.save_card(key, card.to_json())
        return rating

    def get_due_order(self, item_texts: list[str]) -> list[int]:
        """Return indices of items sorted by due date (overdue/new first, future last)."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)

        def due_key(idx: int) -> float:
            key = make_item_key(item_texts[idx])
            card_json = self._logger.get_card(key)
            if not card_json:
                return float('-inf')  # new cards first
            card = Card.from_json(card_json)
            return (card.due - now).total_seconds()

        return sorted(range(len(item_texts)), key=due_key)

    def get_due_count(self, item_texts: list[str]) -> int:
        """Return number of items that are due now (overdue or new)."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        count = 0
        for text in item_texts:
            card_json = self._logger.get_card(make_item_key(text))
            if not card_json:
                count += 1
            else:
                card = Card.from_json(card_json)
                if card.due <= now:
                    count += 1
        return count
