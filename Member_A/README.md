# Member A: Manipuri and agricultural knowledge

Branch: `Manipuri-Integration`. Git does not allow spaces in branch names, so "Manipuri Integration" became `Manipuri-Integration`.

## 1. Purpose

AG-04 ranks monitored areas by crop and pest **risk indicators** and answers questions about them. The indicators are weather favourable to a pest, NDVI anomaly and pest reports. Member A supplies the knowledge this needs, so that AG-04 can be asked and answered in Latin-script Manipuri:

- Latin Manipuri questions mapped to AG-04's own intents;
- agricultural terminology in Latin Manipuri;
- sourced pest-weather rules in the engine's own schema;
- short, sourced, non-chemical advisories.

No second risk engine, model or application was built. The existing engine computes every result; this folder only changes the language a question can be asked in and answered in.

## 2. Files and status

| File | What it holds | Count | Status |
|---|---|---|---|
| `manipuri_queries.json` | Latin Manipuri questions with their AG-04 intent | 8 | DRAFT: 5 corpus sentences, 3 of Member A's own examples |
| `agri_terms_manipuri.json` | Terms, and the question words the router uses, each with verbatim corpus evidence rows | 43 terms (54 forms), 14 cue words | DRAFT: attested in the corpus; alignment awaits a fluent speaker |
| `verified_agricultural_risk_rules.json` | Pest-weather rules in the engine's schema (`satquery/agri/assets/pest_rules.json`) | 2 rules | PLACEHOLDER: rice blast sourced (S1), brown planthopper unsourced |
| `verified_risk_model.json` | Weights, level cut-points and scoring breakpoints, in the engine's schema | the engine's values, unchanged | PLACEHOLDER: no source supports a change |
| `manipuri_responses.json` | Latin Manipuri answer templates (section 9) | 24 messages, 5 written | DRAFT |
| `advisories.md` / `advisory.json` | Field advisories, readable and structured | 2 pests, general guidance | DRAFT |
| `SOURCES.md` | Every source, quotation, mapping choice, applicability and limitation; the corpus evaluation | — | — |

**Nothing is VERIFIED.** Every `verified` flag is `false` and every `verified_by` / `verified_on` is empty, because no named fluent speaker or agronomist has checked the content yet. `team/check_deliverables.py` rejects an entry marked `verified: true` without a named reviewer and a date.

The integration lead's format specification and templates stay in `team/member-a-agronomy/`.

## 3. Language scope: Latin Manipuri

- **Spelling:** questions and terms are romanised Manipuri (`"script": "Latn"`), spelled as in the corpus's `romanstandard` column, with `ā` for the long vowel.
- **Typing it differently:** people type it without macrons, with hyphens or without them. The router folds those away (*kayāno* = *kayano*).
- **Code-mixed questions work** (*Area asi da pest risk yamna lei-i?*): English words count as well.
- **English questions are untouched.** They take the existing English router and get English answers.

## 4. Source dataset

The corpus is `CompiledDataEnglishToMeitei.xlsx`, converted to `CompiledDataEnglishToMeitei.csv`. It contains 107,592 human-translated English–Meitei sentence pairs, with these columns:
- `english`
- `meiteiscript`
- `romanstandard`
- `bengaliscript`
- `Source`
- `Total Words`

The `legend` rows give each row range's source document and contributor.

- **Not committed:** the CSV is 75 MB and the workbook 32 MB, so both stay local, outside Git. Every entry here cites its row number, so a reviewer can check it against them.
- **Quality:**
  - 3 empty `romanstandard` rows and 3,420 exact duplicate pairs;
  - 80.8% of rows mark long vowels with `ā`;
  - the rest follow other spelling conventions.
- **Agricultural content:** only 1.2% of pairs, and no sentence of AG-04's own question types.
- **Verdict:** the corpus is a good **vocabulary** source and a poor **sentence** source. Details are in `SOURCES.md` §1, *Corpus suitability*.

## 5. Query dataset (`manipuri_queries.json`)

