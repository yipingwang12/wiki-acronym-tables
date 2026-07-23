"""Deterministic core of the vocab pipeline (no API). CC-CEDICT is read from cache."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from deck_generator import vocab

CEDICT = vocab.CEDICT_CACHE
pytestmark = pytest.mark.skipif(not CEDICT.exists(), reason="CC-CEDICT cache absent")


@pytest.fixture(scope="module")
def cedict():
    return vocab.load_cedict(CEDICT)


class TestPinyin:
    @pytest.mark.parametrize(
        "numbered,marked",
        [("ni3 hao3", "nǐ hǎo"), ("wo3", "wǒ"), ("fei1 chang2", "fēi cháng"),
         ("lu:4", "lǜ"), ("ma5", "ma")],
    )
    def test_diacritics(self, numbered, marked):
        assert vocab.pinyin_marks(numbered) == marked


class TestRouter:
    def test_function_words_route_to_llm(self, cedict):
        # 被 (passive marker) and 把 (disposal marker) — CC-CEDICT first-sense is wrong.
        cands = {c.hanzi: c for c in vocab.rank_candidates(cedict, exclude=set(), target_n=400)}
        assert cands["被"].needs_llm and cands["被"].functional
        assert cands["把"].needs_llm

    def test_clean_content_word_first_sense(self, cedict):
        cands = vocab.rank_candidates(cedict, exclude=set(), target_n=2000)
        clean = next(c for c in cands if not c.needs_llm)
        row = vocab.clean_row(clean)
        assert row.hanzi == clean.hanzi and row.gloss and row.source == "cedict-first"

    def test_exclude_removes_seed(self, cedict):
        cands = vocab.rank_candidates(cedict, exclude={"的", "我"}, target_n=50)
        assert not any(c.hanzi in {"的", "我"} for c in cands)

    def test_llm_batch_carries_all_senses(self, cedict):
        cands = vocab.rank_candidates(cedict, exclude=set(), target_n=400)
        recs = vocab.llm_batch_records(cands)
        assert recs, "some candidates must need LLM adjudication"
        multi = next(r for r in recs if len(r["readings"]) > 1 or len(r["readings"][0]["glosses"]) > 3)
        assert "hanzi" in multi and multi["readings"]


class TestSeedAndArtifact:
    def test_seed_frozen_verbatim(self, tmp_path):
        deck = {"items": ["我", "你"], "pinyin": ["wǒ", "nǐ"], "labels": ["I", "you"]}
        p = tmp_path / "seed.json"
        p.write_text(json.dumps(deck, ensure_ascii=False), encoding="utf-8")
        rows = vocab.load_seed(p)
        assert [r.hanzi for r in rows] == ["我", "你"]
        assert [r.gloss for r in rows] == ["I", "you"]
        assert all(r.source == "seed" for r in rows)

    def test_artifact_envelope(self):
        rows = [vocab.CuratedRow("我", "wǒ", "I", "seed"),
                vocab.CuratedRow("方式", "fāng shì", "way", "cedict-first")]
        art = vocab.assemble_artifact(rows, {"deck_name": "Chinese — Common Words"}, "vocab/x.yaml")
        assert art["deck_type"] == "vocab" and art["mode"] == "matching"
        assert art["source"] == "manual"  # protected from clear/sync
        assert art["items"] == ["我", "方式"]
        assert art["pinyin"] == ["wǒ", "fāng shì"]
        assert art["labels"] == ["I", "way"]
        assert "CC-BY-SA" in art["license"]


class TestBuild:
    def test_band_collisions_detects_within_window(self):
        rows = [vocab.CuratedRow(str(i), "x", "same", "c") for i in range(3)]
        assert vocab.band_collisions(rows, window=30)          # same gloss, adjacent
        far = [vocab.CuratedRow(str(i), "x", "same" if i in (0, 40) else f"g{i}", "c")
               for i in range(41)]
        assert not vocab.band_collisions(far, window=30)       # 40 apart → outside window

    def test_load_curated_roundtrip(self, tmp_path):
        p = tmp_path / "c.jsonl"
        p.write_text('{"hanzi":"我","pinyin":"wǒ","gloss":"I"}\n'
                     '{"hanzi":"你","pinyin":"nǐ","gloss":"you"}\n', encoding="utf-8")
        rows = vocab.load_curated(p)
        assert [r.hanzi for r in rows] == ["我", "你"]

    def test_committed_deck_builds_clean(self):
        """The shipped curated data assembles to a valid deck: unique hanzi, 0 band collisions."""
        curated = _ROOT_CFG / "chinese_common.curated.jsonl"
        if not curated.exists():
            import pytest as _pt
            _pt.skip("committed curated data absent")
        rows = vocab.load_curated(curated)
        assert len(rows) == 5257
        assert len({r.hanzi for r in rows}) == len(rows)       # no FSRS-key collision
        assert not vocab.band_collisions(rows)                 # no ambiguous rounds


from pathlib import Path as _Path
_ROOT_CFG = _Path(__file__).resolve().parents[1] / "configs" / "vocab"
