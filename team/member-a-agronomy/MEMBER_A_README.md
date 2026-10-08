# Member A delivery: Manipuri and agricultural knowledge

The folder's `README.md` is the integration lead's format specification. This file describes what was delivered against it. Branch: `feature/member-a-manipuri-agri`.

This folder is the `Member_A/` of the task plan. It keeps the integration lead's name, `team/member-a-agronomy/`, because the router, the answer templates and `team/check_deliverables.py` read from it. This file is the plan's `README.md`; the folder's own `README.md` stays the integration lead's specification.

## 1. Purpose

AG-04 ranks monitored areas by crop and pest **risk indicators** (weather favourable to a pest, NDVI anomaly, reports) and answers questions about them. Member A supplies the knowledge that layer needs:

- Latin-script Manipuri questions, mapped to AG-04's intents
- Agricultural terminology in Latin-script Manipuri
- Sourced pest-weather thresholds in the engine's own schema
- Conservative, sourced advisory text

This folder contains data and documentation. The code that reads it is described in section 9.

## 2. Files and status

| File | What it holds | Count | Status |
|---|---|---|---|
| `manipuri_queries.json` | Latin-script Manipuri questions with intent mapping | 8 | DRAFT: 5 dataset sentences, 3 of Member A's examples; awaiting a fluent speaker |
| `agri_terms_manipuri.json` | Agricultural, weather, risk and place terms, each with verbatim evidence rows | 40 terms, 51 forms | DRAFT: attested in the dataset, alignment awaiting a fluent speaker |
| `verified_pest_rules.json` | Pest-weather rules in the schema of `satquery/agri/assets/pest_rules.json` | 2 rules: rice_blast sourced, BPH placeholder | PLACEHOLDER: no agronomist sign-off yet |
| `verified_risk_model.json` | Weights, level cut-points and scoring breakpoints, in the schema of `satquery/agri/assets/risk_model.json` | every value unchanged from the engine | PLACEHOLDER: no source supports a change (`SOURCES.md` §3) |
| `manipuri_responses.json` | Latin Manipuri answer templates (section 9) | 24 messages, 5 written | DRAFT |
| `advisory.json` | Symptoms, weather link, prevention, monitoring, when to contact | 2 pests + 1 general item | DRAFT |
| `SOURCES.md` | Every source, quotation, mapping choice, applicability and limitation | — | — |

**Not delivered:** a separate `advisories.md`. The team format is `advisory.json`.

**Nothing is marked VERIFIED.** Every `verified_by` / `verified_on` field is empty on purpose. These fields record a named person's check, and that check has not happened yet.

## 3. Language scope: Latin Manipuri

- All query texts and term forms use `"script": "Latn"`: romanised Manipuri, as in the dataset's `romanstandard` column.
- The romanisation marks the long vowel as `ā` (for example *aying asā*, *loumi*, *khudongthiningngāi*). Some dataset sources (*Poknampham* news, `en_mni(meitei).xlsx`) romanise without macrons or with other spellings. The terms file lists the common spelling variants in `notes`.
- Meitei Mayek is not the primary form. A query's Meitei Mayek text appears only in `dataset_ref.meiteiscript`, so a reviewer can cross-check it against the dataset.

## 4. Dataset

`CompiledDataEnglishToMeitei.xlsx`: 107,592 human-translated English–Meitei sentence pairs. Each sentence's source document and translator are listed in the `legend` sheet. Every entry here cites its Excel row number, so a reviewer can open the workbook and check it. The workbook itself is not committed (it is 32 MB). Method and row-number checks are in `SOURCES.md` §1.

- **Queries** are whole dataset sentences, copied as they are.
- **Terms** are words that recur across many sentence pairs. Deciding which word matches the English term was a judgement that a speaker must confirm.

Nothing was composed, edited or machine-translated.

## 5. Query intents

The intents are AG-04's own (`INTENTS` in `satquery/agent/language.py`); the checker accepts only these.

