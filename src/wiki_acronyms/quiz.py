"""Blindman's bluff quiz: given line acronym + one revealed letter, spot the wrong word."""

from __future__ import annotations

import random
from dataclasses import dataclass

CONFUSABLES: dict[str, list[str]] = {
    'a': ['e', 'o', 'u'],
    'b': ['d', 'p', 'q', 'h'],
    'c': ['e', 'o', 'g'],
    'd': ['b', 'p', 'q'],
    'e': ['a', 'c', 'o'],
    'f': ['t', 'i', 'l'],
    'g': ['q', 'c', 'o'],
    'h': ['b', 'n', 'm'],
    'i': ['l', 'j', 't'],
    'j': ['i', 'l'],
    'k': ['h', 'x'],
    'l': ['i', 'j', 't'],
    'm': ['n', 'h', 'w'],
    'n': ['m', 'h', 'u'],
    'o': ['a', 'c', 'e'],
    'p': ['b', 'd', 'q'],
    'q': ['g', 'p', 'd'],
    'r': ['n', 'v'],
    's': ['z', 'c'],
    't': ['f', 'l', 'i'],
    'u': ['n', 'v'],
    'v': ['u', 'w', 'r'],
    'w': ['v', 'm', 'n'],
    'x': ['k', 'z'],
    'y': ['v', 'j'],
    'z': ['s', 'x'],
}


def pick_confusable(ch: str) -> str:
    """Return a visually similar but different letter, preserving case."""
    lower = ch.lower()
    options = CONFUSABLES.get(lower, [c for c in 'abcdefghijklmnopqrstuvwxyz' if c != lower])
    chosen = random.choice(options)
    return chosen.upper() if ch.isupper() else chosen


def _alpha_indices(word: str) -> list[int]:
    return [i for i, c in enumerate(word) if c.isalpha()]


def _two_letter_display(word: str, extra_pos: int, extra_ch: str) -> str:
    """Show first alpha char + extra_ch at extra_pos; underscore other alpha chars; preserve non-alpha."""
    alpha = _alpha_indices(word)
    if len(alpha) <= 1:
        return word
    first_idx = alpha[0]
    return ''.join(
        c if (not c.isalpha() or i == first_idx)
        else (extra_ch if i == extra_pos else '_')
        for i, c in enumerate(word)
    )


@dataclass
class LineDisplay:
    display: str
    has_wrong: bool
    wrong_words: list[int]  # 1-based; empty when has_wrong is False


def make_line_display(line: str, wrong_prob: float = 0.15) -> LineDisplay:
    """Build masked display; each word reveals one non-first letter, wrong with prob wrong_prob."""
    words = line.split()
    wrong_words: list[int] = []
    parts: list[str] = []

    for i, w in enumerate(words):
        non_first = _alpha_indices(w)[1:]
        if not non_first:
            parts.append(f"{i+1}:{w}")
            continue
        ci = random.choice(non_first)
        actual_ch = w[ci]
        has_wrong = random.random() < wrong_prob
        shown_ch = pick_confusable(actual_ch) if has_wrong else actual_ch
        if has_wrong:
            wrong_words.append(i + 1)
        parts.append(f"{i+1}:{_two_letter_display(w, ci, shown_ch)}")

    return LineDisplay(
        display='  '.join(parts),
        has_wrong=bool(wrong_words),
        wrong_words=wrong_words,
    )


def score_response(display: LineDisplay, user_words: set[int]) -> tuple[bool, str]:
    """Score user's answer. user_words: set of 1-based word indices claimed to have wrong letters."""
    actual = set(display.wrong_words)
    missed = actual - user_words
    false_alarms = user_words - actual
    correct = not missed and not false_alarms

    if correct:
        return True, "Correct!" if actual else "Correct — no wrong letters."

    parts = []
    if missed:
        w = sorted(missed)
        parts.append(f"missed word{'s' if len(w) > 1 else ''} {', '.join(map(str, w))}")
    if false_alarms:
        w = sorted(false_alarms)
        parts.append(f"false alarm on word{'s' if len(w) > 1 else ''} {', '.join(map(str, w))}")
    return False, '; '.join(parts).capitalize() + '.'
