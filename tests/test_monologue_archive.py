from __future__ import annotations

from wiki_acronyms.monologue_archive import (
    MonologueRef,
    parse_author_page,
    parse_passage_page,
)

_SAMPLE_AUTHOR_HTML = """
<div class="list-group">
  <a href="../m/marlowe_001.html" class="list-group-item active">
    <h4 class="list-group-item-heading">Tamburlaine the Great</h4>
    <p class="list-group-item-text">dramatic monologue for a man</p>
  </a>
  <a href="../m/marlowe_002.html" class="list-group-item active">
    <h4 class="list-group-item-heading">Doctor Faustus</h4>
    <p class="list-group-item-text">dramatic monologue for a man</p>
  </a>
</div>
"""

_SAMPLE_PASSAGE_HTML = """
<p class="monologue">TAMBURLAINE: In thee, thou valiant man of Persia,<br>
I see the folly of thy emperor.<br>
Art thou but captain of a thousand horse?</p>
"""

_SAMPLE_PASSAGE_HTML_SELF_CLOSING = """
<p class="monologue">FAUSTUS: Was this the face that launch'd a thousand ships,<br/>
And burnt the topless towers of Ilium?</p>
"""

_SAMPLE_PASSAGE_NO_CHARACTER = """
<p class="monologue">To be, or not to be, that is the question.</p>
"""

_SAMPLE_AUTHOR_HTML_EMPTY = "<div></div>"


def test_parse_author_page_count():
    refs = parse_author_page(_SAMPLE_AUTHOR_HTML, 'Christopher Marlowe')
    assert len(refs) == 2


def test_parse_author_page_play_names():
    refs = parse_author_page(_SAMPLE_AUTHOR_HTML, 'Christopher Marlowe')
    assert refs[0].play_name == 'Tamburlaine the Great'
    assert refs[1].play_name == 'Doctor Faustus'


def test_parse_author_page_passage_ids():
    refs = parse_author_page(_SAMPLE_AUTHOR_HTML, 'Christopher Marlowe')
    assert refs[0].passage_id == 'marlowe_001'
    assert refs[1].passage_id == 'marlowe_002'


def test_parse_author_page_passage_type():
    refs = parse_author_page(_SAMPLE_AUTHOR_HTML, 'Christopher Marlowe')
    assert refs[0].passage_type == 'dramatic monologue for a man'


def test_parse_author_page_absolute_url():
    refs = parse_author_page(_SAMPLE_AUTHOR_HTML, 'Christopher Marlowe')
    assert refs[0].url == 'http://www.monologuearchive.com/m/marlowe_001.html'


def test_parse_author_page_playwright():
    refs = parse_author_page(_SAMPLE_AUTHOR_HTML, 'Christopher Marlowe')
    assert all(r.playwright == 'Christopher Marlowe' for r in refs)


def test_parse_author_page_empty():
    assert parse_author_page(_SAMPLE_AUTHOR_HTML_EMPTY, 'Marlowe') == []


_SAMPLE_AUTHOR_HTML_WITH_EXTERNAL = """
<a href="http://www.theatrehistory.com/british/marlowe001.html" class="list-group-item active">
    <h4 class="list-group-item-heading">External Site</h4>
    <p class="list-group-item-text">dramatic monologue for a man</p>
</a>
<a href="../m/marlowe_001.html" class="list-group-item active">
    <h4 class="list-group-item-heading">Tamburlaine the Great</h4>
    <p class="list-group-item-text">dramatic monologue for a man</p>
</a>
"""


def test_parse_author_page_skips_external_links():
    refs = parse_author_page(_SAMPLE_AUTHOR_HTML_WITH_EXTERNAL, 'Christopher Marlowe')
    assert len(refs) == 1
    assert refs[0].play_name == 'Tamburlaine the Great'


def _make_ref(**kwargs) -> MonologueRef:
    defaults = dict(playwright='Christopher Marlowe', play_name='Tamburlaine',
                    passage_type='dramatic monologue for a man',
                    passage_id='marlowe_001',
                    url='http://www.monologuearchive.com/m/marlowe_001.html')
    return MonologueRef(**{**defaults, **kwargs})


def test_parse_passage_page_character():
    p = parse_passage_page(_SAMPLE_PASSAGE_HTML, _make_ref())
    assert p.character == 'TAMBURLAINE'


def test_parse_passage_page_lines():
    p = parse_passage_page(_SAMPLE_PASSAGE_HTML, _make_ref())
    assert p.lines == [
        'In thee, thou valiant man of Persia,',
        'I see the folly of thy emperor.',
        'Art thou but captain of a thousand horse?',
    ]


def test_parse_passage_page_self_closing_br():
    p = parse_passage_page(_SAMPLE_PASSAGE_HTML_SELF_CLOSING, _make_ref())
    assert len(p.lines) == 2
    assert p.lines[0] == 'Was this the face that launch\'d a thousand ships,'


def test_parse_passage_page_no_character():
    p = parse_passage_page(_SAMPLE_PASSAGE_NO_CHARACTER, _make_ref())
    assert p.character == ''
    assert p.lines == ['To be, or not to be, that is the question.']


def test_parse_passage_page_line_count():
    p = parse_passage_page(_SAMPLE_PASSAGE_HTML, _make_ref())
    assert p.line_count == 3


def test_parse_passage_page_excerpt():
    p = parse_passage_page(_SAMPLE_PASSAGE_HTML, _make_ref())
    assert p.excerpt == 'In thee, thou valiant man of Persia,'


def test_parse_passage_page_playwright_preserved():
    p = parse_passage_page(_SAMPLE_PASSAGE_HTML, _make_ref(playwright='Christopher Marlowe'))
    assert p.playwright == 'Christopher Marlowe'
