"""Export quiz decks as self-contained JSON artifacts — the generator→quiz boundary.

Runs the generation pipeline (Gutenberg/Wikidata) once and writes one artifact per
deck to ``data/decks/``. The quiz reads these instead of regenerating content live,
so it needs neither the configs nor any generation/network code.

Discovery iteration mirrors ``deck_loader.discover_decks`` so ``config_path``,
``poem_title``, ``group``, ``name`` and ``mode`` are byte-identical — preserving deck
ids and FSRS item keys (``sha256(item)[:16]``) across the migration.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import yaml

from .gutenberg import fetch_text
from .logger import config_hash
from .monarchs import fetch_monarchs, make_monarch_chunks
from .poetry_parser import extract_poem

_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_CONFIG_DIR = _ROOT / 'configs'
DEFAULT_DECKS_DIR = _ROOT / 'data' / 'decks'


def _slug(text: str) -> str:
    """Filesystem-safe slug for disambiguating multi-poem artifact filenames."""
    return re.sub(r'-+', '-', re.sub(r'[^a-z0-9]+', '-', text.lower())).strip('-')


def build_deck_artifacts(config_dir: Path) -> list[dict]:
    """Run generation and return one artifact dict per deck (see module docstring)."""
    artifacts: list[dict] = []
    order = 0

    for yaml_path in sorted(Path(config_dir).glob('poetry/*.yaml')):
        cfg = yaml.safe_load(yaml_path.read_text())
        text = fetch_text(cfg['gutenberg_id'])
        poems = cfg.get('poems', [cfg])
        group = cfg.get('collection_title') if 'poems' in cfg else None
        chash = config_hash(yaml_path)
        for pc in poems:
            title = pc['poem_title']
            items = [l for l in extract_poem(text, pc['start_marker'], pc['end_marker']) if l is not None]
            artifacts.append({
                'order': order,
                'name': title,
                'deck_type': 'poetry',
                'mode': 'words',
                'title': title,
                'items': items,
                'labels': None,
                'group': group,
                'poem_title': title,
                'config_path': str(yaml_path),
                'config_hash': chash,
            })
            order += 1

    for yaml_path in sorted(Path(config_dir).glob('monarchs/*.yaml')):
        cfg = yaml.safe_load(yaml_path.read_text())
        title = cfg.get('subject', yaml_path.stem)
        monarchs = fetch_monarchs(cfg['positions'])
        chunks = make_monarch_chunks(monarchs, cfg.get('chunk_years', 100), cfg.get('chunk_start_year'))
        artifacts.append({
            'order': order,
            'name': title,
            'deck_type': 'monarchs',
            'mode': 'digits',
            'title': title,
            'items': [c.transition_string for c in chunks],
            'labels': [f"{c.start_year}–{c.end_year}" for c in chunks],
            'group': None,
            'poem_title': None,
            'config_path': str(yaml_path),
            'config_hash': config_hash(yaml_path),
        })
        order += 1

    return artifacts


def _artifact_filename(a: dict, multi: bool, used: set[str]) -> str:
    """Readable, unique ``<type>_<config-stem>[_<poem-slug>].json`` name."""
    base = f"{a['deck_type']}_{Path(a['config_path']).stem}"
    if multi and a['poem_title']:
        base = f"{base}_{_slug(a['poem_title'])}"
    name, n = base, 2
    while name in used:
        name = f"{base}-{n}"
        n += 1
    used.add(name)
    return f"{name}.json"


def export_decks(config_dir: Path = DEFAULT_CONFIG_DIR,
                 decks_dir: Path = DEFAULT_DECKS_DIR) -> list[Path]:
    """Write all deck artifacts to ``decks_dir`` (cleared first) and return their paths."""
    decks_dir = Path(decks_dir)
    decks_dir.mkdir(parents=True, exist_ok=True)
    for stale in decks_dir.glob('*.json'):
        stale.unlink()

    artifacts = build_deck_artifacts(config_dir)
    per_config: dict[str, int] = {}
    for a in artifacts:
        per_config[a['config_path']] = per_config.get(a['config_path'], 0) + 1

    used: set[str] = set()
    written: list[Path] = []
    for a in artifacts:
        path = decks_dir / _artifact_filename(a, per_config[a['config_path']] > 1, used)
        path.write_text(json.dumps(a, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        written.append(path)
    return written


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description='Export quiz decks as JSON artifacts.')
    p.add_argument('--config-dir', type=Path, default=DEFAULT_CONFIG_DIR)
    p.add_argument('--out', type=Path, default=DEFAULT_DECKS_DIR)
    args = p.parse_args(argv)
    written = export_decks(args.config_dir, args.out)
    print(f'Wrote {len(written)} deck artifacts to {args.out}')


if __name__ == "__main__":
    main()
