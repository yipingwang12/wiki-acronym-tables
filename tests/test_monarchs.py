from unittest.mock import patch

import pytest

from wiki_acronyms.monarchs import Monarch, MonarchChunk, fetch_monarchs, make_monarch_chunks

_SAMPLE_BINDINGS = [
    {
        "person": {"value": "http://www.wikidata.org/entity/Q12345"},
        "personLabel": {"value": "Alfred the Great"},
        "start": {"value": "0871-01-01T00:00:00Z"},
        "end": {"value": "0899-01-01T00:00:00Z"},
        "fatherLabel": {"value": "Æthelwulf"},
        "motherLabel": {"value": "Osburh"},
    },
    {
        "person": {"value": "http://www.wikidata.org/entity/Q12346"},
        "personLabel": {"value": "Edward the Elder"},
        "start": {"value": "0899-01-01T00:00:00Z"},
        "end": {"value": "0924-01-01T00:00:00Z"},
        "fatherLabel": {"value": "Alfred the Great"},
        "motherLabel": {"value": "Ealhswith"},
    },
    {
        "person": {"value": "http://www.wikidata.org/entity/Q12347"},
        "personLabel": {"value": "William I"},
        "start": {"value": "1066-12-25T00:00:00Z"},
        "end": {"value": "1087-09-09T00:00:00Z"},
        "fatherLabel": {"value": "Robert I, Duke of Normandy"},
        "motherLabel": {"value": "Herleva"},
    },
]


def _mock_sparql(bindings):
    with patch("wiki_acronyms.monarchs._sparql_session", return_value=bindings) as m:
        yield m


# fetch_monarchs
def test_fetch_basic():
    with patch("wiki_acronyms.monarchs._sparql_session", return_value=_SAMPLE_BINDINGS):
        monarchs = fetch_monarchs(["Q18810062"])
    assert len(monarchs) == 3
    assert monarchs[0].name == "Alfred the Great"
    assert monarchs[0].accession_year == 871
    assert monarchs[0].end_year == 899
    assert monarchs[0].father == "Æthelwulf"
    assert monarchs[0].mother == "Osburh"


def test_fetch_ordered_by_accession():
    with patch("wiki_acronyms.monarchs._sparql_session", return_value=_SAMPLE_BINDINGS):
        monarchs = fetch_monarchs(["Q18810062"])
    years = [m.accession_year for m in monarchs]
    assert years == sorted(years)


def test_fetch_missing_end_year():
    bindings = [{
        "person": {"value": "http://www.wikidata.org/entity/Q99999"},
        "personLabel": {"value": "Charles III"},
        "start": {"value": "2022-09-08T00:00:00Z"},
        "fatherLabel": {"value": "Charles, Prince of Wales"},
        "motherLabel": {"value": "Elizabeth II"},
    }]
    with patch("wiki_acronyms.monarchs._sparql_session", return_value=bindings):
        monarchs = fetch_monarchs(["Q192444"])
    assert monarchs[0].end_year is None


def test_fetch_skips_unlabelled_q_ids():
    bindings = [
        {"person": {"value": "http://www.wikidata.org/entity/Q99"}, "personLabel": {"value": "Q99"}, "start": {"value": "0871-01-01T00:00:00Z"}},
        _SAMPLE_BINDINGS[0],
    ]
    with patch("wiki_acronyms.monarchs._sparql_session", return_value=bindings):
        monarchs = fetch_monarchs(["Q18810062"])
    assert len(monarchs) == 1


def test_fetch_deduplicates_same_person_same_year():
    duplicate = dict(_SAMPLE_BINDINGS[0])
    with patch("wiki_acronyms.monarchs._sparql_session", return_value=[_SAMPLE_BINDINGS[0], duplicate]):
        monarchs = fetch_monarchs(["Q18810062"])
    assert len(monarchs) == 1


def test_fetch_deduplicates_same_person_different_title():
    # Same person Q-number, two positions with different start years (title change, not new monarch)
    row_early = {
        "person": {"value": "http://www.wikidata.org/entity/Q127318"},
        "personLabel": {"value": "George III"},
        "start": {"value": "1760-01-01T00:00:00Z"},
    }
    row_late = {
        "person": {"value": "http://www.wikidata.org/entity/Q127318"},
        "personLabel": {"value": "George III"},
        "start": {"value": "1801-01-01T00:00:00Z"},
    }
    with patch("wiki_acronyms.monarchs._sparql_session", return_value=[row_early, row_late]):
        monarchs = fetch_monarchs(["Q110324075", "Q111722535"])
    assert len(monarchs) == 1
    assert monarchs[0].accession_year == 1760  # earliest wins


def test_fetch_merges_parent_info():
    row1 = {"person": {"value": "http://www.wikidata.org/entity/Q12345"}, "personLabel": {"value": "Alfred the Great"}, "start": {"value": "0871-01-01T00:00:00Z"}}
    row2 = {**row1, "fatherLabel": {"value": "Æthelwulf"}, "motherLabel": {"value": "Osburh"}}
    with patch("wiki_acronyms.monarchs._sparql_session", return_value=[row1, row2]):
        monarchs = fetch_monarchs(["Q18810062"])
    assert monarchs[0].father == "Æthelwulf"
    assert monarchs[0].mother == "Osburh"


