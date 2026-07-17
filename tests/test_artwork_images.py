"""Tests for artwork image download + WebP downsizing."""

from __future__ import annotations

import io
from unittest.mock import MagicMock, Mock

from PIL import Image

from wiki_acronyms.artwork_images import fetch_raw, to_webp


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
