"""Tests for the /api/* Blueprint."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from wiki_acronyms.desktop_app import create_full_app
from wiki_acronyms.deck_loader import DeckInfo


def _deck_id(config_path: str, poem_title: str | None) -> str:
    return hashlib.sha256(f"{config_path}|{poem_title or ''}".encode()).hexdigest()[:12]


def _mock_logger(cards: dict | None = None):
    """In-memory logger mock backed by a real SQLite connection."""
    import sqlite3
    conn = sqlite3.connect(':memory:')
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY, started_at TEXT, mode TEXT, title TEXT,
            config_path TEXT, config_hash TEXT, wrong_prob REAL, format_version TEXT
        );
        CREATE TABLE IF NOT EXISTS srs_state (
            item_key TEXT PRIMARY KEY, card_json TEXT NOT NULL, updated_at TEXT NOT NULL
        );
    """)
    for key, (card_json, updated_at) in (cards or {}).items():
        conn.execute(
            'INSERT INTO srs_state VALUES (?,?,?)', (key, card_json, updated_at)
        )
    conn.commit()

    mock = MagicMock()
    mock._conn = conn
    mock.get_card.side_effect = lambda k: (
        conn.execute('SELECT card_json FROM srs_state WHERE item_key=?', (k,)).fetchone() or [None]
    )[0]
    mock.save_card.side_effect = lambda k, v: (
        conn.execute(
            'INSERT INTO srs_state (item_key,card_json,updated_at) VALUES (?,?,?) '
            'ON CONFLICT(item_key) DO UPDATE SET card_json=excluded.card_json, updated_at=excluded.updated_at',
            (k, v, '2024-01-01T00:00:00+00:00')
        ),
        conn.commit(),
    )
    return mock


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


# --- /api/decks ---

class TestListDecks:
    def test_empty_configs(self, client):
        resp = client.get('/api/decks')
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_returns_poetry_deck(self, tmp_path, client, app):
        (tmp_path / 'poetry' / 'sonnet.yaml').write_text(
            "poem_title: Sonnet 18\ngutenberg_id: 1041\n"
            "start_marker: foo\nend_marker: bar\n"
        )
        app.config['CONFIG_DIR'] = tmp_path
        with patch('wiki_acronyms.deck_loader.QuizLogger'):
            resp = client.get('/api/decks')
        data = resp.get_json()
        assert len(data) == 1
        deck = data[0]
        assert deck['name'] == 'Sonnet 18'
        assert deck['mode'] == 'words'
        assert deck['type'] == 'poetry'
        assert 'id' in deck

    def test_returns_monarchs_deck(self, tmp_path, client, app):
        (tmp_path / 'monarchs' / 'britain.yaml').write_text(
            "subject: British Monarchs\npositions: [Q9134365]\n"
        )
        app.config['CONFIG_DIR'] = tmp_path
        with patch('wiki_acronyms.deck_loader.QuizLogger'):
            resp = client.get('/api/decks')
        data = resp.get_json()
        assert any(d['type'] == 'monarchs' for d in data)

    def test_cors_header(self, client):
        resp = client.get('/api/decks')
        assert resp.headers.get('Access-Control-Allow-Origin') == '*'

    def test_collection_deck_has_group(self, tmp_path, client, app):
        (tmp_path / 'poetry' / 'collection.yaml').write_text(
            "collection_title: Sonnets\npoems:\n"
            "  - poem_title: Sonnet 18\n    gutenberg_id: 1041\n"
            "    start_marker: foo\n    end_marker: bar\n"
        )
        app.config['CONFIG_DIR'] = tmp_path
        resp = client.get('/api/decks')
        data = resp.get_json()
        assert data[0]['group'] == 'Sonnets'


# --- /api/deck/<id>/content ---

