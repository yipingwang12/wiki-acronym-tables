from unittest.mock import patch

from wiki_acronyms.country_registry import (
    CountryEntry, fetch_country_registry, load_registry, save_registry,
)

_SAMPLE_BINDINGS = [
    {
        "country": {"value": "http://www.wikidata.org/entity/Q145"},
        "countryLabel": {"value": "United Kingdom"},
        "position": {"value": "http://www.wikidata.org/entity/Q9134365"},
        "positionLabel": {"value": "monarch of the United Kingdom"},
    },
    {
        "country": {"value": "http://www.wikidata.org/entity/Q142"},
        "countryLabel": {"value": "France"},
        "position": {"value": "http://www.wikidata.org/entity/Q191789"},
        "positionLabel": {"value": "President of France"},
    },
    {
        "country": {"value": "http://www.wikidata.org/entity/Q142"},
        "countryLabel": {"value": "France"},
        "position": {"value": "http://www.wikidata.org/entity/Q191790"},
        "positionLabel": {"value": "Prime Minister of France"},
    },
]


def test_fetch_returns_entries():
    with patch("wiki_acronyms.country_registry._sparql_session", return_value=_SAMPLE_BINDINGS):
        entries = fetch_country_registry()
    assert len(entries) == 2
    names = {e.name for e in entries}
    assert "United Kingdom" in names
    assert "France" in names


def test_fetch_groups_multiple_positions():
    with patch("wiki_acronyms.country_registry._sparql_session", return_value=_SAMPLE_BINDINGS):
        entries = fetch_country_registry()
    france = next(e for e in entries if e.name == "France")
    assert len(france.position_qids) == 2
    assert "Q191789" in france.position_qids
    assert "Q191790" in france.position_qids


def test_fetch_no_duplicate_positions():
    # Same position appearing twice should only be stored once
    duplicate = _SAMPLE_BINDINGS[0].copy()
    bindings = [_SAMPLE_BINDINGS[0], duplicate]
    with patch("wiki_acronyms.country_registry._sparql_session", return_value=bindings):
        entries = fetch_country_registry()
    uk = entries[0]
    assert uk.position_qids.count("Q9134365") == 1


def test_fetch_sorted_by_name():
    with patch("wiki_acronyms.country_registry._sparql_session", return_value=_SAMPLE_BINDINGS):
        entries = fetch_country_registry()
    names = [e.name for e in entries]
    assert names == sorted(names)


def test_fetch_skips_unlabelled_q_ids():
    bindings = [{
        "country": {"value": "http://www.wikidata.org/entity/Q999"},
        "countryLabel": {"value": "Q999"},
        "position": {"value": "http://www.wikidata.org/entity/Q1"},
        "positionLabel": {"value": "some position"},
    }]
    with patch("wiki_acronyms.country_registry._sparql_session", return_value=bindings):
        assert fetch_country_registry() == []


def test_fetch_skips_missing_fields():
    with patch("wiki_acronyms.country_registry._sparql_session", return_value=[{}]):
        assert fetch_country_registry() == []


def test_save_load_roundtrip(tmp_path):
    entries = [
        CountryEntry(
            name="United Kingdom",
            country_qid="Q145",
            position_qids=["Q9134365"],
            position_labels=["monarch of the United Kingdom"],
            wikipedia_list="List of British monarchs",
        )
    ]
    path = tmp_path / "registry.yaml"
    save_registry(entries, path)
    loaded = load_registry(path)
    assert len(loaded) == 1
    assert loaded[0].name == "United Kingdom"
    assert loaded[0].country_qid == "Q145"
    assert loaded[0].position_qids == ["Q9134365"]
    assert loaded[0].position_labels == ["monarch of the United Kingdom"]
    assert loaded[0].wikipedia_list == "List of British monarchs"


def test_save_load_null_wikipedia_list(tmp_path):
    entries = [CountryEntry(name="France", country_qid="Q142", position_qids=["Q191789"])]
    path = tmp_path / "registry.yaml"
    save_registry(entries, path)
    loaded = load_registry(path)
    assert loaded[0].wikipedia_list is None


def test_save_load_multiple_entries(tmp_path):
    entries = [
        CountryEntry("France", "Q142", ["Q191789"], ["President of France"]),
        CountryEntry("Germany", "Q183", ["Q4370960"], ["Federal Chancellor of Germany"]),
    ]
    path = tmp_path / "registry.yaml"
    save_registry(entries, path)
    loaded = load_registry(path)
    assert len(loaded) == 2
    assert loaded[0].name == "France"
    assert loaded[1].name == "Germany"
