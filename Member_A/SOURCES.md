# Member A: sources and verification status

Date of this record: 2026-10-08.

- **Language data:** verified by Member A, the team's fluent Manipuri speaker, on 2026-10-08 (`verified_by: "Member A"`). This covers all queries and answer templates and 55 of the 59 lexicon entries; the 4 entries added after that review are not yet verified.
- **Agricultural content:** the rules, the risk model and the advisories have **not** been signed off by an agronomist, so they stay `PLACEHOLDER` or `DRAFT`.

| Status word | Meaning here |
|---|---|
| **Sourced** | The value or text is taken from the cited source. Not yet checked by a person. |
| **Verified** | A named person has checked it and filled in `verified_by` and `verified_on`. So far only Member A's language review has reached this status. |
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
  - mni-001 to mni-005 began as complete dataset sentences, copied as they are. On 2026-10-08 Member A edited their wording; each entry's `edits` gives the previous text, and its `dataset_ref` keeps the published row. I searched the dataset for questions that match an AG-04 intent and kept only sentences whose English meaning fits the intent.
  - mni-006 to mni-008 are Member A's own example questions, given in the integration requests of 2026-10-08. They are not in the corpus. Each entry's `source.quote` repeats the request text. They are code-mixed (English words such as *area*, *pest risk* and *crop condition* inside Manipuri), as Member A wrote them.
  - mni-009 and mni-010, and 19 of the 24 answer templates in `manipuri_responses.json`, began as **AI-assistant drafts** written at Member A's request on 2026-10-08, then corrected and verified by Member A the same day. They are not corpus sentences. Each Manipuri word in them was checked to occur in the corpus, and they are labelled as drafts and unverified until a fluent speaker reviews them.
- **Terms** (`agri_terms_manipuri.json`):
  1. For each English term, I listed the Latin-Manipuri words that co-occur with it across all rows (Dice co-occurrence score).
  2. I read the candidate rows by hand.
  3. I kept only words that recur consistently. For each kept word, 2–4 evidence rows are quoted verbatim.

  A script checked that each listed form occurs in its evidence rows (ignoring accents and hyphens), that each evidence row contains a listed form, and that every form is Latin script.
- **Where judgement was used:** deciding which word in a sentence corresponds to the English term (word alignment). A fluent speaker must confirm that alignment.

### Status

| File | Entries | Status |
|---|---|---|
| `manipuri_queries.json` | 10 queries | **Sourced**: 5 dataset sentences (edited by Member A) and 3 of Member A's examples. **Drafted**: 2 by the AI assistant (mni-009, mni-010), corrected by Member A. All 10 verified by Member A, 2026-10-08. |
| `manipuri_responses.json` | 24 templates | 5 from Member A's sentences; 19 **AI-assistant drafts**, corrected where needed. All 24 verified by Member A, 2026-10-08. |
| `agri_terms_manipuri.json` | 44 terms, 15 cue words | **Sourced** (attested in the dataset). 55 of 59 entries verified by Member A, 2026-10-08. Not yet verified: `place-bishnupur` (spelling *bishnupur* added), `cue-how` (*kamai* added), `term-condition` (*phibam*) and `cue-that` (*adu*). One evidence row of `term-crop` keeps the corpus text, with Member A's better rendering beside it in `member_a_correction`. |

### Not attested in the dataset (left out, not guessed)

- **Agricultural terms:** infestation, pest outbreak, crop disease, plant disease, crop health, healthy crop, vegetation stress, crop stress, water stress, damaged crop (as a noun phrase), high risk, moderate risk, early warning, field inspection, cloudy weather (as a phrase; *leichil* "cloud" is attested), waterlogging, leaf folder, sheath blight, bacterial leaf blight, rice blast, brown planthopper. Each is absent from the corpus, occurs only outside agriculture (*outbreak* of violence, *blighted*), or occurs once (*early warning*, row 72484), which is too little to confirm a term.
- **Native Manipuri word for humidity:** only the loanword *riletiba hayumiditi* appears.
- **Query intents:** AREA_RISK_QUERY, AREA_SPECIFIC_RISK, PEST_RISK and CROP_HEALTH have no suitable dataset sentence (see `README.md`). Member A's examples now cover all of them except AREA_SPECIFIC_RISK.

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

