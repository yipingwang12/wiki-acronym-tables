"""Parse Wikipedia wikitext tables into (year, name) entries."""

from __future__ import annotations

import re
from typing import NamedTuple


class Entry(NamedTuple):
    year: int
    name: str


def parse_entries(wikitext: str, year_col: int, name_col: int) -> list[Entry]:
    """Parse (year, name) entries from the first wikitable in wikitext."""
    table = _extract_first_table(wikitext)
    if not table:
        return []
    entries = []
    for row_block in _split_rows(table):
        cells = _parse_cells(row_block)
        if len(cells) <= max(year_col, name_col):
            continue
        year = _parse_year(cells[year_col])
        if year is None:
            continue
        for name in _parse_names(cells[name_col]):
            entries.append(Entry(year=year, name=name))
    return entries


def _extract_first_table(wikitext: str) -> str | None:
    """Return wikitext of first wikitable, handling nested tables."""
    start = wikitext.find("{|")
    if start == -1:
        return None
    depth, i = 0, start
    while i < len(wikitext):
        if wikitext[i : i + 2] == "{|":
            depth += 1
            i += 2
        elif wikitext[i : i + 2] == "|}":
            depth -= 1
            i += 2
            if depth == 0:
                return wikitext[start:i]
        else:
            i += 1
    return None


def _split_rows(table: str) -> list[str]:
    """Split table into data row blocks, skipping the table header."""
    blocks = re.split(r"\n\s*\|-", table)
    return [
        b
        for b in blocks[1:]
        if "||" in b or re.search(r"^\s*\|[^!|]", b, re.MULTILINE)
    ]


def _parse_cells(row_block: str) -> list[str]:
    """Extract cell contents from a row block."""
    cells = []
    for line in row_block.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("!") or stripped.startswith("|}") or stripped.startswith("|-"):
            continue
        if stripped.startswith("|"):
            rest = stripped[1:]
            if "||" in rest:
                for part in _split_inline_cells(rest):
                    cells.append(_strip_cell_attrs(part))
            else:
                cells.append(_strip_cell_attrs(rest))
    return cells


def _split_inline_cells(text: str) -> list[str]:
    """Split inline cells by ||, respecting [[...]] and {{...}} depth."""
    parts: list[str] = []
    square = curly = 0
    buf: list[str] = []
    i = 0
    while i < len(text):
        two = text[i : i + 2]
        if two == "[[":
            square += 1
            buf.append("[[")
            i += 2
        elif two == "]]":
            square -= 1
            buf.append("]]")
            i += 2
        elif two == "{{":
            curly += 1
            buf.append("{{")
            i += 2
        elif two == "}}":
            curly -= 1
            buf.append("}}")
            i += 2
        elif two == "||" and square == 0 and curly == 0:
            parts.append("".join(buf).strip())
            buf = []
            i += 2
        else:
            buf.append(text[i])
            i += 1
    if buf:
        parts.append("".join(buf).strip())
    return parts


def _strip_cell_attrs(cell: str) -> str:
    """Remove style/class attribute prefix (e.g. 'style="..." | content' → 'content')."""
    cell = cell.strip()
    # Match only when the prefix contains no [ or { (i.e. no wikilinks/templates)
    m = re.match(r"^([^[{\n|]*)\|(.+)$", cell, re.DOTALL)
    if m:
        return m.group(2).strip()
    return cell


def _parse_year(cell: str) -> int | None:
    """Extract a 4-digit year integer from a cell."""
    text = re.sub(r"\{\{[^}]*\}\}", "", cell)
    text = re.sub(r"\[\[[^\]]*\]\]", "", text)
    m = re.search(r"\b(\d{4})\b", text)
    return int(m.group(1)) if m else None


def _parse_names(cell: str) -> list[str]:
    """Extract one or more person names from a name cell, splitting on <br>."""
    parts = re.split(r"<br\s*/?>", cell, flags=re.IGNORECASE)
    names: list[str] = []
    for part in parts:
        m = re.search(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", part)
        if m:
            names.append((m.group(2) or m.group(1)).strip())
        else:
            # Fallback: strip all markup and take plain text
            plain = re.sub(r"\{\{[^}]*\}\}", "", part)
            plain = re.sub(r"\[\[[^\]]*\]\]", "", plain)
            plain = re.sub(r"''+", "", plain).strip()
            if plain:
                names.append(plain)
    return [n for n in names if n]
