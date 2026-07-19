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

from deck_generator import deck_export
from deck_generator.artworks import Artwork
from deck_generator.monarchs import Monarch, make_monarch_chunks
from deck_generator.poetry_parser import extract_poem

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
    with patch('deck_generator.deck_export.fetch_text', return_value=_POEM_TEXT), \
         patch('deck_generator.deck_export.fetch_monarchs', return_value=_MONARCHS):
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
        assert a['group'] == 'Monarchs'   # all monarch decks share one collapsible menu

    def test_monarch_group_overridable_per_config(self, tmp_path):
        path = _write_monarchs(tmp_path)
        path.write_text(path.read_text() + "group: European Monarchs\n")
        decks = tmp_path / 'decks'
        _export(tmp_path, decks)
        assert _find(decks, path)['group'] == 'European Monarchs'

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

    def test_full_export_preserves_manual_artifacts(self, tmp_path):
        # A hand-authored source:manual deck (e.g. the CC-CEDICT vocab deck) has no
        # generator config to rebuild from, so the authoritative clear must not wipe it.
        decks = tmp_path / 'decks'
        decks.mkdir()
        manual = decks / 'vocab_chinese_common.json'
        manual.write_text('{"source": "manual", "items": ["你好"]}', encoding='utf-8')
        (decks / 'stale.json').write_text('{}')
        _write_poetry(tmp_path)
        _export(tmp_path, decks)
        assert manual.exists()
        assert not (decks / 'stale.json').exists()      # generated stale still cleared


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

_ARTWORKS = [
    Artwork("Q12418", "Mona Lisa", "Leonardo da Vinci", "Q762", "http://img/1.jpg", 146, 1503),
    Artwork("Q45585", "The Starry Night", "Vincent van Gogh", "QVG", "http://img/2.jpg", 76, 1889),
    Artwork("Q208601", "The Potato Eaters", "Vincent van Gogh", "QVG", "http://img/3.jpg", 53, 1885),
]


def _write_artworks(config_dir):
    (config_dir / 'artworks').mkdir(parents=True, exist_ok=True)
    path = config_dir / 'artworks' / 'famous.yaml'
    path.write_text(
        "deck_name: Famous Paintings\n"
        "source: wikidata\n"
        "min_sitelinks: 40\n"
        "distractors:\n"
        "  count: 3\n"
    )
    return path


def _export_artworks(config_dir, decks_dir, only=None, arts=None, fail_qids=()):
    """Export with the network + Pillow stubbed: fake fetch, fake per-QID image bytes."""
    def fake_fetch_raw(url, cache_dir, key, **kw):
        if key in fail_qids:
            raise RuntimeError("dead image")
        return f"raw:{key}".encode()

    with patch('deck_generator.deck_export.fetch_artworks', return_value=arts if arts is not None else _ARTWORKS), \
         patch('deck_generator.deck_export.fetch_raw', side_effect=fake_fetch_raw), \
         patch('deck_generator.deck_export.to_webp', side_effect=lambda raw, px: b'WEBP:' + raw):
        return deck_export.export_decks(config_dir, decks_dir, only=only)


