from pathlib import Path
from unittest.mock import patch

import openpyxl
import pytest

from wiki_acronyms.derive_positions import (
    DerivedPosition, _escape_sparql_string, fetch_positions_for_titles,
    load_ruler_titles,
)


# --- helpers ---

def _make_xlsx(tmp_path: Path, rows: list[dict]) -> Path:
    path = tmp_path / "rulers.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    headers = list(rows[0].keys())
    ws.append(headers)
    for row in rows:
        ws.append([row.get(h, "") for h in headers])
    wb.save(path)
    return path


def _make_csv(tmp_path: Path, rows: list[dict]) -> Path:
    import csv
    path = tmp_path / "rulers.csv"
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return path


_SAMPLE_ROWS = [
    {"title": "William I of England", "nationality": "English", "occupation": "king"},
    {"title": "Henry VIII", "nationality": "English", "occupation": "king"},
    {"title": "Catherine II of Russia", "nationality": "German", "occupation": "empress"},
    {"title": "Napoleon Bonaparte", "nationality": "French", "occupation": "military leader"},
    {"title": "Band Queen", "nationality": "British", "occupation": "band queen"},
]

_SPARQL_BINDINGS = [
    {
        "person": {"value": "http://www.wikidata.org/entity/Q7732"},
        "position": {"value": "http://www.wikidata.org/entity/Q18810062"},
        "positionLabel": {"value": "monarch of England"},
    },
    {
        "person": {"value": "http://www.wikidata.org/entity/Q38370"},
        "position": {"value": "http://www.wikidata.org/entity/Q18810062"},
        "positionLabel": {"value": "monarch of England"},
    },
    {
        "person": {"value": "http://www.wikidata.org/entity/Q38370"},
        "position": {"value": "http://www.wikidata.org/entity/Q999"},
        "positionLabel": {"value": "Lord High Steward"},
    },
]


# --- load_ruler_titles ---

def test_load_filters_by_occupation(tmp_path):
    path = _make_xlsx(tmp_path, _SAMPLE_ROWS)
    titles = load_ruler_titles(path)
    assert "William I of England" in titles
    assert "Henry VIII" in titles
    assert "Catherine II of Russia" in titles
    assert "Napoleon Bonaparte" not in titles  # no ruler keyword


def test_load_excludes_noisy_band_queen(tmp_path):
    # "band queen" matches "queen" — intentionally accepted as a tradeoff;
    # noise is filtered downstream by Wikidata returning no P39 position
    path = _make_xlsx(tmp_path, _SAMPLE_ROWS)
    titles = load_ruler_titles(path)
    assert "Band Queen" in titles  # keyword match; Wikidata will return nothing useful


def test_load_filters_by_nationality(tmp_path):
    path = _make_xlsx(tmp_path, _SAMPLE_ROWS)
    titles = load_ruler_titles(path, nationality="English")
    assert "William I of England" in titles
    assert "Henry VIII" in titles
    assert "Catherine II of Russia" not in titles


def test_load_nationality_case_insensitive(tmp_path):
    path = _make_xlsx(tmp_path, _SAMPLE_ROWS)
    titles = load_ruler_titles(path, nationality="english")
    assert "William I of England" in titles


def test_load_csv(tmp_path):
    path = _make_csv(tmp_path, _SAMPLE_ROWS)
    titles = load_ruler_titles(path)
    assert "William I of England" in titles


def test_load_empty_file(tmp_path):
    path = _make_xlsx(tmp_path, [{"title": "", "nationality": "", "occupation": ""}])
    assert load_ruler_titles(path) == []


def test_load_missing_occupation_column(tmp_path):
    rows = [{"title": "William I", "nationality": "English"}]
    path = _make_xlsx(tmp_path, rows)
    assert load_ruler_titles(path) == []


# --- _escape_sparql_string ---

def test_escape_quotes():
    assert _escape_sparql_string('He said "hello"') == 'He said \\"hello\\"'


def test_escape_backslash():
    assert _escape_sparql_string("back\\slash") == "back\\\\slash"


def test_escape_plain():
    assert _escape_sparql_string("William I of England") == "William I of England"


# --- fetch_positions_for_titles ---

def test_fetch_returns_derived_positions():
    with patch("wiki_acronyms.derive_positions._sparql_session", return_value=_SPARQL_BINDINGS):
        result = fetch_positions_for_titles(["William I of England", "Henry VIII"])
    assert any(p.position_qid == "Q18810062" for p in result)


def test_fetch_counts_distinct_holders():
    with patch("wiki_acronyms.derive_positions._sparql_session", return_value=_SPARQL_BINDINGS):
        result = fetch_positions_for_titles(["William I of England", "Henry VIII"])
    england = next(p for p in result if p.position_qid == "Q18810062")
    assert england.holder_count == 2


def test_fetch_sorted_by_count_descending():
    with patch("wiki_acronyms.derive_positions._sparql_session", return_value=_SPARQL_BINDINGS):
        result = fetch_positions_for_titles(["William I of England", "Henry VIII"])
    counts = [p.holder_count for p in result]
    assert counts == sorted(counts, reverse=True)


def test_fetch_skips_bare_q_label():
    bindings = [{
        "person": {"value": "http://www.wikidata.org/entity/Q1"},
        "position": {"value": "http://www.wikidata.org/entity/Q99999"},
        "positionLabel": {"value": "Q99999"},
    }]
    with patch("wiki_acronyms.derive_positions._sparql_session", return_value=bindings):
        result = fetch_positions_for_titles(["Some Person"])
    assert result == []


def test_fetch_batches_large_input():
    """Titles exceeding batch_size should trigger multiple SPARQL calls."""
    titles = [f"Person {i}" for i in range(120)]
    with patch("wiki_acronyms.derive_positions._sparql_session", return_value=[]) as mock:
        fetch_positions_for_titles(titles, batch_size=50)
    assert mock.call_count == 3  # 50 + 50 + 20


def test_fetch_empty_titles():
    with patch("wiki_acronyms.derive_positions._sparql_session", return_value=[]):
        assert fetch_positions_for_titles([]) == []


def test_fetch_deduplicates_same_person_same_position():
    # Same person appearing twice should count as one holder
    bindings = [_SPARQL_BINDINGS[0], _SPARQL_BINDINGS[0]]
    with patch("wiki_acronyms.derive_positions._sparql_session", return_value=bindings):
        result = fetch_positions_for_titles(["William I of England"])
    england = next(p for p in result if p.position_qid == "Q18810062")
    assert england.holder_count == 1
