from __future__ import annotations

import json
import sqlite3

import pytest
from wiki_acronyms.logger import QuizLogger, item_key


@pytest.fixture
def logger():
    lg = QuizLogger(':memory:')
    yield lg
    lg.close()


def test_item_key_stable():
    assert item_key('hello') == item_key('hello')
    assert len(item_key('hello')) == 16


def test_item_key_differs_for_different_text():
    assert item_key('hello') != item_key('world')


def test_schema_created(logger):
    cur = logger._conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cur}
    assert {'sessions', 'attempts'} <= tables


def test_start_session_returns_uuid(logger):
    sid = logger.start_session('words', 'Test', None, None, 0.2)
    assert len(sid) == 36
    assert sid.count('-') == 4


def test_start_session_stored(logger):
    sid = logger.start_session('acronym', 'My Poem', '/cfg', 'abc123', 0.15)
    row = logger._conn.execute('SELECT mode, title, config_path, config_hash, wrong_prob, format_version FROM sessions WHERE id=?', (sid,)).fetchone()
    assert row == ('acronym', 'My Poem', '/cfg', 'abc123', 0.15, 'acronym-v1')


def test_log_display_returns_int(logger):
    sid = logger.start_session('words', 'T', None, None, 0.0)
    aid = logger.log_display(sid, 0, None, 'hello world', '1:h_l__ 2:w___d', 10)
    assert isinstance(aid, int)


def test_log_display_stored(logger):
    sid = logger.start_session('words', 'T', None, None, 0.0)
    aid = logger.log_display(sid, 0, 'label', 'hello world', '1:h_l__ 2:w___d', 10)
    row = logger._conn.execute(
        'SELECT session_id, item_idx, item_label, item_text, display_text, health_before FROM attempts WHERE id=?',
        (aid,)
    ).fetchone()
    assert row == (sid, 0, 'label', 'hello world', '1:h_l__ 2:w___d', 10)


def test_log_display_item_key_matches(logger):
    sid = logger.start_session('words', 'T', None, None, 0.0)
    text = 'hello world'
    aid = logger.log_display(sid, 0, None, text, '...', 10)
    stored = logger._conn.execute('SELECT item_key FROM attempts WHERE id=?', (aid,)).fetchone()[0]
    assert stored == item_key(text)


def test_log_response_stored(logger):
    sid = logger.start_session('words', 'T', None, None, 0.0)
    aid = logger.log_display(sid, 0, None, 'abc', '...', 10)
    logger.log_response(aid, '2', [['2', 120]], [2], True, 10)
    row = logger._conn.execute(
        'SELECT raw_input, keystrokes, user_positions, correct, health_after FROM attempts WHERE id=?',
        (aid,)
    ).fetchone()
    assert row[0] == '2'
    assert json.loads(row[1]) == [['2', 120]]
    assert json.loads(row[2]) == [2]
    assert row[3] == 1
    assert row[4] == 10


def test_log_response_incorrect(logger):
    sid = logger.start_session('words', 'T', None, None, 0.0)
    aid = logger.log_display(sid, 0, None, 'abc', '...', 10)
    logger.log_response(aid, '', [], [], False, 7)
    row = logger._conn.execute('SELECT correct, health_after FROM attempts WHERE id=?', (aid,)).fetchone()
    assert row == (0, 7)


def test_multiple_sessions_independent(logger):
    sid1 = logger.start_session('words', 'T', None, None, 0.0)
    sid2 = logger.start_session('acronym', 'T', None, None, 0.2)
    count = logger._conn.execute('SELECT COUNT(*) FROM sessions').fetchone()[0]
    assert count == 2
    assert sid1 != sid2


def test_indexes_exist(logger):
    cur = logger._conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
    names = {row[0] for row in cur}
    assert 'idx_attempts_item_key' in names
    assert 'idx_attempts_session' in names