def test_fetch_query_contains_position_ids():
    with patch("wiki_acronyms.monarchs._sparql_session", return_value=[]) as mock_session:
        fetch_monarchs(["Q18810062", "Q192444"])
    query = mock_session.call_args[0][1]
    assert "wd:Q18810062" in query
    assert "wd:Q192444" in query


def test_fetch_empty():
    with patch("wiki_acronyms.monarchs._sparql_session", return_value=[]):
        assert fetch_monarchs(["Q18810062"]) == []


def test_fetch_populates_wp_title():
    bindings = [{
        **_SAMPLE_BINDINGS[2],
        "wpTitle": {"value": "William I of England"},
    }]
    with patch("wiki_acronyms.monarchs._sparql_session", return_value=bindings):
        monarchs = fetch_monarchs(["Q18810062"])
    assert monarchs[0].wp_title == "William I of England"


def test_fetch_wp_title_none_when_absent():
    with patch("wiki_acronyms.monarchs._sparql_session", return_value=[_SAMPLE_BINDINGS[0]]):
        monarchs = fetch_monarchs(["Q18810062"])
    assert monarchs[0].wp_title is None


def test_fetch_merges_wp_title():
    # First row has no sitelink; second (same person) has one — should be saved
    row1 = {**_SAMPLE_BINDINGS[0]}
    row2 = {**_SAMPLE_BINDINGS[0], "wpTitle": {"value": "Alfred the Great"}}
    with patch("wiki_acronyms.monarchs._sparql_session", return_value=[row1, row2]):
        monarchs = fetch_monarchs(["Q18810062"])
    assert monarchs[0].wp_title == "Alfred the Great"


# make_monarch_chunks
def _monarchs(*year_name_pairs):
    return [Monarch(name=n, accession_year=y, end_year=None, father="", mother="") for y, n in year_name_pairs]


def test_chunks_single_century():
    monarchs = _monarchs((871, "Alfred"), (899, "Edward"))
    chunks = make_monarch_chunks(monarchs, chunk_years=100, chunk_start_year=800)
    assert len(chunks) == 1
    assert chunks[0].start_year == 800
    assert chunks[0].end_year == 899


def test_chunks_two_centuries():
    monarchs = _monarchs((871, "Alfred"), (924, "Æthelstan"))
    chunks = make_monarch_chunks(monarchs, chunk_years=100, chunk_start_year=800)
    assert len(chunks) == 2
    assert chunks[0].start_year == 800
    assert chunks[1].start_year == 900


def test_transition_string():
    monarchs = _monarchs((871, "Alfred"), (899, "Edward"), (924, "Æthelstan"))
    chunks = make_monarch_chunks(monarchs, chunk_years=100, chunk_start_year=800)
    assert chunks[0].transition_string == "19"
    assert chunks[1].transition_string == "4"


def test_transition_string_same_year_repeated():
    # Two monarchs acceding in 1066 → two 6s
    monarchs = _monarchs((1066, "Harold II"), (1066, "William I"))
    chunks = make_monarch_chunks(monarchs, chunk_years=100, chunk_start_year=1000)
    assert chunks[0].transition_string == "66"


def test_empty_century_skipped():
    monarchs = _monarchs((871, "Alfred"), (1066, "William I"))
    chunks = make_monarch_chunks(monarchs, chunk_years=100, chunk_start_year=800)
    years = [c.start_year for c in chunks]
    # 900–999 has no monarchs; 800–899 and 1000–1099 do
    assert 900 not in years
    assert 800 in years
    assert 1000 in years


def test_empty_monarchs():
    assert make_monarch_chunks([]) == []


# make_monarch_chunks — end-year gap fallback
def _monarchs_with_ends(*tuples):
    """Create monarchs with (accession, end, name)."""
    return [Monarch(name=n, accession_year=a, end_year=e, father="", mother="") for a, e, n in tuples]


def test_gap_inserts_end_year():
    # Edward ends 924, Æthelstan starts 927 → 924 should appear in 900s string
    monarchs = _monarchs_with_ends((899, 924, "Edward"), (927, 939, "Æthelstan"))
    chunks = make_monarch_chunks(monarchs, chunk_years=100, chunk_start_year=800)
    nineties = next(c for c in chunks if c.start_year == 900)
    assert '4' == nineties.transition_string[0]   # 924 % 10
    assert '7' == nineties.transition_string[1]   # 927 % 10


def test_no_gap_no_extra_digit():
    # Normal succession: Henry dies 1547, Edward accedes 1547 → no extra digit
    monarchs = _monarchs_with_ends((1509, 1547, "Henry VIII"), (1547, 1553, "Edward VI"))
    chunks = make_monarch_chunks(monarchs, chunk_years=100, chunk_start_year=1500)
    assert chunks[0].transition_string == "97"   # 1509 % 10, 1547 % 10