class TestDeckContent:
    def _setup_poetry_deck(self, tmp_path, app):
        cfg = tmp_path / 'poetry' / 'sonnet.yaml'
        cfg.write_text(
            "poem_title: Sonnet 18\ngutenberg_id: 1041\n"
            "start_marker: foo\nend_marker: bar\n"
        )
        app.config['CONFIG_DIR'] = tmp_path
        did = _deck_id(str(cfg), 'Sonnet 18')
        return did

    def test_unknown_id_returns_404(self, client):
        resp = client.get('/api/deck/deadbeef0000/content')
        assert resp.status_code == 404

    def test_poetry_deck_content(self, tmp_path, client, app):
        did = self._setup_poetry_deck(tmp_path, app)
        items = ['line one', 'line two']
        with patch('wiki_acronyms.api.load_poetry_deck', return_value=(items, 'Sonnet 18')):
            resp = client.get(f'/api/deck/{did}/content')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['items'] == items
        assert data['mode'] == 'words'
        assert data['title'] == 'Sonnet 18'
        assert data['labels'] is None

    def test_monarchs_deck_content(self, tmp_path, client, app):
        cfg = tmp_path / 'monarchs' / 'britain.yaml'
        cfg.write_text("subject: British Monarchs\npositions: [Q9134365]\n")
        app.config['CONFIG_DIR'] = tmp_path
        did = _deck_id(str(cfg), None)
        with patch('wiki_acronyms.api.load_monarchs_deck',
                   return_value=(['12345', '67890'], 'British Monarchs', ['900–999', '1000–1099'])):
            resp = client.get(f'/api/deck/{did}/content')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['mode'] == 'digits'
        assert data['labels'] == ['900–999', '1000–1099']

    def test_load_error_returns_500(self, tmp_path, client, app):
        did = self._setup_poetry_deck(tmp_path, app)
        with patch('wiki_acronyms.api.load_poetry_deck', side_effect=RuntimeError('network fail')):
            resp = client.get(f'/api/deck/{did}/content')
        assert resp.status_code == 500
        assert 'network fail' in resp.get_json()['error']


# --- /api/sync ---

class TestSync:
    def test_empty_changes_returns_all_server_cards(self, client, app):
        logger = _mock_logger({'abc123': ('{"learning_step":0}', '2024-01-01T00:00:00+00:00')})
        app.config['LOGGER'] = logger
        resp = client.post('/api/sync', json={'changes': []})
        assert resp.status_code == 200
        cards = resp.get_json()['cards']
        assert len(cards) == 1
        assert cards[0]['item_key'] == 'abc123'

    def test_newer_client_change_overwrites_server(self, client, app):
        server_json = '{"learning_step":0}'
        client_json = '{"learning_step":1}'
        logger = _mock_logger({'key1': (server_json, '2024-01-01T00:00:00+00:00')})
        app.config['LOGGER'] = logger
        resp = client.post('/api/sync', json={'changes': [{
            'item_key': 'key1',
            'card_json': client_json,
            'updated_at': '2024-06-01T00:00:00+00:00',
        }]})
        assert resp.status_code == 200
        cards = {c['item_key']: c for c in resp.get_json()['cards']}
        assert cards['key1']['card_json'] == client_json

    def test_older_client_change_does_not_overwrite_server(self, client, app):
        server_json = '{"learning_step":5}'
        client_json = '{"learning_step":0}'
        logger = _mock_logger({'key1': (server_json, '2024-06-01T00:00:00+00:00')})
        app.config['LOGGER'] = logger
        resp = client.post('/api/sync', json={'changes': [{
            'item_key': 'key1',
            'card_json': client_json,
            'updated_at': '2024-01-01T00:00:00+00:00',
        }]})
        cards = {c['item_key']: c for c in resp.get_json()['cards']}
        assert cards['key1']['card_json'] == server_json

    def test_new_key_from_client_inserted(self, client, app):
        logger = _mock_logger()
        app.config['LOGGER'] = logger
        resp = client.post('/api/sync', json={'changes': [{
            'item_key': 'newkey',
            'card_json': '{"learning_step":0}',
            'updated_at': '2024-01-01T00:00:00+00:00',
        }]})
        cards = {c['item_key']: c for c in resp.get_json()['cards']}
        assert 'newkey' in cards

    def test_malformed_change_skipped(self, client, app):
        logger = _mock_logger()
        app.config['LOGGER'] = logger
        resp = client.post('/api/sync', json={'changes': [{'item_key': 'x'}]})
        assert resp.status_code == 200
        assert resp.get_json()['cards'] == []

    def test_cors_preflight(self, client):
        resp = client.options('/api/sync')
        assert resp.status_code == 204

    def test_multiple_changes_merged(self, client, app):
        logger = _mock_logger()
        app.config['LOGGER'] = logger
        changes = [
            {'item_key': f'k{i}', 'card_json': f'{{"v":{i}}}', 'updated_at': '2024-01-01T00:00:00+00:00'}
            for i in range(5)
        ]
        resp = client.post('/api/sync', json={'changes': changes})
        cards = resp.get_json()['cards']
        assert len(cards) == 5
