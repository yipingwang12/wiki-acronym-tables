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
    accession_precision: int | None = None  # Wikidata timePrecision of P580; see _PRECISION


# Wikidata timePrecision codes for a time value. Anything below YEAR means the source does not
# actually claim that year — e.g. Assyria's Tudiya is stored as -2450 at DECADE precision,
# meaning "the 2450s BC", and France's Mallobaudes as 378 meaning "the 370s".
# RECORDED FOR DOCUMENTATION ONLY: digit extraction deliberately ignores precision, so decks
# are byte-identical to before this field existed. Surfaced via `report_imprecise_dates`.
_PRECISION = {11: 'day', 10: 'month', 9: 'year', 8: 'decade', 7: 'century', 6: 'millennium'}
YEAR_PRECISION = 9


@dataclass(frozen=True)
class Correction:
    """A manual, sourced override of Wikidata's transition years.

    Wikidata models one P39 statement per ruler, which cannot express a reign interrupted and
    resumed (Murad II 1421–44, deposed, restored 1446–51), and it carries occasional plain date
    errors. A Correction records not just the patch but WHY and against WHAT — so a later reader
    can re-check it, and so `stale_corrections` can report when upstream has caught up."""

    year: int
    action: str   # 'add' | 'drop'
    reason: str   # why Wikidata's own value is wrong or incomplete
    source: str   # what was checked (e.g. the Wikipedia article title)
    checked: str = ''  # ISO date the source was last verified


_ACTIONS = ('add', 'drop')


def parse_corrections(raw: list[dict] | None) -> list[Correction]:
    """Parse and validate a config's ``corrections:`` block.

    Raises ValueError rather than skipping a malformed entry: a correction that silently fails
    to apply is indistinguishable in the output from one that was never written."""
    if not raw:
        return []
    out = []
    for i, entry in enumerate(raw):
        missing = [k for k in ('year', 'action', 'reason', 'source') if not entry.get(k)]
        if missing:
            raise ValueError(f"corrections[{i}]: missing required key(s): {', '.join(missing)}")
        if entry['action'] not in _ACTIONS:
            raise ValueError(f"corrections[{i}]: action must be one of {_ACTIONS}, got {entry['action']!r}")
        out.append(Correction(
            year=int(entry['year']), action=entry['action'], reason=entry['reason'],
            source=entry['source'], checked=str(entry.get('checked', '')),
        ))
    return out


def correction_years(corrections: list[Correction]) -> tuple[list[int], list[int]]:
    """Split corrections into (add_years, drop_years) for ``make_monarch_chunks``."""
    return ([c.year for c in corrections if c.action == 'add'],
            [c.year for c in corrections if c.action == 'drop'])


@dataclass
class MonarchChunk:
    start_year: int
    end_year: int
    monarchs: list[Monarch] = field(default_factory=list)
    transition_string: str = ""


