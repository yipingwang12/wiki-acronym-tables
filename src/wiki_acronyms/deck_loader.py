"""Deck discovery and content loading from exported JSON artifacts.

The quiz reads decks produced by ``deck_export`` (``data/decks/*.json``) — it does not
regenerate content or touch the network. Artifacts are matched to a config by resolved
path, so callers may pass relative or absolute config paths interchangeably.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .logger import QuizLogger

_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DECKS_DIR = _ROOT / 'data' / 'decks'


@dataclass
class DeckInfo:
    name: str
    deck_type: str      # 'poetry' | 'monarchs'
    config_path: str
    mode: str           # 'words' | 'digits'
    poem_title: Optional[str] = None
    group: Optional[str] = None
    last_studied: Optional[str] = None  # ISO UTC datetime or None


def _read_artifacts(decks_dir: Path) -> list[dict]:
    decks_dir = Path(decks_dir)
    if not decks_dir.exists():
        return []
    return [json.loads(p.read_text(encoding='utf-8')) for p in sorted(decks_dir.glob('*.json'))]


def discover_decks(decks_dir: Path, logger: QuizLogger) -> list[DeckInfo]:
    artifacts = sorted(_read_artifacts(decks_dir), key=lambda a: a.get('order', 0))
    return [
        DeckInfo(
            name=a['name'],
            deck_type=a['deck_type'],
            config_path=a['config_path'],
            mode=a['mode'],
            poem_title=a.get('poem_title'),
            group=a.get('group'),
            last_studied=_last_studied(logger, a['config_path'], a['title']),
        )
        for a in artifacts
    ]


def _last_studied(logger: QuizLogger, config_path: str, title: str) -> Optional[str]:
    row = logger._conn.execute(
        "SELECT MAX(started_at) FROM sessions WHERE config_path=? AND title=?",
        (config_path, title),
    ).fetchone()
    return row[0] if row and row[0] else None


def _find_artifact(decks_dir: Path, config_path, poem_title: Optional[str] = None) -> dict:
    """Return the artifact for a config, preferring an exact poem match (else the first)."""
    target = Path(config_path).resolve()
    matches = [a for a in _read_artifacts(decks_dir) if Path(a['config_path']).resolve() == target]
    if not matches:
        raise FileNotFoundError(
            f"No exported deck for {config_path!r}; run wiki-export-decks"
        )
    if poem_title:
        for a in matches:
            if a.get('poem_title') == poem_title:
                return a
    return matches[0]


def load_poetry_deck(config_path, poem_title, decks_dir: Path = DEFAULT_DECKS_DIR) -> tuple[list[str], str]:
    a = _find_artifact(decks_dir, config_path, poem_title)
    return a['items'], a['title']


def load_monarchs_deck(config_path, decks_dir: Path = DEFAULT_DECKS_DIR) -> tuple[list[str], str, list[str]]:
    a = _find_artifact(decks_dir, config_path)
    return a['items'], a['title'], a['labels']


def deck_config_hash(config_path, poem_title: Optional[str] = None,
                     decks_dir: Path = DEFAULT_DECKS_DIR) -> str:
    """Config hash recorded in the artifact — keeps session ``cfg_hash`` stable post-split."""
    return _find_artifact(decks_dir, config_path, poem_title)['config_hash']
