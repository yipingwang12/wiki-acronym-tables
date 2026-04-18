from __future__ import annotations

import pytest
from wiki_acronyms.quiz import (
    CONFUSABLES,
    LineDisplay,
    _alpha_indices,
    _mask_word,
    make_line_display,
    pick_confusable,
    score_response,
)

_LINE = "From fairest creatures we desire increase,"


# --- pick_confusable ---

def test_pick_confusable_differs_from_input():
    for ch in 'abcdefghijklmnopqrstuvwxyz':
        assert pick_confusable(ch) != ch


def test_pick_confusable_preserves_lowercase():
    result = pick_confusable('b')
    assert result.islower() and result != 'b'


def test_pick_confusable_preserves_uppercase():
    result = pick_confusable('B')
    assert result.isupper() and result != 'B'


def test_pick_confusable_stays_within_confusables_dict():
    results = {pick_confusable('b') for _ in range(50)}
    assert results <= set(CONFUSABLES['b'])


# --- _alpha_indices ---

def test_alpha_indices_plain_word():
    assert _alpha_indices("hello") == [0, 1, 2, 3, 4]


def test_alpha_indices_trailing_punctuation():
    assert _alpha_indices("hello,") == [0, 1, 2, 3, 4]


def test_alpha_indices_leading_punctuation():
    assert _alpha_indices("(word") == [1, 2, 3, 4]


def test_alpha_indices_single_letter():
    assert _alpha_indices("a") == [0]


# --- _mask_word ---

def test_mask_word_shows_first_letter():
    assert _mask_word("hello", {}).startswith("h")


def test_mask_word_underscores_remaining():
    assert _mask_word("hello", {}) == "h____"


def test_mask_word_reveals_given_position():
    assert _mask_word("hello", {2: 'x'}) == "h_x__"


def test_mask_word_preserves_trailing_punctuation():
    assert _mask_word("hello,", {}) == "h____,"


def test_mask_word_preserves_leading_punctuation():
    assert _mask_word("(word", {}) == "(w___"


def test_mask_word_no_alpha_returns_word_unchanged():
    assert _mask_word("---", {}) == "---"


# --- make_line_display ---

def test_make_line_display_no_wrong_at_prob_zero():
    result = make_line_display(_LINE, wrong_prob=0.0)
    assert not result.has_wrong
    assert result.wrong_word is None


def test_make_line_display_always_wrong_at_prob_one():
    result = make_line_display(_LINE, wrong_prob=1.0)
    assert result.has_wrong
    assert result.wrong_word is not None


def test_make_line_display_wrong_word_in_valid_range():
    n_words = len(_LINE.split())
    result = make_line_display(_LINE, wrong_prob=1.0)
    assert 1 <= result.wrong_word <= n_words


def test_make_line_display_all_words_numbered():
    result = make_line_display(_LINE, wrong_prob=0.0)
    for i in range(1, 7):
        assert f"{i}:" in result.display


def test_make_line_display_first_letters_shown():
    result = make_line_display("From fairest creatures", wrong_prob=0.0)
    assert "1:F" in result.display
    assert "2:f" in result.display
    assert "3:c" in result.display


def test_make_line_display_no_wrong_when_no_candidates():
    # all single-letter words → no non-first alpha chars → no wrong possible
    result = make_line_display("a b c", wrong_prob=1.0)
    assert not result.has_wrong


def test_make_line_display_punctuation_preserved():
    result = make_line_display("increase,", wrong_prob=0.0)
    assert result.display.endswith(",")


# --- score_response ---

def test_score_hit():
    d = LineDisplay("...", has_wrong=True, wrong_word=3)
    correct, msg = score_response(d, 3)
    assert correct
    assert "3" in msg


def test_score_miss_typed_zero():
    d = LineDisplay("...", has_wrong=True, wrong_word=3)
    correct, msg = score_response(d, 0)
    assert not correct
    assert "3" in msg


def test_score_miss_wrong_word_number():
    d = LineDisplay("...", has_wrong=True, wrong_word=3)
    correct, msg = score_response(d, 5)
    assert not correct
    assert "3" in msg


def test_score_correct_rejection():
    d = LineDisplay("...", has_wrong=False, wrong_word=None)
    correct, _ = score_response(d, 0)
    assert correct


def test_score_false_alarm():
    d = LineDisplay("...", has_wrong=False, wrong_word=None)
    correct, msg = score_response(d, 2)
    assert not correct
    assert "false alarm" in msg.lower()