_QUERY = """\
SELECT ?person ?personLabel ?start ?startPrec ?end ?fatherLabel ?motherLabel ?wpTitle WHERE {{
  VALUES ?pos {{ {positions} }}
  ?person p:P39 ?stmt .
  ?stmt ps:P39 ?pos .
  ?stmt pq:P580 ?start .{house_clause}
  OPTIONAL {{ ?stmt pqv:P580 ?startNode . ?startNode wikibase:timePrecision ?startPrec }}
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
    house_ids: list[str] | None = None,
) -> list[Monarch]:
    """Fetch monarchs for the given Wikidata position Q-numbers, ordered by accession year.

    ``house_ids`` (optional P53 "noble family" Q-numbers) restrict results to holders in
    those houses — needed when a position is shared across dynasties (e.g. "Emperor of
    China" Q268218 spans every Chinese dynasty; the House of Zhu / Aisin-Gioro filters
    isolate the Ming / Qing rulers from rebels and neighbouring dynasties)."""
    positions = " ".join(f"wd:{qid}" for qid in position_ids)
    if house_ids:
        houses = " ".join(f"wd:{qid}" for qid in house_ids)
        house_clause = f"\n  ?person wdt:P53 ?house .\n  VALUES ?house {{ {houses} }}"
    else:
        house_clause = ""
    bindings = _sparql_session(sparql_url, _QUERY.format(positions=positions, house_clause=house_clause))

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
        prec_val = b.get("startPrec", {}).get("value")
        precision = int(prec_val) if prec_val else None
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
                accession_precision=precision,
            )
        else:
            m = seen[person_id]
            # Keep earliest accession year and latest end year across all position statements.
            # A monarch deposed and restored (e.g. Stephen 1135–1141, 1141–1154) appears twice;
            # we want accession=1135 and end_year=1154 so the gap-fill logic doesn't insert the
            # intermediate deposition year as a spurious transition event.
            if year < m.accession_year:
                m.accession_year = year
                m.accession_precision = precision   # precision must track the year that wins
            if end_year is not None and (m.end_year is None or end_year > m.end_year):
                m.end_year = end_year
            if not m.father and father:
                m.father = father
            if not m.mother and mother:
                m.mother = mother
            if not m.wp_title and wp_title:
                m.wp_title = wp_title

    return sorted(seen.values(), key=lambda m: m.accession_year)


def filter_by_accession(
    monarchs: list[Monarch],
    min_year: int | None = None,
    max_year: int | None = None,
) -> list[Monarch]:
    """Keep monarchs whose accession year is within [min_year, max_year] (either bound
    optional). Used to cap a dynasty at a historical end date — e.g. the Abbasid
    caliphate at its 1258 Baghdad fall, excluding the later Cairo figureheads whose
    accessions run to the 1400s under the same Wikidata position."""
    return [
        m for m in monarchs
        if (min_year is None or m.accession_year >= min_year)
        and (max_year is None or m.accession_year <= max_year)
    ]


def _raw_transition_events(monarchs: list[Monarch]) -> list[int]:
    """Transition years implied by Wikidata alone, before any manual correction.

    Every accession year (duplicates kept — two rulers can accede in one year), plus any end
    year that is not itself some ruler's accession year, i.e. the throne did not pass directly
    to a successor that year."""
    accession_year_set = {m.accession_year for m in monarchs}
    events: list[int] = sorted(m.accession_year for m in monarchs)
    events += [m.end_year for m in monarchs
               if m.end_year is not None and m.end_year not in accession_year_set]
    return events


def stale_corrections(monarchs: list[Monarch], corrections: list[Correction]) -> list[str]:
    """Corrections that no longer change the output — usually because Wikidata fixed itself.

    An 'add' whose year Wikidata now supplies, or a 'drop' whose year Wikidata no longer emits,
    is dead weight: the config keeps asserting something about upstream that stopped being true.
    Neither is an error (add is idempotent, drop is a no-op), which is exactly why they need
    reporting — otherwise they rot invisibly."""
    events = set(_raw_transition_events(monarchs))
    stale = []
    for c in corrections:
        if c.action == 'add' and c.year in events:
            stale.append(f"add {c.year}: Wikidata now supplies this year on its own")
        elif c.action == 'drop' and c.year not in events:
            stale.append(f"drop {c.year}: Wikidata no longer emits this year")
    return stale


def report_imprecise_dates(monarchs: list[Monarch]) -> list[str]:
    """Rulers whose accession date is recorded below year precision.

    DOCUMENTATION ONLY — nothing here feeds digit extraction. Wikidata stores such dates as a
    concrete year (Sigfred = 0770 at decade precision), so the pipeline reads them as exact and
    memorises a digit the source never claimed. This surfaces them without changing any deck."""
    out = []
    for m in monarchs:
        p = m.accession_precision
        if p is not None and p < YEAR_PRECISION:
            out.append(f"{m.name}: {m.accession_year} is {_PRECISION.get(p, p)} precision, not an exact year")
    return out


def make_monarch_chunks(
    monarchs: list[Monarch],
    chunk_years: int = 100,
    chunk_start_year: int | None = None,
    add_transition_years: list[int] | None = None,
    drop_transition_years: list[int] | None = None,
) -> list[MonarchChunk]:
    """Group monarchs into fixed-width year-range chunks.

    The transition_string for each chunk is the last digit of every transition
    year in order. Transition years are accession years plus, for any reign whose
    recorded end year is not itself an accession year, that end year — i.e. the throne
    did not pass directly to a successor that year. This captures a dynasty's final
    year (the last ruler, with no successor) and the start of an interregnum (a gap
    before the next accession), as well as Wikidata coronation-lag (a successor's
    recorded accession a few years after the predecessor's death, e.g. Æthelstan 927
    vs Edward the Elder's death in 924). Continuous same-year successions add nothing.

    ``add_transition_years`` / ``drop_transition_years`` are manual corrections for
    Wikidata's one-statement-per-ruler model, mirroring the award pipeline's
    ``manual_entries`` / ``exclude_entries``. Add covers transitions Wikidata omits —
    a brief deposition and restoration recorded as one unbroken reign (e.g. al-Muqtadir
    deposed for al-Qahir in 929). Drop covers dating artifacts (e.g. Wikidata ends
    al-Musta'in in 865, but he reigned until his 866 deposition). Drop removes every
    occurrence of a year and is applied before add.

    Add is IDEMPOTENT: a year already present is not appended again. Corrections are bets that
    Wikidata stays wrong, and Wikidata improves; an unconditional append would silently double
    a digit the day upstream fixed the underlying statement. Use `stale_corrections` to find
    corrections that have become no-ops.
    """
    if not monarchs:
        return []

    events = _raw_transition_events(monarchs)
    if drop_transition_years:
        dropped = set(drop_transition_years)
        events = [e for e in events if e not in dropped]
    for year in add_transition_years or []:
        if year not in events:      # idempotent — see docstring
            events.append(year)
    events.sort()
    if not events:
        return []

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
