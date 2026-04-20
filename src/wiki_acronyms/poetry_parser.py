"""Extract poem lines from Gutenberg plain text, preserving blank lines as None."""

from __future__ import annotations


def _norm(s: str) -> str:
    """Normalize Unicode quotes/apostrophes to ASCII for fuzzy marker matching."""
    return s.replace('\u2018', "'").replace('\u2019', "'").replace('\u201c', '"').replace('\u201d', '"')


def extract_poem(text: str, start_marker: str, end_marker: str) -> list[str | None]:
    """Return poem lines between start_marker and end_marker (inclusive).

    None entries represent blank lines in the source. Consecutive blank lines
    collapse to one. Leading and trailing blank lines are stripped.
    """
    lines = text.splitlines()
    norm_start = _norm(start_marker)
    norm_end = _norm(end_marker)
    start_idx = end_idx = None
    for i, line in enumerate(lines):
        norm_line = _norm(line)
        if start_idx is None and norm_start in norm_line:
            start_idx = i
        elif start_idx is not None and norm_end in norm_line:
            end_idx = i
            break
    if start_idx is None:
        raise ValueError(f"start_marker not found: {start_marker!r}")
    if end_idx is None:
        raise ValueError(f"end_marker not found after start_marker: {end_marker!r}")

    result: list[str | None] = []
    for line in lines[start_idx : end_idx + 1]:
        stripped = line.strip()
        if stripped:
            result.append(stripped)
        elif result and result[-1] is not None:
            result.append(None)

    while result and result[-1] is None:
        result.pop()
    return result
