"""CLI entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from .chunker import make_chunks
from .wikidata import count_laureates, fetch_entries
from .xlsx_writer import write_xlsx


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate award laureate acronym tables from Wikidata")
    p.add_argument("--config", type=Path, required=True, help="YAML config file for the award")
    p.add_argument("--chunk-years", type=int, default=5)
    p.add_argument("--chunk-start-year", type=int, default=None)
    p.add_argument("--output", type=Path, default=None)
    return p.parse_args(argv)


def main(argv=None) -> None:
    args = parse_args(argv)

    config: dict = yaml.safe_load(args.config.read_text())

    item_id = config.get("wikidata_item")
    if not item_id:
        print("Error: config must specify wikidata_item", file=sys.stderr)
        sys.exit(1)

    chunk_years: int = config.get("chunk_years", args.chunk_years)
    chunk_start_year: int | None = config.get("chunk_start_year", args.chunk_start_year)
    first_letter_only_from: int | None = config.get("first_letter_only_from")
    humans_only: bool = config.get("humans_only", False)
    award_name: str = config.get("award_name", item_id)

    output = args.output
    if output is None:
        slug = award_name.lower().replace(" ", "_")
        output = Path("results") / f"{slug}.xlsx"
    output.parent.mkdir(parents=True, exist_ok=True)

    entries = fetch_entries(item_id, humans_only=humans_only)
    if not entries:
        print(f"Error: no entries found for item '{item_id}'", file=sys.stderr)
        sys.exit(1)

    total = count_laureates(item_id, humans_only=humans_only)
    if total != len(entries):
        print(
            f"Warning: Wikidata reports {total} laureates for '{award_name}' "
            f"but only {len(entries)} have a date qualifier — "
            f"{total - len(entries)} missing and excluded from table",
            file=sys.stderr,
        )

    print(f"Fetched {len(entries)} entries for '{award_name}'")
    chunks = make_chunks(entries, chunk_years=chunk_years, chunk_start_year=chunk_start_year, first_letter_only_from=first_letter_only_from)
    print(f"Grouped into {len(chunks)} chunks of {chunk_years} years")

    write_xlsx(chunks, output, award_name=award_name, first_letter_only_from=first_letter_only_from)
    print(f"Written: {output}")


if __name__ == "__main__":
    main()
