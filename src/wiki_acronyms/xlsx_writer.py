"""Write award laureate chunks with acronyms to xlsx."""

from __future__ import annotations

from pathlib import Path

import openpyxl
from openpyxl.styles import Font, PatternFill

from .acronym import name_initials
from .chunker import Chunk

_CHUNK_FILL = PatternFill("solid", fgColor="E8F0FE")
_HEADER_FONT = Font(bold=True)


def write_xlsx(chunks: list[Chunk], output_path: Path, award_name: str = "") -> None:
    """Write laureate chunks to xlsx with acronym columns."""
    wb = openpyxl.Workbook()
    _write_laureates_sheet(wb.active, chunks)
    _write_summary_sheet(wb.create_sheet("Summary"), chunks)
    wb.save(output_path)


def _write_laureates_sheet(ws, chunks: list[Chunk]) -> None:
    ws.title = "Laureates"
    ws.append(["Year", "Name", "Initials", "Chunk Acronym"])
    for cell in ws[1]:
        cell.font = _HEADER_FONT

    for chunk in chunks:
        for idx, entry in enumerate(chunk.entries):
            initials = name_initials(entry.name)
            acronym_cell = chunk.acronym if idx == 0 else ""
            ws.append([entry.year, entry.name, initials, acronym_cell])
            if idx == 0:
                for cell in ws[ws.max_row]:
                    cell.fill = _CHUNK_FILL

    ws.column_dimensions["A"].width = 6
    ws.column_dimensions["B"].width = 30
    ws.column_dimensions["C"].width = 10
    ws.column_dimensions["D"].width = 30


def _write_summary_sheet(ws, chunks: list[Chunk]) -> None:
    ws.title = "Summary"
    ws.append(["Years", "Acronym"])
    for cell in ws[1]:
        cell.font = _HEADER_FONT
    for chunk in chunks:
        ws.append([f"{chunk.start_year}\u2013{chunk.end_year}", chunk.acronym])
    ws.column_dimensions["A"].width = 15
    ws.column_dimensions["B"].width = 40
