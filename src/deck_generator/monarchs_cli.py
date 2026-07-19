"""CLI entry point for monarch reign transition tables."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from .monarchs import (
    correction_years, fetch_monarchs, filter_by_accession, make_monarch_chunks,
    parse_corrections, report_imprecise_dates, stale_corrections,
)
from .xlsx_writer import write_monarchs_xlsx


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate monarch transition-digit tables from Wikidata")
    p.add_argument("--config", type=Path, required=True, help="YAML config file")
    p.add_argument("--output", type=Path, default=None)
    return p.parse_args(argv)


def main(argv=None) -> None:
    args = parse_args(argv)

    config: dict = yaml.safe_load(args.config.read_text())

    position_ids: list[str] = config.get("positions", [])
    if not position_ids:
        print("Error: config must specify positions", file=sys.stderr)
        sys.exit(1)

    subject: str = config.get("subject", "Monarchs")
    chunk_years: int = config.get("chunk_years", 100)
    chunk_start_year: int | None = config.get("chunk_start_year")

    try:
        corrections = parse_corrections(config.get("corrections"))
    except ValueError as e:
        print(f"Error: {args.config}: {e}", file=sys.stderr)
        sys.exit(1)

    output = args.output
    if output is None:
        slug = subject.lower().replace(" ", "_")
        output = Path("results") / f"{slug}.xlsx"
    output.parent.mkdir(parents=True, exist_ok=True)

    monarchs = fetch_monarchs(position_ids, house_ids=config.get("houses"))
    monarchs = filter_by_accession(monarchs, config.get("accession_min_year"), config.get("accession_max_year"))
    if not monarchs:
        print(f"Error: no monarchs found for positions {position_ids}", file=sys.stderr)
        sys.exit(1)

    print(f"Fetched {len(monarchs)} monarchs for '{subject}'")

    for note in report_imprecise_dates(monarchs):
        print(f"Warning: {note}", file=sys.stderr)   # documentation only; digits unaffected
    for note in stale_corrections(monarchs, corrections):
        print(f"Warning: stale correction — {note}", file=sys.stderr)

    add_years, drop_years = correction_years(corrections)
    chunks = make_monarch_chunks(
        monarchs, chunk_years=chunk_years, chunk_start_year=chunk_start_year,
        add_transition_years=add_years, drop_transition_years=drop_years,
    )
    print(f"Grouped into {len(chunks)} chunks of {chunk_years} years")

    write_monarchs_xlsx(chunks, output, subject=subject)
    print(f"Written: {output}")


if __name__ == "__main__":
    main()