class TestArtworks:
    def test_two_cards_per_artwork_keyed_on_qid_attr(self, tmp_path):
        cfg = _write_artworks(tmp_path)
        decks = tmp_path / 'decks'
        _export_artworks(tmp_path, decks)
        a = _find(decks, cfg)
        assert a['deck_type'] == 'artworks' and a['mode'] == 'image-mc'
        assert a['items'] == ['Q12418|title', 'Q12418|creator',
                              'Q45585|title', 'Q45585|creator',
                              'Q208601|title', 'Q208601|creator']
        assert a['group'] == 'Artworks'

    def test_parallel_arrays_aligned(self, tmp_path):
        cfg = _write_artworks(tmp_path)
        decks = tmp_path / 'decks'
        _export_artworks(tmp_path, decks)
        a = _find(decks, cfg)
        n = len(a['items'])
        assert len(a['labels']) == len(a['prompts']) == len(a['answers']) == len(a['img']) == len(a['choices']) == n
        assert a['prompts'][:2] == ['title', 'creator']
        assert a['answers'][:2] == ['Mona Lisa', 'Leonardo da Vinci']
        assert a['img'][0] == a['img'][1] == 'assets/artworks_famous/Q12418.webp'  # shared per artwork

    def test_choices_include_correct_answer(self, tmp_path):
        cfg = _write_artworks(tmp_path)
        decks = tmp_path / 'decks'
        _export_artworks(tmp_path, decks)
        a = _find(decks, cfg)
        for answer, opts in zip(a['answers'], a['choices']):
            assert answer in opts

    def test_anonymous_work_emits_title_only_and_never_pollutes_choices(self, tmp_path):
        # An anonymous work (empty creator, as fetch_artworks now yields for 'unknown value')
        # gets a title card but NO creator card, and its blank creator never leaks as an option.
        arts = list(_ARTWORKS) + [
            Artwork("Q546241", "Theotokos of Vladimir", "", "", "http://img/ic.jpg", 40, 1130)]
        cfg = _write_artworks(tmp_path)
        decks = tmp_path / 'decks'
        _export_artworks(tmp_path, decks, arts=arts)
        a = _find(decks, cfg)
        assert "Q546241|title" in a['items']
        assert "Q546241|creator" not in a['items']          # title-only
        assert "" not in a['answers']                        # no blank answer
        assert all("" not in opts for opts in a['choices'])  # no blank distractor anywhere

    def test_image_assets_written(self, tmp_path):
        _write_artworks(tmp_path)
        decks = tmp_path / 'decks'
        _export_artworks(tmp_path, decks)
        asset = decks / 'assets' / 'artworks_famous' / 'Q12418.webp'
        assert asset.read_bytes() == b'WEBP:raw:Q12418'

    def test_item_keys_derived_from_qid_attr(self, tmp_path):
        cfg = _write_artworks(tmp_path)
        decks = tmp_path / 'decks'
        _export_artworks(tmp_path, decks)
        a = _find(decks, cfg)
        assert _item_key('Q12418|title') == _item_key(a['items'][0])

    def test_failed_image_skips_artwork_not_deck(self, tmp_path):
        cfg = _write_artworks(tmp_path)
        decks = tmp_path / 'decks'
        _export_artworks(tmp_path, decks, fail_qids={'Q45585'})
        a = _find(decks, cfg)
        assert 'Q45585|title' not in a['items']          # skipped
        assert 'Q12418|title' in a['items']              # deck still built
        assert not (decks / 'assets' / 'artworks_famous' / 'Q45585.webp').exists()

    def test_no_private_keys_leak(self, tmp_path):
        cfg = _write_artworks(tmp_path)
        decks = tmp_path / 'decks'
        _export_artworks(tmp_path, decks)
        a = _find(decks, cfg)
        assert '_assets' not in a and '_filename' not in a

    def test_full_export_clears_stale_assets(self, tmp_path):
        _write_artworks(tmp_path)
        decks = tmp_path / 'decks'
        stale = decks / 'assets' / 'artworks_famous' / 'ZZZ.webp'
        stale.parent.mkdir(parents=True)
        stale.write_bytes(b'old')
        _export_artworks(tmp_path, decks)
        assert not stale.exists()                          # cleared on full rebuild
        assert (decks / 'assets' / 'artworks_famous' / 'Q12418.webp').exists()

    def test_only_refresh_rebuilds_just_this_decks_assets(self, tmp_path):
        _write_artworks(tmp_path)
        decks = tmp_path / 'decks'
        _export_artworks(tmp_path, decks, arts=_ARTWORKS)
        # drop one artwork, refresh only this deck → its removed asset must not linger
        _export_artworks(tmp_path, decks, only='artworks_famous', arts=_ARTWORKS[:1])
        assert (decks / 'assets' / 'artworks_famous' / 'Q12418.webp').exists()
        assert not (decks / 'assets' / 'artworks_famous' / 'Q45585.webp').exists()


