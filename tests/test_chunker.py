from wiki_acronyms.chunker import make_chunks
from wiki_acronyms.list_parser import Entry


def _e(*pairs):
    return [Entry(year=y, name=n) for y, n in pairs]


def test_single_chunk():
    chunks = make_chunks(_e((1901, "A B"), (1902, "C D")), chunk_years=5, chunk_start_year=1901)
    assert len(chunks) == 1
    assert chunks[0].start_year == 1901
    assert chunks[0].end_year == 1905
    assert chunks[0].acronym == "ABCD"


def test_two_chunks():
    chunks = make_chunks(_e((1901, "A B"), (1906, "C D")), chunk_years=5, chunk_start_year=1901)
    assert len(chunks) == 2
    assert chunks[0].acronym == "AB"
    assert chunks[1].acronym == "CD"
    assert chunks[1].start_year == 1906


def test_skipped_year_within_chunk():
    # 1903 missing — chunk still covers 1901–1905
    entries = _e((1901, "A"), (1902, "B"), (1904, "C"), (1905, "D"))
    chunks = make_chunks(entries, chunk_years=5, chunk_start_year=1901)
    assert len(chunks) == 1
    assert len(chunks[0].entries) == 4


def test_two_laureates_same_year():
    chunks = make_chunks(_e((1904, "A B"), (1904, "C D")), chunk_years=5, chunk_start_year=1901)
    assert len(chunks) == 1
    assert chunks[0].acronym == "ABCD"


def test_empty_window_skipped():
    # No entries in 1906–1910; result has 2 chunks not 3
    chunks = make_chunks(_e((1901, "A"), (1911, "B")), chunk_years=5, chunk_start_year=1901)
    assert len(chunks) == 2
    assert chunks[0].start_year == 1901
    assert chunks[1].start_year == 1911


def test_no_entries():
    assert make_chunks([]) == []


def test_default_start_year():
    chunks = make_chunks(_e((1966, "A B"), (1967, "C D")), chunk_years=5)
    assert chunks[0].start_year == 1966