| # | Question type | AG-04 intent → existing behaviour | Delivered |
|---|---|---|---|
| 1 | Which areas are at high risk? | `AREA_RISK_QUERY` → risk ranking | mni-006 *Kanagumba area high risk da lei?* (Member A) |
| 2 | Why is this area at risk? | `AREA_EXPLANATION` → explain the selected area | mni-002 *masi karamna khudongthiningngāi oibano?* "How is it dangerous?"; mni-003 *masi sāphaba mapham ama oibrā?* "Is this a safe area?" |
| 3 | Which area should we inspect first? | `INSPECTION_PRIORITY` → inspection order | mni-001 *ei kadāidagi hougadage?* "Where should I begin?" |
| 4 | How healthy are crops here? | `CROP_HEALTH` → NDVI crop health | mni-008 *Eigi field da crop condition kayano?* (Member A) |
| 5 | Is there pest risk here? | `PEST_RISK` → explain the selected area's pest risk | mni-007 *Area asi da pest risk yamna lei-i?* (Member A) |
| 6 | Is there weather-related crop risk? | `WEATHER_RISK` → weather forecast for a drawn area | mni-004 *aying asā karamna touri?* "How is the weather?"; mni-005 *hayeng nong chugādrā?* "Will it rain tomorrow?". These ask about the weather, not crop risk from it. |
| 7 | Show me the risk in [area]. | `AREA_SPECIFIC_RISK` (with `area`) → explain the named area | **none**: no corpus sentence, no example yet |
| 8 | Why was [area] prioritized? | `AREA_SPECIFIC_RISK` (with `area`) → explain the named area | **none** |

**Notes:**
- mni-002 and mni-003 are general-domain sentences. Their `notes` explain the proposed dashboard reading, which the speaker should confirm or reject.
- mni-006 to mni-008 are code-mixed, as Member A wrote them. Their `source` quotes the request they came from.
- Types 7 and 8 need sentences from Member A or a fluent speaker. A sentence that names a district needs that district's Manipuri form in the terms file (section 6) so the area matcher can find it.

**Left out on purpose:**
- "Which crops are affected?" (row 99907): AG-04 monitors rice areas and cannot answer per crop.
- "What is the cause of the disease?" (row 92755): it would imply AG-04 diagnoses disease, which it does not.

### Worksheet for a fluent speaker: native wording and the missing types

These sentences are **not** written here, because writing them would mean inventing Manipuri. They are needed for question types 7 and 8, and for native (not code-mixed) versions of mni-006 to mni-008. Below are the dataset words and sentence patterns a speaker can draw on. All are attested; the row numbers point to the dataset.

| Intent | English query | Attested pieces |
|---|---|---|
| `AREA_RISK_QUERY` | Which areas are at high risk? | *karamba* "which" (row 99907 *karamba mahei-marongsingda sokhallibano?* "Which crops are affected?"); *maphamsing* "areas"; *khudongthiningngāi* "risk"; *khwāidagi wāngba* "highest" (row 103610) |
| `AREA_SPECIFIC_RISK` (set `area`) | Why is Bishnupur at risk? | *karigi* "why" (rows 26984, 101675); *bisanupura* "Bishnupur" and the other district forms in the terms file; *khudongthiningngāi oire* "is at risk" (row 98175) |
| `PEST_RISK` | Is there pest risk here? | *tin-kāng* "pest"; *mapham asida* "here" (row 7843); *khudongthiningngāi*; yes/no question ending *-brā* (row 15525) |
| `CROP_HEALTH` | How healthy are the crops here? | *mahei-marong* "crops"; *karamna* "how" (row 29434); *mapham asida* "here". No attested word for crop health. |
| `INSPECTION_PRIORITY` (a "we" form) | Which area should we inspect first? | *ahānba* "first" (row 88919 *nangna ahānba oina karamba … yenggadage?* "Which film will you watch first?"); *yengsinba* "inspect"; *eikhoi* "we" (row 102771) |