**Verdict:** the corpus is suitable as a vocabulary resource: terms, spelling variants and attested phrases for the router's lexicon, plus a source a reviewer can check against. It is not a source of AG-04's questions or answers, because the domain sentences are not in it. For the same reason, a translation model fine-tuned on it would learn little of AG-04's wording, and its output would still need a fluent speaker's review. See `README.md` §11.

---

## 2. Agricultural and scientific sources

All sources were accessed on 2026-10-08. PDFs were downloaded and their text extracted. The quotations below are exact, apart from OCR clean-up of the degree sign.

| # | Source | Publisher | URL | What was taken | Used in |
|---|---|---|---|---|---|
| S1 | *Advisory on blast disease (Magnaporthe oryzae) on rice crop*, F.No 3-6/2022-23, dated 22.07.2022, addressed to the Directors of Agriculture of all States/UTs | Directorate of Plant Protection, Quarantine & Storage (DPPQ&S), Ministry of Agriculture & Farmers Welfare, Government of India | https://ppqs.gov.in/sites/default/files/rice_blast_advisory.pdf | "Rice blast is favored by low temperatures (22-28°C), high relative humidity (>95%), dew deposits, leaf wetness for more than 10 hours, application of high nitrogen and aerobic soils." Also its IPM practices (field sanitation, crop rotation, certified seed, water level) and the instruction that fungicides follow the Registration Committee's label claim. | `verified_agricultural_risk_rules.json` (rice_blast), `advisory.json` |
| S2 | *Advisory on Brown Plant Hopper (Nilaparvata lugens) on rice crop*, July 2022 (day illegible in the scan) | DPPQ&S, Government of India | https://ppqs.gov.in/sites/default/files/rce_bph_advisory.pdf | Where BPH occurs, symptoms (hopperburn), IPM practices, and the instruction that pesticides follow the label claim. **No numeric weather threshold.** | `advisory.json` |
| S3 | *Integrated Pest Management Package for Rice* (2014) | NCIPM, DPPQ&S and NIPHM | https://niphm.gov.in/IPMPackages/Rice.pdf | "High dosages of nitrogenous fertilizers, close spacing, and high relative humidity increases planthopper populations." **No numeric threshold.** | `advisory.json` |
| S4 | Rice Knowledge Bank / Rice Doctor fact sheet: *Blast (Leaf and Collar)* | IRRI (with ACIAR and the University of Queensland) | http://www.knowledgebank.irri.org/training/fact-sheets/pest-management/diseases/item/blast-leaf-collar | Qualitative conditions ("low soil moisture, frequent and prolonged periods of rain shower, and cool temperature in the daytime"; dew from large day-night temperature differences), symptoms, management. **No numbers.** | `advisory.json` |
| S5 | Rice Doctor fact sheet: *Blast (Node and Neck)* | IRRI | https://keyserver.lucidcentral.org/key-server/data/0e090d01-0209-460e-810c-0d060708030c/media/Html/Blast_(Node_and_Neck).htm | Neck and node symptoms; distinguishing them from stem borer whiteheads | `advisory.json` |
| S6 | Rice Knowledge Bank fact sheet: *Planthopper* | IRRI | http://www.knowledgebank.irri.org/training/fact-sheets/pest-management/insects/item/planthopper | Where BPH occurs, symptoms, monitoring method and the "1 BPH per stem or less" action note, prevention. **No numeric weather threshold.** | `advisory.json` |
| S7 | TNAU Agritech Portal, rice blast: *Other management* | Tamil Nadu Agricultural University | https://agritech.tnau.ac.in/crop_protection/rice_diseases/another%20methods_rice_1.html | "High relative humidity (93-99 per cent) Low night temperature (between 15-20 C or less than 26 C". **Cross-check only.** It disagrees with S1 on temperature; see below. | not used in any value |
| S8 | Vennila S., J. Singh, P. Wahi, M. Bagri, D.K. Das and M. Srinivasa Rao (2016). *Web enabled weather based prediction for insect pests of rice*, Technical Bulletin 39, 50 p. | ICAR-National Research Centre for Integrated Pest Management (NICRA project) | https://nriipm.res.in/NCIPMPDFs/Publication/InsectPestsRice_.pdf | Table 5, "Weather based prediction for forewarning BPH": location-specific rules, for example Chinsurah (WB) high severity when "Tmax (33-34), Tmin (22-25), RF (0-10), RHI (89-92), RHII (55-65) and SSH (6-9)" with "Greater than four" criteria met. "Weather criteria is based on weekly means"; "Pest severity is based on the light trap catches of BPH (nos.) / week." Also: "high relative humidity (>85%) favoured the population buildup of N. lugens" at Thanjavur (TN). | Documented only; not encodable in the engine (see §3) |
| S9 | TNAU Agritech Portal, *Pest of paddy: Brown plant hopper* | Tamil Nadu Agricultural University | https://agritech.tnau.ac.in/crop_protection/rice/crop_prot_crop_insectpest%20_cereals_paddy_12.html | "ETL: 1 hopper/ tiller in the absence of predatory spider and 2 hoppers /tiller when spider is present at 1/hill." Also its non-chemical practices (spacing, alternate wetting and drying, avoiding excess nitrogen, light or yellow pan traps). Its insecticide list and doses were **not** copied. | `advisories.md` (field scouting) |
| S10 | Kaundal R., A.S. Kapoor and G.P.S. Raghava (2006). *Machine learning techniques in disease forecasting: a case study on rice blast prediction*. BMC Bioinformatics 7: 485. doi:10.1186/1471-2105-7-485 | BioMed Central (authors at IMTECH Chandigarh and CSK HPAU Palampur) | https://pmc.ncbi.nlm.nih.gov/articles/PMC1647291/ | Leaf-blast models from weekly maximum and minimum temperature, maximum and minimum RH, rainfall and rainy days per week (Himachal Pradesh): "rainfall was most influential in predicting the disease followed by rainy days/week, minimum relative humidity, maximum relative humidity, minimum temperature and maximum temperature". Predictors and regression models, **not a threshold rule**. | Not used in any value |

