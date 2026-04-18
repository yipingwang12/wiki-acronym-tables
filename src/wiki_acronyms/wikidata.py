"""Wikidata SPARQL client — fetches award laureates as (year, name) entries."""

from __future__ import annotations

import requests

from .list_parser import Entry

_SPARQL_URL = "https://query.wikidata.org/sparql"

_HUMAN_FILTER = "  ?person wdt:P31 wd:Q5 .\n"

_COUNT_QUERY = """\
SELECT (COUNT(DISTINCT ?person) AS ?count) WHERE {{
{human_filter}  ?person p:P166 ?stmt .
  ?stmt ps:P166 wd:{item_id} .
}}
"""

_QUERY = """\
SELECT ?personLabel ?year WHERE {{
{human_filter}  ?person p:P166 ?stmt .
  ?stmt ps:P166 wd:{item_id} .
  ?stmt pq:P585 ?date .
  BIND(YEAR(?date) AS ?year)
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" }}
}}
ORDER BY ?year ?personLabel
"""


def _sparql_session(sparql_url: str, query: str):
    session = requests.Session()
    session.headers["User-Agent"] = (
        "WikiAcronymTables/0.1 (educational; contact: wiki-acronym-tables@example.com)"
    )
    resp = session.get(sparql_url, params={"query": query, "format": "json"}, timeout=30)
    resp.raise_for_status()
    return resp.json()["results"]["bindings"]


def count_laureates(item_id: str, sparql_url: str = _SPARQL_URL, humans_only: bool = False) -> int:
    """Count all recipients of an award in Wikidata, regardless of date qualifier."""
    human_filter = _HUMAN_FILTER if humans_only else ""
    bindings = _sparql_session(sparql_url, _COUNT_QUERY.format(item_id=item_id, human_filter=human_filter))
    return int(bindings[0]["count"]["value"]) if bindings else 0


def fetch_entries(item_id: str, sparql_url: str = _SPARQL_URL, humans_only: bool = False) -> list[Entry]:
    """Fetch award laureates from Wikidata for the given item Q-number."""
    human_filter = _HUMAN_FILTER if humans_only else ""
    bindings = _sparql_session(sparql_url, _QUERY.format(item_id=item_id, human_filter=human_filter))
    entries = []
    for b in bindings:
        name = b.get("personLabel", {}).get("value", "")
        year_str = b.get("year", {}).get("value", "")
        if not name or not year_str:
            continue
        # Wikidata falls back to Q-number when no English label exists — skip
        if name.startswith("Q") and name[1:].isdigit():
            continue
        entries.append(Entry(year=int(year_str), name=name))
    return entries