AG-04's intents are defined in `INTENTS` in `satquery/agent/language.py`. No new intent names were created.

| # | Question type | AG-04 intent → existing behaviour | Query |
|---|---|---|---|
| 1 | Which areas are at high risk? | `AREA_RISK_QUERY` → risk ranking | mni-006 *Karmba area high risk ta lei?* (Member A) |
| 2 | Why is this area at risk? | `AREA_EXPLANATION` → explain the selected area | mni-002 *Masida karamna khudongthiningngai oibano?*; mni-003 *Masi saphaba mapham oibra?* (corpus, edited by Member A) |
| 3 | Which area should we inspect first? | `INSPECTION_PRIORITY` → inspection order | mni-001 *Ei kadaidagi hougadage?* (corpus) |
| 4 | How healthy are crops here? | `CROP_HEALTH` → NDVI crop health | mni-008 *Eigi field da crop condition kamai touri?* (Member A) |
| 5 | Is there pest risk here? | `PEST_RISK` → the selected area's pest risk | mni-007 *Area asi da pest risk yamna leibra?* (Member A) |
| 6 | Is there weather-related crop risk? | `WEATHER_RISK` → weather forecast for a drawn area | mni-004 *Aying asa karamna touri?*; mni-005 *Hayeng nong chugadra?* (corpus). These ask about the weather itself. |
| 7 | Show me the risk in [area]. | `AREA_SPECIFIC_RISK` → explain the named area | **none yet** |
| 8 | Why was [area] prioritized? | `AREA_SPECIFIC_RISK` → explain the named area | **none yet** |

**Where the sentences come from:**
- **Corpus sentences** started as exact copies. `dataset_ref` keeps the published row (row number, `romanstandard`, `meiteiscript`).
- **Member A's sentences** quote the request they came from in `source`.
- **Member A's edits** of 2026-10-08 are recorded per entry in `edits`, with the previous and new text. Member A rewrote mni-002 and mni-003, and removed the macrons and capitalised mni-001, mni-004 and mni-005; the router reads these the same either way. Member A also revised mni-006 to mni-008. mni-002 and mni-003 carry Member A's own Meitei Mayek in `meiteiscript`.
- **Nothing was composed by the assistant or machine-translated.**

**Types 7 and 8** need a sentence from Member A or a fluent speaker; the corpus has none. The district names are already in the terms file: *bisanupura*, *kākching*, *imphāl*, *thoubāl*, *churāchandapura* and *jiribam*. A Latin Manipuri question that names a district therefore already resolves to that area. A worksheet of attested building blocks for these sentences is in section 10.

## 6. Terminology (`agri_terms_manipuri.json`)

43 terms, each attested in the corpus, with 2–4 evidence rows quoted verbatim:

| Category | Terms |
|---|---|
| crop | crop, rice, paddy, paddy field, field, farming/cultivation, farmer, harvest, seed, soil, plant, vegetation |
| pest / disease | pest, insect, disease, infection |
| weather | rain, weather, temperature, relative humidity, drought, flood, storm, cloud |
| crop health | damage, be ruined, soil health |
| risk / inspection | risk/danger, low risk, warning, affected area, inspection, priority, safe |
| place | area, district, Manipur and the 7 demo districts |

**Needs a fluent speaker:** the corpus has no reliable form for these terms, so none was guessed.
- crop health, healthy crop, crop stress, vegetation stress, water stress, damaged crop;
- infestation, pest outbreak, crop disease, plant disease;
- brown planthopper, leaf folder, rice blast, bacterial leaf blight, sheath blight;
- cloudy weather, waterlogging;
- high risk, moderate risk, early warning, field inspection.

**Things to watch:**
- *aying asā* means both "weather" and "temperature".
- *khudongthiningngāi* means both "risk" and "danger".
- Humidity, infection and priority are attested only as English loanwords.

## 7. Agricultural rules and verification policy

