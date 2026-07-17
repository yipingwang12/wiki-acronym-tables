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
import hashlib
import json
import re
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path

import yaml

from .gutenberg import fetch_text
from .monarchs import (
    correction_years, fetch_monarchs, filter_by_accession, make_monarch_chunks, parse_corrections,
)
from .poetry_parser import extract_poem

_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_CONFIG_DIR = _ROOT / 'configs'
DEFAULT_DECKS_DIR = _ROOT / 'data' / 'decks'


def config_hash(path: Path) -> str:
    """Session ``cfg_hash`` carried into each artifact — sha256 of the config bytes.

    Kept here (not imported from the quiz) so the generator stays standalone after
    the quiz split. Must match the quiz's ``logger.config_hash`` exactly.
    """
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _slug(text: str) -> str:
    """Filesystem-safe slug for disambiguating multi-poem artifact filenames."""
    return re.sub(r'-+', '-', re.sub(r'[^a-z0-9]+', '-', text.lower())).strip('-')


@dataclass(frozen=True)
class _Slot:
    """One deck's identity, resolved WITHOUT touching the network.

    ``order`` and the artifact filename must be assigned across the *whole* config set,
    never the selected subset — otherwise `--only` would renumber decks it isn't rebuilding
    and shuffle the quiz's deck list."""

    order: int
    deck_type: str
    yaml_path: Path
    poem_cfg: dict | None      # poetry: the per-poem config block; monarchs: None
    group: str | None
    filename: str = ''


def _discover_slots(config_dir: Path) -> list[_Slot]:
    """Every deck's order + filename, from configs alone. Mirrors build order exactly."""
    slots: list[_Slot] = []
    order = 0
    for yaml_path in sorted(Path(config_dir).glob('poetry/*.yaml')):
        cfg = yaml.safe_load(yaml_path.read_text())
        poems = cfg.get('poems', [cfg])          # no fetch needed to enumerate poems
        group = cfg.get('collection_title') if 'poems' in cfg else None
        for pc in poems:
            slots.append(_Slot(order, 'poetry', yaml_path, pc, group))
            order += 1
    for yaml_path in sorted(Path(config_dir).glob('monarchs/*.yaml')):
        slots.append(_Slot(order, 'monarchs', yaml_path, None, None))
        order += 1

    per_config: dict[Path, int] = {}
    for s in slots:
        per_config[s.yaml_path] = per_config.get(s.yaml_path, 0) + 1
    used: set[str] = set()
    return [
        _Slot(s.order, s.deck_type, s.yaml_path, s.poem_cfg, s.group,
              _slot_filename(s, per_config[s.yaml_path] > 1, used))
        for s in slots
    ]


def _slot_filename(s: _Slot, multi: bool, used: set[str]) -> str:
    """Readable, unique ``<type>_<config-stem>[_<poem-slug>].json`` name."""
    base = f"{s.deck_type}_{s.yaml_path.stem}"
    if multi and s.poem_cfg is not None:
        base = f"{base}_{_slug(s.poem_cfg['poem_title'])}"
    name, n = base, 2
    while name in used:
        name, n = f"{base}-{n}", n + 1
    used.add(name)
    return f"{name}.json"


