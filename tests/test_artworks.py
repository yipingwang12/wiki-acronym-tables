"""Tests for the Wikidata artworks fetch + query builder."""

from __future__ import annotations

from unittest.mock import MagicMock, Mock, patch

from wiki_acronyms.artworks import Artwork, build_query, fetch_artworks


def _binding(qid, title, creator_qid, creator, img="http://img/x.jpg", sitelinks=50, inception=None):
    b = {
        "work": {"value": f"http://www.wikidata.org/entity/{qid}"},
        "workLabel": {"value": title},
        "creator": {"value": f"http://www.wikidata.org/entity/{creator_qid}"},
        "creatorLabel": {"value": creator},
        "img": {"value": img},
        "sitelinks": {"value": str(sitelinks)},
    }
    if inception is not None:
        b["inception"] = {"value": inception}
    return b


def _mock_session(bindings):
    resp = Mock()
    resp.json.return_value = {"results": {"bindings": bindings}}
    resp.raise_for_status.return_value = None
    session = MagicMock()
    session.get.return_value = resp
    return session


def _fetch(bindings, config=None):
    with patch("wiki_acronyms.wikidata.requests.Session", return_value=_mock_session(bindings)):
        return fetch_artworks(config or {"source": "wikidata"})


class TestFetch:
    def test_parses_rows(self):
        arts = _fetch([_binding("Q12418", "Mona Lisa", "Q762", "Leonardo da Vinci",
                                 sitelinks=146, inception="1503-01-01T00:00:00Z")])
        assert arts == [Artwork("Q12418", "Mona Lisa", "Leonardo da Vinci", "Q762",
                                "http://img/x.jpg", 146, 1503)]

    def test_dedupes_by_qid_keeping_first(self):
        # two P18 images on one work → two rows, one Artwork
        arts = _fetch([
            _binding("Q12418", "Mona Lisa", "Q762", "Leonardo da Vinci", img="http://img/a.jpg"),
            _binding("Q12418", "Mona Lisa", "Q762", "Leonardo da Vinci", img="http://img/b.jpg"),
        ])
        assert len(arts) == 1 and arts[0].image_url == "http://img/a.jpg"

    def test_drops_unlabelled_title_keeps_unlabelled_creator_as_anon(self):
        arts = _fetch([
            _binding("Q1", "Q999999", "Q762", "Leonardo"),      # title = Q-number → drop the work
            _binding("Q2", "Real Title", "Q5", "Q888888"),      # creator = Q-number → keep, anon
            _binding("Q3", "Good", "Q7", "Real Painter"),
        ])
        assert [a.qid for a in arts] == ["Q2", "Q3"]
        anon = next(a for a in arts if a.qid == "Q2")
        assert anon.creator == "" and anon.creator_qid == ""

    def test_unknown_value_creator_kept_as_anonymous(self):
        # Wikidata 'unknown value' P170 → a blank-node genid URI in both creator + creatorLabel.
        b = _binding("Q546241", "Theotokos of Vladimir", "x", "x")
        genid = "http://www.wikidata.org/.well-known/genid/8ae9eff5d369995d380e8b3a3c59c98e"
        b["creator"]["value"] = genid
        b["creatorLabel"]["value"] = genid
        arts = _fetch([b])
        assert len(arts) == 1
        assert arts[0].title == "Theotokos of Vladimir" and arts[0].creator == ""

    def test_drops_work_whose_title_is_a_uri(self):
        b = _binding("Q1", "http://www.wikidata.org/.well-known/genid/deadbeef", "Q2", "C")
        assert _fetch([b]) == []

    def test_skips_missing_image(self):
        b = _binding("Q1", "T", "Q2", "C")
        del b["img"]
        assert _fetch([b]) == []

    def test_bce_inception(self):
        arts = _fetch([_binding("Q1", "T", "Q2", "C", inception="-0450-01-01T00:00:00Z")])
        assert arts[0].inception == -450


class TestQuery:
    def test_wikidata_mode_uses_threshold(self):
        q = build_query({"source": "wikidata", "min_sitelinks": 40})
        assert "wdt:P31 wd:Q3305213" in q and "?sitelinks >= 40" in q

    def test_curated_mode_lists_values(self):
        q = build_query({"source": "curated", "works": ["Q12418", "Q45585"]})
        assert "VALUES ?work { wd:Q12418 wd:Q45585 }" in q

    def test_collection_mode(self):
        q = build_query({"source": "collection", "collection": "Q19675"})
        assert "wdt:P195 wd:Q19675" in q

    def test_limit_applied(self):
        assert "LIMIT 30" in build_query({"source": "wikidata", "limit": 30})

    def test_no_limit_when_absent(self):
        assert "LIMIT" not in build_query({"source": "wikidata"})
