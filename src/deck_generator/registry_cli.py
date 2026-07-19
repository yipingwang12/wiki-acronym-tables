"""CLI: generate country_registry.yaml from Wikidata P1906."""

from __future__ import annotations

import argparse
from pathlib import Path

from .country_registry import fetch_country_registry, save_registry


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate country registry YAML from Wikidata P1906")
    p.add_argument("--output", type=Path, default=Path("configs/monarchs/country_registry.yaml"))
    return p.parse_args(argv)


def main(argv=None) -> None:
    args = parse_args(argv)
    print("Fetching sovereign states from Wikidata P1906...")
    entries = fetch_country_registry()
    print(f"Found {len(entries)} countries")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    save_registry(entries, args.output)
    print(f"Written: {args.output}")
    print("Add 'wikipedia_list' fields manually for countries you want to coverage-check.")


if __name__ == "__main__":
    main()