def build_deck_artifacts(config_dir: Path, only: str | None = None) -> list[dict]:
    """Run generation and return one artifact dict per deck (see module docstring).

    ``only`` is an fnmatch pattern over artifact filenames (e.g. ``monarchs_britain`` or
    ``monarchs_*``); non-matching decks are skipped entirely — not fetched, not built —
    while still consuming their ``order``."""
    slots = _discover_slots(config_dir)
    wanted = [s for s in slots if _slot_selected(s, only)]
    artifacts: list[dict] = []
    text_cache: dict[int, str] = {}

    for s in wanted:
        if s.deck_type != 'poetry':
            continue
        cfg = yaml.safe_load(s.yaml_path.read_text())
        gid = cfg['gutenberg_id']
        if gid not in text_cache:
            text_cache[gid] = fetch_text(gid)
        pc = s.poem_cfg
        title = pc['poem_title']
        items = [l for l in extract_poem(text_cache[gid], pc['start_marker'], pc['end_marker'])
                 if l is not None]
        artifacts.append({
            'order': s.order,
            'name': title,
            'deck_type': 'poetry',
            'mode': 'words',
            'title': title,
            'items': items,
            'labels': None,
            'group': s.group,
            'poem_title': title,
            'config_path': str(s.yaml_path),
            'config_hash': config_hash(s.yaml_path),
            '_filename': s.filename,
        })

    for s in wanted:
        if s.deck_type != 'monarchs':
            continue
        cfg = yaml.safe_load(s.yaml_path.read_text())
        title = cfg.get('subject', s.yaml_path.stem)
        monarchs = fetch_monarchs(cfg['positions'], house_ids=cfg.get('houses'))
        monarchs = filter_by_accession(monarchs, cfg.get('accession_min_year'), cfg.get('accession_max_year'))
        add_years, drop_years = correction_years(parse_corrections(cfg.get('corrections')))
        chunks = make_monarch_chunks(
            monarchs, cfg.get('chunk_years', 100), cfg.get('chunk_start_year'),
            add_transition_years=add_years, drop_transition_years=drop_years,
        )
        artifacts.append({
            'order': s.order,
            'name': title,
            'deck_type': 'monarchs',
            'mode': 'digits',
            'title': title,
            'items': [c.transition_string for c in chunks],
            'labels': [f"{c.start_year}–{c.end_year}" for c in chunks],
            'group': None,
            'poem_title': None,
            'config_path': str(s.yaml_path),
            'config_hash': config_hash(s.yaml_path),
            '_filename': s.filename,
        })

    artifacts.sort(key=lambda a: a['order'])
    return artifacts


def _slot_selected(s: _Slot, only: str | None) -> bool:
    return only is None or fnmatch(s.filename.removesuffix('.json'), only)


def export_decks(config_dir: Path = DEFAULT_CONFIG_DIR,
                 decks_dir: Path = DEFAULT_DECKS_DIR,
                 only: str | None = None,
                 reset_identity: bool = False) -> list[Path]:
    """Write deck artifacts to ``decks_dir`` and return their paths.

    A full export (``only=None``) clears ``decks_dir`` first — a rebuild is authoritative.
    With ``only``, nothing is cleared and only matching decks are overwritten; their
    ``order`` and ``config_path`` are taken from the existing artifact when one is present.
    Those two fields are IDENTITY, not content: ``config_path`` keys the quiz's sessions
    table (`WHERE config_path=?`) and its artifact lookup, and ``order`` drives deck-list
    sort. Re-deriving them during a partial refresh would strand study history and shuffle
    the list — the export directory is an accumulation across runs, so a fresh numbering
    agrees with neither. Pass ``reset_identity=True`` to re-derive them anyway (e.g. after
    genuinely moving the repo).
    """
    decks_dir = Path(decks_dir)
    decks_dir.mkdir(parents=True, exist_ok=True)
    if only is None:
        for stale in decks_dir.glob('*.json'):
            stale.unlink()

    artifacts = build_deck_artifacts(config_dir, only=only)
    written: list[Path] = []
    for a in artifacts:
        a = dict(a)
        path = decks_dir / a.pop('_filename')
        if only is not None and not reset_identity and path.exists():
            prev = json.loads(path.read_text(encoding='utf-8'))
            a['order'] = prev.get('order', a['order'])
            a['config_path'] = prev.get('config_path', a['config_path'])
        path.write_text(json.dumps(a, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        written.append(path)
    return written


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description='Export quiz decks as JSON artifacts.')
    p.add_argument('--config-dir', type=Path, default=DEFAULT_CONFIG_DIR)
    p.add_argument('--out', type=Path, default=DEFAULT_DECKS_DIR)
    p.add_argument('--only', default=None, metavar='GLOB',
                   help="Only rebuild decks whose artifact name matches (e.g. 'monarchs_britain', "
                        "'monarchs_*'). Others are left untouched and not fetched. Without it, "
                        "the output directory is CLEARED and every deck rebuilt.")
    p.add_argument('--reset-identity', action='store_true',
                   help="With --only, re-derive order/config_path instead of preserving the "
                        "existing artifact's. Strands session history keyed on config_path.")
    args = p.parse_args(argv)
    written = export_decks(args.config_dir, args.out, only=args.only,
                           reset_identity=args.reset_identity)
    scope = f"matching {args.only!r}" if args.only else 'all'
    print(f'Wrote {len(written)} deck artifacts ({scope}) to {args.out}')


if __name__ == "__main__":
    main()
