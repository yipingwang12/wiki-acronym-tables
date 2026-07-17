# Monarch reign-year cross-check (7 dynasties)

Wikidata vs English Wikipedia list articles. 138 rulers checked; 6 discrepancies survived
3-of-3 adversarial refutation; 2 killed as false alarms; 0 rulers unmatched.

## Sources actually used

- **umayyad_caliphs** — List of caliphs (Umayyad Caliphate / Damascus section); Ibrahim ibn al-Walid article consulted to disambiguate a reign-vs-death column artifact
- **abbasid_caliphs** — List of caliphs (Abbasid Caliphate section), supplemented by Al-Musta'in, Al-Qahir, and Al-Muqtadir for the 866 and 929 details
- **fatimid_caliphs** — List of caliphs (Fatimid Caliphate section)
- **ottoman_sultans** — List of sultans of the Ottoman Empire
- **safavid_shahs** — Safavid dynasty (primary; its list/succession box/timeline), cross-checked against the individual ruler articles Ismail I, Ismail II, Mohammad Khodabanda, Abbas the Great, and Tahmasp II. "List of monarchs of Persia" was fetched but its Safavid section did not render.
- **ming_dynasty** — List of emperors of the Ming dynasty
- **qing_dynasty** — List of emperors of the Qing dynasty

---
# Monarch Reign-Year Cross-Check: Survivor Report

6 discrepancies survived adversarial refutation (3/3 refuters each, 0 refuted). 2 were killed as false alarms. Confidence below is per-item; all rest on English Wikipedia article text as the reference, which is itself not authoritative for contested medieval dates.

---

## Ottoman Sultans (`configs/monarchs/ottoman_sultans.yaml`)

### Murad II — missing restoration transition — **highest impact**
| ours | Wikipedia | cause |
|---|---|---|
| no add (single statement 1421–1451) | 1446 restoration | `deposition_restoration` |

Article splits the reign: Murad II 1421–Aug 1444, Mehmed II (first reign) Aug 1444–Sep 1446, Murad II (second reign) Sep 1446–Feb 1451. We capture 1444 and 1451 but drop 1446 entirely.

**Recommendation:** fix config — `add_transition_years: [1446]`. Confidence **high**: the interregnum is uncontested and 1446 is a genuine transition year absent from the deck.

### Orhan — accession
| ours | Wikipedia | cause |
|---|---|---|
| 1326 | c. 1324 | `wikidata_error` |

We have Osman I end=1324 but Orhan acc=1326 — a spurious 2-year gap injecting transition digit 6.

**Recommendation:** **needs-human-judgment**, leaning fix to 1324. 1326 is the traditional Bursa-capture date and appears widely in older scholarship; Wikipedia's own table uses c. 1324 and its "c." concedes the date is uncertain. Confidence **medium** — this is a real historiographic dispute, not a data error. If you want internal consistency (no gap between Osman's end and Orhan's accession), 1324 is the right call.

---

## Safavid Shahs (`configs/monarchs/safavid_shahs.yaml`)

### Tahmasp II — accession
| ours | Wikipedia | cause |
|---|---|---|
| 1729 | 1722 | `era_vs_accession` |

Off by seven years — far beyond conversion noise. Article: declared himself shah at Qazvin 10 Nov 1722; reign 1722–1732. 1729 is when he regained control of most of the country after the Afghan occupation. Our Soltan Hoseyn end=1722 already matches, so 1722 is a real transition year our accession value misses.

**Recommendation:** fix config — accession 1722. Confidence **high**: the gap is too large to be conversion drift, and the de jure/de facto distinction explains 1729 cleanly.

### Ismail I — accession
| ours | Wikipedia | cause |
|---|---|---|
| 1502 | 1501 | `wikidata_error` |

Infobox, lead, and dynasty list all give 1501 (22 Dec 1501 – 23 May 1524). Article never states 1502. End year 1524 agrees.

**Recommendation:** fix config — accession 1501. Confidence **medium-high**. The 22 December accession sits days from the year boundary, so a calendar/era convention could conceivably yield 1502 — but no article location supports it.

---

## Qing Dynasty (`configs/monarchs/qing_dynasty.yaml`)

### Puyi — end
| ours | Wikipedia | cause |
|---|---|---|
| 1917 | 1912 | `deposition_restoration` |

Article: Xuantong Emperor reigned 2 Dec 1908 – 12 Feb 1912; formal abdication 12 Feb 1912. 1917 is only the 11-day Manchu Restoration (1–12 July 1917). Our single end=1917 collapses the actual dynastic transition into the restoration stint, and since 1912 is nobody's accession year, the deck drops it entirely.

**Recommendation:** fix config — end 1912. Confidence **high**: 1912 is the dynasty's terminal transition year by any reasonable reading; the 1917 restoration is a footnote, not the end of Qing rule. Whether to *also* add 1917 is a deck-design choice, not a correctness one — recommend not adding.

---

## Fatimid Caliphs (`configs/monarchs/fatimid_caliphs.yaml`)

### Al-Mustansir — end
| ours | Wikipedia | cause |
|---|---|---|
| 1095 | 1094 | `hijri_conversion` |

Article: reign 13 June 1036 – 29 Dec 1094; successor al-Musta'li accedes 29/30 Dec 1094. Same-day handover entirely within 1094. Our end=1095 matches no successor's accession, injecting a spurious transition year (digit 5).

**Recommendation:** fix config — end 1094. Confidence **medium-high**. Likely an off-by-one from 487 AH straddling the 1094/1095 boundary; the article is unambiguous, but Hijri-boundary cases are exactly where sources diverge, so this is the survivor most worth a second source check.

---

## False alarms (2, not itemized)

Both dissolved on inspection rather than being confirmed errors: one Abbasid case (Al-Musta'in) was ordinary Hijri-boundary noise within tolerance, and one Safavid case (Abbas the Great) rested on genuinely ambiguous article wording that does not contradict our value. No config change warranted for either.

**Rulers not found in articles:** none.

---

## How to act on this

1. **Apply the four high/medium-high fixes first** — Murad II (`add: 1446`), Tahmasp II (`1722`), Puyi (`1912`), Ismail I (`1501`). Each removes a spurious digit or restores a dropped one; all four are well-supported.
2. **Verify Al-Mustansir against a second source** before editing — Hijri conversion is precisely where Wikipedia and specialist chronologies disagree most.
3. **Decide Orhan deliberately.** This is a scholarly dispute (1324 vs. 1326), not a bug. Pick one and record the rationale in the config so it isn't re-flagged next run.
4. **Re-run coverage after edits:** `wiki-coverage-check --config configs/monarchs/<dynasty>.yaml`, then regenerate decks. Note that changing transition years changes item strings, which changes FSRS item keys (`sha256(item)[:16]`) — existing review history for affected items will not carry over.
5. **General caveat:** every finding here is Wikipedia-vs-us. Where Wikipedia itself hedges ("c. 1324"), our value isn't necessarily wrong — it may just follow a different convention.
