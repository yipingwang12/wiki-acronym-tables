"""Tests for deck export — the generator→quiz artifact boundary.

The quiz reader lives in the ``memory-quiz-app`` repo; here we verify the written
artifacts directly. The critical guard is item-key parity: exported items must be
byte-identical to what the live generation pipeline produces, so FSRS item keys
(sha256(item)[:16]) — and thus every card's review history — survive the split.
``item_key``/``config_hash`` are inlined to keep the generator self-contained.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from wiki_acronyms import deck_export
from wiki_acronyms.monarchs import Monarch, make_monarch_chunks
from wiki_acronyms.poetry_parser import extract_poem

_POEM_TEXT = "\n".join([
    "PROLOGUE",
    "Shall I compare thee to a summer's day?",
    "Thou art more lovely and more temperate:",
    "",
    "So long lives this, and this gives life to thee.",
    "And summer's lease hath all too short a date.",
    "THE END",
])

_MONARCHS = [
    Monarch(name="Alfred", accession_year=871, end_year=899, father="", mother=""),
    Monarch(name="Edward", accession_year=899, end_year=924, father="", mother=""),
    Monarch(name="William", accession_year=1066, end_year=1087, father="", mother=""),
]


# --- artifact readers (mirror the quiz's deck_loader, without importing it) ---

def _item_key(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _config_hash(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _artifacts(decks_dir: Path) -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(Path(decks_dir).glob('*.json'))]


def _find(decks_dir: Path, config_path, poem_title=None) -> dict:
    target = Path(config_path).resolve()
    matches = [a for a in _artifacts(decks_dir) if Path(a['config_path']).resolve() == target]
    if not matches:
        raise FileNotFoundError(config_path)
    if poem_title:
        for a in matches:
            if a.get('poem_title') == poem_title:
                return a
    return matches[0]


def _write_poetry(config_dir, *, multi=False):
    (config_dir / 'poetry').mkdir(parents=True, exist_ok=True)
    if multi:
        path = config_dir / 'poetry' / 'collection.yaml'
        path.write_text(
            "collection_title: My Collection\n"
            "gutenberg_id: 1041\n"
            "poems:\n"
            "  - poem_title: First Half\n"
            "    start_marker: \"Shall I compare\"\n"
            "    end_marker: \"temperate:\"\n"
            "  - poem_title: Second Half\n"
            "    start_marker: \"So long lives\"\n"
            "    end_marker: \"short a date.\"\n"
        )
    else:
        path = config_dir / 'poetry' / 'sonnet.yaml'
        path.write_text(
            "poem_title: Sonnet 18\n"
            "gutenberg_id: 1041\n"
            "start_marker: \"Shall I compare\"\n"
            "end_marker: \"short a date.\"\n"
        )
    return path


def _write_monarchs(config_dir):
    (config_dir / 'monarchs').mkdir(parents=True, exist_ok=True)
    path = config_dir / 'monarchs' / 'britain.yaml'
    path.write_text(
        "subject: British Monarchs\n"
        "positions: [Q18810062]\n"
        "chunk_years: 100\n"
        "chunk_start_year: 800\n"
    )
    return path


def _export(config_dir, decks_dir):
    with patch('wiki_acronyms.deck_export.fetch_text', return_value=_POEM_TEXT), \
         patch('wiki_acronyms.deck_export.fetch_monarchs', return_value=_MONARCHS):
        return deck_export.export_decks(config_dir, decks_dir)


# --- schema ---

class TestSchema:
    def test_poetry_artifact_fields(self, tmp_path):
        cfg = _write_poetry(tmp_path)
        decks = tmp_path / 'decks'
        _export(tmp_path, decks)
        assert len(_artifacts(decks)) == 1
        a = _find(decks, cfg)
        assert (a['name'], a['deck_type'], a['mode'], a['poem_title']) == ('Sonnet 18', 'poetry', 'words', 'Sonnet 18')
        assert a['config_path'] == str(cfg)
        assert a['group'] is None

    def test_monarchs_artifact_fields(self, tmp_path):
        cfg = _write_monarchs(tmp_path)
        decks = tmp_path / 'decks'
        _export(tmp_path, decks)
        a = _find(decks, cfg)
        assert (a['name'], a['mode'], a['deck_type'], a['poem_title']) == ('British Monarchs', 'digits', 'monarchs', None)

    def test_collection_group_and_multi_filenames(self, tmp_path):
        _write_poetry(tmp_path, multi=True)
        decks = tmp_path / 'decks'
        written = _export(tmp_path, decks)
        assert len(written) == 2
        assert len({p.name for p in written}) == 2  # unique filenames
        arts = _artifacts(decks)
        assert all(a['group'] == 'My Collection' for a in arts)
        assert {a['poem_title'] for a in arts} == {'First Half', 'Second Half'}

    def test_export_clears_stale_artifacts(self, tmp_path):
        decks = tmp_path / 'decks'
        decks.mkdir()
        (decks / 'stale.json').write_text('{}')
        _write_poetry(tmp_path)
        _export(tmp_path, decks)
        assert not (decks / 'stale.json').exists()


# --- config hash continuity ---

class TestConfigHash:
    def test_poetry_artifact_hash_matches_config_bytes(self, tmp_path):
        cfg = _write_poetry(tmp_path)
        decks = tmp_path / 'decks'
        _export(tmp_path, decks)
        assert _find(decks, cfg, 'Sonnet 18')['config_hash'] == _config_hash(cfg)

    def test_monarchs_hash_matches(self, tmp_path):
        cfg = _write_monarchs(tmp_path)
        decks = tmp_path / 'decks'
        _export(tmp_path, decks)
        assert _find(decks, cfg)['config_hash'] == _config_hash(cfg)


# --- golden parity: exported items identical to live generation ---

class TestParity:
    def test_poetry_items_match_live_generation(self, tmp_path):
        cfg = _write_poetry(tmp_path)
        decks = tmp_path / 'decks'
        _export(tmp_path, decks)
        expected = [l for l in extract_poem(_POEM_TEXT, "Shall I compare", "short a date.")
                    if l is not None]
        a = _find(decks, cfg, 'Sonnet 18')
        assert a['items'] == expected
        assert a['title'] == 'Sonnet 18'

    def test_poetry_item_keys_preserved(self, tmp_path):
        """FSRS card identity must be unchanged for every item."""
        cfg = _write_poetry(tmp_path)
        decks = tmp_path / 'decks'
        _export(tmp_path, decks)
        items = _find(decks, cfg, 'Sonnet 18')['items']
        expected = [l for l in extract_poem(_POEM_TEXT, "Shall I compare", "short a date.")
                    if l is not None]
        assert [_item_key(i) for i in items] == [_item_key(e) for e in expected]

    def test_monarchs_items_and_labels_match_live_generation(self, tmp_path):
        cfg = _write_monarchs(tmp_path)
        decks = tmp_path / 'decks'
        _export(tmp_path, decks)
        chunks = make_monarch_chunks(_MONARCHS, 100, 800)
        exp_items = [c.transition_string for c in chunks]
        exp_labels = [f"{c.start_year}–{c.end_year}" for c in chunks]
        a = _find(decks, cfg)
        assert a['items'] == exp_items
        assert a['labels'] == exp_labels
        assert a['title'] == 'British Monarchs'

    def test_relative_and_absolute_config_paths_resolve_same_deck(self, tmp_path, monkeypatch):
        cfg = _write_poetry(tmp_path)
        decks = tmp_path / 'decks'
        _export(tmp_path, decks)
        monkeypatch.chdir(tmp_path)
        rel = cfg.relative_to(tmp_path)
        assert _find(decks, rel, 'Sonnet 18')['items'] == _find(decks, cfg, 'Sonnet 18')['items']


# --- missing artifact ---

def test_missing_artifact_raises(tmp_path):
    decks = tmp_path / 'decks'
    decks.mkdir()
    with pytest.raises(FileNotFoundError):
        _find(decks, tmp_path / 'poetry' / 'nope.yaml', 'X')
