"""Fetch and store a registry of sovereign states and their head-of-state positions via Wikidata P1906."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .wikidata import _SPARQL_URL, _sparql_session

_P1906_QUERY = """\
SELECT ?country ?countryLabel ?position ?positionLabel WHERE {
  ?country wdt:P31/wdt:P279* wd:Q3624078 .
  ?country wdt:P1906 ?position .
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en" }
}
ORDER BY ?countryLabel
"""


@dataclass
class CountryEntry:
    name: str
    country_qid: str
    position_qids: list[str] = field(default_factory=list)
    position_labels: list[str] = field(default_factory=list)
    wikipedia_list: str | None = None


def fetch_country_registry(sparql_url: str = _SPARQL_URL) -> list[CountryEntry]:
    """Query Wikidata P1906 for all sovereign states and their head-of-state positions."""
    bindings = _sparql_session(sparql_url, _P1906_QUERY)
    entries: dict[str, CountryEntry] = {}
    for b in bindings:
        country_uri = b.get("country", {}).get("value", "")
        country_qid = country_uri.split("/")[-1] if country_uri else ""
        country_name = b.get("countryLabel", {}).get("value", "")
        position_uri = b.get("position", {}).get("value", "")
        position_qid = position_uri.split("/")[-1] if position_uri else ""
        position_label = b.get("positionLabel", {}).get("value", "")
        if not country_qid or not country_name or not position_qid:
            continue
        if country_name.startswith("Q") and country_name[1:].isdigit():
            continue
        if country_qid not in entries:
            entries[country_qid] = CountryEntry(name=country_name, country_qid=country_qid)
        entry = entries[country_qid]
        if position_qid not in entry.position_qids:
            entry.position_qids.append(position_qid)
            entry.position_labels.append(position_label)
    return sorted(entries.values(), key=lambda e: e.name)


def save_registry(entries: list[CountryEntry], path: Path) -> None:
    """Write country registry to YAML."""
    data = {
        "countries": [
            {
                "name": e.name,
                "country_qid": e.country_qid,
                "position_qids": e.position_qids,
                "position_labels": e.position_labels,
                "wikipedia_list": e.wikipedia_list,
            }
            for e in entries
        ]
    }
    path.write_text(yaml.dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False))


def load_registry(path: Path) -> list[CountryEntry]:
    """Load country registry from YAML."""
    data = yaml.safe_load(path.read_text())
    return [
        CountryEntry(
            name=c["name"],
            country_qid=c["country_qid"],
            position_qids=c.get("position_qids", []),
            position_labels=c.get("position_labels", []),
            wikipedia_list=c.get("wikipedia_list"),
        )
        for c in data.get("countries", [])
    ]
