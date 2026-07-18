"""Tests for artwork image download + WebP downsizing."""

from __future__ import annotations

import io
from unittest.mock import MagicMock, Mock

import requests
from PIL import Image

from wiki_acronyms.artwork_images import _retry_wait, fetch_raw, to_webp


def _png_bytes(w, h):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (10, 20, 30)).save(buf, format="PNG")
    return buf.getvalue()


class TestToWebp:
    def test_output_is_webp(self):
        out = to_webp(_png_bytes(800, 600), px=480)
        assert Image.open(io.BytesIO(out)).format == "WEBP"

    def test_downscales_longest_side(self):
        img = Image.open(io.BytesIO(to_webp(_png_bytes(1000, 500), px=480)))
        assert max(img.size) == 480

    def test_preserves_aspect(self):
        img = Image.open(io.BytesIO(to_webp(_png_bytes(1000, 500), px=480)))
        assert img.size == (480, 240)

    def test_does_not_upscale_small_images(self):
        img = Image.open(io.BytesIO(to_webp(_png_bytes(100, 80), px=480)))
        assert img.size == (100, 80)

    def test_converts_non_rgb(self):
        buf = io.BytesIO()
        Image.new("P", (200, 200)).save(buf, format="PNG")
        assert Image.open(io.BytesIO(to_webp(buf.getvalue(), px=480))).format == "WEBP"


class TestFetchRaw:
    def _session(self, content):
        resp = Mock()
        resp.content = content
        resp.raise_for_status.return_value = None
        session = MagicMock()
        session.get.return_value = resp
        session.headers = {}
        return session

    def test_downloads_and_caches(self, tmp_path):
        session = self._session(b"IMG")
        got = fetch_raw("http://x/a.jpg", tmp_path, "Q1", session=session)
        assert got == b"IMG"
        assert (tmp_path / "Q1.orig").read_bytes() == b"IMG"

    def test_second_call_uses_cache(self, tmp_path):
        session = self._session(b"IMG")
        fetch_raw("http://x/a.jpg", tmp_path, "Q1", session=session)
        fetch_raw("http://x/a.jpg", tmp_path, "Q1", session=session)
        session.get.assert_called_once()  # not re-downloaded

    def test_width_hint_appended(self, tmp_path):
        session = self._session(b"IMG")
        fetch_raw("http://x/a.jpg", tmp_path, "Q1", hint_width=800, session=session)
        assert "width=800" in session.get.call_args[0][0]

    def _http_error(self, status, retry_after=None):
        resp = Mock()
        resp.status_code = status
        resp.headers = {"Retry-After": retry_after} if retry_after else {}
        return requests.HTTPError(response=resp)

    def test_retries_on_429_then_succeeds(self, tmp_path, monkeypatch):
        monkeypatch.setattr("wiki_acronyms.artwork_images.time.sleep", lambda *_: None)
        ok = Mock(content=b"IMG", raise_for_status=Mock(return_value=None))
        boom = Mock(raise_for_status=Mock(side_effect=self._http_error(429)))
        session = MagicMock(headers={})
        session.get.side_effect = [boom, boom, ok]  # two 429s, then success
        got = fetch_raw("http://x/a.jpg", tmp_path, "Q1", session=session)
        assert got == b"IMG" and session.get.call_count == 3

    def test_raises_after_exhausting_retries(self, tmp_path, monkeypatch):
        monkeypatch.setattr("wiki_acronyms.artwork_images.time.sleep", lambda *_: None)
        boom = Mock(raise_for_status=Mock(side_effect=self._http_error(429)))
        session = MagicMock(headers={})
        session.get.return_value = boom
        try:
            fetch_raw("http://x/a.jpg", tmp_path, "Q1", retries=3, session=session)
            assert False, "expected HTTPError"
        except requests.HTTPError:
            assert session.get.call_count == 3  # caller then skips + warns

    def test_retry_after_header_honoured(self):
        assert _retry_wait(self._http_error(429, retry_after="30"), delay=2.0) == 30.0
        assert _retry_wait(self._http_error(429), delay=2.0) == 2.0        # no header → backoff
        assert _retry_wait(self._http_error(503), delay=2.0) == 2.0        # non-429 → backoff
