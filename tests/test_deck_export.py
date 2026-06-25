"""Tests for deck export and the export→load round-trip.

The golden parity tests are the critical guard: exported deck items must be
byte-identical to what the live generation pipeline produces, so FSRS item keys
(sha256(item)[:16]) — and thus every card's review history — survive the split.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from wiki_acronyms import deck_export
from wiki_acronyms.deck_loader import (
    deck_config_hash, discover_decks, load_monarchs_deck, load_poetry_deck,
)
from wiki_acronyms.logger import config_hash, item_key
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


def _mock_logger():
    """Logger stub whose _last_studied lookup returns None."""
    logger = MagicMock()
    logger._conn.execute.return_value.fetchone.return_value = None
    return logger


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
        logger = _mock_logger()
        info = discover_decks(decks, logger)
        assert len(info) == 1
        d = info[0]
        assert (d.name, d.deck_type, d.mode, d.poem_title) == ('Sonnet 18', 'poetry', 'words', 'Sonnet 18')
        assert d.config_path == str(cfg)
        assert d.group is None

    def test_monarchs_artifact_fields(self, tmp_path):
        _write_monarchs(tmp_path)
        decks = tmp_path / 'decks'
        _export(tmp_path, decks)
        info = discover_decks(decks, _mock_logger())
        d = next(x for x in info if x.deck_type == 'monarchs')
        assert (d.name, d.mode, d.poem_title) == ('British Monarchs', 'digits', None)

    def test_collection_group_and_multi_filenames(self, tmp_path):
        _write_poetry(tmp_path, multi=True)
        decks = tmp_path / 'decks'
        written = _export(tmp_path, decks)
        assert len(written) == 2
        assert len({p.name for p in written}) == 2  # unique filenames
        info = discover_decks(decks, _mock_logger())
        assert all(d.group == 'My Collection' for d in info)
        assert {d.poem_title for d in info} == {'First Half', 'Second Half'}

    def test_export_clears_stale_artifacts(self, tmp_path):
        decks = tmp_path / 'decks'
        decks.mkdir()
        (decks / 'stale.json').write_text('{}')
        _write_poetry(tmp_path)
        _export(tmp_path, decks)
        assert not (decks / 'stale.json').exists()


# --- config hash continuity ---

class TestConfigHash:
    def test_artifact_hash_matches_logger_config_hash(self, tmp_path):
        cfg = _write_poetry(tmp_path)
        decks = tmp_path / 'decks'
        _export(tmp_path, decks)
        assert deck_config_hash(cfg, 'Sonnet 18', decks) == config_hash(cfg)

    def test_monarchs_hash_matches(self, tmp_path):
        cfg = _write_monarchs(tmp_path)
        decks = tmp_path / 'decks'
        _export(tmp_path, decks)
        assert deck_config_hash(cfg, decks_dir=decks) == config_hash(cfg)


# --- golden parity: exported items identical to live generation ---

class TestParity:
    def test_poetry_items_match_live_generation(self, tmp_path):
        cfg = _write_poetry(tmp_path)
        decks = tmp_path / 'decks'
        _export(tmp_path, decks)
        expected = [l for l in extract_poem(_POEM_TEXT, "Shall I compare", "short a date.")
                    if l is not None]
        items, title = load_poetry_deck(cfg, 'Sonnet 18', decks)
        assert items == expected
        assert title == 'Sonnet 18'

    def test_poetry_item_keys_preserved(self, tmp_path):
        """FSRS card identity must be unchanged for every item."""
        cfg = _write_poetry(tmp_path)
        decks = tmp_path / 'decks'
        _export(tmp_path, decks)
        items, _ = load_poetry_deck(cfg, 'Sonnet 18', decks)
        expected = [l for l in extract_poem(_POEM_TEXT, "Shall I compare", "short a date.")
                    if l is not None]
        assert [item_key(i) for i in items] == [item_key(e) for e in expected]

    def test_monarchs_items_and_labels_match_live_generation(self, tmp_path):
        cfg = _write_monarchs(tmp_path)
        decks = tmp_path / 'decks'
        _export(tmp_path, decks)
        chunks = make_monarch_chunks(_MONARCHS, 100, 800)
        exp_items = [c.transition_string for c in chunks]
        exp_labels = [f"{c.start_year}–{c.end_year}" for c in chunks]
        items, title, labels = load_monarchs_deck(cfg, decks)
        assert items == exp_items
        assert labels == exp_labels
        assert title == 'British Monarchs'

    def test_relative_and_absolute_config_paths_resolve_same_deck(self, tmp_path, monkeypatch):
        cfg = _write_poetry(tmp_path)
        decks = tmp_path / 'decks'
        _export(tmp_path, decks)
        monkeypatch.chdir(tmp_path)
        rel = cfg.relative_to(tmp_path)
        items_rel, _ = load_poetry_deck(rel, 'Sonnet 18', decks)
        items_abs, _ = load_poetry_deck(cfg, 'Sonnet 18', decks)
        assert items_rel == items_abs


# --- missing artifact ---

def test_missing_artifact_raises(tmp_path):
    decks = tmp_path / 'decks'
    decks.mkdir()
    with pytest.raises(FileNotFoundError):
        load_poetry_deck(tmp_path / 'poetry' / 'nope.yaml', 'X', decks)
