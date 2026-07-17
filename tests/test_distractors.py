"""Tests for baked multiple-choice distractors."""

from __future__ import annotations

from wiki_acronyms.artworks import Artwork
from wiki_acronyms.distractors import build_choices


def _art(qid, title, creator_qid, creator, inception=None):
    return Artwork(qid, title, creator, creator_qid, f"http://img/{qid}", 50, inception)


# A deck: two van Goghs, one Vermeer, one Leonardo — enough for same-creator biasing.
_DECK = [
    _art("Q1", "The Starry Night", "QVG", "Vincent van Gogh", 1889),
    _art("Q2", "The Potato Eaters", "QVG", "Vincent van Gogh", 1885),
    _art("Q3", "Girl with a Pearl Earring", "QVer", "Johannes Vermeer", 1665),
    _art("Q4", "Mona Lisa", "QLeo", "Leonardo da Vinci", 1503),
]


class TestBuildChoices:
    def test_correct_present_exactly_once(self):
        choices = build_choices(_DECK, "title", count=4)
        assert choices["Q1"].count("The Starry Night") == 1

    def test_correct_not_in_distractor_role(self):
        # all options distinct, correct included
        for opts in build_choices(_DECK, "creator", count=4).values():
            assert len(opts) == len(set(opts))

    def test_deterministic(self):
        assert build_choices(_DECK, "title", 4) == build_choices(_DECK, "title", 4)

    def test_title_distractors_prefer_same_creator(self):
        # Q1 is a van Gogh; the other van Gogh title should be among its distractors.
        opts = build_choices(_DECK, "title", count=2, same_creator_bias=True)["Q1"]
        assert "The Potato Eaters" in opts

    def test_option_count_capped_to_available(self):
        tiny = _DECK[:2]  # only one possible distractor
        opts = build_choices(tiny, "title", count=4)["Q1"]
        assert len(opts) == 2  # correct + the single available distractor, never padded

    def test_creator_options_are_creators(self):
        opts = build_choices(_DECK, "creator", count=4)["Q1"]
        assert "Vincent van Gogh" in opts
        assert all(o in {a.creator for a in _DECK} for o in opts)

    def test_no_duplicate_title_when_two_works_share_it(self):
        deck = _DECK + [_art("Q5", "Mona Lisa", "QLeoschool", "Leonardeschi", 1505)]
        # Q4's correct title is "Mona Lisa"; Q5 shares it → must not appear as a distractor
        opts = build_choices(deck, "title", count=4)["Q4"]
        assert opts.count("Mona Lisa") == 1
