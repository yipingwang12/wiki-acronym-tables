from __future__ import annotations

import pytest
from unittest.mock import MagicMock
from fsrs import Rating as _Rating

from wiki_acronyms.web_app import create_app

_LINES = [
    "From fairest creatures we desire increase,",
    "That thereby beauty's rose might never die,",
]


def _mock_logger():
    mock = MagicMock()
    mock.start_session.return_value = 'test-session-id'
    mock.log_display.return_value = 'test-attempt-id'
    return mock


def _mock_srs(order=None, due_count=None, n=len(_LINES)):
    mock = MagicMock()
    mock.get_due_order.return_value = order if order is not None else list(range(n))
    mock.get_due_count.return_value = due_count if due_count is not None else n
    mock.review.return_value = _Rating.Easy
    return mock


@pytest.fixture
def client():
    app = create_app(_LINES, 'Test Poem', wrong_prob=0.0, mode='words',
                     logger=_mock_logger(), srs=_mock_srs())
    app.config['TESTING'] = True
    return app.test_client()


@pytest.fixture
def acronym_client():
    app = create_app(_LINES, 'Test Poem', wrong_prob=0.0, mode='acronym',
                     logger=_mock_logger(), srs=_mock_srs())
    app.config['TESTING'] = True
    return app.test_client()


def test_index_redirects_to_quiz(client):
    resp = client.get('/')
    assert resp.status_code == 302
    assert '/quiz' in resp.headers['Location']


def test_quiz_get_returns_200(client):
    assert client.get('/quiz').status_code == 200


def test_quiz_shows_title(client):
    assert b'Test Poem' in client.get('/quiz').data


def test_quiz_shows_word_display(client):
    assert b'token-card' in client.get('/quiz').data


def test_correct_answer_advances_line(client):
    client.get('/quiz')
    client.post('/quiz', data={'answer': ''})  # wrong_prob=0 → no wrong letters → correct
    with client.session_transaction() as sess:
        assert sess['line_idx'] == 1


def test_false_alarm_decrements_health(client):
    client.get('/quiz')
    client.post('/quiz', data={'answer': '1'})  # false alarm: -1 health
    with client.session_transaction() as sess:
        assert sess['health'] == 9


def test_health_exhaustion_resets(client):
    with client.session_transaction() as sess:
        sess['line_idx'] = 0
        sess['health'] = 1
        sess['display'] = None
        sess['item_order'] = [0, 1]
        sess['due_count'] = len(_LINES)
        sess['stats'] = {'easy': 0, 'good': 0, 'hard': 0, 'again': 0, 'total_time': 0.0, 'completed': 0}
    client.get('/quiz')
    client.post('/quiz', data={'answer': '1'})  # false alarm → health 0 → reset
    with client.session_transaction() as sess:
        assert sess['line_idx'] == 0
        assert sess['health'] == 10


def test_completion_page_shown(client):
    with client.session_transaction() as sess:
        sess['line_idx'] = len(_LINES)
        sess['health'] = 10
        sess['display'] = None
        sess['item_order'] = [0, 1]
        sess['due_count'] = len(_LINES)
        sess['stats'] = {'easy': 0, 'good': 0, 'hard': 0, 'again': 0, 'total_time': 0.0, 'completed': 0}
    resp = client.get('/quiz')
    assert b'Complete' in resp.data


# --- acronym mode ---

def test_acronym_quiz_get_returns_200(acronym_client):
    assert acronym_client.get('/quiz').status_code == 200


def test_acronym_quiz_shows_letter_hint(acronym_client):
    resp = acronym_client.get('/quiz')
    assert b'letter' in resp.data


def test_digits_mode_shows_digit_hint():
    app = create_app(['194'], 'Test', wrong_prob=0.0, mode='digits',
                     item_labels=['800\u2013899'], logger=_mock_logger(), srs=_mock_srs(n=1))
    app.config['TESTING'] = True
    c = app.test_client()
    resp = c.get('/quiz')
    assert b'digit' in resp.data
    assert b'800' in resp.data  # century label shown


