"""Fetch and cache Project Gutenberg plain-text files."""

from __future__ import annotations

from pathlib import Path

import requests

_URL = "https://www.gutenberg.org/cache/epub/{id}/pg{id}.txt"
_CACHE_DIR = Path(__file__).parent.parent.parent / "cache" / "gutenberg"


def fetch_text(gutenberg_id: int, cache_dir: Path = _CACHE_DIR) -> str:
    """Return plain text of a Gutenberg book, downloading and caching on first call."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached = cache_dir / f"{gutenberg_id}.txt"
    if cached.exists():
        return cached.read_text(encoding="utf-8")
    url = _URL.format(id=gutenberg_id)
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    text = resp.text
    cached.write_text(text, encoding="utf-8")
    return text
