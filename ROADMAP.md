# Roadmap

## Done
- [x] Core acronym logic (name initials, particles, hyphenated names)
- [x] Award laureates pipeline — 31+ configs, Wikidata SPARQL backend
- [x] Poetry pipeline — Gutenberg fetch, multi-poem collections
- [x] Monarchs pipeline — per-century transition-digit strings, parent lineage
- [x] Excel output — detail + summary sheets, chunk highlighting
- [x] Flask quiz app — blindman's bluff, words/acronym/digits modes, health bar, SRS infobox
- [x] FSRS-6 SRS scheduler — learning steps, graduated ramp, relearning, forgiveness params
- [x] Quiz event logger — SQLite sessions/attempts/srs_state tables
- [x] Shakespeare pipeline — Folger API, monologue catalogue
- [x] Desktop app — PyWebView + Anki-style deck picker, macOS .app bundle with custom icon
- [x] PWA Phase 1 — JS ports of `quiz.py` and `srs.py` (ts-fsrs, full custom state machine); 82-test suite with Python↔JS parity fixture
- [x] PWA Phase 2 — Flask `/api` Blueprint: `GET /api/decks`, `GET /api/deck/<id>/content`, `POST /api/sync` (last-write-wins); CORS headers; 16 tests
- [x] PWA Phase 3 — Offline-capable iPhone PWA: IndexedDB (`db.js`), sync engine (`sync.js`), service worker (`sw.js`), manifest + icons, deck picker (`index.html`), touch quiz UI (`quiz.html`); Flask serves `/pwa/*` static files

## Planned

- [x] PWA Phase 4 — Fly.io deployment: `Dockerfile`, `fly.toml` (256MB shared-cpu, persistent `/data` volume, auto-stop), `server.py` WSGI entry point; `pywebview` moved to optional `[desktop]` extra; `gunicorn` added as `[server]` extra
- [x] PWA Phase 5 — Desktop remote mode: `QUIZ_URL` env var in `desktop_app.main()` opens PyWebView window on hosted server instead of starting local Flask
- [x] PWA Phase 6 — Integration testing and hardening: `sw.js` refactored to export `handleInstall`/`handleActivate`/`handleFetch`; 13 SW tests (cache versioning, install, activate purge, fetch routing); 4 sync conflict edge cases (identical timestamps, two-client LWW, other-device cards, mixed newer/older); 5 Python API edge cases (identical timestamps, two-client conflict, missing/invalid body, full state returned); total 98 JS + 21 API tests

### Near-term
- [ ] README with install/usage examples (including PWA install instructions)
- [ ] CI: run pytest + vitest on push
- [ ] Validate all 31 award configs in CI (smoke test, not full fetch)
- [ ] `--dry-run` flag: print chunk acronyms without writing xlsx

### Medium-term
- [ ] `list_parser.py` integration — wire Wikipedia wikitext table source into a pipeline
- [ ] Batch mode: run all configs in a directory with one command
- [ ] Configurable output formatting (column widths, color themes)

### Long-term
- [ ] Additional data sources (DBpedia, OpenLibrary)
- [ ] CSV output option alongside xlsx
- [ ] Interactive config generator (wizard CLI)
