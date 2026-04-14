from wiki_acronyms.list_parser import Entry, parse_entries

SIMPLE = """\
{| class="wikitable"
|-
! Year !! Laureate !! Country
|-
| 1901
| [[Sully Prudhomme]]
| {{flag|France}}
|-
| 1902
| [[Theodor Mommsen]]
| {{flag|Germany}}
|}"""

STYLED_YEAR = """\
{| class="wikitable"
|-
! Year !! Laureate
|-
| style="text-align:center;" | 1901
| [[Sully Prudhomme]]
|-
| style="text-align:center;" | 1902
| [[Theodor Mommsen]]
|}"""

MULTI_LAUREATE = """\
{| class="wikitable"
|-
! Year !! Laureate
|-
| 1904
| {{nowrap|[[Frédéric Mistral]]}}<br />{{nowrap|[[José Echegaray]]}}
|}"""

INLINE_CELLS = """\
{| class="wikitable"
|-
! Year !! Laureate
|-
| 1901 || [[Sully Prudhomme]]
|-
| 1902 || [[Theodor Mommsen]]
|}"""

PIPED_LINK = """\
{| class="wikitable"
|-
! Year !! Laureate
|-
| 1913
| [[Rabindranath Tagore|Rabindranath Tagore]]
|}"""


def test_simple_table():
    entries = parse_entries(SIMPLE, year_col=0, name_col=1)
    assert entries == [Entry(1901, "Sully Prudhomme"), Entry(1902, "Theodor Mommsen")]


def test_styled_year_stripped():
    entries = parse_entries(STYLED_YEAR, year_col=0, name_col=1)
    assert [e.year for e in entries] == [1901, 1902]


def test_multi_laureate_same_year():
    entries = parse_entries(MULTI_LAUREATE, year_col=0, name_col=1)
    assert entries == [Entry(1904, "Frédéric Mistral"), Entry(1904, "José Echegaray")]


def test_inline_cells():
    entries = parse_entries(INLINE_CELLS, year_col=0, name_col=1)
    assert [e.name for e in entries] == ["Sully Prudhomme", "Theodor Mommsen"]


def test_piped_wikilink_uses_display_text():
    entries = parse_entries(PIPED_LINK, year_col=0, name_col=1)
    assert entries[0].name == "Rabindranath Tagore"


def test_empty_wikitext():
    assert parse_entries("", year_col=0, name_col=1) == []


def test_no_table():
    assert parse_entries("No table here.", year_col=0, name_col=1) == []


def test_header_rows_excluded():
    entries = parse_entries(SIMPLE, year_col=0, name_col=1)
    # All parsed years should be integers, not strings like "Year"
    assert all(isinstance(e.year, int) for e in entries)
