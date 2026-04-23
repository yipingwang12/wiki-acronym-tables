"""Fetch monarch reign data from Wikidata and chunk by century."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .wikidata import _SPARQL_URL, _sparql_session


@dataclass
class Monarch:
    name: str
    accession_year: int
    end_year: int | None
    father: str
    mother: str
    wp_title: str | None = None  # English Wikipedia article title (from sitelinks)


@dataclass
class MonarchChunk:
    start_year: int
    end_year: int
    monarchs: list[Monarch] = field(default_factory=list)
    transition_string: str = ""


_QUERY = """\
SELECT ?person ?personLabel ?start ?end ?fatherLabel ?motherLabel ?wpTitle WHERE {{
  VALUES ?pos {{ {positions} }}
  ?person p:P39 ?stmt .
  ?stmt ps:P39 ?pos .
  ?stmt pq:P580 ?start .
  OPTIONAL {{ ?stmt pq:P582 ?end }}
  OPTIONAL {{ ?person wdt:P22 ?father }}
  OPTIONAL {{ ?person wdt:P25 ?mother }}
  OPTIONAL {{
    ?wpArticle schema:about ?person ;
               schema:isPartOf <https://en.wikipedia.org/> ;
               schema:name ?wpTitle .
  }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" }}
}}
ORDER BY ?start
"""


def _parse_year(value: str) -> int | None:
    """Extract year from an xsd:dateTime string such as '1066-10-14T00:00:00Z'."""
    m = re.match(r"(-?)(\d{4})", value)
    if not m:
        return None
    year = int(m.group(2))
    return -year if m.group(1) else year


def fetch_monarchs(
    position_ids: list[str],
    sparql_url: str = _SPARQL_URL,
) -> list[Monarch]:
    """Fetch monarchs for the given Wikidata position Q-numbers, ordered by accession year."""
    positions = " ".join(f"wd:{qid}" for qid in position_ids)
    bindings = _sparql_session(sparql_url, _QUERY.format(positions=positions))

    # Deduplicate by person Q-number, keeping the earliest accession year.
    # A monarch can appear multiple times when their title changes (e.g. George III
    # as King of Great Britain 1760 and King of the UK 1801). We want first accession.
    seen: dict[str, Monarch] = {}
    for b in bindings:
        person_uri = b.get("person", {}).get("value", "")
        person_id = person_uri.split("/")[-1] if person_uri else ""
        name = b.get("personLabel", {}).get("value", "")
        start_val = b.get("start", {}).get("value", "")
        if not person_id or not name or not start_val:
            continue
        if name.startswith("Q") and name[1:].isdigit():
            continue
        year = _parse_year(start_val)
        if year is None:
            continue
        end_val = b.get("end", {}).get("value", "")
        end_year = _parse_year(end_val) if end_val else None
        father = b.get("fatherLabel", {}).get("value", "")
        mother = b.get("motherLabel", {}).get("value", "")
        wp_title = b.get("wpTitle", {}).get("value") or None
        if person_id not in seen:
            seen[person_id] = Monarch(
                name=name,
                accession_year=year,
                end_year=end_year,
                father=father,
                mother=mother,
                wp_title=wp_title,
            )
        else:
            m = seen[person_id]
            # Keep earliest accession year and latest end year across all position statements.
            # A monarch deposed and restored (e.g. Stephen 1135–1141, 1141–1154) appears twice;
            # we want accession=1135 and end_year=1154 so the gap-fill logic doesn't insert the
            # intermediate deposition year as a spurious transition event.
            if year < m.accession_year:
                m.accession_year = year
            if end_year is not None and (m.end_year is None or end_year > m.end_year):
                m.end_year = end_year
            if not m.father and father:
                m.father = father
            if not m.mother and mother:
                m.mother = mother
            if not m.wp_title and wp_title:
                m.wp_title = wp_title

    return sorted(seen.values(), key=lambda m: m.accession_year)


def make_monarch_chunks(
    monarchs: list[Monarch],
    chunk_years: int = 100,
    chunk_start_year: int | None = None,
) -> list[MonarchChunk]:
    """Group monarchs into fixed-width year-range chunks.

    The transition_string for each chunk is the last digit of every transition
    year in order. Transition years are accession years plus, where a gap exists
    between a monarch's recorded end year and the next monarch's accession year,
    the end year itself (fallback for Wikidata accession dates that lag the true
    transition, e.g. Æthelstan 927 vs Edward the Elder's death in 924).
    """
    if not monarchs:
        return []

    # Build sorted list of all transition years: accession years (duplicates preserved
    # for same-year accessions) + end-year fallbacks for monarchs whose death year
    # is not captured by any known accession year (e.g. Wikidata records Æthelstan
    # as 927 but Edward the Elder died in 924).
    # Only insert end-year fallback when the gap to the next known accession year
    # is small (≤ _MAX_GAP_FILL_YEARS), distinguishing Wikidata date lag from genuine
    # interregnums (e.g. Stephen 1141–1154, Henry VI 1471–1483, Commonwealth 1649–1660).
    _MAX_GAP_FILL_YEARS = 5
    accession_year_set = {m.accession_year for m in monarchs}
    sorted_accessions = sorted(accession_year_set)
    events: list[int] = sorted(m.accession_year for m in monarchs)
    for m in monarchs:
        if m.end_year is None or m.end_year in accession_year_set:
            continue
        next_acc = next((y for y in sorted_accessions if y > m.end_year), None)
        if next_acc is not None and (next_acc - m.end_year) <= _MAX_GAP_FILL_YEARS:
            events.append(m.end_year)
    events.sort()

    min_year = min(m.accession_year for m in monarchs)
    max_year = max(events)
    start = chunk_start_year if chunk_start_year is not None else min_year

    chunks: list[MonarchChunk] = []
    n = 0
    while True:
        chunk_start = start + n * chunk_years
        if chunk_start > max_year:
            break
        chunk_end = chunk_start + chunk_years - 1
        bucket_events = [e for e in events if chunk_start <= e <= chunk_end]
        bucket_monarchs = [m for m in monarchs if chunk_start <= m.accession_year <= chunk_end]
        if bucket_events:
            transition_string = "".join(str(e % 10) for e in bucket_events)
            chunks.append(MonarchChunk(
                start_year=chunk_start,
                end_year=chunk_end,
                monarchs=bucket_monarchs,
                transition_string=transition_string,
            ))
        n += 1

    return chunks
