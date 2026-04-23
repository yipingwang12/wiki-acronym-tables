"""CLI: derive Wikidata position Q-IDs from a Wikipedia rulers spreadsheet."""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from .derive_positions import _RULER_KEYWORDS, fetch_positions_for_titles, load_ruler_titles


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Derive position Q-IDs from a Wikipedia rulers xlsx/csv via Wikidata P39 reverse lookup"
    )
    p.add_argument("--input", type=Path, required=True, help="xlsx or csv from wikipedia-data-analysis")
    p.add_argument("--nationality", help="Filter rows by nationality substring (e.g. 'English', 'French')")
    p.add_argument("--wiki", default="https://en.wikipedia.org/", help="Wikipedia base URL for sitelink lookup")
    p.add_argument("--min-holders", type=int, default=2, help="Minimum distinct holders to include (default: 2)")
    p.add_argument("--output", type=Path, help="Write suggested positions YAML to this path")
    return p.parse_args(argv)


def main(argv=None) -> None:
    args = parse_args(argv)

    titles = load_ruler_titles(args.input, nationality=args.nationality)
    if not titles:
        print("No ruler titles found after filtering.")
        return

    nat_label = f" (nationality: {args.nationality})" if args.nationality else ""
    print(f"Found {len(titles)} ruler titles in {args.input.name}{nat_label}")
    print(f"Querying Wikidata in batches...")

    positions = fetch_positions_for_titles(titles, wiki_base=args.wiki)
    filtered = [p for p in positions if p.holder_count >= args.min_holders]

    print(f"\n{'Position':<55} {'Q-ID':<12} {'Holders':>7}")
    print("-" * 76)
    for p in filtered:
        print(f"{p.label:<55} {p.position_qid:<12} {p.holder_count:>7}")

    if not filtered:
        print("No positions met the minimum holder threshold.")
        return

    if args.output:
        data = {
            "positions": [
                {p.position_qid: f"{p.label} ({p.holder_count} holders)"}
                for p in filtered
            ]
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            f"# Derived from {args.input.name}{nat_label}\n"
            + yaml.dump(data, allow_unicode=True, sort_keys=False)
        )
        print(f"\nWritten: {args.output}")


if __name__ == "__main__":
    main()
