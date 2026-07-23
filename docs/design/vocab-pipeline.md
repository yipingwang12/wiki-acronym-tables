# Chinese vocab pipeline (`deck-vocab`)

Frequency-ranked expansion of the `memory-quiz-app` hanzi↔meaning **matching** deck
(`vocab_chinese_common`), 267 → 5257 words (2026-07-23).

## Why a curation tool, not a generated deck

The deck is **`source: manual`** — a load-bearing contract: it's protected from the
`deck-export` full-clear (`deck_export._is_manual`) *and* the orchestrator's `decks` sync,
and it carries live FSRS history (`item_key = sha256(hanzi)[:16]`). So it is **not** a
first-class generated deck (which a full re-export would rebuild non-deterministically).
Instead, like the equations deck: heavy lifting → **committed data** → deterministic
`build`. The seed 267 are frozen **byte-identical** (hanzi unchanged → FSRS keys survive).

## Data sources (both free)

- **wordfreq** — frequency ranking (`top_n_list('zh', …)`).
- **CC-CEDICT** — pinyin + glosses, **CC-BY-SA 4.0** (attribution + share-alike on the
  artifact; `cache/cedict_ts.u8`, fetched from mdbg.net).

## Stages

1. **Seed** — existing 267 rows, frozen verbatim (`vocab.load_seed`).
2. **Rank + route** (`vocab.rank_candidates`) — wordfreq-ranked hanzi in CC-CEDICT minus the
   seed. Each candidate is **clean** (single reading, ≤3 senses → CEDICT first-gloss is
   safe, ~63%) or **needs-LLM** (polyphone ∪ multi-sense ∪ function-word signal, ~37%).
   The router exists because CEDICT's *first* sense is often wrong for the frequent use
   (被→"quilt" not the passive marker; 更→gēng not gèng).
3. **Adjudicate** (needs-LLM only) — an **audited** per-word pass picks the frequency-correct
   reading + sense and writes one short gloss, logging the choice + reason to
   `*.audit.jsonl`. Policy: `configs/vocab/chinese_common.policy.md`. Keep grammatical words
   with functional glosses (被 "by (passive marker)"); drop only surname/variant-only
   non-words. The 5k run used a fan-out of 19 subagents over frequency-band chunks
   (in-session, no API key); a Batch-API path is equivalent.
4. **Assemble** (`deck-vocab build`, deterministic, offline) — merge seed + clean + curated,
   order by wordfreq rank (item_key is hanzi-hash → position-free), verify no duplicate
   hanzi + **band-scoped gloss uniqueness**, stamp the envelope (`source: manual`).

## Band-scoped gloss uniqueness

English has no 5000+ distinct short glosses, so global gloss uniqueness (the old 267-word
invariant) is impossible. But a matching **round** only ever co-displays words within one
frequency band — `matching.plan_rounds` stable-sorts the due set by `freq_band`
(`FREQ_BAND_SIZE = 30`) before chunking into rounds. So glosses only need to be unique
within any `FREQ_BAND_SIZE` window of the frequency-ordered deck (`vocab.band_collisions`;
quiz-side `test_no_ambiguous_round_band_scoped`). The 5k build had 4 residual near-synonym
collisions (每/各 "each", 力量/权力 "power", …), fixed with disambiguating tags → 0.

## CLI

```
deck-vocab                      # preview: clean/needs-LLM split (no writes)
deck-vocab --curate             # prepare needs-LLM chunk files for the adjudication pass
deck-vocab --build              # assemble committed curated rows → artifact (deterministic)
```

Committed data: `configs/vocab/chinese_common.{yaml,curated.jsonl,audit.jsonl,policy.md}`.
`build` reproduces the exact artifact shipped in `memory-quiz-app/data/decks/`.

## Extending to 10k

Raise `target_n`; re-run route → adjudicate the new needs-LLM words → rebuild. The seed +
existing curated rows stay frozen; only new words are adjudicated.
