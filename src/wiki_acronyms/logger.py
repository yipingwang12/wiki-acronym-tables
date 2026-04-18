"""SQLite-backed quiz event logger for spaced-repetition history."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Bump the relevant version string whenever the display format for that mode changes.
FORMAT_VERSIONS: dict[str, str] = {
    'words': 'words-v1',
    'acronym': 'acronym-v1',
    'digits': 'digits-v1',
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id            TEXT PRIMARY KEY,
    started_at    TEXT NOT NULL,
    mode          TEXT NOT NULL,
    title         TEXT NOT NULL,
    config_path   TEXT,
    config_hash   TEXT,
    wrong_prob    REAL NOT NULL,
    format_version TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS attempts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id    TEXT NOT NULL REFERENCES sessions(id),
    item_key      TEXT NOT NULL,
    item_idx      INTEGER NOT NULL,
    item_label    TEXT,
    item_text     TEXT NOT NULL,
    display_text  TEXT NOT NULL,
    displayed_at  TEXT NOT NULL,
    submitted_at  TEXT,
    raw_input     TEXT,
    keystrokes    TEXT,
    user_positions TEXT,
    correct       INTEGER,
    health_before INTEGER,
    health_after  INTEGER
);

CREATE INDEX IF NOT EXISTS idx_attempts_item_key ON attempts(item_key);
CREATE INDEX IF NOT EXISTS idx_attempts_session   ON attempts(session_id);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def item_key(text: str) -> str:
    """Stable 16-char identifier for a quiz item, based on its content."""
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def config_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class QuizLogger:
    def __init__(self, db_path: Path | str = 'logs/quiz.db') -> None:
        if str(db_path) != ':memory:':
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def start_session(
        self,
        mode: str,
        title: str,
        config_path: str | None,
        cfg_hash: str | None,
        wrong_prob: float,
    ) -> str:
        sid = str(uuid.uuid4())
        self._conn.execute(
            "INSERT INTO sessions VALUES (?,?,?,?,?,?,?,?)",
            (sid, _now(), mode, title, config_path, cfg_hash, wrong_prob,
             FORMAT_VERSIONS.get(mode, 'unknown-v1')),
        )
        self._conn.commit()
        return sid

    def log_display(
        self,
        session_id: str,
        item_idx: int,
        item_label: str | None,
        item_text: str,
        display_text: str,
        health_before: int,
    ) -> int:
        cur = self._conn.execute(
            """INSERT INTO attempts
               (session_id, item_key, item_idx, item_label, item_text,
                display_text, displayed_at, health_before)
               VALUES (?,?,?,?,?,?,?,?)""",
            (session_id, item_key(item_text), item_idx, item_label,
             item_text, display_text, _now(), health_before),
        )
        self._conn.commit()
        return cur.lastrowid

    def log_response(
        self,
        attempt_id: int,
        raw_input: str,
        keystrokes: list,
        user_positions: list[int],
        correct: bool,
        health_after: int,
    ) -> None:
        self._conn.execute(
            """UPDATE attempts SET
               submitted_at=?, raw_input=?, keystrokes=?,
               user_positions=?, correct=?, health_after=?
               WHERE id=?""",
            (_now(), raw_input, json.dumps(keystrokes),
             json.dumps(sorted(user_positions)), int(correct), health_after,
             attempt_id),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
