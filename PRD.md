# PRD — memory-deck-generator

## Problem
Memorizing ordered lists (award laureates, poem lines, historical rulers) is hard. Acronym mnemonics help, but generating them from authoritative sources is tedious.

## Goal
Generate Excel acronym-tables and per-deck JSON artifacts from Wikipedia/Wikidata sources automatically, grouped by configurable time windows. The spaced-repetition **quiz app now lives in a separate repo** (`memory-quiz-app`, see its PRD); this repo is generator-only and emits `data/decks/*.json` consumed by the quiz via the orchestrator's Dagster `decks` asset.

### Refreshing decks (`deck-export`)

A bare run **clears the output directory** and rebuilds every deck — authoritative, but it renumbers `order` and re-stamps `config_path` from the running checkout. Both are *identity*, not content: `config_path` keys the quiz's sessions table (`WHERE config_path=?`) and its artifact lookup; `order` sorts the deck list. Because the deck directory accumulates across runs, a fresh numbering agrees with neither — so re-deriving them during a partial refresh strands study history and shuffles the list. (Exporting from a git worktree stamps the *worktree* path in, which strands history once the worktree is removed.)

**`source: manual` artifacts are preserved through the clear.** Some decks the quiz consumes carry curated content (e.g. `memory-quiz-app`'s CC-CEDICT Chinese vocab deck for matching mode — produced out-of-band by `deck-vocab`, see Pipelines §8) and have **no config `deck-export` can rebuild from** — a full run would silently delete them. `export_decks` skips any artifact whose JSON carries `"source": "manual"` (`_is_manual`; unreadable/malformed → treated as generated, so a corrupt generated deck is still rebuilt). The orchestrator's Dagster `decks` sync applies the same guard when clearing the quiz repo's dir.

Use `--only <glob>` to refresh a subset: matching decks are rebuilt, everything else is left untouched and never fetched, and each rebuilt deck keeps the existing artifact's `order`/`config_path` while `items`/`labels`/`config_hash` update. `--reset-identity` opts out (e.g. after genuinely relocating the repo).

**Deck staleness is invisible.** `config_hash` covers the config bytes only, so a change to *generator behaviour* — e.g. the end-year transition rule — leaves every hash identical while the digits change. Decks do not self-report as stale; re-export after any generator change.

## Users
Personal / educational use. Single user driving batch runs via CLI.

## Pipelines

### 1. Award Laureates (`deck-acronyms`)
- Source: Wikidata SPARQL (award Q-number)
- Output: year-chunked acronyms from laureate name initials
- Gap warning: emitted to stderr when `count_laureates()` (all P166 statements) differs from fetched count (those with P585 date qualifier). Computed before manual entry merging so it reflects Wikidata quality only.

| Field | Required | Default | Notes |
|---|---|---|---|
| `award_name` | yes | — | Used in output filename and warning messages |
| `wikidata_item` | yes | — | Q-number, e.g. `Q37922` |
| `chunk_years` | no | 5 | Years per acronym chunk |
| `chunk_start_year` | no | earliest entry year | First year of first chunk |
| `humans_only` | no | false | Adds `wdt:P31 wd:Q5` SPARQL filter; also applies to `count_laureates` |
| `first_letter_only_from` | no | null | Entries from this year onward use only first letter of first name token |
| `manual_entries` | no | [] | `[{year, name}]` — merged after SPARQL fetch; deduped by (year, name); for Wikidata coverage gaps |
| `exclude_entries` | no | [] | List of names — subtracted from `count_laureates` total to suppress gap warnings for known Wikidata errors |

### 2. Poetry Lines (`deck-poetry`)
- Source: Project Gutenberg (plain text, cached locally)
- Output: per-line acronyms (first letter of every word, particles included)
- `line_initials` includes all words (unlike `name_initials` which skips particles)
- `start_marker`/`end_marker`: any substring of the first/last line; robust to minor Gutenberg edition differences

Single poem config:
```yaml
poem_title: "Shakespeare Sonnet 18"
gutenberg_id: 1041
start_marker: "Shall I compare thee to a summer's day?"
end_marker: "So long lives this, and this gives life to thee."
```
Collection config: top-level `collection_title` + `poems` list, each with `poem_title`/`start_marker`/`end_marker`. Single sheet output with bold yellow title row per poem and blank row separators.

### 3. Monarch Reigns (`deck-monarchs`)
- Source: Wikidata SPARQL (position Q-numbers)
- Output: per-century transition-digit strings (last digit of accession year per monarch)
- **End-year events**: any recorded end year that is not itself some ruler's accession year becomes a transition event — i.e. the throne did not pass directly to a successor that year. This covers Wikidata coronation-lag (Edward the Elder died 924, Æthelstan crowned 927 → 924 inserted), the start of a genuine interregnum (Commonwealth: Charles I ends 1649, Charles II accedes 1660 → 1649 inserted), and a dynasty's terminal year (last ruler, no successor). Continuous same-year successions add nothing. *(Superseded the original ≤5-year gap-fill threshold, which suppressed interregnum and terminal years.)*
- **Deduplication by person Q-number**: monarchs whose title changed mid-reign (e.g. George III: King of GB 1760 → King of UK 1801) or who were deposed and restored (e.g. Stephen, Henry VI) appear once with their earliest accession year and latest end year.
- **Fragmented Q-numbers**: Britain requires four position Q-numbers across eras (`Q18810062` England pre-1707, `Q110324075` GB 1707–1801, `Q111722535` UK 1801–1927, `Q9134365` UK 1927–present).

| Field | Required | Default | Notes |
|---|---|---|---|
| `subject` | yes | — | Used in sheet title and output filename |
| `positions` | yes | — | List of Wikidata position Q-numbers (P39 values) |
| `houses` | no | — | P53 noble-family Q-numbers; restricts holders to those houses. Needed when a position spans dynasties (`Q268218` "Emperor of China" covers every dynasty; House of Zhu / Aisin-Gioro isolate Ming / Qing) |
| `accession_min_year` / `accession_max_year` | no | — | Cap a dynasty at a historical boundary (Abbasids at the 1258 Baghdad fall, excluding the Cairo figureheads acceding to 1517) |
| `corrections` | no | — | Sourced manual overrides of transition years — see below |
| `chunk_years` | no | 100 | Years per chunk |
| `chunk_start_year` | no | earliest accession year | First year of first chunk |
| `wikipedia_list` | no | — | Article title used by `deck-coverage-check` and date cross-checks |
| `group` | no | `Monarchs` | Collapsible menu group in the quiz; all monarch decks share one "Monarchs" group by default (like poetry's `collection_title`), override to sub-group |

##### `corrections:` — sourced overrides

Wikidata models one P39 statement per ruler, which cannot express a reign interrupted and resumed, and it carries occasional plain date errors. Each correction records *why* and *against what*, so it can be re-verified and later retired:

```yaml
corrections:
  - year: 1446
    action: add          # 'add' | 'drop'
    reason: "Murad II restored 1446; Wikidata records 1421–1451 as one unbroken statement"
    source: "List of sultans of the Ottoman Empire"
    checked: "2026-07-16"
```

`reason` and `source` are **required** — `parse_corrections` raises rather than skip a malformed entry, since a correction that silently fails to apply looks identical to one never written. Drop removes every occurrence of a year and is applied before add.

**Add is idempotent.** A correction is a bet that Wikidata stays wrong, and Wikidata improves; appending unconditionally would double a digit the day upstream fixed the statement. `stale_corrections` reports corrections that no longer change anything (an `add` Wikidata now supplies, a `drop` it no longer emits) — neither is an error, which is exactly why they need surfacing rather than rotting silently.

There is **no mechanism to correct a ruler's accession/end year directly**; corrections patch the *transition-year output*, not the underlying data. So a wrong accession year is expressed as a `drop` of the bad year plus an `add` of the right one (and sometimes only a drop — Tahmasp II's true 1722 accession is already a transition year via his predecessor's end year).

##### Date precision (documentation only)

`Monarch.accession_precision` carries Wikidata's `timePrecision` for P580 (9 = year, 8 = decade, 7 = century). Below year precision, the source does not actually claim that year — Assyria's Tudiya is stored as `-2450` at decade precision, meaning "the 2450s BC"; Denmark's Sigfred (770) and France's Mallobaudes (378) / Marcomer (380) are decade-precision within shipped decks. **Digit extraction deliberately ignores this**, so decks are byte-identical to before the field existed; `deck-monarchs` merely warns. This matters for any future expansion into ancient series: pharaoh has 527 recorded holders but only 88 with any start date, and Mesopotamian absolute chronology is convention-dependent (High/Middle/Low differ by decades), so precision is the difference between a fact and an artifact.

#### Monarch deck set (2026-07)
**20 decks.** *European (13):* Britain, English Commonwealth, Scotland, Denmark, Norway, Sweden, Holy Roman Empire, Byzantium, Hungary, Portugal, Bohemia, France, Japan. *Non-European (7, 2026-07):* Umayyad, Abbasid, Fatimid caliphs; Ottoman sultans; Safavid shahs; Ming, Qing emperors. Selection was data-driven from a full Wikidata survey:
- **Survey**: ~566 monarch positions (`wdt:P279* wd:Q116`) carry reign holders; 268 have ≥8 reigns. Median date coverage 92%. Full categorized list saved at `results/monarch_positions_wikidata.md`.
- **Rank by conditioning, not size** (2026-07 re-survey): 325 monarch positions have ≥6 holders but only **272 have ≥6 *dated* ones** — our pipeline needs `P580`. The largest counts are generic umbrella classes, not series (`Q12097` "king" 284, `Q116` "monarch" 158, `Q181888` "khan" 117); they mix every realm and need the same `houses` treatment as Emperor of China. Best unbuilt candidate is **Pope (`Q19546`)**: 268 holders, 99% dated, 229 at day precision, one clean position, irregular reigns. Ancient series are mirages — **pharaoh has 527 holders but only 88 dated (17%)**, and Mesopotamian absolute chronology is convention-dependent (High/Middle/Low differ by decades), so those digits would encode a convention, not a fact.
- **Quality gates** (what makes a good deck): **date coverage** ≥70% (sparse `P580` start-years → weak deck) and **per-century density** ≤~15 holders (each accession = one transition digit, so a dense century = an unlearnably long card).
- **Multi-QID chains** (France-style, like Britain's): France = king of the Franks → king of France → King of France and Navarre → King of the French → Emperor of the French (`Q22923081, Q24851389, Q3439798, Q3439814, Q5373953`), `chunk_start_year: 480`. `fetch_monarchs` dedups by person across the chain.
- **BCE handling**: setting `chunk_start_year` to a CE value cleanly excludes earlier (legendary/BCE) reigns — the chunk loop only buckets events ≥ start. Japan starts at 500 (drops 11 legendary BCE emperors); `e % 10` is safe for negative years but BCE labels are ugly.
- **China: solved by `houses`** *(was "deferred — Wikidata has no per-dynasty positions")*. "Emperor of China" (`Q268218`) does conflate every dynasty and all parallel claimants (Three/Sixteen Kingdoms, Five Dynasties) → century cards of 33–44 digits. The dynasty-membership model that was thought missing is **P53 "noble family"**: filtering holders by House of Zhu / Aisin-Gioro isolates the Ming (16 rulers) and Qing (11) cleanly. Other fragmentation-era dynasties remain unbuilt but are now tractable the same way.
- **Remaining opportunity**: ~111 more positions are clean/viable for batch generation now (≥70% dated, ≤15 density); ~22 marginal; 5 China-like dense; 46 too sparse; 72 excluded (consorts + ecclesiastical). Iberia (Aragon/Castile/León/Navarre) is fragmented and would need France-style chains or per-kingdom decks.
- **Known data-quality gaps** (2026-07 cross-check, 138 rulers over the 7 non-European decks vs Wikipedia with 3-of-3 adversarial verification — report at `results/verify_monarch_dates/report.md`):
  - **Consort contamination**: `Q18577504` "Byzantine emperor" is attached to consorts on Wikidata (Theodora *wife of Justinian I*, Zenonis, Gregoria, Anna of Moscow, Irene Gattilusio). The survey's consort exclusion filtered consort *positions*, not consorts holding the emperor position — byzantium's digits include women who never reigned.
  - **Scope bleed**: `english_commonwealth` uses `Q512196` "Lord Protector", which also matches Edward Seymour (1547–49), Edward VI's regent — a different institution. Harmless only because `chunk_start_year: 1600` puts him out of range; wants an `accession_min_year`.
  - **Data holes read as interregnums**: the end-year rule inserts a transition wherever no successor follows within the data, which cannot distinguish a real interregnum from missing rulers. 9 such cases exceed 50 years — france 511 (Clovis I, 118yr hole), france 869, japan 200, holy_roman_empire 814 (Charlemagne, 61yr) — all spurious.
  - **Unresolved**: Orhan's accession (we follow the traditional 1326; Wikipedia's table says "c. 1324") is a historiographic dispute, documented in-config. Fatimid al-Mustansir (1095 vs 1094) sits on a Hijri year boundary and awaits a second source.

### 4. Shakespeare Passages (`deck-shakespeare`)
- Source: Folger Digital Texts API (`folgerdigitaltexts.org`)
- Output: YAML catalogue + xlsx of monologue passages (character, play, line count, full text)
- Config: list of play codes (e.g. `Ham`, `Mac`) and `min_lines` threshold
- Caching: raw HTML responses cached locally under `cache/folger/`; segments under `cache/folger/segments/`
- Catalogue includes `meta` block with `total_passages` and `total_lines`
- Core 10-play config (`configs/shakespeare/core_plays.yaml`): Hamlet, Macbeth, King Lear, Othello, The Tempest, Romeo and Juliet, A Midsummer Night's Dream, The Merchant of Venice, Julius Caesar, Richard III — 163 passages, 4,673 lines

### 5. Monologue Archive Passages (`deck-monologue-archive`)
- Source: monologuearchive.com (static HTML, scraped with `requests`)
- Output: YAML catalogue + xlsx of monologue passages (playwright, play, character, type, lines)
- Config: list of `{slug, name}` entries — slug matches URL pattern `/{letter}/{slug}.html`
- Caching: author index pages under `cache/monologue_archive/`; individual passages under `cache/monologue_archive/passages/`
- Filters out external `list-group-item active` links that share the same CSS class as internal entries
- Core config (`configs/monologue_archive/core_playwrights.yaml`): Christopher Marlowe, Ben Jonson — 23 passages, 850 lines

### 6. Famous Artworks (`deck-artworks`) — *in design*
- Source: Wikidata SPARQL — `instance of painting (Q3305213)` with creator (P170) + image (P18), ranked by `wikibase:sitelinks` (fame proxy); `min_sitelinks`/`limit` knob, plus curated-QID and collection (P195) source modes. Survey (2026-07-17): 381,330 paintings have creator+image; ~104 at ≥30 sitelinks, ~1,533 at ≥10.
- Output: unlike the xlsx pipelines, emits **directly to the quiz artifact seam** — an expanded two-card-per-artwork deck (`data/decks/*.json`, `items` = `<QID>|title` / `<QID>|creator`) plus downsized **WebP image files** under `data/decks/assets/<deck>/`, and **baked multiple-choice distractors**. Consumed by `memory-quiz-app`'s `image-mc` mode.
- Key stability: item strings are `<QID>|attr`, so re-fetching an image or a corrected label never strands FSRS history (contrast monarch digits). Image licensing (drop non-free) is the main open risk.
- See [`docs/design/artworks-pipeline.md`](docs/design/artworks-pipeline.md) and the quiz's [`artwork-mc-mode.md`](../memory-quiz-app/docs/design/artwork-mc-mode.md).

### 7. Equations (`deck-equations`) — *built*
- Source: **hand-curated** LaTeX in `configs/equations/{statistics,physics,mathematics}.yaml` (an article's wikitext holds every `<math>` on the page with nothing marking *the* formula — that choice stays human). Corruptions, by contrast, are **generated**.
- Output: emits **directly to the quiz artifact seam** — a `deck_type: equations` / `mode: error-spot` deck with baked MathML and, per equation, a pool of **verified single-token corruptions** (`{id, i, to, type}`) plus `bad_pairs`. sympy *proves* each corruption non-equivalent (fails closed); `normalise.py` rewrites real notation (`P(A\mid B)`, `\operatorname{Var}`) into a sympy-parsable form **for verification only**. Consumed by `memory-quiz-app`'s `error-spot` mode.
- Split: one config → **two decks** (2-error / 1-error) by supportable error count (`classify`), disambiguated by `poem_title`. Key stability: item = canonical LaTeX, so retuning the engine, retiring a type, or an equation moving between decks never strands FSRS history.
- See [`docs/design/equations-pipeline.md`](docs/design/equations-pipeline.md).

### 8. Chinese Vocab (`deck-vocab`) — *built*
- Source: **wordfreq** frequency ranking ⋈ **CC-CEDICT** (CC-BY-SA 4.0) for pinyin + glosses. A curation tool for the quiz's `matching` deck, **not** a full-export deck: the deck stays `source: manual` (protected from the clear + orchestrator sync; carries live FSRS history), so — like equations' curated content — heavy lifting is done once and **committed as data**, then `build` assembles the artifact deterministically (offline, no API key).
- Pipeline: `rank_candidates` routes each candidate into *clean* (single reading/≤3 senses → CC-CEDICT first-gloss is safe, ~63%) or *needs-LLM* (polyphone ∪ multi-sense ∪ function-word, ~37%, where the first sense is unreliable — 被→"quilt" not the passive marker). Needs-LLM words get an **audited per-word LLM adjudication** (frequency-correct reading+sense + one short gloss + logged reason). The existing 267-word seed is frozen byte-identical (FSRS keys survive). Grown **267→5257** (2026-07-23).
- Gloss uniqueness is **band-scoped** (`band_collisions`, `FREQ_BAND_SIZE` window): English has no 5000+ distinct short glosses, and a matching round only co-displays same-band words. `deck-vocab build` reproduces the exact artifact shipped to `memory-quiz-app`.
- Committed data: `configs/vocab/chinese_common.{yaml,curated.jsonl,audit.jsonl,policy.md}`. See [`docs/design/vocab-pipeline.md`](docs/design/vocab-pipeline.md) and the quiz's [`matching-mode.md`](../memory-quiz-app/docs/design/matching-mode.md).

## Output
Excel `.xlsx` workbook, two sheets:
- Detail sheet — one row per entry with initials and chunk acronym highlighted on first row of each chunk
- Summary sheet — one row per chunk with acronym only

## Retention testing — quiz modes

### Goal
Given an acronym line as cue, test whether the user can recall the full text line. Must be fast enough to scale to large texts (Bible ~31k verses, Homeric epics ~15k lines).

### Alternatives considered

| Method | Speed | Tests recall? | Notes |
|---|---|---|---|
| Full line typing | Slow | Yes, strongly | 50–80 keystrokes per line; impractical at scale |
| Self-rating (think → reveal → rate) | 1 keypress | Yes, if honest | Anki's default; relies on user not fooling themselves |
| First-word typing | Fast | Yes, adequately | Knowing first word strongly predicts line recall |
| Multiple choice | 1 keypress | Weakly (recognition only) | Much easier than recall; poor retention signal |
| **Blindman's bluff** (selected) | 1 keypress | Yes, objectively | See below |

### Selected method — blindman's bluff
Display: first letter of each word shown; remaining letters as underscores; one randomly selected non-first, non-pinned letter revealed, correct 80–90% of the time and wrong 10–20% of the time. For words with 5+ alphabetic characters, every 4th alpha position (4th, 8th, 12th…) is also auto-shown as a positional anchor.

Task: identify the word containing the wrong letter (if any).

Scoring: uses a limited health bar (max 10). Missing a wrong letter (false negative) costs 3 health. Claiming a wrong letter when all are correct (false alarm) costs 1 health. Reaching zero health restarts from the beginning.

**Pros:** single keypress; objective (no self-rating honesty problem); forces letter-level recall; gamified; scales to any text size.

**Cons:** 10–20% wrong-letter rate means 80–90% of trials have no wrong letter — naive "always type 0" strategy scores high without recall. Health bar asymmetry addresses this but must penalise false alarms too, or gaming shifts to "always guess a word." Wrong letters must be plausible distractors, not visually obvious.

### Quiz modes

Three modes are implemented, all using the same scoring and health system:

| Mode | CLI | Items | Display |
|---|---|---|---|
| `words` | `wiki-quiz-web --mode words` | Poetry lines | Per word: first letter + every 4th alpha position (for 5+ letter words) always shown; one random non-pinned letter revealed; underscores for rest |
| `acronym` | `wiki-quiz-web --mode acronym` | Poetry lines | One letter per word (first letter only); each independently 20% chance wrong |
| `digits` | `wiki-quiz-monarchs-web` | Century transition strings | One digit per position; each independently 20% chance wrong |

### Flask web app
The quiz is served as a localhost Flask app. Features:
- Live timer per item (JS `setInterval`, 100ms update)
- Session infobox: items done, per-rating counts (E/G/H/A), average time per item
- Progress label (item index / due count, or custom label from config) with inline phase badge (Learning / Graduated / Review / Relearning)
- Flash messages for correct/wrong/restart outcomes

### Desktop app (`wiki-quiz-app`)
A PyWebView-wrapped desktop app with an Anki-style deck picker home screen. Flask runs in a background thread; PyWebView opens a native macOS window (no browser required). Entry point: `deck_generator.desktop_app:main`.

- **Home screen**: lists all configs from `configs/poetry/` and `configs/monarchs/`. Single-poem configs appear as individual deck rows; multi-poem collections are collapsible groups. Shows last-studied date per deck from `sessions` table.
- **Deck loading**: async (background thread) with a polling spinner — handles slow Wikidata SPARQL calls without blocking the UI. Errors shown inline with a back link.
- **Navigation**: "← Decks" link on every quiz page; "Study again" / "← Decks" on the completion screen.
- **macOS .app bundle**: `~/Desktop/Quiz.app` — double-click to launch, no terminal required. Custom `.icns` icon (green rounded square, stacked flashcard motif).
- **Remote mode**: set `QUIZ_URL=https://your-app.fly.dev` before launching; `main()` opens the PyWebView window on the hosted server and skips starting a local Flask instance.
- **Quote normalisation**: `poetry_parser.py` normalises Unicode curly quotes (`\u2018/\u2019/\u201c/\u201d`) to ASCII before marker lookup, so YAML configs with straight apostrophes match Gutenberg text with curly quotes.
- **SRS parameters**: desktop app uses fixed defaults (same as CLI defaults); advanced users can still use `wiki-quiz-web` / `wiki-quiz-monarchs-web` for custom params.

### iPhone PWA (`/pwa/`)
An installable Progressive Web App that shares SRS state with the desktop app via the Flask server.

- **Install (LAN)**: navigate to `http://<LAN-IP>:5001/pwa/` in Safari → Share → Add to Home Screen. Runs as a standalone app (no browser chrome).
- **Install (hosted)**: same flow against the Fly.io URL once deployed (`fly deploy`). See `Dockerfile` and `fly.toml`.
- **Offline support**: static assets cached by service worker (`sw.js`); deck content and SRS state stored in IndexedDB (`db.js`). Quiz runs fully offline once a deck has been loaded.
- **Sync**: on page load and after each session completion, `sync.js` POSTs all local IndexedDB card state to `POST /api/sync`. Server applies last-write-wins merge (compares `updated_at` timestamps) and returns full server state; client applies any newer server cards back to IndexedDB.
- **Shared database**: both desktop and iPhone write to the same SQLite `srs_state` table via the Flask API. Cards reviewed on either device advance the same FSRS schedule.
- **Quiz UI**: touch-optimised chip selection for wrong word/letter/digit positions (iPhone/browser). On the desktop app (PyWebView), detected via `window.pywebview`, chips are non-interactive and a text input is shown instead — type space/comma-separated word numbers and press Enter or Submit. Health bar, live timer, answer reveal after each item, phase badge (Learning/Graduated/Review/Relearning).
- **Flask quiz input modes**: default is text input (type space-separated wrong-word numbers). A "Switch to click" toggle button in the mode bar enables click-to-select — word cards become clickable; clicking highlights them red and populates a hidden form field. Preference persists via `localStorage`.
- **SRS parity**: `srs.js` is a verified port of `srs.py` using `ts-fsrs`. Python↔JS parity is tested by a fixture generator that replays identical review sequences through both implementations and asserts matching state transitions.

#### API Blueprint (`api.py`)
Registered on the Flask app alongside existing quiz routes. Serves both the JSON API and PWA static files.

| Endpoint | Description |
|---|---|
| `GET /api/decks` | Lists all decks with stable SHA-256 IDs, mode, group, last-studied date |
| `GET /api/deck/<id>/content` | Returns `{items, mode, labels, title}` for a deck; 500 on load failure |
| `POST /api/sync` | Last-write-wins merge; body: `{changes:[{item_key,card_json,updated_at}]}`; returns full server state |
| `GET /pwa/*` | Serves PWA static files from `pwa/` directory |

### Related research
No known tool combines acronym cueing with adversarial partial-letter reveal. Closest prior work:

- **Vanishing cues** (Glisky et al., 1986) — memory rehabilitation technique where letters are progressively removed until minimal cue triggers recall. Structurally the reverse of this method.
- **Error detection reading tasks** — participants find plausible word substitutions in text; tests comprehension but not recall from memory.
- **Signal detection theory (SDT)** — the 80/20 wrong-letter setup is formally a yes/no detection task. SDT metrics (d′, criterion) give a rigorous per-card scoring framework tracking hits, misses, false alarms, and correct rejections separately.
- **Retrieval practice / testing effect** — broad finding that attempted recall (even partial) consolidates memory more than passive review; supports the forced-recall nature of this method.

### Distractor letter selection
Wrong letters must be plausible enough that detection requires recall, not just visual oddness. Sources ranked by relevance:

1. **Visual confusion matrices** (Bouma 1971, Townsend 1971) — primary source; pairs like b/d, p/q, m/n, c/e, i/l, rn/m that humans misidentify under brief exposure.
2. **Phonetic similarity** — letters whose names sound alike (b/d, f/v, m/n, s/z, c/k); especially relevant for poetry, which memorizers subvocalise.
3. **OCR error corpora** — empirical substitution frequencies from real misreads; ecologically valid but reflects machine vision, not human perception.
4. **Keyboard adjacency** — models typo patterns during typing; least relevant here since distractors are generated programmatically, not typed.

## Logging and SRS

### Quiz event logger
All quiz sessions are logged to `logs/quiz.db` (SQLite, gitignored). Tables:

- **`sessions`** — one row per quiz run: `id` (UUID), `started_at`, `mode`, `title`, `config_path`, `config_hash`, `wrong_prob`, `format_version`
- **`attempts`** — one row per item shown: `item_key` (SHA256[:16] of item text), `item_idx`, `item_label`, `item_text`, `display_text`, `displayed_at`, `submitted_at`, `raw_input`, `keystrokes` (JSON array of `[key, ms_since_display]`), `user_positions` (JSON), `correct`, `health_before`, `health_after`
- **`srs_state`** — one row per item: `item_key`, `card_json` (FSRS Card serialised as JSON), `updated_at`

`item_key` is stable across sessions and config changes, enabling SRS scheduling per item.
`config_hash` (SHA256 of config file bytes) detects data-source changes.

### ⚠ Format versioning — manual step required
`FORMAT_VERSIONS` in `logger.py` maps each mode to a version string (e.g. `words-v1`). This string is stored in every `sessions` row so that SRS analysis can exclude sessions using an old display format.

**Whenever you change how items are displayed** (e.g. modify `make_line_display`, `make_acronym_display`, `make_digit_display`, `_two_letter_display`, or the Jinja template rendering), **bump the relevant version string** in `FORMAT_VERSIONS`:

```python
FORMAT_VERSIONS: dict[str, str] = {
    'words': 'words-v2',   # ← bump when words display format changes
    'acronym': 'acronym-v1',
    'digits': 'digits-v1',
}
```

This is not automatic. Claude will not bump it unless explicitly asked.

### Spaced repetition system (SRS)
Implemented using **FSRS-6** (`fsrs` pip package v6.3.1). Every quiz response updates a per-item Card stored in `srs_state`.

#### Rating classification
Each response is rated by latency relative to item length:

| Mode | Easy threshold | Hard threshold |
|---|---|---|
| `words` | `1.5 + n_words×0.30 + n_chars×0.05` s | `1.5 + n_words×1.50 + n_chars×0.20` s |
| `acronym` | `1.5 + n_words×0.30` s | `1.5 + n_words×1.50` s |
| `digits` | `1.5 + n_digits×0.40` s | `1.5 + n_digits×2.00` s |

- Incorrect response → `Again` regardless of latency
- Latency < easy threshold → `Easy`
- Easy ≤ latency < hard threshold → `Good`
- Latency ≥ hard threshold → `Hard`

Scaling by item length ensures a 5-word line and a 20-word line are judged at appropriate speeds; a response fast for a short line is not automatically fast for a long one.

#### Learning steps, graduated ramp, and new-cards-per-day
New items pass through two fixed phases before FSRS takes over free scheduling. Both CLIs accept:

- `--learning-steps MIN [MIN ...]` — minute-interval burn-in (default: `1 10 60 360`)
- `--graduated-steps DAYS [DAYS ...]` — day-interval ramp after learning completes (default: `1 2 3 4 5 6 7`); provides a week of structured consolidation before FSRS schedules freely
- `--new-per-day N` — max new items introduced per day (default: 20); unintroduced items queue indefinitely and unused daily slots do not accumulate

Card flow: **new → learning steps → graduated ramp → FSRS free scheduling**

State is stored in the `card_json` envelope alongside the FSRS card:

| Field | Meaning |
|---|---|
| `learning_step` | Current learning step index; `null` if past learning |
| `step_due` | ISO timestamp when current learning step is reviewable |
| `introduced_date` | UTC date string when card was first shown (used for daily budget) |
| `graduated_step` | Current graduated-ramp step index; `null` if not in graduated phase |
| `graduated_step_due` | ISO timestamp when current graduated step is reviewable |
| `relearning_step` | Current relearning step index after a lapse; `null` if not in relearning |
| `relearn_step_due` | ISO timestamp when current relearning step is reviewable |
| `fsrs` | Serialised FSRS Card (null until graduation from graduated ramp) |

Correct answer advances to the next step; incorrect resets to step 0 of the current phase. Correct at the final graduated step initialises the FSRS card. Legacy `card_json` rows (bare FSRS JSON without an envelope) are treated as already in FSRS phase.

**Note:** learning-step cards that come due during a session are shown; cards that become due mid-session (e.g. the 1-minute step expiring while reviewing other items) are not re-queued within the same session — they appear in the next session. For fast burn-in, run short back-to-back sessions.

#### Due-order quiz flow
At session start `_classify_items` sorts all items into buckets and returns `(ordered_indices, due_count)`:

| Priority | Bucket | Condition |
|---|---|---|
| 1 | New (within daily budget) | No card state; budget = `new_per_day - introduced_today` |
| 2 | Learning/graduated/relearning due | Step due ≤ now; sorted most-overdue first |
| 3 | FSRS review due | `card.due` ≤ now; sorted most-overdue first |
| 4 | Learning/graduated/relearning future | Step due > now; sorted soonest first |
| 5 | FSRS future | `card.due` > now; sorted soonest first |
| 6 | New (over daily budget) | Queued for future days |

`session['item_order']` stores the full sorted index list; `session['due_count']` caps the session at buckets 1–3. The quiz completes when all due items are reviewed. Buckets 4–6 are present in the order list to support `--review-ahead`.

#### Review-ahead (`--review-ahead N`)
Both `wiki-quiz-web` and `wiki-quiz-monarchs-web` accept `--review-ahead N`. When set, `due_count` is extended by N to include the N soonest-due future items after the normally-due set. Future items are reviewed early, so FSRS calculates the next interval from the actual (early) review time — this shortens the next interval and increases total lifetime reviews. It is never neutral or beneficial from a scheduling-efficiency standpoint, but provides extra exposure when the user has time.

**Overdue handling**: FSRS uses actual elapsed time when reviewing overdue cards.

#### Memory stability asymptote and max-interval cap
FSRS models memory stability as converging toward a personal upper limit ("stability asymptote"), documented also in SuperMemo research as "stabilization decay." In practice this means long-interval cards (>6–12 months) may still be forgotten even when FSRS predicts high retention, because FSRS's 21 trainable parameters may over-estimate an individual's stability ceiling — especially if long-interval data is sparse (a circular problem: cards are forgotten before enough data accumulates).

Both CLIs accept `--max-interval N` (days, default 365). After each review, if FSRS schedules the next due date beyond the cap, it is clamped to `now + N days` and `scheduled_days` is updated to match. This trades a small increase in review frequency for protection against the stability asymptote problem. Reviewing ahead of schedule appears to FSRS as an early review, so the subsequent interval will be shorter than if the card had been reviewed on the natural due date — consistent with the review-ahead tradeoff documented above. A correct response on an overdue card produces a longer next interval (memory proved stronger than the model predicted), which is the desired behaviour.

#### Lapse behavior — stability drop, difficulty increase, and relearning

A **lapse** is an incorrect response on a card that has already graduated from learning steps into the FSRS queue. FSRS applies three changes simultaneously:

**1. Stability drop**
Stability collapses via FSRS's forgetting-stability formula — independent of how stable the card was beforehand. The resulting interval is typically 1–3 days. This new stability is computed at lapse time and then frozen: relearning steps (if any) are a confirmation phase that runs against this already-computed stability, not a further input to it. After relearning, the card re-enters the queue at whatever interval FSRS scheduled at the moment of the lapse.

**2. Difficulty increase**
FSRS difficulty D (scale 1–10) is updated in three steps:

1. Grade adjustment: `ΔD = -w6 × (G - 3)` — Again (G=1) increases D by `2 × w6`
2. Linear damping: `D' = D + ΔD × (10-D)/9` — as D approaches 10, changes shrink toward zero
3. Mean reversion: `D'' = w7 × D₀(4) + (1-w7) × D'` — blends back toward a baseline (~5–6)

The damping in step 2 is a trap: once D is high, even successive correct Good responses produce negligible decreases. Going from D=10 to D=9 requires ~118 consecutive Good reviews at default parameters. Mean reversion (step 3) was introduced in FSRS v2 to fix this, but the default weight `w7 = 0.001` is so small that recovery from high difficulty takes thousands of reviews. FSRS optimisation across 10,000 users found w7 frequently optimises to near zero, making mean reversion practically absent. This pathology is called "Difficulty Hell."

**3. Relearning steps**
Without relearning steps, the card re-enters the SRS queue after a single re-exposure at lapse time, then intervals ramp back up — but with higher difficulty baked in. Relearning steps instead route the card through a short-interval confirmation phase (e.g. 10 minutes) before it returns to the queue. This is supported by:

- **Errorful generation**: making an error followed by prompt correction is a well-studied enhancer of long-term retention; the error itself aids re-encoding
- **Reconsolidation window**: forgetting triggers a labile memory state; immediate re-exposure can update the trace while malleable
- **Review density**: multiple near-term exposures after a lapse increase short-term review density without affecting the FSRS-computed post-lapse stability

**Lapse interventions:**

| Parameter | Default | Effect |
|---|---|---|
| `--relearn-steps DAYS [...]` | `1 2 3` | Day-based relearning steps after a lapse; card must pass each before re-entering the FSRS queue. Incorrect during relearning resets to step 0; health penalty applies as normal. |
| `--difficulty-forgiveness F` | `1.0` | Scales the FSRS difficulty increase at lapse time by `(1-F)`; 1.0 = no increase, 0.0 = full FSRS default. Directly addresses Difficulty Hell, which mean reversion fails to fix in practice. |
| `--stability-forgiveness F` | `1.0` | Scales the FSRS stability drop at lapse time by `(1-F)`; 1.0 = no drop (card returns to pre-lapse stability after relearning), 0.0 = full FSRS default. Card state is reset to Review after forgiveness is applied so FSRS treats the next real review correctly. |

With both forgiveness values at 1.0 (defaults), a lapse costs nothing in FSRS terms — difficulty and stability are preserved — but the card is gated through relearning steps before re-entering the queue, providing short-term consolidation via the errorful generation and reconsolidation mechanisms described above.


## Non-goals
- Web UI beyond localhost
- Automatic publishing / sharing
- Non-English sources

## Success criteria
- All 31+ award configs produce correct `.xlsx` outputs
- Acronyms match independently verified initials
- CLI runs end-to-end without errors on clean install
- Quiz logger records all sessions and attempts with correct metadata
- SRS due-order presents overdue/new items before future-scheduled items
- Shakespeare pipeline downloads and caches all passages from configured plays
