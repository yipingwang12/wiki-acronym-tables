"""Folger Shakespeare API client with file-based caching."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from html import unescape
from pathlib import Path

import requests

_CACHE_DIR = Path(__file__).parent.parent.parent / 'cache' / 'folger'
_BASE_URL = 'https://www.folgerdigitaltexts.org'
_DELAY = 0.5  # seconds between uncached requests

PLAY_NAMES: dict[str, str] = {
    'AWW': "All's Well That Ends Well",
    'Ant': 'Antony and Cleopatra',
    'AYL': 'As You Like It',
    'Err': 'The Comedy of Errors',
    'Cor': 'Coriolanus',
    'Cym': 'Cymbeline',
    'Ham': 'Hamlet',
    '1H4': 'Henry IV, Part 1',
    '2H4': 'Henry IV, Part 2',
    'H5': 'Henry V',
    '1H6': 'Henry VI, Part 1',
    '2H6': 'Henry VI, Part 2',
    '3H6': 'Henry VI, Part 3',
    'H8': 'Henry VIII',
    'JC': 'Julius Caesar',
    'Jn': 'King John',
    'Lr': 'King Lear',
    'LLL': "Love's Labour's Lost",
    'Mac': 'Macbeth',
    'MM': 'Measure for Measure',
    'MV': 'The Merchant of Venice',
    'Wiv': 'The Merry Wives of Windsor',
    'MND': "A Midsummer Night's Dream",
    'Ado': 'Much Ado About Nothing',
    'Oth': 'Othello',
    'Per': 'Pericles',
    'R2': 'Richard II',
    'R3': 'Richard III',
    'Rom': 'Romeo and Juliet',
    'Shr': 'The Taming of the Shrew',
    'Tmp': 'The Tempest',
    'Tim': 'Timon of Athens',
    'Tit': 'Titus Andronicus',
    'Tro': 'Troilus and Cressida',
    'TN': 'Twelfth Night',
    'TGV': 'The Two Gentlemen of Verona',
    'TNK': 'The Two Noble Kinsmen',
    'WT': "The Winter's Tale",
}

_MONOLOGUE_RE = re.compile(
    r'^(.+?)\s*\((\d+)\):\s*<a href="[^"]*/segment/(sp-\d+)">(.+?)</a>'
)


@dataclass
class MonologueRef:
    play_code: str
    play_name: str
    character: str
    line_count: int
    segment_id: str
    excerpt: str


@dataclass
class Passage:
    play_code: str
    play_name: str
    character: str
    line_count: int
    segment_id: str
    excerpt: str
    lines: list[str]


def _get(url: str) -> str:
    resp = requests.get(url, allow_redirects=True, timeout=30)
    resp.raise_for_status()
    time.sleep(_DELAY)
    return resp.text


def parse_monologue_list(html: str, play_code: str) -> list[MonologueRef]:
    """Parse the raw HTML from the /monologue endpoint."""
    play_name = PLAY_NAMES.get(play_code, play_code)
    refs = []
    for line in html.splitlines():
        m = _MONOLOGUE_RE.match(line.strip())
        if m:
            character, line_count, segment_id, excerpt = m.groups()
            refs.append(MonologueRef(
                play_code=play_code,
                play_name=play_name,
                character=character.strip(),
                line_count=int(line_count),
                segment_id=segment_id,
                excerpt=unescape(excerpt.rstrip('.')).strip(),
            ))
    return refs


def parse_segment_lines(html: str) -> list[str]:
    """Parse the raw HTML from the /segment endpoint into a list of text lines.

    The first chunk contains the character name (bold span) and optional stage
    direction (italic span), possibly followed immediately by the first line of
    text. Strip the markup elements and keep any trailing text as line 1.
    """
    parts = html.split('<br/>')
    lines = []
    for i, part in enumerate(parts):
        if i == 0:
            # Remove bold character name and italic stage directions only
            text = re.sub(r'<span[^>]*font-weight:bold[^>]*>[^<]*</span>', '', part)
            text = re.sub(r'<span[^>]*font-style:italic[^>]*>[^<]*</span>', '', text)
            text = re.sub(r'<[^>]+>', '', text).strip()
        else:
            text = re.sub(r'<[^>]+>', '', part).strip()
        text = unescape(text)
        if text:
            lines.append(text)
    return lines


def fetch_monologue_refs(
    play_code: str,
    min_lines: int = 20,
    cache_dir: Path = _CACHE_DIR,
) -> list[MonologueRef]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f'{play_code}_monologues_{min_lines}.html'
    if cache_file.exists():
        html = cache_file.read_text(encoding='utf-8')
    else:
        html = _get(f'{_BASE_URL}/{play_code}/monologue/{min_lines}')
        cache_file.write_text(html, encoding='utf-8')
    return parse_monologue_list(html, play_code)


def fetch_passage_lines(
    play_code: str,
    segment_id: str,
    cache_dir: Path = _CACHE_DIR,
) -> list[str]:
    seg_dir = cache_dir / 'segments'
    seg_dir.mkdir(parents=True, exist_ok=True)
    cache_file = seg_dir / f'{play_code}_{segment_id}.html'
    if cache_file.exists():
        html = cache_file.read_text(encoding='utf-8')
    else:
        html = _get(f'{_BASE_URL}/{play_code}/segment/{segment_id}')
        cache_file.write_text(html, encoding='utf-8')
    return parse_segment_lines(html)


def fetch_passages(
    play_codes: list[str],
    min_lines: int = 20,
    cache_dir: Path = _CACHE_DIR,
) -> list[Passage]:
    passages = []
    for play_code in play_codes:
        refs = fetch_monologue_refs(play_code, min_lines, cache_dir)
        for ref in refs:
            lines = fetch_passage_lines(play_code, ref.segment_id, cache_dir)
            passages.append(Passage(
                play_code=ref.play_code,
                play_name=ref.play_name,
                character=ref.character,
                line_count=ref.line_count,
                segment_id=ref.segment_id,
                excerpt=ref.excerpt,
                lines=lines,
            ))
    return passages
