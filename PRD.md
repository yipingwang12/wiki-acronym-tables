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
- Progress label (item index / due count, or custom label from config)
- Flash messages for correct/wrong/restart outcomes

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

#### Due-order quiz flow
At session start the quiz calls `SRSScheduler.get_due_order(lines)` and `get_due_count(lines)` to sort items by FSRS due date:

1. New items (no prior review) — shown first
2. Overdue items (due date in the past) — shown next, sorted by how overdue
3. Future items (due date not yet reached) — skipped for this session

`session['item_order']` stores the sorted index list; `session['due_count']` caps the session at items 0..due_count-1. The quiz completes when all due items have been reviewed, even if future-scheduled items remain.

**Overdue handling**: FSRS uses actual elapsed time when reviewing overdue cards. A correct response on an overdue card produces a longer next interval (memory proved stronger than the model predicted), which is the desired behaviour.

Without SRS (no `--db` flag), all items are shown sequentially as before.

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
