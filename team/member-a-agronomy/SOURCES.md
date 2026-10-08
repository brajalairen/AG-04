# Member A: sources and verification status

Date of this record: 2026-10-08. Nothing in this folder has yet been signed off by a named fluent speaker or agronomist, so every `verified_by` / `verified_on` field is empty and every file is `DRAFT` or `PLACEHOLDER`.

| Status word | Meaning here |
|---|---|
| **Sourced** | The value or text is taken from the cited source. Not yet checked by a person. |
| **Verified** | A named person has checked it against the source and filled in `verified_by` and `verified_on`. Nothing has reached this status yet. |
| **Placeholder** | A development value with no supporting source. |

---

## 1. Language data

### Dataset

| Field | Value |
|---|---|
| File | `CompiledDataEnglishToMeitei.xlsx`. It is not committed to the repository (32 MB; the team rules forbid committing large datasets). |
| Sheets | `compiled`: 107,592 English–Meitei sentence pairs (Excel rows 2–107,593). `legend`: 103 batches, mapping each row range to its source document and contributor. |
| Columns used | `english`, `romanstandard` (Latin-script Manipuri). The `meiteiscript` column is copied into `dataset_ref` for cross-checking only. |
| Source documents | Batches come from *The Sangai Express*, *Poknampham*, `fresh_eng_meit_datasets_AZURE.xlsx`, `en_mni(meitei).xlsx`, `bpcc_daily_mni_mtei.xlsx`, test sets, school readers and translated books (full list in the `legend` sheet). |
| Accessed | 2026-10-08, from a local copy |
| Row numbers | Every `row` in the JSON files is the Excel row number in the `compiled` sheet. Spot-checked against the workbook with openpyxl (rows 2, 15525, 29434, 29686, 80425, 91825, 100486 and 107593 all match). |

### How the entries were chosen

- **Queries** (`manipuri_queries.json`):
  - mni-001 to mni-005 are complete dataset sentences, copied as they are. I searched the dataset for questions that match an AG-04 intent and kept only sentences whose English meaning fits the intent.
  - mni-006 to mni-008 are Member A's own example questions, given in the integration requests of 2026-10-08. They are not in the corpus. Each entry's `source.quote` repeats the request text. They are code-mixed (English words such as *area*, *pest risk* and *crop condition* inside Manipuri), as Member A wrote them.
  - Nothing was composed by the assistant, edited or machine-translated.
- **Terms** (`agri_terms_manipuri.json`):
  1. For each English term, I listed the Latin-Manipuri words that co-occur with it across all rows (Dice co-occurrence score).
  2. I read the candidate rows by hand.
  3. I kept only words that recur consistently. For each kept word, 2–4 evidence rows are quoted verbatim.

  A script checked that each listed form occurs in its evidence rows (ignoring accents and hyphens), that each evidence row contains a listed form, and that every form is Latin script.
- **Where judgement was used:** deciding which word in a sentence corresponds to the English term (word alignment). A fluent speaker must confirm that alignment.

### Status

| File | Entries | Status |
|---|---|---|
| `manipuri_queries.json` | 8 queries | **Sourced**: 5 dataset sentences and 3 of Member A's examples. Not yet checked by a fluent speaker for meaning or intent mapping. |
| `agri_terms_manipuri.json` | 40 terms, 51 Latin forms | **Sourced** (attested in the dataset). Alignment not yet checked by a fluent speaker. |

### Not attested in the dataset (left out, not guessed)

- **Agricultural terms:** infestation, pest outbreak, crop disease, plant disease, crop health, healthy crop, vegetation, vegetation stress, crop stress, water stress, damaged crop (as a noun phrase), high risk, moderate risk, early warning, field inspection.
- **Native Manipuri word for humidity:** only the loanword *riletiba hayumiditi* appears.
- **Query intents:** AREA_RISK_QUERY, AREA_SPECIFIC_RISK, PEST_RISK and CROP_HEALTH have no suitable dataset sentence (see `MEMBER_A_README.md`). Member A's examples now cover all of them except AREA_SPECIFIC_RISK.

### Corpus suitability (checked 2026-10-08)

Read-only count over the CSV export of the workbook (`CompiledDataEnglishToMeitei.csv`: the `compiled` sheet plus the 103 `legend` rows). The script is not committed; it ran outside the repository.

