"""Tests for cli.py manual_entries merging logic."""

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from wiki_acronyms.cli import main
from wiki_acronyms.list_parser import Entry

_SPARQL_ENTRIES = [Entry(year=2000, name="Alice Foo"), Entry(year=2005, name="Bob Bar")]

_SPARQL_RESPONSE = {
    "results": {
        "bindings": [
            {"personLabel": {"value": "Alice Foo"}, "year": {"value": "2000"}},
            {"personLabel": {"value": "Bob Bar"}, "year": {"value": "2005"}},
        ]
    }
}

_COUNT_RESPONSE = {"results": {"bindings": [{"count": {"value": "3"}}]}}


def _mock_session(response):
    from unittest.mock import MagicMock
    session = MagicMock()
    session.get.return_value.json.return_value = response
    session.get.return_value.raise_for_status = MagicMock()
    return session


def _write_config(tmp_path, extra=None):
    cfg = {"award_name": "Test Award", "wikidata_item": "Q99999", "chunk_years": 5, "chunk_start_year": 2000}
    if extra:
        cfg.update(extra)
    p = tmp_path / "test.yaml"
    p.write_text(yaml.dump(cfg))
    return p


def test_manual_entries_added(tmp_path, capsys):
    cfg_path = _write_config(tmp_path, {"manual_entries": [{"year": 2003, "name": "Carol Baz"}]})
    with patch("wiki_acronyms.wikidata.requests.Session") as mock_cls:
        mock_cls.return_value = _mock_session(_SPARQL_RESPONSE)
        mock_cls.return_value.get.return_value.json.side_effect = [
            _SPARQL_RESPONSE, _COUNT_RESPONSE
        ]
        main(["--config", str(cfg_path), "--output", str(tmp_path / "out.xlsx")])
    out = capsys.readouterr().out
    assert "Added 1 manual" in out


def test_manual_entries_deduped(tmp_path, capsys):
    cfg_path = _write_config(tmp_path, {"manual_entries": [{"year": 2000, "name": "Alice Foo"}]})
    with patch("wiki_acronyms.wikidata.requests.Session") as mock_cls:
        mock_cls.return_value = _mock_session(_SPARQL_RESPONSE)
        mock_cls.return_value.get.return_value.json.side_effect = [
            _SPARQL_RESPONSE, _COUNT_RESPONSE
        ]
        main(["--config", str(cfg_path), "--output", str(tmp_path / "out.xlsx")])
    out = capsys.readouterr().out
    assert "Added 0 manual" not in out


def test_no_manual_entries_no_message(tmp_path, capsys):
    cfg_path = _write_config(tmp_path)
    with patch("wiki_acronyms.wikidata.requests.Session") as mock_cls:
        mock_cls.return_value.get.return_value.json.side_effect = [
            _SPARQL_RESPONSE, _COUNT_RESPONSE
        ]
        main(["--config", str(cfg_path), "--output", str(tmp_path / "out.xlsx")])
    out = capsys.readouterr().out
    assert "Added" not in out


def test_exclude_entries_suppresses_gap_warning(tmp_path, capsys):
    # count=3, fetched=2, exclude=1 → adjusted total=2, no warning
    cfg_path = _write_config(tmp_path, {"exclude_entries": ["Carol Baz"]})
    with patch("wiki_acronyms.wikidata.requests.Session") as mock_cls:
        mock_cls.return_value.get.return_value.json.side_effect = [
            _SPARQL_RESPONSE, _COUNT_RESPONSE
        ]
        main(["--config", str(cfg_path), "--output", str(tmp_path / "out.xlsx")])
    err = capsys.readouterr().err
    assert "Warning" not in err


def test_exclude_entries_partial_suppression(tmp_path, capsys):
    # count=4, fetched=2, exclude=1 → adjusted total=3, warning still fires
    count4 = {"results": {"bindings": [{"count": {"value": "4"}}]}}
    cfg_path = _write_config(tmp_path, {"exclude_entries": ["Carol Baz"]})
    with patch("wiki_acronyms.wikidata.requests.Session") as mock_cls:
        mock_cls.return_value.get.return_value.json.side_effect = [
            _SPARQL_RESPONSE, count4
        ]
        main(["--config", str(cfg_path), "--output", str(tmp_path / "out.xlsx")])
    err = capsys.readouterr().err
    assert "Warning" in err
