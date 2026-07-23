# Chinese vocab adjudication policy

You are curating rows for a **hanzi ↔ English matching flashcard deck**. Each input word
carries all its CC-CEDICT readings/senses; your job is to pick the ONE reading + sense that
reflects the word's **most frequent modern usage** and write one clean English gloss.

## Output (one JSON object per input word, JSONL)
`{"hanzi": "...", "pinyin": "...", "gloss": "...", "reason": "...", "decision": "keep|drop"}`

- **Every input word appears exactly once.** Do not add or drop words silently.

## Reading + sense selection
- For **polyphones**, pick the reading of the most frequent modern sense. **Prefer a content
  sense over a purely grammatical one when both are common** — e.g. 过→**guò** "to cross" (not
  the aspect particle `guo`); 地→**dì** "earth/ground" (not the adverbial `de`).
- Override CC-CEDICT's *first* sense when it isn't the frequent one — e.g. 被 is dominantly the
  passive marker "by", not the "quilt" noun CEDICT lists first.

## Keep vs drop
- **Keep grammatical / function words** with a short **functional gloss**:
  被 "by (passive marker)", 了 "completed-action marker", 个 "general classifier",
  的 "'s (possessive)", 吗 "question particle (yes/no)", 把 "object marker (把)".
- **Drop** (`decision: "drop"`, empty pinyin/gloss) ONLY degenerate entries whose senses are
  *all*: "surname X", "variant of / old variant of Y", "abbr. for Z", a proper-noun-only
  reading, or a bound morpheme with no usable standalone meaning.

## Gloss style
- 1–3 short lowercase senses, **semicolon-separated**; no CC-CEDICT parenthetical cruft, no `CL:`.
- Add a short **parenthetical tag only to disambiguate** near-synonyms: "and; with (written)".
- **Keep glosses distinct within your chunk.** If two words would land on the same gloss,
  differentiate them (register, nuance, or a tag) — a matching tile must be unambiguous.
- `pinyin`: space-separated syllables in tone-mark diacritics matching the chosen reading
  (e.g. `fēi cháng`, `wèn tí`).
- `reason`: one clause — which reading/sense you picked and why (especially when overriding
  CEDICT's first sense or choosing among readings).

## Worked examples (from the validated pilot)
- 和 → `hé` / "and; with" — conjunction, over rare huó/huò "to mix".
- 与 → `yǔ` / "and; with (written)" — register tag keeps it distinct from 和.
- 由 → `yóu` / "by; via; due to" — distinct from 从 "from", 被 "by (passive)", 以 "by means of".
- 之 → `zhī` / "'s (literary)" — distinct from 的 "'s (possessive)".
- 问题 → `wèn tí` / "question; problem" — clean content noun.
