"""Fetch famous artworks (title, creator, image) from Wikidata.

Feeds the quiz's image + multiple-choice mode. Three source modes select the QID set:

- ``wikidata`` — paintings ranked by ``wikibase:sitelinks`` (fame proxy), ``min_sitelinks`` /
  ``limit`` knobs. Beware: a low threshold over ~381k paintings can exceed the public
  endpoint's ~60s cap — page by narrower bands or raise the threshold.
- ``curated``  — an explicit ``works: [Q…]`` list (cheap, fully controlled).
- ``collection`` — every work in a ``collection: Q…`` (P195), e.g. a museum.

All three emit the same :class:`Artwork` shape. Distractors and image bytes are handled by
``distractors`` and ``artwork_images``; this module only resolves metadata.
"""

from __future__ import annotations

from dataclasses import dataclass

from .wikidata import _SPARQL_URL, _sparql_session

PAINTING = "Q3305213"


@dataclass(frozen=True)
class Artwork:
    qid: str
    title: str
    creator: str
    creator_qid: str
    image_url: str
    sitelinks: int
    inception: int | None = None  # year (P571), for same-era distractor biasing


_CORE = {
    "wikidata": (
        "  ?work wdt:P31 wd:{instance} ;\n"
        "        wdt:P170 ?creator ;\n"
        "        wdt:P18 ?img ;\n"
        "        wikibase:sitelinks ?sitelinks .\n"
        "  FILTER(?sitelinks >= {min_sitelinks})\n"
    ),
    "collection": (
        "  ?work wdt:P31 wd:{instance} ;\n"
        "        wdt:P195 wd:{collection} ;\n"
        "        wdt:P170 ?creator ;\n"
        "        wdt:P18 ?img ;\n"
        "        wikibase:sitelinks ?sitelinks .\n"
    ),
    "curated": (
        "  VALUES ?work {{ {works} }}\n"
        "  ?work wdt:P170 ?creator ;\n"
        "        wdt:P18 ?img ;\n"
        "        wikibase:sitelinks ?sitelinks .\n"
    ),
}

_QUERY = """\
SELECT ?work ?workLabel ?creator ?creatorLabel ?img ?sitelinks ?inception WHERE {{
{core}  OPTIONAL {{ ?work wdt:P571 ?inception . }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" }}
}}
ORDER BY DESC(?sitelinks)
{limit}"""


def build_query(config: dict) -> str:
    """Assemble the SPARQL for a config's source mode."""
    mode = config.get("source", "wikidata")
    instance = (config.get("instance_of") or [PAINTING])[0]
    if mode == "wikidata":
        core = _CORE["wikidata"].format(instance=instance, min_sitelinks=config.get("min_sitelinks", 10))
    elif mode == "collection":
        core = _CORE["collection"].format(instance=instance, collection=config["collection"])
    elif mode == "curated":
        works = " ".join(f"wd:{q}" for q in config["works"])
        core = _CORE["curated"].format(works=works)
    else:
        raise ValueError(f"unknown source mode: {mode!r}")
    limit = f"LIMIT {config['limit']}" if config.get("limit") else ""
    return _QUERY.format(core=core, limit=limit)


def _qid(uri: str) -> str:
    """``http://www.wikidata.org/entity/Q12418`` → ``Q12418``."""
    return uri.rsplit("/", 1)[-1]


def _is_unresolved(value: str) -> bool:
    """A label that never resolved to a real name. Wikidata falls back to the bare
    Q-number when no English label exists, and an 'unknown value' / 'no value' P170
    statement (an explicitly anonymous work) surfaces as a blank-node or entity URI
    (``http://www.wikidata.org/.well-known/genid/…``)."""
    return value.startswith("http") or (value.startswith("Q") and value[1:].isdigit())


def _year(iso: str | None) -> int | None:
    """Leading year of a Wikidata time literal (``1503-01-01T…`` / ``-0450-…``)."""
    if not iso:
        return None
    neg = iso.startswith("-")
    digits = iso.lstrip("-").split("-", 1)[0]
    return -int(digits) if neg else int(digits)


def fetch_artworks(config: dict, sparql_url: str = _SPARQL_URL) -> list[Artwork]:
    """Fetch artworks for a config, deduplicated by QID (highest-fame row wins).

    A work with several P18 images or P170 creators yields multiple SPARQL rows; the first
    seen (already sorted by descending sitelinks) is kept. A row without a usable title or
    image is dropped; a row whose *creator* is unresolved (an anonymous work) is kept with an
    empty creator, so the export emits it as a title-only card (no impossible creator card).
    """
    bindings = _sparql_session(sparql_url, build_query(config))
    seen: set[str] = set()
    out: list[Artwork] = []
    for b in bindings:
        qid = _qid(b["work"]["value"])
        if qid in seen:
            continue
        title = b.get("workLabel", {}).get("value", "")
        creator = b.get("creatorLabel", {}).get("value", "")
        img = b.get("img", {}).get("value", "")
        if not title or not img or _is_unresolved(title):
            continue  # a card needs a real title and an image
        creator_qid = _qid(b["creator"]["value"]) if b.get("creator") else ""
        if not creator or _is_unresolved(creator):
            creator = creator_qid = ""  # anonymous → title-only downstream
        seen.add(qid)
        out.append(Artwork(
            qid=qid,
            title=title,
            creator=creator,
            creator_qid=creator_qid,
            image_url=img,
            sitelinks=int(b.get("sitelinks", {}).get("value", 0)),
            inception=_year(b.get("inception", {}).get("value")),
        ))
    return out
