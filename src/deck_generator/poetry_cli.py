"""CLI entry point for poetry acronym tables."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from .gutenberg import fetch_text
from .poetry_parser import extract_poem
from .xlsx_writer import write_poetry_xlsx


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate poetry line acronym tables from Project Gutenberg")
    p.add_argument("--config", type=Path, required=True, help="YAML config file for the poem")
    p.add_argument("--output", type=Path, default=None)
    return p.parse_args(argv)


def main(argv=None) -> None:
    args = parse_args(argv)

    config: dict = yaml.safe_load(args.config.read_text())

    gutenberg_id: int = config.get("gutenberg_id")
    if not gutenberg_id:
        print("Error: config must specify gutenberg_id", file=sys.stderr)
        sys.exit(1)

    # Normalise single-poem and multi-poem configs to list[{poem_title, start_marker, end_marker}]
    if "poems" in config:
        poem_configs = config["poems"]
        sheet_title: str = config.get("collection_title", str(gutenberg_id))
    else:
        poem_configs = [config]
        sheet_title = config.get("poem_title", str(gutenberg_id))

    for pc in poem_configs:
        if not pc.get("start_marker") or not pc.get("end_marker"):
            print(f"Error: poem '{pc.get('poem_title', '?')}' must specify start_marker and end_marker", file=sys.stderr)
            sys.exit(1)

    output = args.output
    if output is None:
        slug = sheet_title.lower().replace(" ", "_")
        output = Path("results") / f"{slug}.xlsx"
    output.parent.mkdir(parents=True, exist_ok=True)

    text = fetch_text(gutenberg_id)
    poems = []
    for pc in poem_configs:
        title = pc.get("poem_title", "")
        lines = extract_poem(text, pc["start_marker"], pc["end_marker"])
        print(f"Extracted {sum(1 for l in lines if l is not None)} lines for '{title}'")
        poems.append((title, lines))

    write_poetry_xlsx(poems, output, sheet_title=sheet_title)
    print(f"Written: {output}")


if __name__ == "__main__":
    main()
