# PRD — wiki-acronym-tables

## Problem
Memorizing ordered lists (award laureates, poem lines, historical rulers) is hard. Acronym mnemonics help, but generating them from authoritative sources is tedious.

## Goal
Generate Excel acronym-tables from Wikipedia/Wikidata sources automatically, grouped by configurable time windows. Run spaced-repetition quizzes against the generated material.

## Users
Personal / educational use. Single user driving batch runs via CLI.

## Pipelines

### 1. Award Laureates (`wiki-acronym-tables`)
- Source: Wikidata SPARQL (award Q-number)
- Output: year-chunked acronyms from laureate name initials
- Config: `award_name`, `wikidata_item`, `chunk_years`, `chunk_start_year`, `first_letter_only_from`, `humans_only`

### 2. Poetry Lines (`wiki-poetry`)
- Source: Project Gutenberg (plain text, cached locally)
- Output: per-line acronyms (first letter of every word, particles included)
- Config: `poem_title`, `gutenberg_id`, `start_marker`, `end_marker`; supports multi-poem collections

### 3. Monarch Reigns (`wiki-monarchs`)
- Source: Wikidata SPARQL (position Q-numbers)
- Output: per-century transition-digit strings (last digit of accession year per monarch)
- Config: `subject`, `positions`, `chunk_years`, `chunk_start_year`
- **Gap-fill**: when a monarch's recorded end year doesn't match any accession year (e.g. Wikidata shows Æthelstan at 927 but Edward the Elder died in 924), the end year is inserted into the transition string as a fallback event. This corrects Wikidata's known lag between a monarch's death and the next monarch's formal accession date.

### 4. Shakespeare Passages (`wiki-shakespeare`)
- Source: Folger Digital Texts API (`folgerdigitaltexts.org`)
- Output: YAML catalogue of monologue passages (character, play, line count, full text)
- Config: list of play codes (e.g. `Ham`, `Mac`) and `min_lines` threshold
- Caching: raw HTML responses cached locally under `cache/folger/`; segments under `cache/folger/segments/`
- Catalogue includes `meta` block with `total_passages` and `total_lines`
- Core 10-play config (`configs/shakespeare/core_plays.yaml`): Hamlet, Macbeth, King Lear, Othello, The Tempest, Romeo and Juliet, A Midsummer Night's Dream, The Merchant of Venice, Julius Caesar, Richard III — 163 passages, 4,673 lines

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
Display: first letter of each word shown; remaining letters as underscores; one randomly selected non-first letter revealed, correct 80–90% of the time and wrong 10–20% of the time.

Task: type the number of the word containing the wrong letter, or leave blank if all letters are correct.

Scoring: uses a limited health bar (max 10). Missing a wrong letter (false negative) costs 3 health. Claiming a wrong letter when all are correct (false alarm) costs 1 health. Reaching zero health restarts from the beginning.

**Pros:** single keypress; objective (no self-rating honesty problem); forces letter-level recall; gamified; scales to any text size.

**Cons:** 10–20% wrong-letter rate means 80–90% of trials have no wrong letter — naive "always type 0" strategy scores high without recall. Health bar asymmetry addresses this but must penalise false alarms too, or gaming shifts to "always guess a word." Wrong letters must be plausible distractors, not visually obvious.

### Quiz modes

Three modes are implemented, all using the same scoring and health system:

| Mode | CLI | Items | Display |
|---|---|---|---|
| `words` | `wiki-quiz-web --mode words` | Poetry lines | Per word: first letter + one random non-first letter; underscores for rest |
| `acronym` | `wiki-quiz-web --mode acronym` | Poetry lines | One letter per word (first letter only); each independently 20% chance wrong |
| `digits` | `wiki-quiz-monarchs-web` | Century transition strings | One digit per position; each independently 20% chance wrong |

### Flask web app
The quiz is served as a localhost Flask app. Features:
- Live timer per item (JS `setInterval`, 100ms update)
- Session infobox: items done, per-rating counts (E/G/H/A), average time per item
- Progress label (item index / due count, or custom label from config) with inline phase badge (Learning / Graduated / Review / Relearning)
- Flash messages for correct/wrong/restart outcomes

### Desktop app (`wiki-quiz-app`)
A PyWebView-wrapped desktop app with an Anki-style deck picker home screen. Flask runs in a background thread; PyWebView opens a native macOS window (no browser required). Entry point: `wiki_acronyms.desktop_app:main`.

- **Home screen**: lists all configs from `configs/poetry/` and `configs/monarchs/`. Single-poem configs appear as individual deck rows; multi-poem collections are collapsible groups. Shows last-studied date per deck from `sessions` table.
- **Deck loading**: async (background thread) with a polling spinner — handles slow Wikidata SPARQL calls without blocking the UI. Errors shown inline with a back link.
- **Navigation**: "← Decks" link on every quiz page; "Study again" / "← Decks" on the completion screen.
- **macOS .app bundle**: `~/Desktop/Quiz.app` — double-click to launch, no terminal required. Custom `.icns` icon (green rounded square, stacked flashcard motif).
- **Quote normalisation**: `poetry_parser.py` normalises Unicode curly quotes (`\u2018/\u2019/\u201c/\u201d`) to ASCII before marker lookup, so YAML configs with straight apostrophes match Gutenberg text with curly quotes.
- **SRS parameters**: desktop app uses fixed defaults (same as CLI defaults); advanced users can still use `wiki-quiz-web` / `wiki-quiz-monarchs-web` for custom params.

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
