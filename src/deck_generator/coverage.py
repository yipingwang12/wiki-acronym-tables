"""Coverage check: compare a Wikidata monarch list against a Wikipedia list article."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .monarchs import fetch_monarchs
from .wiki_api import WikiApiClient
from .wikidata import _SPARQL_URL

_EXCLUDE_PREFIXES = (
    "List of", "Lists of", "House of", "Kingdom of", "Duchy of", "County of",
    "Empire of", "Republic of", "Battle of", "Treaty of", "War of",
    "File:", "Image:", "Category:", "Template:", "Wikipedia:", "Help:",
    "Portal:", "Talk:", "User:",
)
_EXCLUDE_SUFFIXES = (
    "(disambiguation)", "(dynasty)", "(country)", "(kingdom)", "(empire)",
)


def _is_likely_person_link(title: str) -> bool:
    for prefix in _EXCLUDE_PREFIXES:
        if title.startswith(prefix):
            return False
    for suffix in _EXCLUDE_SUFFIXES:
        if title.endswith(suffix):
            return False
    if re.fullmatch(r"\d{3,4}([-–]\d{3,4})?", title):
        return False
    return True


def fetch_wikipedia_list_links(
    article_title: str,
    api_client: WikiApiClient | None = None,
) -> set[str]:
    """Return mainspace article titles linked from a Wikipedia list article, filtered to likely persons."""
    client = api_client or WikiApiClient()
    links = client.fetch_article_links(article_title)
    return {t for t in links if _is_likely_person_link(t)}


@dataclass
class CoverageReport:
    subject: str
    wikipedia_list: str
    wikidata_count: int
    matched_count: int
    in_wikipedia_not_wikidata: list[str] = field(default_factory=list)
    in_wikidata_not_wikipedia: list[str] = field(default_factory=list)
    no_wp_sitelink: list[str] = field(default_factory=list)


def check_coverage(
    position_ids: list[str],
    wikipedia_list_title: str,
    subject: str = "",
    sparql_url: str = _SPARQL_URL,
    api_client: WikiApiClient | None = None,
) -> CoverageReport:
    """Compare a Wikidata monarch list against a Wikipedia list article by sitelink title."""
    monarchs = fetch_monarchs(position_ids, sparql_url=sparql_url)
    wp_links = fetch_wikipedia_list_links(wikipedia_list_title, api_client=api_client)

    wp_title_set = {m.wp_title for m in monarchs if m.wp_title}
    matched = wp_title_set & wp_links

    return CoverageReport(
        subject=subject,
        wikipedia_list=wikipedia_list_title,
        wikidata_count=len(monarchs),
        matched_count=len(matched),
        in_wikipedia_not_wikidata=sorted(wp_links - wp_title_set),
        in_wikidata_not_wikipedia=sorted(
            m.wp_title for m in monarchs if m.wp_title and m.wp_title not in wp_links
        ),
        no_wp_sitelink=sorted(m.name for m in monarchs if not m.wp_title),
    )
