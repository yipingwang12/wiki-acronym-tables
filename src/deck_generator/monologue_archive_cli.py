"""CLI to scrape Monologue Archive passages and write YAML catalogue and xlsx."""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from .monologue_archive import fetch_all_passages
from .xlsx_writer import write_monologue_xlsx


def main(argv=None) -> None:
    p = argparse.ArgumentParser(
        description='Scrape Monologue Archive passages and write YAML + xlsx.'
    )
    p.add_argument('--config', type=Path, required=True)
    p.add_argument('--output', type=Path)
    p.add_argument('--xlsx', type=Path)
    args = p.parse_args(argv)

    config = yaml.safe_load(args.config.read_text())
    authors = config['authors']

    output = args.output or Path('results/monologue_archive_passages.yaml')
    xlsx_output = args.xlsx or Path('results/monologue_archive_passages.xlsx')
    output.parent.mkdir(parents=True, exist_ok=True)

    print(f'Fetching passages for {len(authors)} playwright(s)...')
    passages = fetch_all_passages(authors)
    total_lines = sum(p.line_count for p in passages)

    catalogue = {
        'meta': {
            'authors': [a['name'] for a in authors],
            'total_passages': len(passages),
            'total_lines': total_lines,
        },
        'passages': [
            {
                'playwright': p.playwright,
                'play_name': p.play_name,
                'character': p.character,
                'passage_type': p.passage_type,
                'passage_id': p.passage_id,
                'line_count': p.line_count,
                'excerpt': p.excerpt,
                'lines': p.lines,
            }
            for p in passages
        ],
    }

    output.write_text(
        yaml.dump(catalogue, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding='utf-8',
    )
    write_monologue_xlsx(passages, xlsx_output)
    print(f'Done: {len(passages)} passages, {total_lines} lines → {output}, {xlsx_output}')
