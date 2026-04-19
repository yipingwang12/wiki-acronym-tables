from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from wiki_acronyms.folger import (
    MonologueRef,
    Passage,
    fetch_monologue_refs,
    fetch_passage_lines,
    fetch_passages,
    parse_monologue_list,
    parse_segment_lines,
)

# --- Fixtures matching actual Folger API response format ---

_MONOLOGUE_HTML = """\
King Claudius (39): <a href="http://www.folgerdigitaltexts.org/Ham/segment/sp-0191">Though yet of Hamlet our dear brother's death...</a><br/>
Hamlet (35): <a href="http://www.folgerdigitaltexts.org/Ham/segment/sp-1762">To be or not to be—that is the question:...</a><br/>
The Ghost (50): <a href="http://www.folgerdigitaltexts.org/Ham/segment/sp-0767">Ay, that incestuous, that adulterate beast,...</a><br/>
"""

_SEGMENT_HTML = """\
<span style="font-weight:bold">HAMLET</span> <br/>
To be or not to be—that is the question:<br/>
Whether 'tis nobler in the mind to suffer<br/>
The slings and arrows of outrageous fortune,<br/>
"""

# Segment where text begins on the same chunk as the character name
_SEGMENT_HTML_INLINE = (
    '<span style="font-weight:bold">LADY MACBETH</span>  '
    '<span style="font-style:italic">, reading the letter</span>'
    'They met me in the<br/>'
    'day of success, and I have learned<br/>'
)


# --- parse_monologue_list ---

def test_parse_monologue_list_count():
    refs = parse_monologue_list(_MONOLOGUE_HTML, 'Ham')
    assert len(refs) == 3


def test_parse_monologue_list_character():
    refs = parse_monologue_list(_MONOLOGUE_HTML, 'Ham')
    assert refs[0].character == 'King Claudius'
    assert refs[1].character == 'Hamlet'
    assert refs[2].character == 'The Ghost'


def test_parse_monologue_list_line_count():
    refs = parse_monologue_list(_MONOLOGUE_HTML, 'Ham')
    assert refs[0].line_count == 39
    assert refs[1].line_count == 35
    assert refs[2].line_count == 50


def test_parse_monologue_list_segment_id():
    refs = parse_monologue_list(_MONOLOGUE_HTML, 'Ham')
    assert refs[0].segment_id == 'sp-0191'
    assert refs[1].segment_id == 'sp-1762'


def test_parse_monologue_list_play_name():
    refs = parse_monologue_list(_MONOLOGUE_HTML, 'Ham')
    assert all(r.play_name == 'Hamlet' for r in refs)


def test_parse_monologue_list_excerpt():
    refs = parse_monologue_list(_MONOLOGUE_HTML, 'Ham')
    assert refs[1].excerpt.startswith('To be or not to be')


def test_parse_monologue_list_empty():
    assert parse_monologue_list('', 'Ham') == []


def test_parse_monologue_list_unknown_play_code():
    refs = parse_monologue_list(_MONOLOGUE_HTML, 'XYZ')
    assert refs[0].play_name == 'XYZ'


# --- parse_segment_lines ---

def test_parse_segment_lines_drops_character_name():
    lines = parse_segment_lines(_SEGMENT_HTML)
    assert 'HAMLET' not in lines


def test_parse_segment_lines_content():
    lines = parse_segment_lines(_SEGMENT_HTML)
    assert lines[0] == 'To be or not to be\u2014that is the question:'
    assert lines[1] == "Whether 'tis nobler in the mind to suffer"


def test_parse_segment_lines_count():
    lines = parse_segment_lines(_SEGMENT_HTML)
    assert len(lines) == 3


def test_parse_segment_lines_empty():
    assert parse_segment_lines('') == []


def test_parse_segment_lines_strips_html():
    html = '<span style="font-weight:bold">IAGO</span> <br/><b>O</b>, beware, my lord, of jealousy!<br/>'
    lines = parse_segment_lines(html)
    assert lines == ['O, beware, my lord, of jealousy!']