def test_end_year_lands_in_correct_century():
    # Edward (899-924) is in 800s chunk; his end year 924 should appear in 900s chunk
    monarchs = _monarchs_with_ends((899, 924, "Edward"), (927, 939, "Æthelstan"))
    chunks = make_monarch_chunks(monarchs, chunk_years=100, chunk_start_year=800)
    eighties = next(c for c in chunks if c.start_year == 800)
    nineties = next(c for c in chunks if c.start_year == 900)
    assert eighties.transition_string == "9"    # only Edward's accession 899
    assert "4" in nineties.transition_string    # Edward's end 924 in 900s


def test_gap_cnut_harold(monkeypatch):
    # Cnut ends 1035, Harold Harefoot starts 1037 → 1035 should appear
    monarchs = _monarchs_with_ends((1016, 1035, "Cnut"), (1037, 1040, "Harold"))
    chunks = make_monarch_chunks(monarchs, chunk_years=100, chunk_start_year=1000)
    ts = chunks[0].transition_string
    idx_cnut = ts.index('6')     # 1016 % 10
    assert ts[idx_cnut + 1] == '5'   # 1035 % 10 inserted next
    assert ts[idx_cnut + 2] == '7'   # 1037 % 10


def test_no_end_year_no_gap_inserted():
    # Monarchs with no end_year should behave as before
    monarchs = _monarchs((871, "Alfred"), (899, "Edward"), (924, "Æthelstan"))
    chunks = make_monarch_chunks(monarchs, chunk_years=100, chunk_start_year=800)
    assert chunks[0].transition_string == "19"
    assert chunks[1].transition_string == "4"


def test_default_start_year():
    monarchs = _monarchs((1837, "Victoria"), (1901, "Edward VII"))
    chunks = make_monarch_chunks(monarchs, chunk_years=100)
    assert chunks[0].start_year == 1837


def test_last_digit_extraction():
    monarchs = _monarchs((1900, "Edward VII"), (1910, "George V"))
    chunks = make_monarch_chunks(monarchs, chunk_years=100, chunk_start_year=1900)
    assert chunks[0].transition_string == "00"


# write_monarchs_xlsx
import openpyxl
from wiki_acronyms.xlsx_writer import write_monarchs_xlsx


def _sample_chunks():
    m1 = Monarch("Alfred the Great", 871, 899, "Æthelwulf", "Osburh")
    m2 = Monarch("Edward the Elder", 899, 924, "Alfred the Great", "Ealhswith")
    m3 = Monarch("William I", 1066, 1087, "Robert I", "Herleva")
    c1 = MonarchChunk(800, 899, [m1, m2], "19")
    c2 = MonarchChunk(1000, 1099, [m3], "6")
    return [c1, c2]


def test_monarchs_xlsx_created(tmp_path):
    out = tmp_path / "monarchs.xlsx"
    write_monarchs_xlsx(_sample_chunks(), out, subject="Test Monarchs")
    assert out.exists()


def test_monarchs_sheet_title(tmp_path):
    out = tmp_path / "monarchs.xlsx"
    write_monarchs_xlsx(_sample_chunks(), out, subject="Test Monarchs")
    wb = openpyxl.load_workbook(out)
    assert "Test Monarchs" in wb.sheetnames


def test_monarchs_header(tmp_path):
    out = tmp_path / "monarchs.xlsx"
    write_monarchs_xlsx(_sample_chunks(), out)
    ws = openpyxl.load_workbook(out).active
    assert ws[1][0].value == "Accession"
    assert ws[1][2].value == "Name"
    assert ws[1][6].value == "Century String"


def test_monarchs_first_data_row(tmp_path):
    out = tmp_path / "monarchs.xlsx"
    write_monarchs_xlsx(_sample_chunks(), out)
    rows = list(openpyxl.load_workbook(out).active.iter_rows(values_only=True))
    assert rows[1][0] == 871
    assert rows[1][2] == "Alfred the Great"
    assert rows[1][3] == "Æthelwulf"
    assert rows[1][5] == 1       # last digit of 871
    assert rows[1][6] == "19"    # century string on first row of chunk


def test_monarchs_century_string_blank_on_non_first(tmp_path):
    out = tmp_path / "monarchs.xlsx"
    write_monarchs_xlsx(_sample_chunks(), out)
    rows = list(openpyxl.load_workbook(out).active.iter_rows(values_only=True))
    assert rows[2][6] in (None, "")  # second monarch in chunk has no century string


def test_monarchs_summary_sheet(tmp_path):
    out = tmp_path / "monarchs.xlsx"
    write_monarchs_xlsx(_sample_chunks(), out)
    wb = openpyxl.load_workbook(out)
    assert "Summary" in wb.sheetnames
    rows = list(wb["Summary"].iter_rows(values_only=True))
    assert len(rows) == 3  # header + 2 chunks
    assert rows[1][1] == "19"
    assert rows[2][1] == "6"
