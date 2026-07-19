# Design — Equations error-spot pipeline (`deck-equations`)

Status: **vertical slice built** (generator side only). Quiz-side display/scoring not started.

## Goal

Study equations the way the poetry decks study verse: render the equation with exactly two
tokens silently corrupted and ask which ones are wrong. Error detection gives recall-grade
difficulty with no typing — you cannot type LaTeX fast enough for a daily drill, and
"recall the Cauchy–Schwarz inequality" has no short typeable answer. It is also close to a
real skill: spotting a wrong exponent or a flipped sign is what sanity-checking is.

Target fields: mathematics, statistics, physics, computer science.

## Locked decisions

1. **Equations are curated; corruptions are generated.** An article's wikitext holds every
   `<math>` on the page — derivation steps, special cases, notation asides — with nothing
   marking which is *the* formula. That choice stays human. The mechanical work (finding
   candidate errors, proving them wrong) is automated.
2. **A corruption is a single-token substitution.** `{id, i, to, type}`, applied by the
   client swapping one token's text in the already-rendered MathML. Consequence: structural
   errors (swapped numerator/denominator, dropped factor, changed limits) are **out of
   scope** — they don't map to one token index.
3. **Baked MathML, not client-side rendering.** `latex2mathml` at export; the client injects
   the string. No math library in the PWA (offline for free), and no Python↔JS rendering
   parity to maintain. Costs some typography versus KaTeX.
4. **Markup is identical for clean and corrupted tokens.** Corruption swaps *text*, never
   wraps. Wrapping only the wrong tokens would leak the answer through the DOM and through
   renderer spacing.
