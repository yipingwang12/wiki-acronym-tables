"""Convert names to first-letter acronyms."""

from __future__ import annotations


def name_initials(name: str) -> str:
    """First letter (uppercase) of each word: 'Sully Prudhomme' → 'SP'."""
    return "".join(w[0].upper() for w in name.split() if w)


def chunk_acronym(names: list[str]) -> str:
    """Concatenate initials for all names in chunk order."""
    return "".join(name_initials(n) for n in names)
