# CLAUDE.md — memory-deck-generator

Generates Excel acronym-tables from Wikipedia/Wikidata sources (award laureates, poetry lines, monarch reigns, Shakespeare passages), and exports per-deck JSON artifacts (`deck-export` → `data/decks/`) consumed by the quiz app.

**The spaced-repetition quiz (FSRS-6 + PWA) lives in the separate `memory-quiz-app` repo** — split out via the `data/decks/*.json` artifact seam. This repo is generator-only; it never imports the quiz.

See [PRD.md](PRD.md) for pipeline configs, output format, and success criteria.

## Pipelines

| CLI | Source | Output |
|---|---|---|
| `deck-acronyms` | Wikidata SPARQL | Year-chunked laureate initials |
| `deck-poetry` | Project Gutenberg | Per-line acronyms |
| `deck-monarchs` | Wikidata SPARQL | Per-century transition-digit strings |
| `deck-artworks` | Wikidata SPARQL + Wikimedia Commons | Artwork title/creator/image → quiz `image-mc` deck (JSON + WebP assets) |
| `deck-shakespeare` | Folger Digital Texts API | YAML catalogue of monologue passages |
| `deck-equations` | Hand-curated YAML | Equation + verified corruption pool → quiz `error-spot` deck (MathML baked) |
| `deck-vocab` | wordfreq × CC-CEDICT (+ audited LLM adjudication of hard words) | Curated Chinese `matching` vocab deck (`source: manual`; committed out-of-band, not a full-export deck) |

## Modules

