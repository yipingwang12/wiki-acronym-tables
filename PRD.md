# PRD — wiki-acronym-tables

## Problem
Memorizing ordered lists (award laureates, poem lines, historical rulers) is hard. Acronym mnemonics help, but generating them from authoritative sources is tedious.

## Goal
Generate Excel acronym-tables from Wikipedia/Wikidata sources automatically, grouped by configurable time windows.

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

## Output
Excel `.xlsx` workbook, two sheets:
- Detail sheet — one row per entry with initials and chunk acronym highlighted on first row of each chunk
- Summary sheet — one row per chunk with acronym only

## Non-goals
- Web UI or interactive app
- Automatic publishing / sharing
- Non-English sources

## Success criteria
- All 31+ award configs produce correct `.xlsx` outputs
- Acronyms match independently verified initials
- CLI runs end-to-end without errors on clean install
