"""Derive Wikidata position Q-IDs from a Wikipedia rulers spreadsheet via reverse P39 lookup."""

from __future__ import annotations

import csv
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import openpyxl

from .wikidata import _SPARQL_URL, _sparql_session

_RULER_KEYWORDS: frozenset[str] = frozenset([
    "king", "queen", "emperor", "empress", "monarch", "pharaoh", "sultan",
    "sultana", "tsar", "tsarina", "czar", "czarina", "ruler", "sovereign",
    "prince", "princess", "duke", "duchess", "regent", "viceroy", "caliph",
    "khan", "emir", "shah", "maharaja", "rajah", "lord protector",
])

_BATCH_SIZE = 50

_POSITIONS_QUERY = """\
SELECT ?position ?positionLabel ?person WHERE {{
  VALUES ?wpTitle {{ {titles} }}
  ?article schema:isPartOf <{wiki_base}> ;
           schema:name ?wpTitle ;
           schema:about ?person .
  ?person wdt:P31 wd:Q5 .
  ?person p:P39/ps:P39 ?position .
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" }}
}}
"""


@dataclass
class DerivedPosition:
    position_qid: str
    label: str
    holder_count: int


def _escape_sparql_string(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _load_file(path: Path) -> list[dict[str, str]]:
    """Read an xlsx or csv file into a list of dicts keyed by column name."""
    if path.suffix.lower() == ".csv":
        with path.open(newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    wb = openpyxl.load_workbook(path, read_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []
    headers = [str(h) if h is not None else "" for h in rows[0]]
    return [dict(zip(headers, (str(v) if v is not None else "" for v in row))) for row in rows[1:]]


def load_ruler_titles(
    path: Path,
    nationality: str | None = None,
    occupation_keywords: frozenset[str] = _RULER_KEYWORDS,
) -> list[str]:
    """Return Wikipedia article titles of likely rulers from an xlsx/csv file."""
    rows = _load_file(path)
    titles: list[str] = []
    for row in rows:
        title = row.get("title", "").strip()
        if not title:
            continue
        if nationality:
            nat = row.get("nationality", "") or ""
            if nationality.lower() not in nat.lower():
                continue
        occ = (row.get("occupation", "") or "").lower()
        if not any(kw in occ for kw in occupation_keywords):
            continue
        titles.append(title)
    return titles


def fetch_positions_for_titles(
    titles: list[str],
    wiki_base: str = "https://en.wikipedia.org/",
    sparql_url: str = _SPARQL_URL,
    batch_size: int = _BATCH_SIZE,
) -> list[DerivedPosition]:
    """Batch-query Wikidata for P39 positions held by people with the given Wikipedia titles."""
    position_labels: dict[str, str] = {}
    person_positions: dict[str, set[str]] = {}  # person_uri → set of position Q-IDs

    for i in range(0, len(titles), batch_size):
        batch = titles[i : i + batch_size]
        lang = wiki_base.split("//")[1].split(".")[0]  # "en", "simple", etc.
        values = " ".join(f'"{_escape_sparql_string(t)}"@{lang}' for t in batch)
        query = _POSITIONS_QUERY.format(titles=values, wiki_base=wiki_base)
        bindings = _sparql_session(sparql_url, query)
        for b in bindings:
            person_uri = b.get("person", {}).get("value", "")
            position_uri = b.get("position", {}).get("value", "")
            if not person_uri or not position_uri:
                continue
            position_qid = position_uri.split("/")[-1]
            label = b.get("positionLabel", {}).get("value", position_qid)
            # Skip if label is still a bare Q-number
            if re.fullmatch(r"Q\d+", label):
                continue
            position_labels[position_qid] = label
            person_positions.setdefault(person_uri, set()).add(position_qid)

    # Count distinct holders per position
    counts: Counter[str] = Counter()
    for positions in person_positions.values():
        counts.update(positions)

    return sorted(
        [DerivedPosition(qid, position_labels[qid], count) for qid, count in counts.items()],
        key=lambda p: p.holder_count,
        reverse=True,
    )
