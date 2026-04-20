"""Deck discovery and content loading for the desktop quiz app."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

from .gutenberg import fetch_text
from .logger import QuizLogger, config_hash
from .monarchs import fetch_monarchs, make_monarch_chunks
from .poetry_parser import extract_poem


@dataclass
class DeckInfo:
    name: str
    deck_type: str      # 'poetry' | 'monarchs'
    config_path: str
    mode: str           # 'words' | 'digits'
    poem_title: Optional[str] = None
    group: Optional[str] = None
    last_studied: Optional[str] = None  # ISO UTC datetime or None


def discover_decks(config_dir: Path, logger: QuizLogger) -> list[DeckInfo]:
    decks: list[DeckInfo] = []

    for yaml_path in sorted(config_dir.glob('poetry/*.yaml')):
        cfg = yaml.safe_load(yaml_path.read_text())
        poems = cfg.get('poems', [cfg])
        group = cfg.get('collection_title') if 'poems' in cfg else None
        for pc in poems:
            title = pc['poem_title']
            decks.append(DeckInfo(
                name=title,
                deck_type='poetry',
                config_path=str(yaml_path),
                mode='words',
                poem_title=title,
                group=group,
                last_studied=_last_studied(logger, str(yaml_path), title),
            ))

    for yaml_path in sorted(config_dir.glob('monarchs/*.yaml')):
        cfg = yaml.safe_load(yaml_path.read_text())
        title = cfg.get('subject', yaml_path.stem)
        decks.append(DeckInfo(
            name=title,
            deck_type='monarchs',
            config_path=str(yaml_path),
            mode='digits',
            last_studied=_last_studied(logger, str(yaml_path), title),
        ))

    return decks


def _last_studied(logger: QuizLogger, config_path: str, title: str) -> Optional[str]:
    row = logger._conn.execute(
        "SELECT MAX(started_at) FROM sessions WHERE config_path=? AND title=?",
        (config_path, title),
    ).fetchone()
    return row[0] if row and row[0] else None


def load_poetry_deck(config_path: Path, poem_title: str) -> tuple[list[str], str]:
    cfg = yaml.safe_load(config_path.read_text())
    text = fetch_text(cfg['gutenberg_id'])
    poems = cfg.get('poems', [cfg])
    pc = next((p for p in poems if p['poem_title'] == poem_title), poems[0])
    lines = [l for l in extract_poem(text, pc['start_marker'], pc['end_marker']) if l is not None]
    return lines, pc['poem_title']


def load_monarchs_deck(config_path: Path) -> tuple[list[str], str, list[str]]:
    cfg = yaml.safe_load(config_path.read_text())
    monarchs = fetch_monarchs(cfg['positions'])
    chunks = make_monarch_chunks(monarchs, cfg.get('chunk_years', 100), cfg.get('chunk_start_year'))
    items = [c.transition_string for c in chunks]
    labels = [f"{c.start_year}\u2013{c.end_year}" for c in chunks]
    return items, cfg.get('subject', config_path.stem), labels
