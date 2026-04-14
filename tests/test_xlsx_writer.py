import openpyxl

from wiki_acronyms.chunker import make_chunks
from wiki_acronyms.list_parser import Entry
from wiki_acronyms.xlsx_writer import write_xlsx


def _chunks():
    entries = [Entry(1901, "Sully Prudhomme"), Entry(1902, "Theodor Mommsen")]
    return make_chunks(entries, chunk_years=5, chunk_start_year=1901)


def test_file_created(tmp_path):
    out = tmp_path / "test.xlsx"
    write_xlsx(_chunks(), out)
    assert out.exists()


def test_laureates_sheet_header(tmp_path):
    out = tmp_path / "test.xlsx"
    write_xlsx(_chunks(), out)
    wb = openpyxl.load_workbook(out)
    ws = wb["Laureates"]
    header = [cell.value for cell in ws[1]]
    assert header == ["Year", "Name", "Initials", "Chunk Acronym"]


def test_laureates_sheet_first_row(tmp_path):
    out = tmp_path / "test.xlsx"
    write_xlsx(_chunks(), out)
    wb = openpyxl.load_workbook(out)
    rows = list(wb["Laureates"].iter_rows(values_only=True))
    # Header + 2 data rows
    assert len(rows) == 3
    assert rows[1] == (1901, "Sully Prudhomme", "SP", "SPTM")


def test_chunk_acronym_blank_on_non_first_row(tmp_path):
    out = tmp_path / "test.xlsx"
    write_xlsx(_chunks(), out)
    wb = openpyxl.load_workbook(out)
    rows = list(wb["Laureates"].iter_rows(values_only=True))
    assert rows[2][3] in (None, "")


def test_summary_sheet_exists(tmp_path):
    out = tmp_path / "test.xlsx"
    write_xlsx(_chunks(), out)
    wb = openpyxl.load_workbook(out)
    assert "Summary" in wb.sheetnames


def test_summary_sheet_rows(tmp_path):
    entries = [Entry(1901, "Sully Prudhomme"), Entry(1906, "Bjørnstjerne Bjørnson")]
    chunks = make_chunks(entries, chunk_years=5, chunk_start_year=1901)
    out = tmp_path / "test.xlsx"
    write_xlsx(chunks, out)
    ws = openpyxl.load_workbook(out)["Summary"]
    rows = list(ws.iter_rows(values_only=True))
    assert len(rows) == 3  # header + 2 chunks
    assert rows[1][1] == "SP"
    assert rows[2][1] == "BB"
