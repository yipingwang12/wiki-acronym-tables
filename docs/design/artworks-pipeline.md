# Design — Famous Artworks pipeline (`deck-artworks`)

*Status: scoping, 2026-07-17. A new generator pipeline: Wikidata → famous paintings →
downsized WebP image assets + an expanded two-card artifact with baked multiple-choice
distractors, emitted across the `deck-export` seam. Quiz side (display, MC scoring,
PWA image caching): [`memory-quiz-app/docs/design/artwork-mc-mode.md`](../../../memory-quiz-app/docs/design/artwork-mc-mode.md).
Two coordinated branches (`artwork-cards`).*

## Goal
Produce committed artwork decks for the quiz's image + multiple-choice mode: for each famous
artwork, its **title**, **creator**, a **downsized image file**, and **baked distractors** for
both attributes. The quiz never fetches or generates at study time — this pipeline bakes
everything into `data/decks/*.json` + `data/decks/assets/<deck>/*.webp`.

## Data volume (live Wikidata survey, 2026-07-17)
`instance of painting (Q3305213)` with **both** creator (P170) and image (P18): **381,330**.
Fame tail (fame = `wikibase:sitelinks`, i.e. # of language Wikipedias linking the work):

| sitelinks ≥ | count | character |
|---|---|---|
| 50 | 14 | the absolute icons (Mona Lisa 146, Starry Night 76, Guernica 70…) |
| 30 | 104 | unmistakable masterpieces |
| ~20 | ~350 (interp.) | very famous |
| 10 | 1,533 | famous → art-history known |
| 5 | 4,916 | broad, includes lesser-known |

A `min_sitelinks` (or top-N) config knob sets deck size directly. Image sizing (WebP ~400–500px
≈ 25 KB): 104 works ≈ 2.5 MB, 1,500 ≈ 37 MB, 5,000 ≈ 125 MB on disk. The PWA caches only
studied decks (see quiz doc), so the phone footprint is a fraction of this.

## Locked decisions (from scoping)
| Decision | Choice |
|---|---|
| Source | Wikidata SPARQL, ranked by `wikibase:sitelinks`; config knob for threshold / top-N |
| Image format | Download from Wikimedia Commons → downsize to ~480px **WebP** (~25 KB), store as files |
| Asset layout | `data/decks/assets/<deck>/<QID>.webp`, referenced by relative path from the JSON |
| Distractors | **Baked at export**, 4 choices, same-domain bias, **deterministic** (seeded by QID) |
| Card expansion | Artifact `items` expanded **2× per artwork** (`<QID>\|title`, `<QID>\|creator`) |
| Licensing | Restrict to **freely-licensed** images (see risks) |

## Config schema (`configs/artworks/famous.yaml`)
```yaml
deck_name: "Famous Paintings"
group: "Artworks"
source: wikidata            # wikidata | curated | collection
instance_of: [Q3305213]     # painting; extensible (sculpture Q860861, …)
min_sitelinks: 30           # fame threshold  (wikidata mode)
limit: 150                  # optional top-N cap
# curated mode:    works: [Q12418, Q45585, ...]
# collection mode: collection: Q19675      # P195, e.g. the Louvre → one deck per museum
image_px: 480
distractors:
  count: 4
  same_creator_bias: true   # title-card distractors prefer same movement/era; creator-card same period
```
All three source modes emit the identical artifact shape — only how the QID set is chosen differs.

## Pipeline modules (new, under `src/deck_generator/`)
| Module | Role |
|---|---|
| `artworks.py` | `fetch_artworks(config)` — SPARQL for QID set (fame / curated / collection); returns `Artwork(qid, title, creator, creator_qid, image_url, sitelinks, movement, inception, license)`. **Dedups by QID**; license filter. |
| `artwork_images.py` | `fetch_image(url)` → cache raw under `cache/artworks/`; `downsize(raw, px) -> webp_bytes`. Exponential-backoff Commons fetch. |
| `distractors.py` | `build_choices(artworks, attr, n, bias, seed=qid)` → per-artwork option list incl. the correct answer; **deterministic** (seeded by QID, no RNG state), so re-export is byte-stable and testable. Guards against duplicate options (shared titles / dominant creators). |
| `artworks_cli.py` | `deck-artworks` entry point. |

## Export seam (`deck_export.py` extension)
`deck-export` gains artwork handling: for each artwork deck it writes the expanded
two-card JSON **and** copies the downsized WebP assets into `data/decks/assets/<deck>/`.
- **`items` are `<QID>|<attr>` strings**, byte-identical across runs given the same QID set →
  the quiz's FSRS `item_key = sha256(item)[:16]` is preserved. Re-ranking that *adds* works
  leaves existing works' keys intact; only dropped/added QIDs retire/mint keys.
- **Answer-text and distractor changes do NOT strand history** — the key is `QID|attr`, not the
  answer. This is the key contrast with monarch digits (keyed on the digit string), and means
  the artwork mode needs **no `recovery.py` path** on the quiz side.
- **Clear/rebuild:** a bare `deck-export` run clears `data/decks` — the **assets dir must
  be cleared and rebuilt in lockstep** with the JSON (and the orchestrator's Dagster `decks`
  sync must carry `assets/` alongside the JSON). `--only <glob>` refreshes an artwork deck +
  its own asset subfolder, leaving others untouched. `config_hash` still covers config bytes
  only, so a generator-behaviour change is invisible — re-export after any change (same caveat
  as every other deck).

## Testing
- `fetch_artworks` against a recorded SPARQL fixture; dedup + license filter.
- `build_choices` determinism (same seed → same options) + no-duplicate-option guard.
- `downsize` output is WebP within target px / size.
- Artifact byte-stability: same config → identical `items`/`labels`/`choices` bytes.

## Open questions / risks
- **Image licensing (must-resolve).** Commons images vary — most pre-20th-C paintings are
  public domain (author died >70y), but modern works (Guernica, Klimt's *The Kiss*) may be
  non-free. Filter by license metadata and/or `inception`/creator death date; a famous but
  non-free image should be **dropped from the deck**, not shipped. Decide the exact rule.
- **Fame proxy imperfections.** `wikibase:sitelinks` favours Western canon; a curated list or
  collection mode can rebalance. Duplicate QIDs / same title different attribution (Salvator
  Mundi) need dedup before card expansion.
- **Commons rate limits / dead image URLs.** Cache raw responses; exponential backoff; skip +
  warn on a missing image rather than aborting the deck.
- **Deep-catalog cost.** ≥5 sitelinks ≈ 5k works ≈ 125 MB of assets in-repo — fine on disk, but
  keep decks scoped (per-threshold or per-collection) so any single deck stays reasonable.

## Non-goals (v1)
- Non-free images (dropped, not shipped).
- Artwork types beyond paintings (schema extensible via `instance_of`, deferred).
- Any quiz-time fetch — this pipeline is the only place the network is touched.
