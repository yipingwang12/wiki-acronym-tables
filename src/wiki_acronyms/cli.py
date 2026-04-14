"""CLI entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from .chunker import make_chunks
from .list_parser import parse_entries
from .wiki_api import WikiApiClient
from .xlsx_writer import write_xlsx


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate award laureate acronym tables from Wikipedia")
    p.add_argument("--config", type=Path, help="YAML config file for the award")
    p.add_argument("--page", help="Wikipedia page title (overrides config)")
    p.add_argument("--year-col", type=int, default=0)
    p.add_argument("--name-col", type=int, default=1)
    p.add_argument("--chunk-years", type=int, default=5)
    p.add_argument("--chunk-start-year", type=int, default=None)
    p.add_argument("--output", type=Path, default=None)
    p.add_argument("--wiki", default="enwiki")
    return p.parse_args(argv)


def main(argv=None) -> None:
    args = parse_args(argv)

    config: dict = {}
    if args.config:
        config = yaml.safe_load(args.config.read_text())

    page = args.page or config.get("page")
    if not page:
        print("Error: provide --page or --config with page title", file=sys.stderr)
        sys.exit(1)

    cols = config.get("table_cols", {})
    year_col: int = cols.get("year", args.year_col)
    name_col: int = cols.get("name", args.name_col)
    chunk_years: int = config.get("chunk_years", args.chunk_years)
    chunk_start_year: int | None = config.get("chunk_start_year", args.chunk_start_year)
    award_name: str = config.get("award_name", page)

    wiki = config.get("wiki", args.wiki)
    lang = wiki[:-4] if wiki.endswith("wiki") else wiki
    api_url = f"https://{lang}.wikipedia.org/w/api.php"

    output = args.output
    if output is None:
        slug = page.lower().replace(" ", "_")
        output = Path("results") / f"{slug}.xlsx"
    output.parent.mkdir(parents=True, exist_ok=True)

    client = WikiApiClient(api_url=api_url)
    wikitext_map = client.fetch_wikitext_batch([page])
    wikitext = wikitext_map.get(page, "")

    if not wikitext:
        print(f"Error: could not fetch page '{page}'", file=sys.stderr)
        sys.exit(1)

    entries = parse_entries(wikitext, year_col=year_col, name_col=name_col)
    if not entries:
        print(f"Error: no entries found in '{page}'", file=sys.stderr)
        sys.exit(1)

    print(f"Parsed {len(entries)} entries from '{page}'")
    chunks = make_chunks(entries, chunk_years=chunk_years, chunk_start_year=chunk_start_year)
    print(f"Grouped into {len(chunks)} chunks of {chunk_years} years")

    write_xlsx(chunks, output, award_name=award_name)
    print(f"Written: {output}")


if __name__ == "__main__":
    main()
