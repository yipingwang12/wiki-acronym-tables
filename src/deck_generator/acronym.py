"""Convert names and poetry lines to first-letter acronyms."""

from __future__ import annotations

import re

_PARTICLES = frozenset({
    "von", "van", "de", "du", "da", "di",
    "del", "della", "des", "den", "der",
    "le", "la", "les", "of", "the",
})


def name_initials(name: str, first_only: bool = False) -> str:
    """First letter of each meaningful word/hyphen-component, skipping particles.

    'Paul von Heyse'   → 'PH'
    'Jean-Paul Sartre' → 'JPS'

    first_only=True: only the first letter of the first name token.
    'Toni Morrison'    → 'T'
    'Jean-Paul Sartre' → 'J'
    """
    if first_only:
        first_token = (name.split() or [""])[0].split("-")[0]
        return first_token[0].upper() if first_token else ""

    # Split on spaces, then expand hyphenated tokens into their components
    tokens: list[str] = []
    for word in name.split():
        tokens.extend(word.split("-"))

    significant = [t for t in tokens if t.lower() not in _PARTICLES]
    if not significant:
        significant = tokens  # fallback: all particles, use them anyway

    return "".join(t[0].upper() for t in significant if t)


def chunk_acronym(names: list[str]) -> str:
    """Concatenate initials for all names in chunk order."""
    return "".join(name_initials(n) for n in names)


def line_initials(line: str) -> str:
    """First letter of each word in a poetry line, including particles.

    'Shall I compare thee to a summer\'s day?' → 'SICTTASD'
    Leading punctuation is stripped before taking the first letter.
    """
    result = []
    for word in line.split():
        clean = re.sub(r"^[^a-zA-Z]+", "", word)
        if clean:
            result.append(clean[0].upper())
    return "".join(result)