| Module | Role |
|---|---|
| `wikidata.py` | SPARQL client: `fetch_entries(item_id, humans_only)` + `count_laureates(item_id, humans_only)`. Skips bare Q-number labels. Gap warning computed before manual entry merging. |
| `chunker.py` | `make_chunks(entries, chunk_years, chunk_start_year, first_letter_only_from)` → `list[Chunk]`. Empty year windows omitted. |
| `acronym.py` | `name_initials`: skips particles, expands hyphenated tokens. `line_initials`: all words including particles. |
| `xlsx_writer.py` | `write_xlsx()` (awards), `write_poetry_xlsx()` (poetry), `write_monarchs_xlsx()` (monarchs). |
| `gutenberg.py` | HTTP fetch + cache in `cache/gutenberg/`. |
| `folger.py` | Folger Digital Texts API; caches HTML under `cache/folger/`. |
| `poetry_parser.py` | `extract_poem(text, start_marker, end_marker)` → `list[str \| None]`. `None` = blank line. |
| `monarchs.py` | `fetch_monarchs` (includes `wp_title` sitelink + `accession_precision`), `make_monarch_chunks`; deduplicates by person Q-number. `parse_corrections`/`correction_years` read the config's sourced `corrections:` block; `stale_corrections` reports ones upstream has made redundant; `report_imprecise_dates` flags sub-year-precision dates (documentation only — digits unaffected). |
| `artworks.py` | `fetch_artworks(config)` — Wikidata paintings by fame (`min_sitelinks`) / curated QIDs / collection (P195); dedup by QID; `build_query`. `Artwork(qid, title, creator, image_url, sitelinks, inception)`. |
| `equations.py` | LaTeX → MathML with per-token `id`s. `Equation`, `load_equations`, `to_mathml`, `token_texts`, `eligible_indices` (excludes delimiters/accents/differentials), `annotate`. |
| `corruptions.py` | Generated + verified single-token corruptions. `build_pool` → pool + `bad_pairs`; `differs` proves non-equivalence via **numeric sampling on the residue `a-b`** (never `simplify`, which hangs on infinite integrals; finite ops are `.doit()`'d, infinite/heavy residues rejected — see `equations-pipeline.md` "equivalence predicate"; fails closed; guards sympy's silent mis-parse of `\mathbf`/`\hat`/`\operatorname`); `_variable_tokens` swaps ASCII + whitelisted Greek variables (excludes `\pi`/operators); `classify` splits equations into 2-error / 1-error / drop by supportable pair count; `pool_warnings` flags thin pools. |
| `normalise.py` | Verification-only LaTeX rewrites so sympy can parse real notation (`\operatorname{Var}(X)`, `E[X^2]`, `P(A\mid B)`, bold vectors). `opaque_spans` marks argument lists where corruption is barred (`Var(X+Y)`→`Var(Y+X)` is an equivalence). Never displayed. |
| `equations_cli.py` | `deck-equations` — preview pool health + 2/1 classification per config; `--sample` prints a text two-error display; `--export` writes the artifact(s). |
| `vocab.py` | Chinese vocab pipeline: CC-CEDICT parse/`fetch_cedict` (CC-BY-SA), numbered→diacritic `pinyin_marks`, `load_seed` (freeze existing 267), `rank_candidates` + clean/needs-LLM router, `load_curated`, `band_collisions` (band-scoped uniqueness), `assemble_artifact`. |
| `vocab_cli.py` | `deck-vocab` — **preview** (clean/needs-LLM split) / **curate** (prepare needs-LLM chunk files for the audited adjudication pass) / **build** (assemble committed curated rows → `source: manual` artifact, deterministic; verifies no-dup-hanzi + band uniqueness). Committed data: `configs/vocab/chinese_common.{yaml,curated.jsonl,audit.jsonl,policy.md}`. See [docs/design/vocab-pipeline.md](docs/design/vocab-pipeline.md). |
| `distractors.py` | `build_choices(artworks, attr, n, same_creator_bias)` — deterministic (QID-seeded) MC options; same-creator/era bias; no duplicate values. |
| `artwork_images.py` | `fetch_raw` (Commons download, cached under `cache/artworks/`, UA-compliant — the CDN 403s placeholder UAs) + `to_webp` (Pillow downsize). |
| `country_registry.py` | `fetch_country_registry` via Wikidata P1906 → `CountryEntry` list; `save_registry`/`load_registry` YAML I/O. |
| `coverage.py` | `check_coverage`: compares Wikidata monarch sitelinks against Wikipedia list article links; returns `CoverageReport`. |
| `derive_positions.py` | `load_ruler_titles` filters xlsx/csv by occupation keywords; `fetch_positions_for_titles` batch-queries Wikidata P39 to rank position Q-IDs by holder count. |
| `cli.py` | `deck-acronyms` entry point. Supports `manual_entries` and `exclude_entries` config keys. |
| `poetry_cli.py` | `deck-poetry` entry point. Single-poem and multi-poem collection configs. |
| `monarchs_cli.py` | `deck-monarchs` entry point. Reads `wikipedia_list` field from config for coverage checks. |
| `registry_cli.py` | `deck-registry-generate` — queries Wikidata P1906, writes `configs/monarchs/country_registry.yaml`. |
| `coverage_cli.py` | `deck-coverage-check` — takes `--config` or `--country`/`--registry`; reports rulers in Wikipedia list missing from Wikidata fetch. |
| `derive_positions_cli.py` | `deck-derive-positions` — takes `--input` xlsx/csv + optional `--nationality`; prints ranked position Q-IDs for adding to YAML configs. |
| `shakespeare_cli.py` | `deck-shakespeare` entry point. |
| `artworks_cli.py` | `deck-artworks` entry point — previews a config (fetch + print, no image download) by default; `--export` writes the deck artifact + WebP assets via the export seam. |
| `list_parser.py` | Wikipedia wikitext → `[(year, name)]`. Unused by CLI; kept for potential future use. |
| `wiki_api.py` | MediaWiki API client. `fetch_article_links(title)` used by coverage checker. |
| `deck_export.py` | `deck-export` entry point — the generator→quiz boundary. Runs the generation pipeline and writes one self-contained JSON artifact per deck to `data/decks/` (`items`, `labels`, `config_hash`, …). Item strings are byte-identical to live generation, preserving deck ids and FSRS item keys (`sha256(item)[:16]`). Consumed by the `memory-quiz-app` repo. **A bare run CLEARS the output dir and rebuilds everything; use `--only <glob>` to refresh a subset** (leaves others untouched/unfetched and preserves their `order`/`config_path`). Artwork decks additionally emit WebP image files under `data/decks/assets/<deck>/` (cleared/rebuilt in lockstep). `source: manual` artifacts (e.g. the quiz's Chinese vocab deck — curated out-of-band by `deck-vocab`, not by `deck-export`) are **preserved through the clear** (`_is_manual`) — a full export has no config to rebuild them. |

## Award configs (31)

**Science:** `nobel_physics`, `nobel_economics`, `fields_medal` (chunk_years: 4, ICM-aligned), `abel_prize`, `turing_award`, `knuth_prize`, `godel_prize`, `ieee_von_neumann_medal`, `clay_research_award`, `dirac_medal`, `breakthrough_physics`, `breakthrough_life_sciences`, `kavli_astrophysics`, `ramanujan_prize`, `priestley_medal`, `crafoord_prize`, `wolf_physics`, `wolf_chemistry`, `wolf_mathematics`, `lasker_basic_medical`, `gairdner_award`, `john_bates_clark_medal`

**Literature:** `nobel_literature`, `booker_prize`, `man_booker_international`, `pulitzer_fiction`, `national_book_award_fiction`, `prix_goncourt`, `franz_kafka_prize`

**Human rights:** `sakharov_prize`, `right_livelihood_award`

## Key implementation notes

- Monarch transition years: every accession year, plus any end year that is not itself an accession year (throne didn't pass directly to a successor) — covers Wikidata coronation-lag, interregnum starts, and dynasty terminal years
- Monarch config corrections (`corrections:`) require `reason` + `source`; add is idempotent so an upstream Wikidata fix can't double a digit. `accession_precision` is recorded and warned on but never affects digits — see PRD
- Monarch coverage workflow: (1) `deck-registry-generate` → `country_registry.yaml`; (2) add `wikipedia_list` field to config; (3) `deck-coverage-check --config <yaml>` reports gaps; (4) `deck-derive-positions --input politicians_rulers.xlsx` suggests position Q-IDs for historical polities not covered by P1906
- `Monarch.wp_title` is fetched via SPARQL sitelinks (`schema:isPartOf <https://en.wikipedia.org/>`); used as join key by coverage checker
- Folger API responses cached under `cache/folger/`; segments under `cache/folger/segments/`
- Excel output: two sheets — Detail (one row per entry) + Summary (one row per chunk)
- Equation decks (`configs/equations/{statistics,physics,mathematics,computer_science}.yaml`, **1301 total since the 2026-07-23 expansion** — math 332, physics 310, stats 329, CS 330): the `item` is the canonical LaTeX, so retuning the corruption engine, retiring a type, or an equation moving between the 2-error/1-error decks never strands FSRS history (unlike the monarch end-year change). Corruptions are generated, equations are curated (the big set was LLM-drafted → sympy-verified → correctness-audited — see equations-pipeline.md "Expansion pipeline"). One config → two decks (2-error / 1-error, split by `classify`), disambiguated by `poem_title`. `normalise.py` unlocked real notation (`P(A\mid B)`, `\operatorname{Var}`); vector calculus (`\nabla \times`) still fails closed. `differs` now verifies by **numeric sampling on the residue** (not `simplify`, which hangs on infinite integrals). **Pool cache**: `deck_export` persists verified pools to `cache/equation_pools.json` keyed by `sha256(latex+types+pool_size+_POOL_ENGINE_VERSION)` — re-export is near-instant; **bump `_POOL_ENGINE_VERSION` when `corruptions.py`/`normalise.py` change** or it serves stale pools. Building a fresh full field's pools is sympy-heavy (~5–20 min) and can hang on a pathological equation — warm the cache fork-isolated (a per-equation hard timeout) rather than trusting a bare `deck-export`. **LLM-recovered pools**: equations sympy can't verify (boolean/set/info-theory/matrix notation) get corruptions from a committed sidecar `configs/equations/llm_pools.json` (LLM-generated + 2-skeptic adversarially-verified, provenance `llm`, 1-error only) that `_equation_rows` reads BEFORE `build_pool` and forces `kind='one'` — engine-version-independent. See [docs/design/equations-pipeline.md](docs/design/equations-pipeline.md)
- `results/` is gitignored; long-term xlsx storage is local in-repo
