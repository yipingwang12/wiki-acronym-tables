from unittest.mock import MagicMock, patch

import pytest

from wiki_acronyms.gutenberg import fetch_text

_FAKE_TEXT = "Project Gutenberg text\n\nShall I compare thee..."


def _mock_response(text: str):
    resp = MagicMock()
    resp.text = text
    resp.raise_for_status.return_value = None
    return resp


def test_fetches_and_returns_text(tmp_path):
    with patch("wiki_acronyms.gutenberg.requests.get", return_value=_mock_response(_FAKE_TEXT)) as mock_get:
        result = fetch_text(1041, cache_dir=tmp_path)
    assert result == _FAKE_TEXT
    mock_get.assert_called_once()


def test_caches_to_disk(tmp_path):
    with patch("wiki_acronyms.gutenberg.requests.get", return_value=_mock_response(_FAKE_TEXT)):
        fetch_text(1041, cache_dir=tmp_path)
    assert (tmp_path / "1041.txt").read_text(encoding="utf-8") == _FAKE_TEXT


def test_cache_hit_skips_network(tmp_path):
    (tmp_path / "1041.txt").write_text("cached content", encoding="utf-8")
    with patch("wiki_acronyms.gutenberg.requests.get") as mock_get:
        result = fetch_text(1041, cache_dir=tmp_path)
    mock_get.assert_not_called()
    assert result == "cached content"


def test_different_ids_cached_separately(tmp_path):
    with patch("wiki_acronyms.gutenberg.requests.get", return_value=_mock_response("book A")):
        fetch_text(100, cache_dir=tmp_path)
    with patch("wiki_acronyms.gutenberg.requests.get", return_value=_mock_response("book B")):
        fetch_text(200, cache_dir=tmp_path)
    assert (tmp_path / "100.txt").read_text(encoding="utf-8") == "book A"
    assert (tmp_path / "200.txt").read_text(encoding="utf-8") == "book B"


def test_http_error_propagates(tmp_path):
    resp = MagicMock()
    resp.raise_for_status.side_effect = Exception("404 Not Found")
    with patch("wiki_acronyms.gutenberg.requests.get", return_value=resp):
        with pytest.raises(Exception, match="404"):
            fetch_text(9999, cache_dir=tmp_path)
