"""``deck-vocab`` — preview / curate / build the Chinese matching vocab deck.

The deck is a **curated** artifact (``source: manual``): heavy lifting is done offline and
committed as data, then ``build`` assembles the artifact deterministically (no network, no
API key). Three modes:

- **preview** (default): join wordfreq×CC-CEDICT, report the clean/needs-LLM split. Tuning
  loop — no writes.
- **curate**: prepare the needs-LLM batch for the audited adjudication pass (the per-word
  sense/reading/gloss calls, done by an LLM pass that writes ``*.curated.jsonl`` +
  ``*.audit.jsonl``). Emits chunk files; adjudication itself is external.
- **build**: assemble the committed ``*.curated.jsonl`` into the deck artifact. Verifies
  band-scoped gloss uniqueness + no duplicate hanzi first.

See docs/design/vocab-pipeline.md.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from .deck_export import DEFAULT_DECKS_DIR, config_hash
from . import vocab

_ARTIFACT_NAME = "vocab_chinese_common.json"


def _load_cfg(path: Path) -> tuple[dict, Path, Path]:
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    curated = path.parent / cfg["curated"]
    return cfg, curated, path


def _preview(cfg: dict, seed_deck: Path) -> None:
    vocab.fetch_cedict()
    cedict = vocab.load_cedict()
    exclude = {r.hanzi for r in vocab.load_seed(seed_deck)} if seed_deck.exists() else set()
    cands = vocab.rank_candidates(cedict, exclude=exclude, target_n=cfg["target_n"])
    n_llm = sum(c.needs_llm for c in cands)
    print(f"CC-CEDICT entries : {len(cedict):,}")
    print(f"seed excluded     : {len(exclude)}")
    print(f"candidates        : {len(cands)} (target {cfg['target_n']})")
    print(f"  clean (no LLM)  : {len(cands) - n_llm} ({100*(len(cands)-n_llm)//max(len(cands),1)}%)")
    print(f"  needs LLM       : {n_llm} (polyphone ∪ multi-sense ∪ function-word)")


def _curate(cfg: dict, seed_deck: Path, out_dir: Path, chunk: int) -> None:
    vocab.fetch_cedict()
    cedict = vocab.load_cedict()
    exclude = {r.hanzi for r in vocab.load_seed(seed_deck)} if seed_deck.exists() else set()
    cands = vocab.rank_candidates(cedict, exclude=exclude, target_n=cfg["target_n"])
    batch = vocab.llm_batch_records(cands)
    out_dir.mkdir(parents=True, exist_ok=True)
    for i in range(0, len(batch), chunk):
        (out_dir / f"chunk_{i//chunk:02d}.json").write_text(
            json.dumps(batch[i:i + chunk], ensure_ascii=False, indent=1), encoding="utf-8")
    n = -(-len(batch) // chunk)
    print(f"wrote {n} chunk files ({len(batch)} needs-LLM words) to {out_dir}")
    print("→ run the audited adjudication pass (per-word sense/reading/gloss + reason) over")
    print(f"  these chunks and write {cfg['curated']} + {cfg['audit']}, then `deck-vocab build`.")


def _build(cfg: dict, curated_path: Path, config_path: Path, out_dir: Path) -> None:
    rows = vocab.load_curated(curated_path)
    hanzi = [r.hanzi for r in rows]
    assert len(set(hanzi)) == len(hanzi), "duplicate hanzi → FSRS item_key collision"
    collisions = vocab.band_collisions(rows)
    assert not collisions, f"in-band gloss collisions (ambiguous rounds): {collisions[:10]}"
    art = vocab.assemble_artifact(rows, cfg, f"manual/{config_path.name}")
    art["config_hash"] = config_hash(curated_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / _ARTIFACT_NAME
    out.write_text(json.dumps(art, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"built {out} — {len(rows)} words (source: manual, {len(rows)-cfg.get('seed_count',0)} beyond seed)")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Preview/curate/build the Chinese vocab matching deck.")
    p.add_argument("--config", type=Path, default=Path("configs/vocab/chinese_common.yaml"))
    p.add_argument("--seed-deck", type=Path,
                   default=Path("../memory-quiz-app/data/decks/vocab_chinese_common.json"),
                   help="existing deck to exclude as seed (preview/curate only)")
    p.add_argument("--out", type=Path, default=DEFAULT_DECKS_DIR)
    p.add_argument("--curate", action="store_true", help="prepare needs-LLM chunk files")
    p.add_argument("--build", action="store_true", help="assemble artifact from committed curated rows")
    p.add_argument("--chunk", type=int, default=100)
    args = p.parse_args(argv)

    cfg, curated, config_path = _load_cfg(args.config)
    if args.build:
        _build(cfg, curated, config_path, args.out)
    elif args.curate:
        _curate(cfg, args.seed_deck, args.out / "vocab_chunks", args.chunk)
    else:
        _preview(cfg, args.seed_deck)


if __name__ == "__main__":
    main()
