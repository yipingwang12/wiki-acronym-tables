from __future__ import annotations

import json

import pytest
from fsrs import Rating
from wiki_acronyms.logger import QuizLogger, item_key
from wiki_acronyms.srs import SRSScheduler, classify_response, _thresholds


# --- classify_response ---

def test_incorrect_always_again():
    assert classify_response('words', 'hello world', 1.0, False) == Rating.Again


def test_words_easy_fast():
    # 2 words, 10 chars: easy_t = 1.5 + 2*0.3 + 10*0.05 = 2.6
    assert classify_response('words', 'hello world', 1.0, True) == Rating.Easy


def test_words_good_medium():
    # easy_t = 2.6, hard_t = 1.5 + 2*1.5 + 10*0.2 = 5.5
    assert classify_response('words', 'hello world', 4.0, True) == Rating.Good


def test_words_hard_slow():
    assert classify_response('words', 'hello world', 20.0, True) == Rating.Hard


def test_acronym_easy():
    # 3 words: easy_t = 1.5 + 3*0.3 = 2.4
    assert classify_response('acronym', 'one two three', 1.0, True) == Rating.Easy


def test_acronym_good():
    # hard_t = 1.5 + 3*1.5 = 6.0
    assert classify_response('acronym', 'one two three', 4.0, True) == Rating.Good


def test_acronym_hard():
    assert classify_response('acronym', 'one two three', 10.0, True) == Rating.Hard


def test_digits_easy():
    # 5 digits: easy_t = 1.5 + 5*0.4 = 3.5
    assert classify_response('digits', '19428', 2.0, True) == Rating.Easy


def test_digits_good():
    # hard_t = 1.5 + 5*2.0 = 11.5
    assert classify_response('digits', '19428', 6.0, True) == Rating.Good


def test_digits_hard():
    assert classify_response('digits', '19428', 20.0, True) == Rating.Hard


def test_thresholds_scale_with_word_count():
    easy_short, hard_short = _thresholds('words', 'hi')
    easy_long, hard_long = _thresholds('words', 'one two three four five six seven eight nine ten')
    assert easy_long > easy_short
    assert hard_long > hard_short


def test_thresholds_scale_with_char_count():
    # Same word count, different char lengths
    easy_short, _ = _thresholds('words', 'a b')
    easy_long, _ = _thresholds('words', 'abcdefgh ijklmnop')
    assert easy_long > easy_short


def test_thresholds_scale_with_digit_count():
    easy_3, _ = _thresholds('digits', '194')
    easy_8, _ = _thresholds('digits', '19428374')
    assert easy_8 > easy_3


# --- SRSScheduler ---

@pytest.fixture
def logger():
    lg = QuizLogger(':memory:')
    yield lg
    lg.close()


@pytest.fixture
def srs(logger):
    return SRSScheduler(logger)


@pytest.fixture
def graduated_srs(logger):
    """SRSScheduler with no learning steps — cards graduate immediately on first review."""
    return SRSScheduler(logger, learning_steps=[])


def test_review_stores_card(srs, logger):
    srs.review('hello world', 'words', 1.0, True)
    key = item_key('hello world')
    assert logger.get_card(key) is not None


def test_review_card_json_valid(graduated_srs, logger):
    graduated_srs.review('hello world', 'words', 1.0, True)
    state = json.loads(logger.get_card(item_key('hello world')))
    card_data = json.loads(state['fsrs'])
    assert 'stability' in card_data
    assert 'difficulty' in card_data


def test_review_again_keeps_short_interval(srs, logger):
    from datetime import datetime, timezone
    srs.review('hello world', 'words', 1.0, False)  # Again → learning step 0
    state = json.loads(logger.get_card(item_key('hello world')))
    step_due = datetime.fromisoformat(state['step_due'])
    days_until_due = (step_due - datetime.now(timezone.utc)).total_seconds() / 86400
    assert days_until_due <= 1


def test_review_easy_gives_longer_interval_than_again(graduated_srs, logger):
    from fsrs import Card
    graduated_srs.review('easy item', 'words', 0.5, True)   # Easy → graduates immediately
    graduated_srs.review('hard item', 'words', 0.5, False)  # Again → graduates immediately
    easy_state = json.loads(logger.get_card(item_key('easy item')))
    again_state = json.loads(logger.get_card(item_key('hard item')))
    easy_card = Card.from_json(easy_state['fsrs'])
    again_card = Card.from_json(again_state['fsrs'])
    assert easy_card.due >= again_card.due


def test_review_updates_existing_card(graduated_srs, logger):
    from fsrs import Card
    graduated_srs.review('hello world', 'words', 1.0, True)
    state_v1 = json.loads(logger.get_card(item_key('hello world')))
    card_v1 = Card.from_json(state_v1['fsrs'])
    graduated_srs.review('hello world', 'words', 1.0, True)
    state_v2 = json.loads(logger.get_card(item_key('hello world')))
    card_v2 = Card.from_json(state_v2['fsrs'])
    assert card_v2.last_review >= card_v1.last_review


def test_get_due_order_new_items_first(srs):
    items = ['alpha', 'beta', 'gamma']
    order = srs.get_due_order(items)
    assert set(order) == {0, 1, 2}


def test_get_due_order_reviewed_item_last(srs):
    items = ['alpha', 'beta']
    srs.review('alpha', 'words', 1.0, True)  # reviewed → due in future
    order = srs.get_due_order(items)
    # 'beta' (new) should come before 'alpha' (future due)
    assert order.index(1) < order.index(0)


def test_get_due_count_new_items_all_due(srs):
    assert srs.get_due_count(['alpha', 'beta', 'gamma']) == 3


def test_get_due_count_reviewed_item_not_due(srs):
    srs.review('alpha', 'words', 1.0, True)  # Easy → due in future
    assert srs.get_due_count(['alpha', 'beta']) == 1  # only 'beta' (new) is due
