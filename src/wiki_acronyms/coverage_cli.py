"""CLI: check coverage of a monarch config against a Wikipedia list article."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from .coverage import check_coverage
from .country_registry import load_registry


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Check Wikidata monarch coverage against a Wikipedia list article"
    )
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--config", type=Path, help="Monarch YAML config (positions + optional wikipedia_list)")
    group.add_argument("--country", help="Country name to look up in the registry")
    p.add_argument(
        "--registry", type=Path, default=Path("configs/monarchs/country_registry.yaml"),
        help="Country registry YAML — used with --country (default: configs/monarchs/country_registry.yaml)",
    )
    p.add_argument("--wikipedia-list", help="Wikipedia list article title (overrides config/registry value)")
    return p.parse_args(argv)


def main(argv=None) -> None:
    args = parse_args(argv)

    if args.config:
        config: dict = yaml.safe_load(args.config.read_text())
        position_ids: list[str] = config.get("positions", [])
        subject: str = config.get("subject", "")
        wikipedia_list: str | None = args.wikipedia_list or config.get("wikipedia_list")
    else:
        if not args.registry.exists():
            print(
                f"Error: registry not found at {args.registry} — run wiki-registry-generate first",
                file=sys.stderr,
            )
            sys.exit(1)
        registry = load_registry(args.registry)
        match = next((e for e in registry if e.name.lower() == args.country.lower()), None)
        if not match:
            print(f"Error: '{args.country}' not found in registry", file=sys.stderr)
            sys.exit(1)
        position_ids = match.position_qids
        subject = match.name
        wikipedia_list = args.wikipedia_list or match.wikipedia_list

    if not position_ids:
        print("Error: no position IDs found", file=sys.stderr)
        sys.exit(1)
    if not wikipedia_list:
        print(
            "Error: no Wikipedia list title — use --wikipedia-list or add wikipedia_list to the config/registry",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Checking '{subject}' against Wikipedia: '{wikipedia_list}'...")
    report = check_coverage(position_ids, wikipedia_list, subject=subject)

    print(f"\nWikidata rulers fetched:   {report.wikidata_count}")
    print(f"Matched in Wikipedia list: {report.matched_count}")

    if report.in_wikipedia_not_wikidata:
        print(f"\n=== In Wikipedia list but NOT in Wikidata fetch ({len(report.in_wikipedia_not_wikidata)}) ===")
        for name in report.in_wikipedia_not_wikidata:
            print(f"  {name}")

    if report.in_wikidata_not_wikipedia:
        print(f"\n=== In Wikidata fetch but NOT linked from Wikipedia list ({len(report.in_wikidata_not_wikipedia)}) ===")
        for name in report.in_wikidata_not_wikipedia:
            print(f"  {name}")

    if report.no_wp_sitelink:
        print(f"\n=== Wikidata rulers with no English Wikipedia sitelink ({len(report.no_wp_sitelink)}) ===")
        for name in report.no_wp_sitelink:
            print(f"  {name}")


if __name__ == "__main__":
    main()
