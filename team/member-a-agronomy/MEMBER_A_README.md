# Member A delivery: Manipuri and agricultural knowledge

The folder's `README.md` is the integration lead's format specification. This file describes what was delivered against it. Branch: `feature/member-a-manipuri-agri`.

## 1. Purpose

AG-04 ranks monitored areas by crop and pest **risk indicators** (weather favourable to a pest, NDVI anomaly, reports) and answers questions about them. Member A supplies the knowledge that layer needs:

- Latin-script Manipuri questions, mapped to AG-04's intents
- Agricultural terminology in Latin-script Manipuri
- Sourced pest-weather thresholds in the engine's own schema
- Conservative, sourced advisory text

This folder contains data and documentation only. No application code was changed.

## 2. Files and status

| File | What it holds | Count | Status |
|---|---|---|---|
| `manipuri_queries.json` | Latin-script Manipuri questions with intent mapping | 5 | DRAFT: dataset sentences, awaiting a fluent speaker |
| `agri_terms_manipuri.json` | Agricultural, weather, risk and place terms, each with verbatim evidence rows | 40 terms, 51 forms | DRAFT: attested in the dataset, alignment awaiting a fluent speaker |
| `verified_pest_rules.json` | Pest-weather rules in the schema of `satquery/agri/assets/pest_rules.json` | 2 rules: rice_blast sourced, BPH placeholder | PLACEHOLDER: no agronomist sign-off yet |
| `advisory.json` | Symptoms, weather link, prevention, monitoring, when to contact | 2 pests + 1 general item | DRAFT |
| `SOURCES.md` | Every source, quotation, mapping choice, applicability and limitation | — | — |

**Not delivered:**
- `verified_risk_model.json`: no source supports changing the weights or cut-points (see `SOURCES.md` §3).
- A separate `advisories.md`: the team format is `advisory.json`.

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

The intents are the ones the checker accepts (`team/check_deliverables.py`).

| Intent | Existing AG-04 behaviour | Delivered |
|---|---|---|
| `INSPECTION_PRIORITY` | Inspection order | mni-001 *ei kadāidagi hougadage?* "Where should I begin?" |
| `AREA_EXPLANATION` | Why the selected area is flagged | mni-002 *masi karamna khudongthiningngāi oibano?* "How is it dangerous?"; mni-003 *masi sāphaba mapham ama oibrā?* "Is this a safe area?" |
| `WEATHER_RISK` | Weather forecast for a drawn area | mni-004 *aying asā karamna touri?* "How is the weather?"; mni-005 *hayeng nong chugādrā?* "Will it rain tomorrow?" |
| `AREA_RISK_QUERY` | Ranking of high-risk areas | **none**: no suitable dataset sentence |
| `AREA_SPECIFIC_RISK` | Why a named area is flagged | **none** |
| `PEST_RISK` | Pest risk in an area | **none** |
| `CROP_HEALTH` | NDVI crop-health answer | **none** |

mni-002 and mni-003 are general-domain sentences. Their `notes` explain the proposed dashboard reading, which the speaker should confirm or reject.

**Left out on purpose:**
- "Which crops are affected?" (row 99907): AG-04 monitors rice areas and cannot answer per crop.
- "What is the cause of the disease?" (row 92755): it would imply AG-04 diagnoses disease, which it does not.

### Worksheet for a fluent speaker: the missing intents

These sentences are **not** written here, because writing them would mean inventing Manipuri. Below are the dataset words and sentence patterns a speaker can draw on. All are attested; the row numbers point to the dataset.

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

No application file was changed. Integration is the integration lead's job (`team/README.md`).

**`verified_pest_rules.json`:** works today through existing configuration, with no code change. It loads with the engine's own loader, and the dashboard keeps its PLACEHOLDER label because the rules are not verified.

```bash
SATQUERY_AGRI_PEST_RULES=team/member-a-agronomy/verified_pest_rules.json python -m satquery.agri thresholds
SATQUERY_AGRI_PEST_RULES=team/member-a-agronomy/verified_pest_rules.json python -m satquery.agri assess --no-ndvi
```

**`manipuri_queries.json` and `agri_terms_manipuri.json`:** for Phase 6 (Manipuri). Questions are currently routed by English wording only:
- `satquery/agri/query.py` decides rank, inspect and explain;
- `satquery/agent/intents.py` detects weather and crop-health questions.

A Latin-Manipuri question currently matches none of these cues. The intent labels in the queries file map directly onto those paths, and the term forms (risk, inspection, weather words and district names) are the natural keyword list for them. Wire them in only after the entries are verified.

**`advisory.json`:** not read by the application yet. It could feed the area drawer's "what to do" text later.

## 10. What still needs a person

| Who | Task |
|---|---|
| Fluent Manipuri speaker | Check the 5 queries and 40 terms against their rows; fill `verified_by`/`verified_on`; write the missing intents (section 5). |
| Agronomist (Department of Agriculture, KVK or CAU Imphal) | Decide the blast mapping choices; sign off S1; provide a sourced BPH threshold; review `advisory.json`. |

Check after any edit:

```bash
python team/check_deliverables.py
```