Each new sentence needs `verified_by`, `verified_on` and an `english_meaning`. Run `python team/check_deliverables.py` afterwards.

## 6. Agricultural terminology

The 40 terms fall into these categories:

| Category | Terms |
|---|---|
| crop | crop, rice, paddy, paddy field, field, farming, farmer, harvest, seed, soil, plant |
| pest | pest, insect |
| disease | disease, infection |
| weather | rain/rainfall, weather, temperature, relative humidity, drought, flood, storm |
| crop_health | damage, ruined (verb), soil health |
| risk | risk/danger, low risk, warning, affected area |
| inspection | inspection, priority |
| place | area, district, Manipur and the 7 demo districts' names |

**Things to watch:**
- *aying asā* means both "weather" and "temperature".
- *khudongthiningngāi* means both "risk" and "danger".
- *maru* also means "important".
- Humidity, infection and priority are attested only as English loanwords.

**Not attested** (left out): infestation, pest outbreak, crop disease, plant disease, crop health, healthy crop, vegetation, vegetation stress, crop stress, water stress, high risk, moderate risk, early warning, field inspection.

The district forms (*bisanupura*, *kākching*, *imphāl*, *thoubāl*, *churāchandapura*, *jiribam*) differ from the English spellings. The app's area matcher (`resolve_area` in `satquery/agri/query.py`) would need them to recognise districts in Latin-Manipuri questions.

## 7. Risk-rule verification policy

- A rule may be `VERIFIED` only when every number traces to a cited source and a named agronomist has checked it. The engine refuses `VERIFIED` without `verified_by` and `verified_on` on each source.
- **Rice blast** values now come from the Government of India DPPQ&S advisory of 22.07.2022 (22–28 °C; RH > 95%; leaf wetness > 10 h). Two mapping choices are documented in `SOURCES.md` §3 and need an agronomist's decision:
  - the temperature range is read as a daily mean;
  - hours with RH ≥ 95% stand in for leaf wetness.
- **Brown planthopper**: the authoritative sources consulted give no numeric threshold. Its values are the original, unsourced development placeholders, and its `sources` list stays empty so nothing appears to back them.
- **Framing:** rules describe weather that **favours** a pest. A high score is an early-warning indicator for field inspection, not a diagnosis. Satellite NDVI shows crop stress, not a specific disease.

## 8. Placeholder policy

- Anything without a source stays `PLACEHOLDER`, and anything without a named reviewer stays `DRAFT` or `PLACEHOLDER`.
- Unattested Manipuri is left out and listed (sections 5 and 6), never guessed.
- The dashboard keeps showing "PLACEHOLDER thresholds" until a fully verified rules file is configured. That is correct for now.

## 9. How the SatQuery application can use these files

The application code that reads these files is on this branch. Merging it is the integration lead's decision (`team/README.md`).

**`verified_pest_rules.json`:** works today through existing configuration, with no code change. It loads with the engine's own loader, and the dashboard keeps its PLACEHOLDER label because the rules are not verified.

```bash
SATQUERY_AGRI_PEST_RULES=team/member-a-agronomy/verified_pest_rules.json python -m satquery.agri thresholds
SATQUERY_AGRI_PEST_RULES=team/member-a-agronomy/verified_pest_rules.json python -m satquery.agri assess --no-ndvi
```

**`agri_terms_manipuri.json` and `manipuri_queries.json`:** wired into the router, on DRAFT data:

```text
question -> satquery/agent/language.py: words -> concepts -> common intent (+ language, places)
         -> existing router: risk engine (rank / inspect / explain), weather specialist, or NDVI crop health
```