- **Schema:** `verified_agricultural_risk_rules.json` uses the engine's own pest-rule schema, so it loads with the engine's loader. Two optional fields, `applicability` and `limitations`, were added to that schema. They document a rule and are never scored.
- **Rice blast:** the values come from the Government of India DPPQ&S advisory of 22.07.2022 (S1). Two mapping choices need an agronomist:
  - the 22–28 °C range is read as a daily mean;
  - hours at RH ≥ 95% stand in for leaf wetness.
- **Brown planthopper:** the values are unsourced development placeholders, and their `sources` list is empty.
  - ICAR-NCIPM's weather rules for BPH (S8) are location-specific and weekly, and none is for Manipur. The engine's daily rules cannot express them.
  - TNAU's economic threshold level (S9) is a field count of hoppers, so it is in `advisories.md` instead.
- **VERIFIED needs a named check:** a rule becomes `VERIFIED` only when every value traces to a cited source and a named agronomist has signed it off. The engine refuses `VERIFIED` without `verified_by` and `verified_on`.
- **Rules describe favourable conditions.** A high score is an early-warning signal for field inspection. AG-04 never says a pest or disease is confirmed. In Latin Manipuri answers, a template that claims a confirmed diagnosis or outbreak is refused.

## 8. Placeholder policy

- **No source → PLACEHOLDER.** Anything without a named reviewer stays `DRAFT` or `PLACEHOLDER`.
- **Unattested Manipuri is left out and listed** (sections 5 and 6), never guessed.
- **The dashboard says "PLACEHOLDER thresholds"** until verified rules are configured. Latin Manipuri answers keep that warning word for word.

## 9. How AG-04 uses these files

```text
Latin Manipuri / English question
  -> satquery/agent/language.py   words -> concepts -> AG-04 intent (+ language, places)
  -> existing router              risk engine (rank / inspect / explain) | weather | NDVI crop health
  -> existing engine result
  -> answer                       English as before; Latin Manipuri via satquery/agri/answer_language.py
```

### Understanding a question

- **Lexicon:** `language.py` reads the terms and cue words from `agri_terms_manipuri.json`. No Manipuri word is written in code.
- **Rules work on concepts.** The intent rules are written on concepts (risk, pest, why, which, here…), so one rule serves English, Latin Manipuri and code-mixed questions. No sentence is hard-coded.
- **Clarification:** an unclear agricultural question gets a request to rephrase. It is no longer sent to satellite image analysis.
- **Override:** point `SATQUERY_MANIPURI_LEXICON` at another lexicon file.

### Answering it

- **Templates, not a model:** AG-04's answers are written by code, so a Latin Manipuri question is answered by filling the templates in `manipuri_responses.json` with the engine's own values.
- **Inserted unchanged:** level, score, confidence, the engine's reasons (the evidence, including pest-report counts), NDVI figures and the PLACEHOLDER/SAMPLE warnings.
- **English fallback:** a message with no usable template stays in English, so a value or warning is never dropped. A template is unusable if it changes the `{slots}`, drops PLACEHOLDER or SAMPLE, or claims a confirmed diagnosis.
- **Written so far:** 5 of the 24 templates. The other 19 need a fluent speaker; until then those lines are in English.
- **Weather answers stay English** for now; their values are unchanged.
- **Override:** point `SATQUERY_MANIPURI_RESPONSES` at another templates file.

### Rules files

Use them through the engine's existing settings:

```bash
SATQUERY_AGRI_PEST_RULES=Member_A/verified_agricultural_risk_rules.json python -m satquery.agri assess --no-ndvi
SATQUERY_AGRI_RISK_MODEL=Member_A/verified_risk_model.json python -m satquery.agri thresholds
```

### Checks

```bash
python team/check_deliverables.py     # formats, provenance, verification claims, engine loaders
python -m pytest tests/test_language_routing.py tests/test_answer_language.py tests/test_meitei_mayek.py tests/test_team_deliverables.py
```

Every query in `manipuri_queries.json` is routed by the tests and must reach its labelled intent. New queries are covered automatically.

