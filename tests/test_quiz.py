from __future__ import annotations

import pytest
from wiki_acronyms.quiz import (
    CONFUSABLES,
    DIGIT_CONFUSABLES,
    AcronymDisplay,
    DigitDisplay,
    LineDisplay,
    _alpha_indices,
    _bluff_display,
    _pinned_indices,
    make_acronym_display,
    make_digit_display,
    make_line_display,
    pick_confusable,
    pick_digit_confusable,
    score_acronym_response,
    score_digit_response,
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


# --- _pinned_indices ---

def test_pinned_indices_short_word_only_first():
    # "hello" has 5 alpha chars → pinned = {0, 3} (first + alpha[3])
    assert _pinned_indices("hello") == {0, 3}


def test_pinned_indices_four_alpha_only_first():
    # 4 alpha chars → no every-4th pinning, just first
    assert _pinned_indices("word") == {0}


def test_pinned_indices_long_word():
    # "creatures" = 9 alpha chars → pinned = alpha[0]=0, alpha[3]=3, alpha[7]=7
    assert _pinned_indices("creatures") == {0, 3, 7}


def test_pinned_indices_leading_punctuation():
    # "(word" alpha=[1,2,3,4] (4 chars) → only first pinned → {1}
    assert _pinned_indices("(word") == {1}


def test_pinned_indices_empty():
    assert _pinned_indices("---") == set()


# --- _bluff_display ---

def test_bluff_display_short_word_shows_pinned_and_extra():
    # "hello" alpha=[0..4], pinned={0,3} → h(pinned), _(1), x(extra at 2), l(pinned at 3), _(4)
    assert _bluff_display("hello", 2, 'x') == "h_xl_"


def test_bluff_display_preserves_trailing_punctuation():
    assert _bluff_display("hello,", 2, 'x') == "h_xl_,"


def test_bluff_display_preserves_leading_punctuation():
    # "(word" alpha=[1,2,3,4] (4 chars), pinned={1}; extra_pos=3 → "(w_x_"
    assert _bluff_display("(word", 3, 'x') == "(w_x_"


def test_bluff_display_single_alpha_returns_word():
    assert _bluff_display("a", 0, 'x') == "a"


def test_bluff_display_no_alpha_returns_word():
    assert _bluff_display("---", 0, 'x') == "---"


# --- make_line_display ---

def test_make_line_display_no_wrong_at_prob_zero():
    result = make_line_display(_LINE, wrong_prob=0.0)
    assert not result.has_wrong
    assert result.wrong_words == []


def test_make_line_display_always_wrong_at_prob_one():
    result = make_line_display(_LINE, wrong_prob=1.0)
    assert result.has_wrong
    assert len(result.wrong_words) > 0


def test_make_line_display_all_words_wrong_at_prob_one():
    # all 6 words in _LINE have >1 letter, so all should be wrong at prob=1.0
    result = make_line_display(_LINE, wrong_prob=1.0)
    assert result.wrong_words == [1, 2, 3, 4, 5, 6]


def test_make_line_display_wrong_words_in_valid_range():
    n_words = len(_LINE.split())
    result = make_line_display(_LINE, wrong_prob=1.0)
    assert all(1 <= w <= n_words for w in result.wrong_words)


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
    assert result.wrong_words == []


def test_make_line_display_pinned_letters_shown():
    # "creatures" = c(0)r(1)e(2)a(3)t(4)u(5)r(6)e(7)s(8), pinned={0,3,7} → c,a,e always shown
    result = make_line_display("creatures", wrong_prob=0.0)
    word_part = result.display.split(":")[1]
    assert word_part[0] == 'c'   # alpha[0] pinned
    assert word_part[3] == 'a'   # alpha[3] pinned
    assert word_part[7] == 'e'   # alpha[7] pinned


def test_make_line_display_punctuation_preserved():
    result = make_line_display("increase,", wrong_prob=0.0)
    assert result.display.endswith(",")


# --- score_response ---

def test_score_hit():
    d = LineDisplay("...", has_wrong=True, wrong_words=[3])
    correct, _ = score_response(d, {3})
    assert correct


def test_score_miss_typed_empty():
    d = LineDisplay("...", has_wrong=True, wrong_words=[3])
    correct, msg = score_response(d, set())
    assert not correct
    assert "3" in msg


def test_score_miss_wrong_word_number():
    d = LineDisplay("...", has_wrong=True, wrong_words=[3])
    correct, msg = score_response(d, {5})
    assert not correct
    assert "3" in msg


def test_score_partial_hit_partial_miss():
    d = LineDisplay("...", has_wrong=True, wrong_words=[2, 4])
    correct, msg = score_response(d, {2})  # got 2, missed 4
    assert not correct
    assert "4" in msg


def test_score_correct_rejection():
    d = LineDisplay("...", has_wrong=False, wrong_words=[])
    correct, _ = score_response(d, set())
    assert correct


def test_score_false_alarm():
    d = LineDisplay("...", has_wrong=False, wrong_words=[])
    correct, msg = score_response(d, {2})
    assert not correct
    assert "false alarm" in msg.lower()


def test_score_multiple_false_alarms():
    d = LineDisplay("...", has_wrong=False, wrong_words=[])
    correct, msg = score_response(d, {1, 3})
    assert not correct
    assert "false alarm" in msg.lower()


# --- make_acronym_display ---

def test_make_acronym_display_no_wrong_at_prob_zero():
    result = make_acronym_display(_LINE, wrong_prob=0.0)
    assert not result.has_wrong
    assert result.wrong_letters == []


def test_make_acronym_display_always_wrong_at_prob_one():
    result = make_acronym_display(_LINE, wrong_prob=1.0)
    assert result.has_wrong
    assert len(result.wrong_letters) == len(_LINE.split())


def test_make_acronym_display_letter_count():
    line = "From fairest creatures"
    result = make_acronym_display(line, wrong_prob=0.0)
    assert "1:" in result.display
    assert "2:" in result.display
    assert "3:" in result.display


def test_make_acronym_display_preserves_case():
    result = make_acronym_display("From fairest", wrong_prob=0.0)
    assert "1:F" in result.display
    assert "2:f" in result.display


def test_make_acronym_display_wrong_in_valid_range():
    n = len(_LINE.split())
    result = make_acronym_display(_LINE, wrong_prob=1.0)
    assert all(1 <= w <= n for w in result.wrong_letters)


# --- score_acronym_response ---

def test_score_acronym_hit():
    d = AcronymDisplay("...", has_wrong=True, wrong_letters=[2])
    correct, _ = score_acronym_response(d, {2})
    assert correct


def test_score_acronym_miss():
    d = AcronymDisplay("...", has_wrong=True, wrong_letters=[2])
    correct, msg = score_acronym_response(d, set())
    assert not correct
    assert "2" in msg


def test_score_acronym_false_alarm():
    d = AcronymDisplay("...", has_wrong=False, wrong_letters=[])
    correct, msg = score_acronym_response(d, {3})
    assert not correct
    assert "false alarm" in msg.lower()


def test_score_acronym_correct_rejection():
    d = AcronymDisplay("...", has_wrong=False, wrong_letters=[])
    correct, _ = score_acronym_response(d, set())
    assert correct


# --- pick_digit_confusable ---

def test_pick_digit_confusable_differs_from_input():
    for d in '0123456789':
        assert pick_digit_confusable(d) != d


def test_pick_digit_confusable_stays_within_dict():
    results = {pick_digit_confusable('6') for _ in range(50)}
    assert results <= set(DIGIT_CONFUSABLES['6'])


# --- make_digit_display ---

def test_make_digit_display_no_wrong_at_prob_zero():
    result = make_digit_display("19428", wrong_prob=0.0)
    assert not result.has_wrong
    assert result.wrong_digits == []


def test_make_digit_display_always_wrong_at_prob_one():
    result = make_digit_display("19428", wrong_prob=1.0)
    assert result.has_wrong
    assert result.wrong_digits == [1, 2, 3, 4, 5]


def test_make_digit_display_count():
    result = make_digit_display("194", wrong_prob=0.0)
    assert "1:" in result.display
    assert "2:" in result.display
    assert "3:" in result.display


def test_make_digit_display_wrong_in_valid_range():
    result = make_digit_display("19428", wrong_prob=1.0)
    assert all(1 <= d <= 5 for d in result.wrong_digits)


# --- score_digit_response ---

def test_score_digit_hit():
    d = DigitDisplay("...", has_wrong=True, wrong_digits=[3])
    correct, _ = score_digit_response(d, {3})
    assert correct


def test_score_digit_miss():
    d = DigitDisplay("...", has_wrong=True, wrong_digits=[3])
    correct, msg = score_digit_response(d, set())
    assert not correct
    assert "3" in msg


def test_score_digit_false_alarm():
    d = DigitDisplay("...", has_wrong=False, wrong_digits=[])
    correct, msg = score_digit_response(d, {2})
    assert not correct
    assert "false alarm" in msg.lower()


def test_score_digit_correct_rejection():
    d = DigitDisplay("...", has_wrong=False, wrong_digits=[])
    correct, _ = score_digit_response(d, set())
    assert correct