| Check | Result | What it means |
|---|---|---|
| Size | 107,592 pairs; 3 empty `romanstandard`; 3,420 exact duplicate pairs | A large general resource |
| Romanisation | 80.8% of `romanstandard` rows use macrons (`ā`); the rest follow other conventions (*Kayam saathige*, *sathibro*, *cheng leibro*) | Spelling varies, so the router matches spelling variants and folds accents |
| Domain | 1,297 pairs (1.2%) mention crops, rice, pests, farms, fields, insects or disease; *pest* 11, *planthopper* 0, *humidity* 6, *NDVI/satellite* 21 | Very little agricultural text |
| Questions | 6,438 question pairs; 35 of them agricultural | Few question forms in the domain |
| AG-04's question types | High-risk areas 0; why at risk 0; crop health 0; pest risk 0; weather risk to crops 0; risk in a named area 0 (3 loose matches); inspect first 1 (*ei kadāidagi hougadage?*); why prioritised 0 (*nangbu karigi khankhibano?* "Why have you been selected?" is the nearest) | The corpus cannot supply these questions |
| Phrases it does attest | *khudongthiningngāida leibrā?* "at risk?" (row 100976); *hakchāng phabrā?* "is it healthy?" (row 62727); *ngasigi aying asā asi kamāina touri?* "what's the weather like today?" (row 3058) | Building blocks for a speaker, not sentences to compose from |

**Verdict:** the corpus is suitable as a vocabulary resource: terms, spelling variants and attested phrases for the router's lexicon, plus a source a reviewer can check against. It is not a source of AG-04's questions or answers, because the domain sentences are not in it. For the same reason, a translation model fine-tuned on it would learn little of AG-04's wording, and its output would still need a fluent speaker's review. See `MEMBER_A_README.md` §11.

---

## 2. Agricultural and scientific sources

All sources were accessed on 2026-10-08. PDFs were downloaded and their text extracted. The quotations below are exact, apart from OCR clean-up of the degree sign.

| # | Source | Publisher | URL | What was taken | Used in |
|---|---|---|---|---|---|
| S1 | *Advisory on blast disease (Magnaporthe oryzae) on rice crop*, F.No 3-6/2022-23, dated 22.07.2022, addressed to the Directors of Agriculture of all States/UTs | Directorate of Plant Protection, Quarantine & Storage (DPPQ&S), Ministry of Agriculture & Farmers Welfare, Government of India | https://ppqs.gov.in/sites/default/files/rice_blast_advisory.pdf | "Rice blast is favored by low temperatures (22-28°C), high relative humidity (>95%), dew deposits, leaf wetness for more than 10 hours, application of high nitrogen and aerobic soils." Also its IPM practices (field sanitation, crop rotation, certified seed, water level) and the instruction that fungicides follow the Registration Committee's label claim. | `verified_pest_rules.json` (rice_blast), `advisory.json` |
| S2 | *Advisory on Brown Plant Hopper (Nilaparvata lugens) on rice crop*, July 2022 (day illegible in the scan) | DPPQ&S, Government of India | https://ppqs.gov.in/sites/default/files/rce_bph_advisory.pdf | Where BPH occurs, symptoms (hopperburn), IPM practices, and the instruction that pesticides follow the label claim. **No numeric weather threshold.** | `advisory.json` |
| S3 | *Integrated Pest Management Package for Rice* (2014) | NCIPM, DPPQ&S and NIPHM | https://niphm.gov.in/IPMPackages/Rice.pdf | "High dosages of nitrogenous fertilizers, close spacing, and high relative humidity increases planthopper populations." **No numeric threshold.** | `advisory.json` |
| S4 | Rice Knowledge Bank / Rice Doctor fact sheet: *Blast (Leaf and Collar)* | IRRI (with ACIAR and the University of Queensland) | http://www.knowledgebank.irri.org/training/fact-sheets/pest-management/diseases/item/blast-leaf-collar | Qualitative conditions ("low soil moisture, frequent and prolonged periods of rain shower, and cool temperature in the daytime"; dew from large day-night temperature differences), symptoms, management. **No numbers.** | `advisory.json` |
| S5 | Rice Doctor fact sheet: *Blast (Node and Neck)* | IRRI | https://keyserver.lucidcentral.org/key-server/data/0e090d01-0209-460e-810c-0d060708030c/media/Html/Blast_(Node_and_Neck).htm | Neck and node symptoms; distinguishing them from stem borer whiteheads | `advisory.json` |
| S6 | Rice Knowledge Bank fact sheet: *Planthopper* | IRRI | http://www.knowledgebank.irri.org/training/fact-sheets/pest-management/insects/item/planthopper | Where BPH occurs, symptoms, monitoring method and the "1 BPH per stem or less" action note, prevention. **No numeric weather threshold.** | `advisory.json` |
| S7 | TNAU Agritech Portal, rice blast: *Other management* | Tamil Nadu Agricultural University | https://agritech.tnau.ac.in/crop_protection/rice_diseases/another%20methods_rice_1.html | "High relative humidity (93-99 per cent) Low night temperature (between 15-20 C or less than 26 C". **Cross-check only.** It disagrees with S1 on temperature; see below. | not used in any value |

Research papers on BPH and weather (correlation studies from Bangladesh, Korea and India, found by web search) were **not** used. They report the conditions seen during particular outbreak periods, not decision thresholds.

---

## 3. Thresholds in `verified_pest_rules.json`

The file uses the engine's own schema (`satquery/agri/config.py`) and loads with the engine's loader (`python team/check_deliverables.py`). File status: **PLACEHOLDER**.

### Rice blast (`rice_blast`): sourced from S1, still PLACEHOLDER

