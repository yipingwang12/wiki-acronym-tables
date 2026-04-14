"""Group award entries into fixed-width year-range chunks."""

from __future__ import annotations

from dataclasses import dataclass, field

from .acronym import chunk_acronym
from .list_parser import Entry


@dataclass
class Chunk:
    start_year: int
    end_year: int
    entries: list[Entry] = field(default_factory=list)
    acronym: str = ""


def make_chunks(
    entries: list[Entry],
    chunk_years: int = 5,
    chunk_start_year: int | None = None,
) -> list[Chunk]:
    """Group entries into year-range chunks of chunk_years width.

    chunk_start_year: first year of the first chunk (defaults to earliest entry year).
    Empty year-range windows (no laureates) are omitted.
    """
    if not entries:
        return []

    min_year = min(e.year for e in entries)
    max_year = max(e.year for e in entries)
    start = chunk_start_year if chunk_start_year is not None else min_year

    chunks: list[Chunk] = []
    n = 0
    while True:
        chunk_start = start + n * chunk_years
        if chunk_start > max_year:
            break
        chunk_end = chunk_start + chunk_years - 1
        bucket = [e for e in entries if chunk_start <= e.year <= chunk_end]
        if bucket:
            chunks.append(Chunk(
                start_year=chunk_start,
                end_year=chunk_end,
                entries=bucket,
                acronym=chunk_acronym([e.name for e in bucket]),
            ))
        n += 1

    return chunks
