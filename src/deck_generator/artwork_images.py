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
_UA = "memory-quiz-artworks/0.1 (https://github.com/yipingwang12/memory-deck-generator; educational personal project)"


def _hinted(url: str, width: int) -> str:
    """Ask Commons for a pre-scaled thumbnail to avoid downloading the full original."""
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}width={width}"


def _retry_wait(exc: Exception, delay: float) -> float:
    """Seconds to wait before the next attempt; honour a 429 ``Retry-After`` when present.

    Commons rate-limits bot traffic with 429s (``reduce your request rate``); its Retry-After
    tells us how long to wait, so respect it rather than dropping the artwork on backoff."""
    resp = getattr(exc, "response", None)
    if resp is not None and getattr(resp, "status_code", None) == 429:
        ra = resp.headers.get("Retry-After", "")
        if ra.isdigit():
            return max(delay, float(ra))
    return delay


def fetch_raw(url: str, cache_dir: Path, key: str, *, hint_width: int = 1024,
              session: requests.Session | None = None, retries: int = 5,
              throttle: float = 0.0) -> bytes:
    """Download (and cache under ``cache_dir/<key>.orig``) the source image bytes.

    Sleeps ``throttle`` seconds before each network request to stay under Commons' bot rate
    limit, and retries with exponential backoff (honouring a 429 ``Retry-After``) so a
    transient rate-limit doesn't silently drop the artwork. Cache hits skip both. The caller
    decides how to handle a final raise (skip + warn on a dead image, not abort the deck)."""
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached = cache_dir / f"{key}.orig"
    if cached.exists():
        return cached.read_bytes()

    session = session or requests.Session()
    session.headers["User-Agent"] = _UA
    delay = 2.0
    for attempt in range(retries):
        if throttle:
            time.sleep(throttle)
        try:
            resp = session.get(_hinted(url, hint_width), timeout=30)
            resp.raise_for_status()
            cached.write_bytes(resp.content)
            return resp.content
        except requests.RequestException as e:
            if attempt == retries - 1:
                raise
            time.sleep(_retry_wait(e, delay))
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