5. **The `item` is the canonical LaTeX**, so `item_key = sha256(item)[:16]` depends on the
   equation alone. The engine can be retuned and types retired with **no stranded FSRS
   history** — deliberately unlike the monarch decks, where a generator behaviour change
   rewrote items and orphaned review history (see the quiz PRD's "Recovering stranded
   history").
6. **Verification fails closed.** A corruption ships only if sympy *proves* it differs.

## Pipeline modules (`src/deck_generator/`)

| Module | Role |
|---|---|
| `equations.py` | `Equation` dataclass, `load_equations`, `to_mathml`, `token_texts`, `eligible_indices`, `annotate` (adds `id="tok-N"`). |
| `corruptions.py` | Taxonomy span generators, `apply_spans`, `differs` (the equivalence predicate), `build_pool` (pool + `bad_pairs`), `pool_warnings`/`valid_pairs` (health). |
| `equations_cli.py` | `deck-equations` — preview pool health per config, `--sample` renders one two-error display as text, `--export` writes the artifact. |
| `deck_export.py` | `_build_equation_deck` — the export seam. |

### Why the token index is *derived*, not assumed

Candidates are generated on the **LaTeX** (what sympy can verify) but the quiz needs a
**MathML token index**. Rather than tracking source spans through the conversion, a
candidate is applied, re-converted, and its token list diffed against the clean one. Exactly
one differing position → that's the index and the replacement. Zero or several → rejected.
The index and the verification therefore cannot disagree about which token changed.

## The equivalence predicate (`differs`)

Compares `lhs - rhs` **up to a nonzero constant factor**, so negating both sides reads as
equivalent — as it must, being the same equation. A naive expression subtraction gets this
wrong and would ship a false corruption.

Returns False (reject) on anything unparseable, mis-parsed, or inconclusive — discarding a
possibly-good corruption rather than risking a "mistake" the user is correct not to find.

**sympy's LaTeX parser does not raise on unknown notation.** `\mathbf`, `\hat`,
`\operatorname`, `\pm`, `\nabla` become ordinary free symbols and the parse "succeeds" with
a wrong expression. Fail-closed-on-exception is therefore not enough; `_MISPARSE_MARKERS`
positively checks for those invented symbols.

Verified against the traps (all correctly judged equivalent, i.e. rejected):
commutative reorder `ma`→`am`, operand reorder, bound-variable rename, algebraic
restatement `a/b`→`ab⁻¹`, negation of both sides.

## Taxonomy (v1)

| Type | Applies to | Note |
|---|---|---|
| `sign_flip` | binary `+`/`−` | Not catchable by dimensional analysis — stays useful longest. |
| `exponent_off_by_one` | integer exponents | Dimensionally detectable; retirement candidate. |
| `constant_perturb` | standalone integer coefficients | Broad applicability. |
| `variable_swap` | single-letter variables | Reuses an in-equation symbol so the result stays plausible. Macro-aware: `mc` is m·c, two variables, while `\sigma` is one macro. |

Two types were not enough: with only `sign_flip` + `exponent_off_by_one`, **1 of 6** sample
equations could produce a two-error display (`E = mc^2` yielded two corruptions on the *same*
token, so its only pair was self-blocked). Adding the latter two took it to 5/6.

## Artifact schema

Parallel arrays, positionally aligned with `items`, matching the artworks `choices` idiom:

```json
{ "deck_type": "equations", "mode": "error-spot",
  "items":  ["Z = \\frac{x-M}{S}"],
  "labels": ["Z-score"],
  "mathml": ["<math …><mi id=\"tok-1\">Z</mi>…</math>"],
  "pool":   [[{"id": "581f51", "i": 4, "to": "+", "type": "sign_flip"}]],
  "bad_pairs": [[["b8e569", "f2da61"]]] }
```

- `i` is **1-based into eligible (clickable) tokens**, matching `tok-N` and the quiz's
  `wrong_tokens`, whose scoring is pure set arithmetic over those indices.
- `id = sha256("{i}|{to}|{type}")[:6]` — content-derived, so an unchanged corruption keeps
  its id across re-exports. Retirement config and `bad_pairs` both reference ids, never pool
  positions, which are not stable across regeneration.
- `bad_pairs` is a sparse blocklist (most pairs are fine): overlapping edits, and pairs whose
  two corruptions cancel back into a true equation. **The pairwise check is load-bearing** —
  the quiz shows exactly two, and each would pass a solo check.
- No `assets/` — MathML is inline, so unlike artworks there is no second sync path.

Sampling is unseeded and per-showing (like poetry), so these never need to be byte-stable;
unlike artwork `choices`, they don't participate in the key.

## Quiz-side contract (not yet built)

`score_response` in the quiz is **content-agnostic** — pure set arithmetic over 1-based
indices, with missed vs. false-alarm feedback. An equation display returning `LineDisplay`
with `wrong_tokens` reuses it verbatim. What must be new is the *display encoding*: poetry
emits `"{i+1}:{text}"` strings, which can't work for rendered math. Retirement lives in the
quiz repo (`retired_types` + per-id `retired_ids`), not the artifact, so a bare re-export
can't wipe it.

## Health guards

`pool_warnings` flags what would otherwise be silent:

- **no valid two-error pair** → card unusable (e.g. `V = L`: a two-token equation cannot host
  two errors; every swap yields `L = L` or `V = V`, correctly rejected as equivalent)
- **fewer than 3 distinct pairs** → token positions will repeat, teaching positions not formulas
- **all one type** → one trick to learn

Never padded: an equation with fewer survivors ships with fewer, mirroring `build_choices`.

## Open questions / risks

1. **Verifiable notation vs. real notation — the central tension.** sympy cannot parse the
   notation the good formulas are written in: `P(A|B)`, `\operatorname{Var}(X)`,
   `E[X^2]`, vector calculus. The v1 `statistics.yaml` works around this with single-letter
   stand-ins (`P = \frac{L Q}{M}` for Bayes), which **verify cleanly but are not the
   formulas worth memorising**. Options: accept stand-ins, pin notation-heavy equations and
   hand-author their corruptions, or add a notation-normalising layer that maps real
   notation to a sympy-parsable form for verification only. **Unresolved, and it gates
   whether physics is viable at all** (`\nabla \times \mathbf{E}` yields pool=0).
2. **Always exactly two** lets you hunt until you find two and stop. Varying 0–3 would force
   genuine evaluation; the `LineDisplay` contract already supports a zero-error case. Decide
   from practice.
3. **Touch targets** — superscripts are tiny tap targets on a phone; generous padding risks
   overlapping hit areas in dense expressions. Untested; prototype before building the PWA.
4. **`variable_swap` can produce visually repeated tokens** (`M = np` → `M = M M`), which is
   spottable without knowing the formula. Consider blocking pairs that introduce duplicates.
5. **Which types are too obvious** is deliberately an empirical question — hence per-type and
   per-id retirement, and the `attempts` type tag the quiz side must record.

## Non-goals (v1)

- Structural corruptions (see decision 2).
- Extraction of equations from Wikipedia (see decision 1); the `source:` mode switch leaves
  the door open.
- Proof or derivation study — this mode tests the statement, not the reasoning.
