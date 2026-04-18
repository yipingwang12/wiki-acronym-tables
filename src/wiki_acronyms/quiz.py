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


def _mask_word(word: str, reveal: dict[int, str]) -> str:
    """Show first alpha char and non-alpha chars; underscore other alpha chars unless in reveal."""
    alpha = _alpha_indices(word)
    if not alpha:
        return word
    first = alpha[0]
    return ''.join(
        c if (not c.isalpha() or i == first) else reveal.get(i, '_')
        for i, c in enumerate(word)
    )


@dataclass
class LineDisplay:
    display: str
    has_wrong: bool
    wrong_word: int | None  # 1-based; None when has_wrong is False


def make_line_display(line: str, wrong_prob: float = 0.15) -> LineDisplay:
    """Build masked display for a line, optionally substituting one letter with a confusable."""
    words = line.split()
    candidates = [
        (wi, ci)
        for wi, w in enumerate(words)
        for ci in _alpha_indices(w)[1:]
    ]
    if not candidates:
        display = '  '.join(f"{i+1}:{w}" for i, w in enumerate(words))
        return LineDisplay(display, False, None)

    wi, ci = random.choice(candidates)
    has_wrong = random.random() < wrong_prob
    actual_ch = words[wi][ci]
    shown_ch = pick_confusable(actual_ch) if has_wrong else actual_ch

    parts = [
        f"{i+1}:{_mask_word(w, {ci: shown_ch} if i == wi else {})}"
        for i, w in enumerate(words)
    ]
    return LineDisplay(
        display='  '.join(parts),
        has_wrong=has_wrong,
        wrong_word=(wi + 1) if has_wrong else None,
    )


def score_response(display: LineDisplay, user_input: int) -> tuple[bool, str]:
    """Score user's answer. user_input: 0 = no wrong letter, N = word N has wrong letter."""
    if display.has_wrong:
        if user_input == display.wrong_word:
            return True, f"Correct — word {display.wrong_word} had the wrong letter."
        elif user_input == 0:
            return False, f"Miss — word {display.wrong_word} had the wrong letter."
        else:
            return False, f"Wrong word — it was word {display.wrong_word}."
    else:
        if user_input == 0:
            return True, "Correct — no wrong letter."
        else:
            return False, "False alarm — all letters were correct."
