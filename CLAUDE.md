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

## Key implementation notes

- Wikidata gap-fill for monarchs: when a monarch's end year ≠ next accession year, end year is inserted as fallback event (corrects known Wikidata lag)
- Folger API responses cached under `cache/folger/`; segments under `cache/folger/segments/`
- Excel output: two sheets — Detail (one row per entry) + Summary (one row per chunk)
