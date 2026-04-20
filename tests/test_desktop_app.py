"""Tests for the multi-deck desktop app (create_full_app)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fsrs import Rating as _Rating

from wiki_acronyms.desktop_app import create_full_app
from wiki_acronyms.deck_loader import DeckInfo

_LINES = [
    "From fairest creatures we desire increase,",
    "That thereby beauty's rose might never die,",
]


def _mock_logger():
    mock = MagicMock()
    mock.start_session.return_value = 'test-session-id'
    mock.log_display.return_value = 1
    mock._conn.execute.return_value.fetchone.return_value = None
    return mock


def _mock_srs(order=None, due_count=None, n=len(_LINES)):
    mock = MagicMock()
    mock.get_due_order.return_value = order if order is not None else list(range(n))
    mock.get_due_count.return_value = due_count if due_count is not None else n
    mock.review.return_value = _Rating.Easy
    return mock


def _fake_deck(app, lines=_LINES, mode='words'):
    srs = _mock_srs(n=len(lines))
    app.config['DECK'] = {
        'lines': lines,
        'title': 'Test Deck',
        'mode': mode,
        'wrong_prob': 0.0,
        'item_labels': None,
        'config_path': '/fake/config.yaml',
        'cfg_hash': 'abc123',
        'srs': srs,
    }
    app.config['LOAD_STATE'] = 'ready'
    return srs


@pytest.fixture
def app(tmp_path):
    (tmp_path / 'poetry').mkdir()
    (tmp_path / 'monarchs').mkdir()
    a = create_full_app(tmp_path, _mock_logger())
    a.config['TESTING'] = True
    return a


@pytest.fixture
def client(app):
    return app.test_client()


# --- home page ---

def test_home_returns_200(client):
    assert client.get('/').status_code == 200


def test_home_shows_no_decks_message(client):
    assert b'No configs' in client.get('/').data


def test_home_shows_deck_name(app, client, tmp_path):
    (tmp_path / 'monarchs' / 'brit.yaml').write_text(
        'subject: "British Monarchs"\npositions: []\n'
    )
    with patch('wiki_acronyms.desktop_app.discover_decks') as mock:
        mock.return_value = [DeckInfo(
            name='British Monarchs', deck_type='monarchs',
            config_path='/fake/brit.yaml', mode='digits',
        )]
        resp = client.get('/')
    assert b'British Monarchs' in resp.data


# --- loading / status ---

def test_status_returns_idle_initially(client):
    resp = client.get('/status')
    assert resp.get_json()['state'] == 'idle'


def test_loading_page_returns_200(client):
    assert client.get('/loading').status_code == 200


# --- quiz without deck redirects home ---

def test_quiz_without_deck_redirects_home(client):
    resp = client.get('/quiz')
    assert resp.status_code == 302
    assert '/' in resp.headers['Location']


# --- quiz with deck loaded ---

def test_quiz_with_deck_returns_200(app, client):
    _fake_deck(app)
    assert client.get('/quiz').status_code == 200


def test_quiz_shows_title(app, client):
    _fake_deck(app)
    assert b'Test Deck' in client.get('/quiz').data


def test_quiz_shows_back_link(app, client):
    _fake_deck(app)
    assert b'Decks' in client.get('/quiz').data


def test_correct_answer_advances(app, client):
    _fake_deck(app)
    client.get('/quiz')
    client.post('/quiz', data={'answer': ''})
    with client.session_transaction() as sess:
        assert sess['line_idx'] == 1


def test_false_alarm_decrements_health(app, client):
    _fake_deck(app)
    client.get('/quiz')
    client.post('/quiz', data={'answer': '1'})
    with client.session_transaction() as sess:
        assert sess['health'] == 9


def test_completion_shows_back_button(app, client):
    _fake_deck(app)
    with client.session_transaction() as sess:
        sess['line_idx'] = len(_LINES)
        sess['health'] = 10
        sess['display'] = None
        sess['item_order'] = list(range(len(_LINES)))
        sess['due_count'] = len(_LINES)
        sess['stats'] = {'easy': 0, 'good': 0, 'hard': 0, 'again': 0, 'total_time': 0.0, 'completed': 0}
    resp = client.get('/quiz')
    assert b'Complete' in resp.data
    assert b'Decks' in resp.data


# --- restart ---

def test_restart_clears_session_and_redirects(app, client):
    _fake_deck(app)
    client.get('/quiz')
    resp = client.get('/restart')
    assert resp.status_code == 302
    assert '/quiz' in resp.headers['Location']
    with client.session_transaction() as sess:
        assert 'line_idx' not in sess


# --- stats ---

def test_stats_initialized(app, client):
    _fake_deck(app)
    client.get('/quiz')
    with client.session_transaction() as sess:
        assert sess['stats']['completed'] == 0


def test_stats_incremented_on_answer(app, client):
    _fake_deck(app)
    client.get('/quiz')
    client.post('/quiz', data={'answer': ''})
    with client.session_transaction() as sess:
        assert sess['stats']['completed'] == 1