def test_parse_segment_lines_inline_text_preserved():
    lines = parse_segment_lines(_SEGMENT_HTML_INLINE)
    assert lines[0] == 'They met me in the'
    assert lines[1] == 'day of success, and I have learned'


def test_parse_segment_lines_stage_direction_dropped():
    lines = parse_segment_lines(_SEGMENT_HTML_INLINE)
    assert not any('reading the letter' in l for l in lines)
    assert not any('LADY MACBETH' in l for l in lines)


# --- fetch_monologue_refs (cached) ---

def test_fetch_monologue_refs_uses_cache(tmp_path):
    cache_file = tmp_path / 'Ham_monologues_20.html'
    cache_file.write_text(_MONOLOGUE_HTML, encoding='utf-8')
    refs = fetch_monologue_refs('Ham', min_lines=20, cache_dir=tmp_path)
    assert len(refs) == 3


def test_fetch_monologue_refs_fetches_when_no_cache(tmp_path):
    mock_resp = MagicMock()
    mock_resp.text = _MONOLOGUE_HTML
    with patch('wiki_acronyms.folger.requests.get', return_value=mock_resp) as mock_get:
        with patch('wiki_acronyms.folger.time.sleep'):
            refs = fetch_monologue_refs('Ham', min_lines=20, cache_dir=tmp_path)
    mock_get.assert_called_once()
    assert len(refs) == 3


def test_fetch_monologue_refs_writes_cache(tmp_path):
    mock_resp = MagicMock()
    mock_resp.text = _MONOLOGUE_HTML
    with patch('wiki_acronyms.folger.requests.get', return_value=mock_resp):
        with patch('wiki_acronyms.folger.time.sleep'):
            fetch_monologue_refs('Ham', min_lines=20, cache_dir=tmp_path)
    assert (tmp_path / 'Ham_monologues_20.html').exists()


# --- fetch_passage_lines (cached) ---

def test_fetch_passage_lines_uses_cache(tmp_path):
    seg_dir = tmp_path / 'segments'
    seg_dir.mkdir()
    (seg_dir / 'Ham_sp-1762.html').write_text(_SEGMENT_HTML, encoding='utf-8')
    lines = fetch_passage_lines('Ham', 'sp-1762', cache_dir=tmp_path)
    assert lines[0].startswith('To be or not to be')


def test_fetch_passage_lines_fetches_when_no_cache(tmp_path):
    mock_resp = MagicMock()
    mock_resp.text = _SEGMENT_HTML
    with patch('wiki_acronyms.folger.requests.get', return_value=mock_resp):
        with patch('wiki_acronyms.folger.time.sleep'):
            lines = fetch_passage_lines('Ham', 'sp-1762', cache_dir=tmp_path)
    assert len(lines) == 3


# --- fetch_passages ---

def test_fetch_passages_returns_passages(tmp_path):
    mono_cache = tmp_path / 'Ham_monologues_20.html'
    mono_cache.write_text(_MONOLOGUE_HTML, encoding='utf-8')
    seg_dir = tmp_path / 'segments'
    seg_dir.mkdir()
    for seg_id in ('sp-0191', 'sp-1762', 'sp-0767'):
        (seg_dir / f'Ham_{seg_id}.html').write_text(_SEGMENT_HTML, encoding='utf-8')

    passages = fetch_passages(['Ham'], min_lines=20, cache_dir=tmp_path)
    assert len(passages) == 3
    assert all(isinstance(p, Passage) for p in passages)


def test_fetch_passages_lines_populated(tmp_path):
    mono_cache = tmp_path / 'Ham_monologues_20.html'
    mono_cache.write_text(_MONOLOGUE_HTML, encoding='utf-8')
    seg_dir = tmp_path / 'segments'
    seg_dir.mkdir()
    for seg_id in ('sp-0191', 'sp-1762', 'sp-0767'):
        (seg_dir / f'Ham_{seg_id}.html').write_text(_SEGMENT_HTML, encoding='utf-8')

    passages = fetch_passages(['Ham'], min_lines=20, cache_dir=tmp_path)
    assert all(len(p.lines) > 0 for p in passages)
