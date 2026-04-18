import pytest

from wiki_acronyms.poetry_parser import extract_poem

_SONNET = """\
Some preamble text.

Shall I compare thee to a summer's day?
Thou art more lovely and more temperate:
Rough winds do shake the darling buds of May,
And summer's lease hath all too short a date:

Sometime too hot the eye of heaven shines,
And often is his gold complexion dimm'd;
And every fair from fair sometime declines,
By chance, or nature's changing course, untrimm'd;

But thy eternal summer shall not fade,
Nor lose possession of that fair thou ow'st;
Nor shall death brag thou wander'st in his shade,
When in eternal lines to time thou grow'st:

So long as men can breathe, or eyes can see,
So long lives this, and this gives life to thee.

Some trailing text.
"""


def test_basic_extraction():
    lines = extract_poem(
        _SONNET,
        "Shall I compare thee",
        "So long lives this",
    )
    assert lines[0] == "Shall I compare thee to a summer's day?"
    assert lines[-1] == "So long lives this, and this gives life to thee."


def test_line_count():
    lines = extract_poem(_SONNET, "Shall I compare thee", "So long lives this")
    text_lines = [l for l in lines if l is not None]
    assert len(text_lines) == 14


def test_blank_lines_preserved():
    lines = extract_poem(_SONNET, "Shall I compare thee", "So long lives this")
    assert None in lines


def test_blank_lines_count():
    lines = extract_poem(_SONNET, "Shall I compare thee", "So long lives this")
    blank_count = sum(1 for l in lines if l is None)
    assert blank_count == 3  # after each of the three quatrains


def test_no_trailing_blank():
    lines = extract_poem(_SONNET, "Shall I compare thee", "So long lives this")
    assert lines[-1] is not None


def test_no_leading_blank():
    lines = extract_poem(_SONNET, "Shall I compare thee", "So long lives this")
    assert lines[0] is not None


def test_consecutive_blanks_collapse():
    text = "line one\n\n\n\nline two\n"
    lines = extract_poem(text, "line one", "line two")
    assert lines == ["line one", None, "line two"]


def test_start_marker_not_found():
    with pytest.raises(ValueError, match="start_marker not found"):
        extract_poem(_SONNET, "XXXXXXXXXXX", "So long lives this")


def test_end_marker_not_found():
    with pytest.raises(ValueError, match="end_marker not found"):
        extract_poem(_SONNET, "Shall I compare thee", "XXXXXXXXXXX")


def test_end_marker_before_start_raises():
    with pytest.raises(ValueError, match="end_marker not found"):
        extract_poem(_SONNET, "So long lives this", "Shall I compare thee")


def test_no_blank_lines_in_continuous_poem():
    text = "line one\nline two\nline three\n"
    lines = extract_poem(text, "line one", "line three")
    assert lines == ["line one", "line two", "line three"]