Research papers on BPH and weather (correlation studies from Bangladesh, Korea and India, found by web search) were **not** used. They report the conditions seen during particular outbreak periods, not decision thresholds.

**Found but not read (so not used):** Padmanabhan's *Studies on forecasting outbreaks of blast disease of rice*, Proceedings of the Indian Academy of Sciences, Section B, vol. 62 no. 3, pp. 117–129 (https://www.ias.ac.in/public/Volumes/secb/062/03/0117-0129.pdf). The server returned HTTP 403 on 2026-10-08. Search summaries attribute minimum-temperature and RH ≥ 90% forecasting rules to it, but a summary is not the source. Someone with access should read the paper before any of its values are used.

Accessed on 2026-10-08: S8, S9 and S10 (S8 as a downloaded PDF, text extracted with pdftotext).

---

## 3. Thresholds in `verified_agricultural_risk_rules.json`

### Summary by verification status

**VERIFIED:** none. No rule has been checked by a named agronomist, so no rule is presented as scientifically validated.

**PLACEHOLDER / NEEDS HUMAN VERIFICATION:**

| Field | `rice_blast` | `brown_planthopper` | Risk model |
|---|---|---|---|
| Source | S1 (DPPQ&S, Government of India) | none for the encoded values; S8 and S9 documented | none |
| URL | https://ppqs.gov.in/sites/default/files/rice_blast_advisory.pdf | — (S8, S9 above) | — |
| Publication/title | Advisory on blast disease (Magnaporthe oryzae) on rice crop, 22.07.2022 | — | `satquery/agri/assets/risk_model.json` (engine default) |
| Relevant finding | Blast favoured by 22–28 °C, RH > 95%, leaf wetness > 10 h | S8: location-specific weekly multi-criteria rules (none for Manipur). S9: field ETL 1 hopper/tiller | — |
| Crop | rice | rice | all monitored areas |
| Pest/disease | rice blast (*Magnaporthe oryzae*) | brown planthopper (*Nilaparvata lugens*) | — |
| Applicability | National, kharif, all growth stages; not Manipur-specific | Placeholder only | Operating choices |
| Date accessed | 2026-10-08 | 2026-10-08 (S8, S9) | — |
| Verification status | Sourced, PLACEHOLDER: the two mapping choices below need an agronomist | PLACEHOLDER: values unsourced | PLACEHOLDER: values unchanged |