| Condition in the file | Value | Unit | Source text (S1) | How it was mapped | Status |
|---|---|---|---|---|---|
| `temperature_2m`, `mean`, `between` | 22–28 | °C (daily mean of hourly 2 m air temperature) | "low temperatures (22-28°C)" | S1 does not say whether this is a daily mean, a night temperature or an hourly range. Daily mean was chosen to match the engine's existing form. | Sourced (mapping needs an agronomist) |
| `relative_humidity_2m`, `hours_at_or_above` | threshold 95, at least 11 | % RH; hours per day | "high relative humidity (>95%) … leaf wetness for more than 10 hours" | Leaf wetness is not in the weather data. Hours with RH ≥ 95% stand in for wet-leaf hours: **a modelling assumption, not in S1**. "More than 10 hours" over hourly values = at least 11. The engine can only test ≥, so a value of exactly 95% also counts. | Sourced (proxy needs an agronomist) |
| Not encoded | — | — | "dew deposits", "application of high nitrogen and aerobic soils" | Not available from weather data | — |
| `past_days` 7, `forecast_days` 3, `full_score_days` 5 | — | days | — | Engine operating choices kept from the original placeholder, not from a source | Placeholder |

**Applicability:**
- Region: national advisory for all States/UTs, not specific to Manipur.
- Crop stage: S1 says blast "can infect rice crop at all growth stages"; the rule is not tied to a stage.
- Season: issued in July 2022 for the kharif crop.

**Limitations:**
- The rule describes weather that favours blast. It does not detect blast.
- Weather is modelled at one Open-Meteo point per area, not field microclimate.
- Sources disagree: S7 gives low night temperature 15–20 °C (or under 26 °C) and RH 93–99%, against S1's 22–28 °C and RH > 95%. S1 was preferred as the Government of India advisory to state agriculture departments. An agronomist should confirm that choice for Manipur.

**Behaviour check (an observation, not validation):** live weather on 2026-10-08, 7 demo areas, 7 past + 3 forecast days, `python -m satquery.agri assess --no-ndvi`.

| Rule | Favourable days, rice blast | Blast index | Weather factor |
|---|---|---|---|
| Original placeholder (RH ≥ 90% for ≥ 8 h, mean 20–28 °C) | 9–10 of 10 in every area | 1.0 in all 7 areas | 71.4 points everywhere |
| S1-based candidate | 1–6 of 10 | 0.2–1.0 | 14.3–71.4 points |

The candidate rule separates areas where the placeholder could not. That says nothing about whether either rule is agronomically right.

### Brown planthopper (`brown_planthopper`): PLACEHOLDER, values unchanged

- S2, S3 and S6 describe BPH qualitatively (submerged fields, shade, high humidity, excess nitrogen, dense canopy) but give **no numeric temperature or humidity threshold**.
- The original development values (daily mean 25–32 °C, daily mean RH ≥ 80%) are therefore kept **unchanged and unsourced**, with an empty `sources` list, so that no source appears to back them.
- **Needed:** a published threshold from ICAR-NRRI, ICAR-IIRR, an SAU (for example CAU Imphal) or a KVK, or a decision by the Department of Agriculture.

### Risk model (`verified_risk_model.json`): PLACEHOLDER, values unchanged

`verified_risk_model.json` is a copy of `satquery/agri/assets/risk_model.json` with **every value unchanged**. Its `sources` list is empty and its status is PLACEHOLDER. The weights (0.5 / 0.3 / 0.2), level cut-points and scoring breakpoints are operating choices. None of the sources above supports changing them, and the team rule is to change them only with a cited reason.

The file gives the agronomist one place to record reviewed values: change a value, cite its source with `verified_by`/`verified_on`, and set VERIFIED only when every value is backed. A test (`tests/test_team_deliverables.py`) fails if a value changes while the file has no source.

---

## 4. `advisory.json`

Every item names its source (S1–S6) and URL. Deliberately left out:
- fungicide and insecticide names and doses (S1 and S2 list them; chemical advice is left to the Department of Agriculture / KVK);
- bio-agent doses;
- all phone numbers and e-mail addresses (those in S1 and S2 are addressed to state officials, not farmers).

The one "general" item states AG-04 project policy and is labelled as such, not as an external source.

---

## 5. What a reviewer needs to do

1. **Fluent speaker:** check each query and term against its evidence rows. Fill `verified_by` and `verified_on` per entry, and set the file `status` to `VERIFIED` once every entry is checked. Correct or remove anything wrong.
2. **Agronomist (Department of Agriculture, KVK or CAU):**
   - Read S1 and decide on the two mapping assumptions for blast (daily mean, and the RH ≥ 95% leaf-wetness proxy).
   - Then add `verified_by` and `verified_on` to S1 in `verified_pest_rules.json` and set `rice_blast` to `VERIFIED`.
   - Supply a sourced BPH threshold, or keep BPH as PLACEHOLDER.
   - Review `advisory.json`.
