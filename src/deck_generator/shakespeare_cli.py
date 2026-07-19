"""CLI to build a catalogue of Shakespeare passages from the Folger API."""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from .folger import fetch_passages
from .xlsx_writer import write_shakespeare_xlsx


def main(argv=None) -> None:
    p = argparse.ArgumentParser(
        description='Fetch Shakespeare passages from the Folger API and write a YAML catalogue and xlsx.'
    )
    p.add_argument('--config', type=Path, required=True)
    p.add_argument('--output', type=Path)
    p.add_argument('--xlsx', type=Path)
    args = p.parse_args(argv)

    config = yaml.safe_load(args.config.read_text())
    play_codes = list(config.get('plays', {}).keys())
    min_lines = config.get('min_lines', 20)

    output = args.output or Path('results/shakespeare_passages.yaml')
    xlsx_output = args.xlsx or Path('results/shakespeare_passages.xlsx')
    output.parent.mkdir(parents=True, exist_ok=True)

    print(f'Fetching passages from {len(play_codes)} plays (min_lines={min_lines})...')
    passages = fetch_passages(play_codes, min_lines)
    total_lines = sum(len(p.lines) for p in passages)

    catalogue = {
        'meta': {
            'plays': play_codes,
            'min_lines': min_lines,
            'total_passages': len(passages),
            'total_lines': total_lines,
        },
        'passages': [
            {
                'play_code': p.play_code,
                'play_name': p.play_name,
                'character': p.character,
                'segment_id': p.segment_id,
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
    write_shakespeare_xlsx(passages, xlsx_output)
    print(f'Done: {len(passages)} passages, {total_lines} lines → {output}, {xlsx_output}')
