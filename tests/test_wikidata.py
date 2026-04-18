from unittest.mock import MagicMock, Mock, patch

from wiki_acronyms.list_parser import Entry
from wiki_acronyms.wikidata import fetch_entries

_SAMPLE = {
    "results": {
        "bindings": [
            {"personLabel": {"value": "Sully Prudhomme"}, "year": {"value": "1901"}},
            {"personLabel": {"value": "Theodor Mommsen"}, "year": {"value": "1902"}},
        ]
    }
}


def _mock_session(response_json: dict):
    mock_resp = Mock()
    mock_resp.json.return_value = response_json
    mock_resp.raise_for_status.return_value = None
    mock_session = MagicMock()
    mock_session.get.return_value = mock_resp
    return mock_session


def test_basic():
    with patch("wiki_acronyms.wikidata.requests.Session", return_value=_mock_session(_SAMPLE)):
        entries = fetch_entries("Q37922")
    assert entries == [Entry(1901, "Sully Prudhomme"), Entry(1902, "Theodor Mommsen")]


def test_skips_unlabelled_q_ids():
    response = {
        "results": {
            "bindings": [
                {"personLabel": {"value": "Q12345"}, "year": {"value": "1901"}},
                {"personLabel": {"value": "Theodor Mommsen"}, "year": {"value": "1902"}},
            ]
        }
    }
    with patch("wiki_acronyms.wikidata.requests.Session", return_value=_mock_session(response)):
        entries = fetch_entries("Q37922")
    assert entries == [Entry(1902, "Theodor Mommsen")]


def test_empty_bindings():
    response = {"results": {"bindings": []}}
    with patch("wiki_acronyms.wikidata.requests.Session", return_value=_mock_session(response)):
        entries = fetch_entries("Q37922")
    assert entries == []


def test_missing_fields_skipped():
    response = {
        "results": {
            "bindings": [
                {"personLabel": {"value": "Sully Prudhomme"}},  # no year
                {"year": {"value": "1902"}},  # no name
                {"personLabel": {"value": "Bjørnstjerne Bjørnson"}, "year": {"value": "1903"}},
            ]
        }
    }
    with patch("wiki_acronyms.wikidata.requests.Session", return_value=_mock_session(response)):
        entries = fetch_entries("Q37922")
    assert entries == [Entry(1903, "Bjørnstjerne Bjørnson")]


def test_query_contains_item_id():
    with patch("wiki_acronyms.wikidata.requests.Session", return_value=_mock_session(_SAMPLE)) as mock_cls:
        fetch_entries("Q99999")
    call_kwargs = mock_cls.return_value.get.call_args
    query_param = call_kwargs[1]["params"]["query"]
    assert "wd:Q99999" in query_param


# count_laureates
from wiki_acronyms.wikidata import count_laureates


def test_count_laureates():
    response = {"results": {"bindings": [{"count": {"value": "42"}}]}}
    with patch("wiki_acronyms.wikidata.requests.Session", return_value=_mock_session(response)):
        assert count_laureates("Q37922") == 42


def test_count_laureates_zero():
    response = {"results": {"bindings": [{"count": {"value": "0"}}]}}
    with patch("wiki_acronyms.wikidata.requests.Session", return_value=_mock_session(response)):
        assert count_laureates("Q37922") == 0


def test_count_query_contains_item_id():
    response = {"results": {"bindings": [{"count": {"value": "1"}}]}}
    with patch("wiki_acronyms.wikidata.requests.Session", return_value=_mock_session(response)) as mock_cls:
        count_laureates("Q99999")
    query_param = mock_cls.return_value.get.call_args[1]["params"]["query"]
    assert "wd:Q99999" in query_param


def test_humans_only_filter_in_fetch():
    with patch("wiki_acronyms.wikidata.requests.Session", return_value=_mock_session(_SAMPLE)) as mock_cls:
        fetch_entries("Q37922", humans_only=True)
    query_param = mock_cls.return_value.get.call_args[1]["params"]["query"]
    assert "wdt:P31 wd:Q5" in query_param


def test_no_humans_only_filter_by_default():
    with patch("wiki_acronyms.wikidata.requests.Session", return_value=_mock_session(_SAMPLE)) as mock_cls:
        fetch_entries("Q37922")
    query_param = mock_cls.return_value.get.call_args[1]["params"]["query"]
    assert "wdt:P31 wd:Q5" not in query_param


def test_humans_only_filter_in_count():
    response = {"results": {"bindings": [{"count": {"value": "5"}}]}}
    with patch("wiki_acronyms.wikidata.requests.Session", return_value=_mock_session(response)) as mock_cls:
        count_laureates("Q37922", humans_only=True)
    query_param = mock_cls.return_value.get.call_args[1]["params"]["query"]
    assert "wdt:P31 wd:Q5" in query_param