def test_missing_artifact_raises(tmp_path):
    decks = tmp_path / 'decks'
    decks.mkdir()
    with pytest.raises(FileNotFoundError):
        _find(decks, tmp_path / 'poetry' / 'nope.yaml', 'X')


# --- --only: surgical refresh -------------------------------------------------------
# The export dir accumulates across runs, so a partial rebuild must not re-derive the two
# IDENTITY fields: config_path keys the quiz's sessions table and artifact lookup, order
# drives deck-list sort. Re-deriving either during a subset refresh strands study history
# or shuffles the list.

def _export_only(config_dir, decks_dir, only=None, reset_identity=False):
    with patch('deck_generator.deck_export.fetch_text', return_value=_POEM_TEXT), \
         patch('deck_generator.deck_export.fetch_monarchs', return_value=_MONARCHS):
        return deck_export.export_decks(config_dir, decks_dir, only=only,
                                        reset_identity=reset_identity)


class TestOnly:
    def test_only_writes_just_the_match(self, tmp_path):
        _write_poetry(tmp_path)
        _write_monarchs(tmp_path)
        decks = tmp_path / 'decks'
        _export_only(tmp_path, decks)                      # full first
        written = _export_only(tmp_path, decks, only='monarchs_britain')
        assert [p.name for p in written] == ['monarchs_britain.json']

    def test_only_leaves_other_decks_untouched(self, tmp_path):
        _write_poetry(tmp_path)
        _write_monarchs(tmp_path)
        decks = tmp_path / 'decks'
        _export_only(tmp_path, decks)
        poetry = decks / 'poetry_sonnet.json'
        before = poetry.read_text()
        _export_only(tmp_path, decks, only='monarchs_britain')
        assert poetry.read_text() == before   # not rewritten, not deleted

    def test_only_does_not_clear_the_directory(self, tmp_path):
        # The guard that would have wiped 174 live decks: a full export unlinks *.json.
        _write_poetry(tmp_path)
        _write_monarchs(tmp_path)
        decks = tmp_path / 'decks'
        _export_only(tmp_path, decks)
        _export_only(tmp_path, decks, only='monarchs_britain')
        assert (decks / 'poetry_sonnet.json').exists()

    def test_full_export_still_clears(self, tmp_path):
        _write_poetry(tmp_path)
        decks = tmp_path / 'decks'
        decks.mkdir()
        (decks / 'obsolete.json').write_text('{}')
        _export_only(tmp_path, decks)
        assert not (decks / 'obsolete.json').exists()

    def test_only_preserves_order_of_the_rebuilt_deck(self, tmp_path):
        _write_poetry(tmp_path)
        _write_monarchs(tmp_path)
        decks = tmp_path / 'decks'
        _export_only(tmp_path, decks)
        path = decks / 'monarchs_britain.json'
        stale = json.loads(path.read_text())
        stale['order'] = 999          # simulate an artifact numbered by an earlier run
        path.write_text(json.dumps(stale))
        _export_only(tmp_path, decks, only='monarchs_britain')
        assert json.loads(path.read_text())['order'] == 999

    def test_only_preserves_config_path_of_the_rebuilt_deck(self, tmp_path):
        # Regression: exporting from a git worktree stamped the worktree path in, which
        # would strand session history keyed on the canonical path.
        _write_poetry(tmp_path)
        _write_monarchs(tmp_path)
        decks = tmp_path / 'decks'
        _export_only(tmp_path, decks)
        path = decks / 'monarchs_britain.json'
        stale = json.loads(path.read_text())
        stale['config_path'] = '/canonical/checkout/configs/monarchs/britain.yaml'
        path.write_text(json.dumps(stale))
        _export_only(tmp_path, decks, only='monarchs_britain')
        assert json.loads(path.read_text())['config_path'] == \
            '/canonical/checkout/configs/monarchs/britain.yaml'

    def test_only_still_refreshes_content(self, tmp_path):
        # Identity is preserved, but items/config_hash must still update.
        _write_poetry(tmp_path)
        _write_monarchs(tmp_path)
        decks = tmp_path / 'decks'
        _export_only(tmp_path, decks)
        path = decks / 'monarchs_britain.json'
        stale = json.loads(path.read_text())
        real_items = stale['items']
        stale['items'] = ['STALE']
        path.write_text(json.dumps(stale))
        _export_only(tmp_path, decks, only='monarchs_britain')
        assert json.loads(path.read_text())['items'] == real_items

    def test_reset_identity_re_derives(self, tmp_path):
        _write_poetry(tmp_path)
        _write_monarchs(tmp_path)
        decks = tmp_path / 'decks'
        _export_only(tmp_path, decks)
        path = decks / 'monarchs_britain.json'
        stale = json.loads(path.read_text())
        fresh_order = stale['order']
        stale['order'] = 999
        path.write_text(json.dumps(stale))
        _export_only(tmp_path, decks, only='monarchs_britain', reset_identity=True)
        assert json.loads(path.read_text())['order'] == fresh_order

    def test_only_glob_matches_many(self, tmp_path):
        _write_poetry(tmp_path, multi=True)
        _write_monarchs(tmp_path)
        decks = tmp_path / 'decks'
        _export_only(tmp_path, decks)
        written = _export_only(tmp_path, decks, only='poetry_*')
        assert len(written) == 2 and all('poetry_' in p.name for p in written)

    def test_only_skips_fetch_for_unmatched(self, tmp_path):
        # The point of resolving order from configs alone: an unmatched deck is never fetched.
        _write_poetry(tmp_path)
        _write_monarchs(tmp_path)
        decks = tmp_path / 'decks'
        _export_only(tmp_path, decks)
        with patch('deck_generator.deck_export.fetch_text', return_value=_POEM_TEXT) as ft, \
             patch('deck_generator.deck_export.fetch_monarchs', return_value=_MONARCHS) as fm:
            deck_export.export_decks(tmp_path, decks, only='monarchs_britain')
        ft.assert_not_called()      # poetry not fetched
        fm.assert_called_once()

    def test_order_is_global_not_subset_relative(self, tmp_path):
        # monarchs sort after poetry; rebuilding only monarchs must keep its global order,
        # not renumber it to 0 as a subset-relative counter would.
        _write_poetry(tmp_path, multi=True)   # consumes orders 0 and 1
        _write_monarchs(tmp_path)             # order 2
        decks = tmp_path / 'decks'
        _export_only(tmp_path, decks)
        assert json.loads((decks / 'monarchs_britain.json').read_text())['order'] == 2
        _export_only(tmp_path, decks, only='monarchs_britain', reset_identity=True)
        assert json.loads((decks / 'monarchs_britain.json').read_text())['order'] == 2

    def test_filenames_stable_under_only(self, tmp_path):
        # Uniqueness suffixes are assigned across ALL slots; filtering must not shift them.
        _write_poetry(tmp_path, multi=True)
        decks = tmp_path / 'decks'
        full = sorted(p.name for p in _export_only(tmp_path, decks))
        sub = _export_only(tmp_path, decks, only='poetry_collection_second-half')
        assert [p.name for p in sub] == ['poetry_collection_second-half.json']
        assert 'poetry_collection_second-half.json' in full

    def test_no_private_filename_key_leaks_into_artifact(self, tmp_path):
        _write_monarchs(tmp_path)
        decks = tmp_path / 'decks'
        _export_only(tmp_path, decks)
        assert '_filename' not in json.loads((decks / 'monarchs_britain.json').read_text())