- **Lexicon:** `language.py` reads the terms (concept from `category`, or from an optional `concept` field) and the `cue_words` (why, how, which/any, where, begin, first, this, here, high) from `agri_terms_manipuri.json`. No Manipuri word is written in code.
- **Path:** override the lexicon file with `SATQUERY_MANIPURI_LEXICON`.
- **Meitei Mayek:** a question in Meitei Mayek is converted letter by letter to the `romanstandard` spelling (`satquery/agent/meitei_mayek.py`) and then read like a Latin one. The answer comes in Latin Manipuri. Checked against all 107,551 corpus rows:
  - 96.2% of words convert to their `romanstandard` spelling, ignoring accents;
  - 99.3% of the 2,070 rows that get an intent get the same one from Meitei Mayek.

  The rest come from the corpus spelling one word several ways (*ee*/*i*, *ao*/*āu*, *parāioriti*/*prāioriti*), or from English words written phonetically in Meitei Mayek. Bengali script is not converted.
- **Intents:** the intent names are the ones in this README. `INTENTS` in `language.py` maps each onto the existing behaviour, and `team/check_deliverables.py` uses the same table.
- **Tests:** `tests/test_language_routing.py` routes every entry of `manipuri_queries.json` and checks that it reaches its labelled intent. New verified queries are covered automatically.
- **Unverified label:** every Latin Manipuri routing rule says the lexicon is not yet verified, until the file's `status` is `VERIFIED`.

**`manipuri_responses.json`:** Latin Manipuri answers. A question asked in Latin Manipuri is answered in Latin Manipuri; English questions keep their English answers.

- **Why templates:** AG-04's answers are written by code, not by a language model, so `satquery/agri/answer_language.py` fills one template per message with the engine's own values (level, score, confidence, names, counts). The engine's reasons and NDVI figures are inserted verbatim.
- **Fallback:** a message whose `text` is `null` is shown in English. A template is refused, and English shown instead, if it changes the `{slots}`, drops PLACEHOLDER or SAMPLE from a warning, or claims a confirmed diagnosis or outbreak.
- **Written so far:** 5 of 24 templates, all taken from sentences Member A gave on 2026-10-08 (DRAFT). The other 19 have their English text in `english`, ready for a fluent speaker to write `text`. A machine translation is never put in `text` as finished wording (section 11).
- **Path:** override the file with `SATQUERY_MANIPURI_RESPONSES`.

**`advisory.json`:** not read by the application yet. It could feed the area drawer's "what to do" text later.

## 10. What still needs a person

| Who | Task |
|---|---|
| Fluent Manipuri speaker | Check the 8 queries and 40 terms against their rows; fill `verified_by`/`verified_on`; write question types 7 and 8 (section 5) and the 19 unwritten answer templates (section 9). |
| Agronomist (Department of Agriculture, KVK or CAU Imphal) | Decide the blast mapping choices; sign off S1; provide a sourced BPH threshold; review `verified_risk_model.json` and `advisory.json`. |

Check after any edit:

```bash
python team/check_deliverables.py
```

## 11. Is fine-tuning a translation model necessary? Not now

Training is paused. The language layer was built and checked first, and on that evidence fine-tuning is not needed.

- **Understanding** a question needs words, not a model. AG-04 has 7 intents, and `language.py` maps a question onto one through concepts (risk, pest, crop, why, which, here and so on) read from `agri_terms_manipuri.json`. New wording is handled by adding attested forms to the lexicon.
- **Answering** needs about 24 fixed sentences, not open translation. Every answer is assembled by code from the engine's values. A fluent speaker writing the 19 missing templates is a short, checkable job. A model's draft of the same sentences would still need that speaker's review.
- **The corpus lacks the domain.** It has no sentence of AG-04's question types and about 1% agricultural text (`SOURCES.md` §1, *Corpus suitability*). A model fine-tuned on it would not learn AG-04's wording.
- **The values must stay exact.** A translation model could reword a score, a level or a PLACEHOLDER warning. Templates with checked `{slots}` cannot.

**When to reconsider:**
- the questions people ask in the field outgrow the lexicon (measure that from real queries first);
- a speaker wants machine drafts to edit.

Any machine draft must be labelled as such, stay `DRAFT` with empty `verified_by`, and pass `usable()` in `answer_language.py`. It is never presented as verified.