def test_acronym_correct_answer_advances_line(acronym_client):
    acronym_client.get('/quiz')
    acronym_client.post('/quiz', data={'answer': ''})  # wrong_prob=0 → no wrong letters
    with acronym_client.session_transaction() as sess:
        assert sess['line_idx'] == 1


def test_acronym_false_alarm_decrements_health(acronym_client):
    acronym_client.get('/quiz')
    acronym_client.post('/quiz', data={'answer': '1'})
    with acronym_client.session_transaction() as sess:
        assert sess['health'] == 9


# --- infobox / stats ---

def test_stats_initialized_in_session(client):
    client.get('/quiz')
    with client.session_transaction() as sess:
        assert 'stats' in sess
        assert sess['stats']['completed'] == 0


def test_stats_completed_increments_on_answer(client):
    client.get('/quiz')
    client.post('/quiz', data={'answer': ''})
    with client.session_transaction() as sess:
        assert sess['stats']['completed'] == 1


def test_stats_outcome_recorded(client):
    client.get('/quiz')
    client.post('/quiz', data={'answer': ''})  # correct → Easy (fast test response)
    with client.session_transaction() as sess:
        total = sum(sess['stats'][k] for k in ('easy', 'good', 'hard', 'again'))
        assert total == 1


def test_stats_reset_on_health_exhaustion(client):
    with client.session_transaction() as sess:
        sess['line_idx'] = 0
        sess['health'] = 1
        sess['display'] = None
        sess['item_order'] = [0, 1]
        sess['due_count'] = len(_LINES)
        sess['stats'] = {'easy': 3, 'good': 2, 'hard': 1, 'again': 0, 'total_time': 30.0, 'completed': 6}
    client.get('/quiz')
    client.post('/quiz', data={'answer': '1'})  # false alarm → exhaustion → reset
    with client.session_transaction() as sess:
        assert sess['stats']['completed'] == 0
        assert sess['stats']['total_time'] == 0.0


def test_infobox_rendered_in_response(client):
    resp = client.get('/quiz')
    assert b'unit-timer' in resp.data
    assert b'Avg / unit' in resp.data
    assert b'Done' in resp.data


# --- SRS due-order integration ---

def test_srs_item_order_stored_in_session():
    app = create_app(_LINES, 'T', wrong_prob=0.0, logger=_mock_logger(), srs=_mock_srs(order=[1, 0]))
    app.config['TESTING'] = True
    c = app.test_client()
    c.get('/quiz')
    with c.session_transaction() as sess:
        assert sess['item_order'] == [1, 0]


def test_srs_due_count_stored_in_session():
    app = create_app(_LINES, 'T', wrong_prob=0.0, logger=_mock_logger(), srs=_mock_srs(due_count=1))
    app.config['TESTING'] = True
    c = app.test_client()
    c.get('/quiz')
    with c.session_transaction() as sess:
        assert sess['due_count'] == 1


def test_srs_reversed_order_shows_second_line_first():
    """When item_order=[1,0], progress label reflects item 1 (index 1 in lines)."""
    labels = ['Line A', 'Line B']
    app = create_app(_LINES, 'T', wrong_prob=0.0, logger=_mock_logger(),
                     srs=_mock_srs(order=[1, 0]), item_labels=labels)
    app.config['TESTING'] = True
    c = app.test_client()
    resp = c.get('/quiz')
    assert b'Line B' in resp.data


def test_srs_completion_after_due_items_only():
    """Session completes after due_count items, not total len(lines)."""
    app = create_app(_LINES, 'T', wrong_prob=0.0, logger=_mock_logger(),
                     srs=_mock_srs(order=[0, 1], due_count=1))
    app.config['TESTING'] = True
    c = app.test_client()
    c.get('/quiz')
    c.post('/quiz', data={'answer': ''})  # correct → line_idx becomes 1
    resp = c.get('/quiz')
    assert b'Complete' in resp.data