## 10. Worksheet for a fluent speaker

These sentences are **not** written here, because writing them would mean inventing Manipuri. The pieces below are attested; the row numbers point to the corpus.

| Intent | English | Attested pieces |
|---|---|---|
| `AREA_SPECIFIC_RISK` | Show me the risk in Bishnupur. / Why was Bishnupur prioritized? | *karigi* "why" (rows 26984, 101675); *bisanupura* and the other district forms; *khudongthiningngāi oire* "is at risk" (row 98175); *nangbu karigi khankhibano?* "Why have you been selected?" (row 102557) |
| `PEST_RISK` (native wording) | Is there pest risk here? | *tin-kāng* "pest"; *mapham asida* "here" (row 7843); *khudongthiningngāida leibrā?* "at risk?" (row 100976) |
| `CROP_HEALTH` (native wording) | How healthy are the crops here? | *mahei-marong* "crops"; *karamna* "how" (row 29434); *hakchāng phabrā?* "is it healthy?" (row 62727) |
| `INSPECTION_PRIORITY` ("we") | Which area should we inspect first? | *ahānba* "first" (row 88919); *yengsinba* "inspect"; *eikhoi* "we" (row 102771) |

Each new sentence needs:
- an `english_meaning`;
- a `source` (who gave it);
- `verified_by` and `verified_on` once checked.

Run `python team/check_deliverables.py` afterwards.

**Who still needs to do what:**
- **Fluent Manipuri speaker:**
  - check the 8 queries and 43 terms;
  - write types 7 and 8 and the 19 answer templates.
- **Agronomist** (Department of Agriculture, KVK or CAU Imphal):
  - decide the two blast mapping choices and sign off S1;
  - provide a BPH threshold that fits Manipur;
  - review `verified_risk_model.json` and the advisories.

## 11. Meitei Mayek: what exists and what to add

**Input already works.** A question in Meitei Mayek is converted letter by letter to the `romanstandard` spelling (`satquery/agent/meitei_mayek.py`), then routed like a Latin one. The answer comes in Latin Manipuri. Checked against all 107,551 corpus rows:
- 96.2% of words convert to their `romanstandard` spelling, ignoring accents;
- 99.3% of the 2,070 rows that get an intent get the same intent from Meitei Mayek.

**To add later:**
1. **Answers in Meitei Mayek:** add a `meiteiscript` text per template in `manipuri_responses.json`. Choose the answer script from the question's script, with the same slot and warning checks.
2. **Bengali-script input:** a converter like `meitei_mayek.py`, checked against the corpus's `bengaliscript` column in the same way.
3. **Voice:** the browser's speech recognition would need a Manipuri language option. Whether Chrome supports one is untested.

## 12. Fine-tuning: not proposed

The existing approach meets the goal without a trained model:
- **Understanding** needs vocabulary, and the lexicon holds it.
- **Answers** are about 24 fixed templates that a speaker can write and check.
- **The corpus lacks AG-04's domain** (section 4).
- **A translation model could reword a score or a warning.** Slot-checked templates cannot.

**If it is ever reconsidered** (for example, if real field questions outgrow the lexicon):

| Item | Plan |
|---|---|
| Model | A pretrained Indic translation model: IndicTrans2 distilled (about 200M parameters) or NLLB-200 distilled 600M |
| GPU | Fits the team's 6 GB RTX 4050 with fp16 and LoRA adapters, small batches and gradient accumulation (an estimate, not measured) |
| Data | The corpus's `english` and `romanstandard` columns as sentence pairs, with duplicates removed and a held-out test split |
| Evaluation | chrF and BLEU on the held-out split, then a fluent speaker's review of AG-04's own 24 messages |
| Risks | Little agricultural data, so domain wording would be weak; mixed romanisation; numbers or warnings may be reworded; each source document's licence must be checked; machine output must stay DRAFT until a speaker reviews it |

It would run offline, to draft text for a speaker to review. It would never be part of the application.
