#!/usr/bin/env python3
"""Parse all 154 Shakespeare sonnets from Gutenberg ID 1041 and write YAML config."""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from wiki_acronyms.gutenberg import fetch_text

_ROMAN_VALS = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}


def _from_roman(s: str) -> int:
    result = prev = 0
    for c in reversed(s):
        v = _ROMAN_VALS[c]
        result += v if v >= prev else -v
        prev = v
    return result


def parse_sonnets(text: str) -> list[dict]:
    lines = text.splitlines()
    sonnets = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or not re.match(r"^[IVXLCDM]+$", stripped):
            continue
        num = _from_roman(stripped)
        if not 1 <= num <= 154:
            continue
        # Require blank line before (or start of file)
        if i > 0 and lines[i - 1].strip():
            continue
        # Skip blank lines after the numeral heading
        j = i + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        # Collect the sonnet's lines until a blank line or EOF
        sonnet_lines = []
        while j < len(lines) and lines[j].strip():
            sonnet_lines.append(lines[j].strip())
            j += 1
        if len(sonnet_lines) < 12:
            continue
        sonnets.append({"number": num, "first": sonnet_lines[0], "last": sonnet_lines[-1]})

    return sorted(sonnets, key=lambda s: s["number"])


def _yaml_str(s: str) -> str:
    """Quote a string for YAML, escaping internal double quotes."""
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def main() -> None:
    text = fetch_text(1041)
    sonnets = parse_sonnets(text)
    print(f"Parsed {len(sonnets)} sonnets", file=sys.stderr)
    if len(sonnets) != 154:
        print(f"WARNING: expected 154, got {len(sonnets)}", file=sys.stderr)

    out = Path("configs/poetry/shakespeare_sonnets_complete.yaml")
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        f.write('collection_title: "Shakespeare\'s Sonnets"\n')
        f.write("gutenberg_id: 1041\n")
        f.write("poems:\n")
        for s in sonnets:
            f.write(f'  - poem_title: "Sonnet {s["number"]}"\n')
            f.write(f'    start_marker: {_yaml_str(s["first"])}\n')
            f.write(f'    end_marker: {_yaml_str(s["last"])}\n')
    print(f"Written: {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
