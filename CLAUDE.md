# CLAUDE.md — wiki-acronym-tables

Generates Excel acronym-tables from Wikipedia/Wikidata sources (award laureates, poetry lines, monarch reigns, Shakespeare passages). Includes a spaced-repetition CLI quiz using FSRS-6 and the blindman's bluff recall method.

See [PRD.md](PRD.md) for pipeline configs, output format, quiz mode design rationale, FSRS-6 parameters, and success criteria.

## Pipelines

| CLI | Source | Output |
|---|---|---|
| `wiki-acronym-tables` | Wikidata SPARQL | Year-chunked laureate initials |
| `wiki-poetry` | Project Gutenberg | Per-line acronyms |
| `wiki-monarchs` | Wikidata SPARQL | Per-century transition-digit strings |
| `wiki-shakespeare` | Folger Digital Texts API | YAML catalogue of monologue passages |

## Quiz

- **Method**: blindman's bluff — first letter of each word shown, remaining as underscores, one random non-first letter revealed
- **SRS**: FSRS-6 with per-mode rating thresholds and lapse behavior
- **Interface**: Flask web app

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
| `monarchs.py` | `fetch_monarchs`, `make_monarch_chunks`; deduplicates by person Q-number. |
| `quiz.py` | Blindman's bluff display + health-bar scoring. Three modes: words / acronym / digits. |
| `srs.py` | FSRS-6 card state + due-order scheduling. |
| `logger.py` | SQLite event log (`sessions`, `attempts`, `srs_state`). `FORMAT_VERSIONS` must be bumped manually on display changes. |
| `web_app.py` | Flask routes + Jinja templates. Timer, session infobox, phase badge. |
| `cli.py` | `wiki-acronym-tables` entry point. Supports `manual_entries` and `exclude_entries` config keys. |
| `poetry_cli.py` | `wiki-poetry` entry point. Single-poem and multi-poem collection configs. |
| `monarchs_cli.py` | `wiki-monarchs` entry point. |
| `web_cli.py` | `wiki-quiz-web` entry point. |
| `monarchs_web_cli.py` | `wiki-quiz-monarchs-web` entry point. |
| `shakespeare_cli.py` | `wiki-shakespeare` entry point. |
| `list_parser.py` | Wikipedia wikitext → `[(year, name)]`. Unused by CLI; kept for potential future use. |
| `wiki_api.py` | Vendored MediaWiki API client. Unused by CLI. |
| `api.py` | Flask Blueprint: `GET /api/decks`, `GET /api/deck/<id>/content`, `POST /api/sync`, `GET /pwa/*` static files. Registered in `desktop_app.py`. |
| `deck_loader.py` | `DeckInfo`, `discover_decks()`, `load_poetry_deck()`, `load_monarchs_deck()`. Used by desktop app and API. |
| `server.py` | WSGI entry point for Fly.io: reads `PORT`/`DB_PATH`/`CONFIG_DIR` env vars; `create_app()` factory for gunicorn. Run locally with `python server.py`. |

## PWA modules (`pwa/`)

| File | Role |
|---|---|
| `srs.js` | Port of `srs.py` — `SRSScheduler` class using `ts-fsrs`; preserves all custom modifications (learning→graduated→FSRS state machine, lapse forgiveness, interval cap). |
| `quiz.js` | Port of `quiz.py` — blindman's bluff display generators and scorers for all three modes. |
| `itemKey.js` | SHA-256 item key via Web Crypto API, produces identical output to Python `hashlib.sha256().hexdigest()[:16]`. |
| `db.js` | IndexedDB wrapper: `getCard`/`saveCard`/`countIntroducedToday` (SRSScheduler interface) + `getAllCards`/`putCard` (sync) + deck/deck-list cache. |
| `sync.js` | Last-write-wins sync engine: POSTs local IndexedDB state to `/api/sync`, merges server response back. |
| `sw.js` | Service worker: cache-first for `/pwa/*` static assets, network-only for `/api/*`. Exports `handleInstall`/`handleActivate`/`handleFetch` for testing; SW registration guard (`typeof self !== 'undefined'`) prevents Node import errors. |
| `srs.bundle.js` | esbuild bundle of `srs.js` + `ts-fsrs` for browser use (committed; rebuild with `npm run build` if `srs.js` changes). |
| `index.html` | Deck picker: fetches `/api/decks`, groups by collection, falls back to IndexedDB cache offline. |
| `quiz.html` | Quiz UI: touch chip selection for wrong positions, health bar, live timer, answer reveal, auto-sync on completion. |
| `manifest.json` | PWA manifest — enables "Add to Home Screen" on iPhone. Scope: `/pwa/`. |
| `sw.js` | Service worker for offline caching. Registered from `index.html`. |

**To install on iPhone:** open `http://<LAN-IP>:5001/pwa/` in Safari → Share → Add to Home Screen.

**Tests:** `pwa/tests/` — 98 vitest tests covering quiz display, SRS state machine, IndexedDB wrapper, sync engine (incl. conflict edge cases), service worker handler logic, and Python↔JS parity.

## Award configs (31)

**Science:** `nobel_physics`, `nobel_economics`, `fields_medal` (chunk_years: 4, ICM-aligned), `abel_prize`, `turing_award`, `knuth_prize`, `godel_prize`, `ieee_von_neumann_medal`, `clay_research_award`, `dirac_medal`, `breakthrough_physics`, `breakthrough_life_sciences`, `kavli_astrophysics`, `ramanujan_prize`, `priestley_medal`, `crafoord_prize`, `wolf_physics`, `wolf_chemistry`, `wolf_mathematics`, `lasker_basic_medical`, `gairdner_award`, `john_bates_clark_medal`

**Literature:** `nobel_literature`, `booker_prize`, `man_booker_international`, `pulitzer_fiction`, `national_book_award_fiction`, `prix_goncourt`, `franz_kafka_prize`

**Human rights:** `sakharov_prize`, `right_livelihood_award`

## Key implementation notes

- Wikidata gap-fill for monarchs: when a monarch's end year ≠ next accession year, end year is inserted as fallback event (corrects known Wikidata lag)
- Folger API responses cached under `cache/folger/`; segments under `cache/folger/segments/`
- Excel output: two sheets — Detail (one row per entry) + Summary (one row per chunk)
- `results/` is gitignored; long-term xlsx storage is local in-repo
