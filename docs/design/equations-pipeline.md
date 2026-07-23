# Design — Equations error-spot pipeline (`deck-equations`)

Status: **built and in use** — generator + desktop/web quiz surfaces. Live decks: Statistics
(10 equations), Physics (6), Mathematics (4) — 20 cards across the Equations group. **The PWA
surface and `study.json` gate opt-in are not yet built.**

## Goal

Study equations the way the poetry decks study verse: render the equation with a fixed number
of tokens silently corrupted and ask which ones are wrong. Error detection gives recall-grade
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
| `corruptions.py` | Taxonomy span generators (incl. Greek-aware `_variable_tokens`), `apply_spans`, `differs` (the equivalence predicate), `build_pool` (pool + `bad_pairs`), `classify` (2/1/drop split), `pool_warnings`/`valid_pairs` (health). |
| `normalise.py` | Verification-only LaTeX rewrites (real notation → sympy-parsable) + `opaque_spans`. Never displayed. |
| `equations_cli.py` | `deck-equations` — preview pool health per config, `--sample` renders a two-error display as text, `--export` writes the artifact(s). |
| `deck_export.py` | `_build_equation_deck` (per-variant) + `_equation_rows` (cached pools) — the export seam; one config → 2-error/1-error decks. |

Configs: `configs/equations/{statistics,physics,mathematics}.yaml`.

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

## Notation normalisation (`normalise.py`)

Verification parses a **rewritten** form; the displayed MathML always comes from the
original LaTeX, so the rewrite never reaches the user and can be as ugly as needed.

| Rewrite | Why |
|---|---|
| `\mathbf{E}`, `\mathrm`, `\boldsymbol` → `E` | Formatting, no mathematical content. |
| `\hat{H}` → `Hhat`, `\bar{x}` → `xbar` | An operator or estimate is *not* the plain symbol — fold the accent into the name to keep them distinct. |
| `\operatorname{Var}(X)` → `Var(X)` | sympy then reads a function application, and correctly sees `Var(X+Y) == Var(Y+X)`. |
| `E[X^2]` → `E(X^2)` | Square brackets parse as a list; parentheses keep `E[X^2]` and `E[X]^2` distinct. |
| `P(A\mid B)` → `P(A, B)` | A bare `\|` parses as absolute value. An ordered argument list loses the "given" reading but preserves the only thing verification needs: `P(A\|B) ≠ P(B\|A)`. |

**Opaque regions.** Argument lists are reported by `opaque_spans` and corruption is barred
inside them. `Var(X+Y)` → `Var(Y+X)` is a true equivalence; barring edits there makes that
whole class of false-corruption unreachable rather than relying on the CAS to catch each one.

## Taxonomy (v1)

| Type | Applies to | Note |
|---|---|---|
| `sign_flip` | binary `+`/`−` | Not catchable by dimensional analysis — stays useful longest. |
| `exponent_off_by_one` | integer exponents | Dimensionally detectable; retirement candidate. |
| `constant_perturb` | standalone integer coefficients | Broad applicability. |
| `variable_swap` | single-letter variables **and whitelisted Greek macros** | Reuses an in-equation symbol so the result stays plausible. Macro-aware: `mc` is m·c (two variables); `\sigma`/`\lambda`/`\mu` are single Greek variables; `\pi` and operator macros (`\sum`, `\int`) are excluded. |

Two types were not enough: with only `sign_flip` + `exponent_off_by_one`, **1 of 6** sample
equations could produce a two-error display (`E = mc^2` yielded two corruptions on the *same*
token, so its only pair was self-blocked). Adding `constant_perturb` + `variable_swap` took it
to 5/6; adding **Greek-letter support** to `variable_swap` reached 10/10 on `statistics.yaml`
and revived `Var(X)=\lambda` (Greek-plus-one-variable was all it had, so it was previously
dropped). `_variable_tokens` is the scanner — it emits ASCII letters and whitelisted single
Greek macros as swap candidates, skipping operator-name arguments (`\operatorname{Var}` →
never corrupt the `a` in "Var").

## Artifact schema

Parallel arrays, positionally aligned with `items`, matching the artworks `choices` idiom:

```json
{ "deck_type": "equations", "mode": "error-spot",
  "title": "Statistics — Core Formulas (2 errors)",
  "poem_title": "2 errors", "n_wrong": 2,
  "items":  ["Z = \\frac{x-\\mu}{\\sigma}"],
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
- `n_wrong` is the deck's fixed error count (see the deck split below); `poem_title`
  (`"2 errors"`/`"1 error"`) disambiguates a config's two decks, like a collection's poems.

Sampling is unseeded and per-showing (like poetry), so these never need to be byte-stable;
unlike artwork `choices`, they don't participate in the key.

## Fixed-count deck split (2-error / 1-error)

Rather than varying the error count per showing, each **equation** is classified by how many
distinct two-error displays its pool supports, and a config emits **two decks**:

- `classify(pool, bad_pairs)` → `'two'` (≥3 valid pairs), `'one'` (usable pool, fewer pairs),
  or `'drop'` (no verified corruption — warned, e.g. a two-token identity).
- The `'two'` equations form a **2-error deck** (`n_wrong: 2`), the `'one'` a **1-error deck**
  (`n_wrong: 1`); a variant with no qualifying equations yields no deck.
- Splitting by *supportable* count keeps difficulty honest: a 2-error card whose pool can't
  vary would repeat the same two positions, teaching positions rather than the formula. The
  ≥3-pair threshold is the same number `pool_warnings` uses for "positions will repeat".
- One config → two decks disambiguated by `poem_title`, exactly like a poetry collection's
  poems. Pools are computed **once per config** (cached) across the two variant slots.

Because `item_key` is the canonical LaTeX, an equation that later moves between the two decks
(its pool grew or shrank) **keeps its FSRS history** — the move changes only which deck lists it.

## Quiz-side (built — in `memory-quiz-app`)

- **Display** (`equations.py`): `make_equation_display(mathml, pool, bad_pairs, n_wrong)`
  samples `n_wrong` corruptions on distinct tokens (respecting `bad_pairs` for pairs) and
  swaps their *text* in the baked MathML — never re-rendering, never wrapping, so clean and
  corrupted markup are structurally identical. Degrades downward if retirement thins a pool.
- **Scoring**: `score_response` is reused **verbatim** — it is pure set arithmetic over 1-based
  indices with missed/false-alarm feedback; only a `noun='token'` parameter was added so
  feedback reads "token" not "word". The display encoding differs from poetry's `"{i+1}:{text}"`
  strings (rendered math needs per-token DOM ids), but the *scoring contract* is unchanged.
- **Rating** (`srs.py`): `error-spot` rates on **correctness only** — a slow correct answer is
  a good answer; rating on latency would train skimming.
- **Retirement** (`retirement.py` + `config/retired_corruptions.json`): `retired_types` (global)
  + per-`item_key` `retired_ids`, filtered out of the pool before display. Lives in the quiz
  repo, **not the artifact**, so a bare `deck-export` (which clears the output dir) can't wipe it.
- **Review on miss** (`equation_routes.py`): a wrong answer holds on the card and renders the
  **correct** equation with the missed tokens highlighted (via `highlight_tokens` on the clean
  MathML) until the user clicks Continue. The SRS review is recorded at submit time regardless —
  only the UI pauses. Server-side gate (`session['e_review']` + `action=continue`), so it
  behaves identically across desktop / web / PWA without client-side modal state.
- **Instrumentation**: each attempt records the shown corruptions' `id:type` in the existing
  `display_text` column — the only trace of what was asked, and what makes "which types are too
  obvious" answerable later.

## Health guards

`pool_warnings` flags what would otherwise be silent:

- **no valid two-error pair** → card unusable (e.g. `V = L`: a two-token equation cannot host
  two errors; every swap yields `L = L` or `V = V`, correctly rejected as equivalent)
- **fewer than 3 distinct pairs** → token positions will repeat, teaching positions not formulas
- **all one type** → one trick to learn

Never padded: an equation with fewer survivors ships with fewer, mirroring `build_choices`.

## Open questions / risks

1. ~~**Verifiable notation vs. real notation.**~~ **Resolved** by `normalise.py` — a
   verification-only rewrite layer (see below). `statistics.yaml` now carries real notation
   (`\operatorname{Var}(X) = E[X^2] - (E[X])^2`, `P(A\mid B) = …`) and **10/10 equations are
   usable**, including `\operatorname{Var}(X) = \lambda`, which had pool=0 as a stand-in.
   Vector calculus (`\nabla \times`) still fails closed — textual rewriting cannot give
   sympy vector algebra — so physics remains gated on pinning or hand-authoring.
2. ~~**Always exactly two.**~~ **Resolved** by the fixed-count deck split (above): equations are
   partitioned into 2-error and 1-error decks by supportable count, and the "No errors" button
   was removed (a plain Submit with nothing selected still scores a clean card correct). A deck
   with a fixed count still allows hunt-for-N, but each card is guaranteed enough pool variety
   not to repeat positions — the honest-difficulty tradeoff we chose over per-showing variance.
3. **Touch targets** — superscripts are tiny tap targets on a phone; generous padding risks
   overlapping hit areas in dense expressions. Untested; prototype before building the PWA
   (the desktop/web surfaces are built; **the PWA surface is not**).
4. **`variable_swap` can produce visually repeated tokens** (`M = np` → `M = M M`, Ohm's law
   `V = IR` → `V = V·V`), spottable without knowing the formula — inherent to thin
   variable-only pools. Not yet mitigated; could block pairs that introduce duplicate tokens.
5. **Which types are too obvious** is deliberately an empirical question — hence per-type and
   per-id retirement, and the `id:type` record now written to `attempts.display_text`.
6. **Opaque regions are conservative.** An edit inside an argument list is barred even when
   `differs` would catch any equivalence (so `Var(X)=\lambda` yields only the RHS swap → the
   1-error deck). Loosening this per-corruption-type is possible but risks the false-corruption
   class the bar prevents; deferred.

## Non-goals (v1)

- Structural corruptions (see decision 2).
- Extraction of equations from Wikipedia (see decision 1); the `source:` mode switch leaves
  the door open.
- Proof or derivation study — this mode tests the statement, not the reasoning.
