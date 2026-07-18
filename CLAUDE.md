# CLAUDE.md — wiki-acronym-tables

Generates Excel acronym-tables from Wikipedia/Wikidata sources (award laureates, poetry lines, monarch reigns, Shakespeare passages), and exports per-deck JSON artifacts (`wiki-export-decks` → `data/decks/`) consumed by the quiz app.

**The spaced-repetition quiz (FSRS-6 + PWA) lives in the separate `memory-quiz-app` repo** — split out via the `data/decks/*.json` artifact seam. This repo is generator-only; it never imports the quiz.

See [PRD.md](PRD.md) for pipeline configs, output format, and success criteria.

## Pipelines

| CLI | Source | Output |
|---|---|---|
| `wiki-acronym-tables` | Wikidata SPARQL | Year-chunked laureate initials |
| `wiki-poetry` | Project Gutenberg | Per-line acronyms |
| `wiki-monarchs` | Wikidata SPARQL | Per-century transition-digit strings |
| `wiki-shakespeare` | Folger Digital Texts API | YAML catalogue of monologue passages |

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
| `country_registry.py` | `fetch_country_registry` via Wikidata P1906 → `CountryEntry` list; `save_registry`/`load_registry` YAML I/O. |
| `coverage.py` | `check_coverage`: compares Wikidata monarch sitelinks against Wikipedia list article links; returns `CoverageReport`. |
| `derive_positions.py` | `load_ruler_titles` filters xlsx/csv by occupation keywords; `fetch_positions_for_titles` batch-queries Wikidata P39 to rank position Q-IDs by holder count. |
| `cli.py` | `wiki-acronym-tables` entry point. Supports `manual_entries` and `exclude_entries` config keys. |
| `poetry_cli.py` | `wiki-poetry` entry point. Single-poem and multi-poem collection configs. |
| `monarchs_cli.py` | `wiki-monarchs` entry point. Reads `wikipedia_list` field from config for coverage checks. |
| `registry_cli.py` | `wiki-registry-generate` — queries Wikidata P1906, writes `configs/monarchs/country_registry.yaml`. |
| `coverage_cli.py` | `wiki-coverage-check` — takes `--config` or `--country`/`--registry`; reports rulers in Wikipedia list missing from Wikidata fetch. |
| `derive_positions_cli.py` | `wiki-derive-positions` — takes `--input` xlsx/csv + optional `--nationality`; prints ranked position Q-IDs for adding to YAML configs. |
| `shakespeare_cli.py` | `wiki-shakespeare` entry point. |
| `list_parser.py` | Wikipedia wikitext → `[(year, name)]`. Unused by CLI; kept for potential future use. |
| `wiki_api.py` | MediaWiki API client. `fetch_article_links(title)` used by coverage checker. |
| `deck_export.py` | `wiki-export-decks` entry point — the generator→quiz boundary. Runs the generation pipeline and writes one self-contained JSON artifact per deck to `data/decks/` (`items`, `labels`, `config_hash`, …). Item strings are byte-identical to live generation, preserving deck ids and FSRS item keys (`sha256(item)[:16]`). Consumed by the `memory-quiz-app` repo. **A bare run CLEARS the output dir and rebuilds everything; use `--only <glob>` to refresh a subset** (leaves others untouched/unfetched and preserves their `order`/`config_path`). Hand-authored `source: manual` artifacts (e.g. the quiz's Chinese vocab deck) are **preserved through the clear** (`_is_manual`) — the generator has no config to rebuild them from. |

## Award configs (31)

**Science:** `nobel_physics`, `nobel_economics`, `fields_medal` (chunk_years: 4, ICM-aligned), `abel_prize`, `turing_award`, `knuth_prize`, `godel_prize`, `ieee_von_neumann_medal`, `clay_research_award`, `dirac_medal`, `breakthrough_physics`, `breakthrough_life_sciences`, `kavli_astrophysics`, `ramanujan_prize`, `priestley_medal`, `crafoord_prize`, `wolf_physics`, `wolf_chemistry`, `wolf_mathematics`, `lasker_basic_medical`, `gairdner_award`, `john_bates_clark_medal`

**Literature:** `nobel_literature`, `booker_prize`, `man_booker_international`, `pulitzer_fiction`, `national_book_award_fiction`, `prix_goncourt`, `franz_kafka_prize`

**Human rights:** `sakharov_prize`, `right_livelihood_award`

## Key implementation notes

- Monarch transition years: every accession year, plus any end year that is not itself an accession year (throne didn't pass directly to a successor) — covers Wikidata coronation-lag, interregnum starts, and dynasty terminal years
- Monarch config corrections (`corrections:`) require `reason` + `source`; add is idempotent so an upstream Wikidata fix can't double a digit. `accession_precision` is recorded and warned on but never affects digits — see PRD
- Monarch coverage workflow: (1) `wiki-registry-generate` → `country_registry.yaml`; (2) add `wikipedia_list` field to config; (3) `wiki-coverage-check --config <yaml>` reports gaps; (4) `wiki-derive-positions --input politicians_rulers.xlsx` suggests position Q-IDs for historical polities not covered by P1906
- `Monarch.wp_title` is fetched via SPARQL sitelinks (`schema:isPartOf <https://en.wikipedia.org/>`); used as join key by coverage checker
- Folger API responses cached under `cache/folger/`; segments under `cache/folger/segments/`
- Excel output: two sheets — Detail (one row per entry) + Summary (one row per chunk)
- `results/` is gitignored; long-term xlsx storage is local in-repo
