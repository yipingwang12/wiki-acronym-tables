"""Monologue Archive scraper with file-based caching."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from html import unescape
from pathlib import Path

import requests

_CACHE_DIR = Path(__file__).parent.parent.parent / 'cache' / 'monologue_archive'
_BASE_URL = 'http://www.monologuearchive.com'
_DELAY = 0.5

_ENTRY_RE = re.compile(
    r'<a\s+href="([^"]+)"\s+class="list-group-item active">'
    r'.*?<h4[^>]*>(.*?)</h4>'
    r'.*?<p[^>]*>(.*?)</p>',
    re.DOTALL,
)
_MONOLOGUE_RE = re.compile(r'<p\s+class="monologue">(.*?)</p>', re.DOTALL)
_TAG_RE = re.compile(r'<[^>]+>')


@dataclass
class MonologueRef:
    playwright: str
    play_name: str
    passage_type: str   # e.g. "dramatic monologue for a man"
    passage_id: str     # e.g. "marlowe_001"
    url: str            # absolute URL


@dataclass
class MonologuePassage:
    playwright: str
    play_name: str
    character: str
    passage_type: str
    passage_id: str
    lines: list[str]

    @property
    def excerpt(self) -> str:
        return self.lines[0] if self.lines else ''

    @property
    def line_count(self) -> int:
        return len(self.lines)


_HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; research-bot/1.0)'}


def _get(url: str) -> str:
    resp = requests.get(url, headers=_HEADERS, timeout=30)
    resp.raise_for_status()
    time.sleep(_DELAY)
    return resp.text


def _author_url(slug: str) -> str:
    letter = slug[0]
    return f'{_BASE_URL}/{letter}/{slug}.html'


def parse_author_page(html: str, playwright: str) -> list[MonologueRef]:
    refs = []
    for m in _ENTRY_RE.finditer(html):
        href, play_name, passage_type = m.group(1), m.group(2), m.group(3)
        # Skip external links — only process relative monologue archive paths
        if not href.startswith('../'):
            continue
        # href is like "../m/marlowe_001.html" — extract passage_id and build absolute URL
        filename = href.rsplit('/', 1)[-1]          # "marlowe_001.html"
        passage_id = filename.removesuffix('.html')  # "marlowe_001"
        letter = passage_id[0]
        url = f'{_BASE_URL}/{letter}/{filename}'
        refs.append(MonologueRef(
            playwright=playwright,
            play_name=unescape(_TAG_RE.sub('', play_name).strip()),
            passage_type=unescape(_TAG_RE.sub('', passage_type).strip()),
            passage_id=passage_id,
            url=url,
        ))
    return refs


def parse_passage_page(html: str, ref: MonologueRef) -> MonologuePassage:
    m = _MONOLOGUE_RE.search(html)
    raw = m.group(1) if m else ''
    segments = [
        unescape(_TAG_RE.sub('', seg)).strip()
        for seg in re.split(r'<br\s*/?>', raw)
    ]
    segments = [s for s in segments if s]

    character = ''
    lines: list[str] = []
    if segments:
        first = segments[0]
        if ':' in first:
            char_part, line_part = first.split(':', 1)
            character = char_part.strip()
            if line_part.strip():
                lines.append(line_part.strip())
        else:
            lines.append(first)
        lines.extend(segments[1:])

    return MonologuePassage(
        playwright=ref.playwright,
        play_name=ref.play_name,
        character=character,
        passage_type=ref.passage_type,
        passage_id=ref.passage_id,
        lines=lines,
    )


def fetch_author_refs(
    slug: str,
    playwright: str,
    cache_dir: Path = _CACHE_DIR,
) -> list[MonologueRef]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f'{slug}.html'
    if not cache_file.exists():
        cache_file.write_text(_get(_author_url(slug)), encoding='utf-8')
    return parse_author_page(cache_file.read_text(encoding='utf-8'), playwright)


def fetch_passage(ref: MonologueRef, cache_dir: Path = _CACHE_DIR) -> MonologuePassage:
    passages_dir = cache_dir / 'passages'
    passages_dir.mkdir(parents=True, exist_ok=True)
    cache_file = passages_dir / f'{ref.passage_id}.html'
    if not cache_file.exists():
        cache_file.write_text(_get(ref.url), encoding='utf-8')
    return parse_passage_page(cache_file.read_text(encoding='utf-8'), ref)


def fetch_all_passages(
    authors: list[dict],   # [{'slug': ..., 'name': ...}]
    cache_dir: Path = _CACHE_DIR,
) -> list[MonologuePassage]:
    passages = []
    for author in authors:
        refs = fetch_author_refs(author['slug'], author['name'], cache_dir)
        for ref in refs:
            passages.append(fetch_passage(ref, cache_dir))
    return passages