Each rule's `applicability` and `limitations` fields in the JSON say the same. The engine stores them and never scores them.


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
- **ICAR-NCIPM (S8)** does publish weather rules for BPH, but they do not fit this engine:
  - they are tied to six locations, none in the North-East;
  - they use weekly means, morning and evening RH, sunshine hours and wind speed;
  - they count how many of five or six criteria are met.

  The engine tests daily conditions, all of which must hold. Copying, say, the Chinsurah rule in as daily conditions would change what the rule means, so it was not done.
- **TNAU's ETL (S9)** is a count of hoppers on the plant, made in the field. Weather data cannot measure it. It is in `advisories.md` as scouting guidance.
- **Needed:** a published threshold that fits Manipur and can be expressed as daily conditions. It could come from ICAR-NRRI, ICAR-IIRR, an SAU (for example CAU Imphal) or a KVK, or the Department of Agriculture could decide one. Alternatively, the engine could be extended to support weekly, k-of-n rules like S8's.

### Risk model (`verified_risk_model.json`): PLACEHOLDER, values unchanged

`verified_risk_model.json` is a copy of `satquery/agri/assets/risk_model.json` with **every value unchanged**. Its `sources` list is empty and its status is PLACEHOLDER. The weights (0.5 / 0.3 / 0.2), level cut-points and scoring breakpoints are operating choices. None of the sources above supports changing them, and the team rule is to change them only with a cited reason.

The file gives the agronomist one place to record reviewed values: change a value, cite its source with `verified_by`/`verified_on`, and set VERIFIED only when every value is backed. A test (`tests/test_team_deliverables.py`) fails if a value changes while the file has no source.

---

## 4. `advisory.json` and `advisories.md`

`advisories.md` is the short, readable version of `advisory.json`, with the field-scouting thresholds of S6 and S9. Every item names its source (S1–S6, S9) and URL. Deliberately left out:
- fungicide and insecticide names and doses (S1 and S2 list them; chemical advice is left to the Department of Agriculture / KVK);
- bio-agent doses;
- all phone numbers and e-mail addresses (those in S1 and S2 are addressed to state officials, not farmers).

The one "general" item states AG-04 project policy and is labelled as such, not as an external source.

---

## 5. What a reviewer needs to do

1. **Fluent speaker:** done by Member A on 2026-10-08. Still to check: `place-bishnupur` (spelling *bishnupur* added), `cue-how` (*kamai* added), `term-condition` (*phibam*) and `cue-that` (*adu*). After that, set the terms file `status` to `VERIFIED`.
2. **Agronomist (Department of Agriculture, Manipur; a KVK; or CAU Imphal).** No agronomist has reviewed anything yet, so every rule stays PLACEHOLDER. Do not fill a name, approval or date until that review has happened:
   - Read S1 and decide on the two mapping assumptions for blast (daily mean, and the RH ≥ 95% leaf-wetness proxy).
   - Then add `verified_by` and `verified_on` to S1 in `verified_agricultural_risk_rules.json` and set `rice_blast` to `VERIFIED`.
   - Supply a sourced BPH threshold, or keep BPH as PLACEHOLDER.
   - Review `advisory.json` and `advisories.md`.
