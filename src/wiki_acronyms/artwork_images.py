"""Download artwork images from Wikimedia Commons and downsize them to WebP.

Quiz display needs a small image, not the multi-MB Commons original — so we request a
scaled thumbnail (``Special:FilePath?width=``) to save bandwidth, then re-encode to WebP
at the target size (~480px ≈ 25 KB). Raw downloads are cached under ``cache/artworks/`` so
re-exports don't re-fetch.
"""

from __future__ import annotations

import io
import time
from pathlib import Path

import requests
from PIL import Image

# Wikimedia's image CDN (upload.wikimedia.org) enforces its User-Agent policy and 403s
# placeholder/example.com UAs — it needs a real identifying URL. (The SPARQL endpoint is laxer.)
_UA = "memory-quiz-artworks/0.1 (https://github.com/yipingwang12/wiki-acronym-tables; educational personal project)"


def _hinted(url: str, width: int) -> str:
    """Ask Commons for a pre-scaled thumbnail to avoid downloading the full original."""
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}width={width}"


def fetch_raw(url: str, cache_dir: Path, key: str, *, hint_width: int = 1024,
              session: requests.Session | None = None, retries: int = 3) -> bytes:
    """Download (and cache under ``cache_dir/<key>.orig``) the source image bytes.

    Exponential backoff on transient failures; the caller decides how to handle a raise
    (skip + warn on a dead image rather than aborting a whole deck)."""
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached = cache_dir / f"{key}.orig"
    if cached.exists():
        return cached.read_bytes()

    session = session or requests.Session()
    session.headers["User-Agent"] = _UA
    delay = 1.0
    for attempt in range(retries):
        try:
            resp = session.get(_hinted(url, hint_width), timeout=30)
            resp.raise_for_status()
            cached.write_bytes(resp.content)
            return resp.content
        except requests.RequestException:
            if attempt == retries - 1:
                raise
            time.sleep(delay)
            delay *= 2
    raise RuntimeError("unreachable")


def to_webp(raw: bytes, px: int, quality: int = 80) -> bytes:
    """Re-encode image bytes to WebP, longest side capped at ``px`` (aspect preserved)."""
    img = Image.open(io.BytesIO(raw))
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")
    img.thumbnail((px, px))  # in place, preserves aspect, only downscales
    out = io.BytesIO()
    img.save(out, format="WEBP", quality=quality, method=6)
    return out.getvalue()
