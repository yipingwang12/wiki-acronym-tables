"""CLI entry point for blindman's bluff poetry quiz."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from .gutenberg import fetch_text
from .poetry_parser import extract_poem
from .quiz import make_line_display, score_response

_MISS_COST = 3
_FALSE_ALARM_COST = 1
_MAX_HEALTH = 10


def _health_bar(health: int) -> str:
    filled = max(0, health)
    return f"[{'*' * filled}{'.' * (_MAX_HEALTH - filled)}] {health}/{_MAX_HEALTH}"


def _load_poems(config: dict) -> list[tuple[str, list[str | None]]]:
    text = fetch_text(config['gutenberg_id'])
    poem_cfgs = config['poems'] if 'poems' in config else [config]
    return [
        (pc['poem_title'], extract_poem(text, pc['start_marker'], pc['end_marker']))
        for pc in poem_cfgs
    ]


def _run_poem(title: str, lines: list[str | None], wrong_prob: float) -> None:
    text_lines = [l for l in lines if l is not None]
    health = _MAX_HEALTH
    i = 0

    print(f"\n=== {title} ===\n")
    while i < len(text_lines):
        d = make_line_display(text_lines[i], wrong_prob)
        print(f"Line {i+1}/{len(text_lines)}  {_health_bar(health)}")
        print(f"\n  {d.display}\n")

        raw = input("Wrong letter in word # (0 = none): ").strip()
        try:
            user_input = int(raw)
        except ValueError:
            print("Enter a number.\n")
            continue

        correct, feedback = score_response(d, user_input)
        print(f"  {feedback}\n")

        if not correct:
            health -= _MISS_COST if d.has_wrong else _FALSE_ALARM_COST
            if health <= 0:
                print(f"Health exhausted — restarting {title}.\n")
                health = _MAX_HEALTH
                i = 0
                continue

        i += 1

    print(f"=== {title} complete! ===\n")


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description="Quiz poetry line retention via blindman's bluff.")
    p.add_argument('--config', type=Path, required=True)
    p.add_argument('--poem', help='Poem title (for multi-poem configs)')
    p.add_argument('--wrong-prob', type=float, default=0.15)
    args = p.parse_args(argv)

    config = yaml.safe_load(args.config.read_text())
    poems = _load_poems(config)

    if args.poem:
        poems = [(t, ls) for t, ls in poems if t == args.poem]
        if not poems:
            print(f"Poem '{args.poem}' not found.", file=sys.stderr)
            sys.exit(1)

    for title, lines in poems:
        _run_poem(title, lines, args.wrong_prob)
