"""``deck-equations`` — preview or export an error-spotting equation deck config.

By default it *previews*: builds each equation's verified corruption pool and reports its
health, writing nothing. That is the tuning loop — pool thinness and "one trick to learn"
monotony are the failure modes that only show up per-config, and both are cheaper to see
here than after a re-export.

``--sample`` additionally prints a text rendering of one two-error display per equation, so
a corruption that is too obvious can be spotted without opening a browser. ``--export``
writes the artifact for just this deck via the same ``deck-export`` seam.
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path

import yaml

from .corruptions import build_pool, pool_warnings, valid_pairs
from .deck_export import DEFAULT_DECKS_DIR, export_decks
from .equations import eligible_indices, load_equations, to_mathml, token_texts

_DEFAULT_TYPES = ('sign_flip', 'exponent_off_by_one', 'constant_perturb', 'variable_swap')


def _sample_display(tokens: list[str], eligible: list[int], pool: list[dict],
                    bad_pairs: list[list[str]], rng: random.Random) -> str:
    """One plausible two-error display, as text. Mirrors what the client does: sample two
    non-blocked pool entries and swap those tokens' text — never re-render."""
    blocked = {tuple(sorted(p)) for p in bad_pairs}
    by_id = {e['id']: e for e in pool}
    pairs = [(a['id'], b['id']) for i, a in enumerate(pool) for b in pool[i + 1:]
             if tuple(sorted((a['id'], b['id']))) not in blocked]
    if not pairs:
        return '(no valid two-error pair)'
    shown = list(tokens)
    picked = rng.choice(pairs)
    for eid in picked:
        entry = by_id[eid]
        shown[eligible[entry['i'] - 1]] = f'[{entry["to"]}]'
    wrong = ', '.join(str(by_id[e]['i']) for e in picked)
    return f'{" ".join(shown)}    (wrong: tok-{wrong})'


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description="Preview or export an equation error-spot deck.")
    p.add_argument("--config", type=Path, required=True, help="Path to a configs/equations/*.yaml")
    p.add_argument("--export", action="store_true",
                   help="Write the deck artifact (default: preview only).")
    p.add_argument("--sample", action="store_true",
                   help="Also print one example two-error display per equation.")
    p.add_argument("--seed", type=int, default=0, help="Seed for --sample (reproducible).")
    p.add_argument("--out", type=Path, default=DEFAULT_DECKS_DIR)
    args = p.parse_args(argv)

    if args.export:
        stem = f"equations_{args.config.stem}"
        written = export_decks(args.config.parent.parent, args.out, only=stem)
        print(f"Exported {len(written)} deck(s) matching {stem!r} to {args.out}")
        return

    cfg = yaml.safe_load(args.config.read_text())
    ccfg = cfg.get('corruption') or {}
    types = ccfg.get('types', list(_DEFAULT_TYPES))
    pool_size = ccfg.get('pool_size', 12)
    rng = random.Random(args.seed)

    equations = load_equations(cfg)
    print(f"{len(equations)} equations for {cfg.get('deck_name', args.config.stem)!r}"
          f"  (types: {', '.join(types)})\n")

    warnings_seen, unusable = 0, 0
    for eq in equations:
        mathml = to_mathml(eq.latex)
        tokens, eligible = token_texts(mathml), eligible_indices(mathml)
        pool, bad = build_pool(eq, types, pool_size)
        by_type: dict[str, int] = {}
        for e in pool:
            by_type[e['type']] = by_type.get(e['type'], 0) + 1
        pairs = valid_pairs(pool, bad)
        unusable += not pairs
        print(f"  {eq.label}")
        print(f"    {eq.latex}")
        print(f"    clickable={len(eligible)}/{len(tokens)}  pool={len(pool)}  "
              f"pairs={pairs}  {by_type or '{}'}")
        if args.sample:
            print(f"    {_sample_display(tokens, eligible, pool, bad, rng)}")
        for w in pool_warnings(eq, pool, bad):
            warnings_seen += 1
            print(f"    ! {w}")
        print()

    print(f"{len(equations) - unusable}/{len(equations)} equations usable; "
          f"{warnings_seen} warning(s).")


if __name__ == "__main__":
    main()
