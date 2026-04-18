# Roadmap

## Done
- [x] Core acronym logic (name initials, particles, hyphenated names)
- [x] Award laureates pipeline — 31+ configs, Wikidata SPARQL backend
- [x] Poetry pipeline — Gutenberg fetch, multi-poem collections
- [x] Monarchs pipeline — per-century transition-digit strings, parent lineage
- [x] Excel output — detail + summary sheets, chunk highlighting

## Planned

### Near-term
- [ ] README with install/usage examples
- [ ] CI: run pytest on push
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
