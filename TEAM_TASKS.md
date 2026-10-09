# AG-04 Team Tasks

## Repository and Git rules (read first)

- **Authoritative repository:** **AG-04**, https://github.com/brajalairen/AG-04.git. Clone it and work from branch `ag04-prototype`.
- **Frozen:** **SatQuery-AI** (https://github.com/brajalairen/SatQuery-AI.git) is the original SIH submission. Never push to it, merge into it or change its `main`. In the integration clone its remote is `sih-frozen`, with push disabled.
- **Your own branch:** create one from `ag04-prototype` (for example `feature/manipuri`, `feature/district-boundaries`, `feature/ui-qa`, `feature/pitch`) and hand it over for review. Only the integration lead merges into `ag04-prototype`, after `git diff`, the tests and the build.
- **Never commit:** `.env`, credentials or API keys, `runs/` (caches), `.venv`, `node_modules`, `web/dist`, or large datasets.
- **Status:** Phases 1–3 are complete and committed; the last application commit is `5c966f6`. Phase 4 has not started.

Who owns what while Claude does the main implementation in this repository. Roles are a suggested split: help each other, but each person keeps a clear primary area. Update the **Status** and **Blocker** columns as you go. The master feature list is [AG04_CHECKLIST.md](AG04_CHECKLIST.md).

**Hand-off rule:** put deliverables **only in your own folder under `team/`** (see `team/README.md`), on your own branch. The integration lead moves reviewed files into `satquery/agri/assets/` or points the settings at them. The file schemas are enforced by `satquery/agri/config.py` and `satquery/agri/areas.py`. A wrong file fails to load, with a message saying which field is wrong. Check your files with `python team/check_deliverables.py` (thresholds and boundaries go through the engine's own loaders). Do not commit secrets, real personal data, or unverified "official" information.

**How to hand in verified thresholds (Member A):**
- Edit `satquery/agri/assets/pest_rules.json` (or a copy pointed to by `SATQUERY_AGRI_PEST_RULES`).
- For each pest, set `"status": "VERIFIED"` and list `sources`, each with `title`, `url`, `verified_by` and `verified_on`.
- The loader refuses VERIFIED without them.
- Conditions use `variable` (temperature_2m, relative_humidity_2m, dew_point_2m, precipitation), `aggregate` (mean, min, max, sum, hours_at_or_above, hours_between) and `between` / `at_least` / `at_most` / `threshold`, plus a plain-language `label`.
- The weights and level cut-points live in `risk_model.json` (status PLACEHOLDER too).

**Trust rules for everyone:** never invent Manipuri text, official phone numbers, district boundaries, outbreak statistics, pest observations or scientific sources. Anything synthetic is labelled **SAMPLE / SYNTHETIC** ("SAMPLE DATA — PROTOTYPE SIMULATION"). Pest/disease data sources and their limits are in [data/agri/SOURCES.md](data/agri/SOURCES.md).

---

## Member A: Manipuri + agronomy

Folder `team/member-a-agronomy/` · branch `feature/manipuri-agronomy` · formats in that folder's `README.md`. Data, configuration and documentation only: do **not** modify the risk engine.

| Task | Deliverable | Status | Dependency | Blocker |
|---|---|---|---|---|
| **MOST URGENT.** Replace the PLACEHOLDER thresholds with sourced, verified rules (rice blast leaf/neck, brown planthopper, and others if relevant), each with threshold, unit, crop, pest, source, verifier, date, applicability and limits. Keep anything unverifiable as PLACEHOLDER.<br>**Evidence from the 2026-10-08 evening live run:**<br>- The blast rule held on 8–10 of 10 days in 6 zones, and `full_score_days` = 5 saturates the index.<br>- The BPH rule held only in Jiribam, because the valley daily mean (22–23 °C) is below its 25 °C floor.<br>**Candidate sources:** NICRA Bulletin 39 (location-specific weekly rules; see `data/agri/SOURCES.md` §4) and an Imphal rice blast epidemiology study (citation not yet located; §9–10).<br>The engine now shows the weather arithmetic (`details.calculation`): the uncapped ratio was 1.6–2.0 in every zone, all capped to 1.0. |  `verified_pest_rules.json` (the schema of `satquery/agri/assets/pest_rules.json`); optionally `verified_risk_model.json` | not started | None | **Blocks the credibility of the ranking** |
| Verify the ETLs in `satquery/agri/assets/observation_rules.json`. They are transcribed from the IPM Package for Rice (NCIPM / DPPQ&S 2014, Table 3.1.2, p. 9). Confirm each value, its applicability to Manipur, and the low/moderate/high reading of an ETL range. Then set VERIFIED with `verified_by` / `verified_on` | reviewed `observation_rules.json` | not started | None | Needed before real field counts are scored |
| 5–10 reliable Manipuri agricultural queries, each mapped to an AG-04 intent (`AREA_RISK_QUERY`, `AREA_EXPLANATION`, `INSPECTION_PRIORITY`, `CROP_HEALTH`, `PEST_RISK`, `WEATHER_RISK`, `AREA_SPECIFIC_RISK`) and verified by a fluent speaker | `manipuri_queries.json` | not started | None | None |
| Agricultural terminology: crops, pests, diseases, weather, crop health, inspection/risk, place names | `agri_terms_manipuri.json` | not started | None | None |
| Advisory content (symptoms, weather link, preventive/IPM steps, when to contact the Department or KVK), only where verified. No invented contacts or helplines | `advisory.json` | not started | None | None |
| Sources and verification for everything above | `SOURCES.md` | not started | None | None |

## Member B: Geography

Folder `team/member-b-geo/` · branch `feature/district-boundaries` · formats in that folder's `README.md`. No API is needed. Never invent or redraw boundaries, and do not modify the risk engine.

| Task | Deliverable | Status | Dependency | Blocker |
|---|---|---|---|---|
| Current Manipur district boundaries from a named, citable dataset, WGS84, with properties `id`, `name`, `kind: district`, `boundary_source`, `district` and `state`. **Lead:** OpenStreetMap places points in the post-2016 districts (Kakching, Jiribam; checked 2026-10-08). It is ODbL-licensed and must be checked against the official list | `manipur_districts.geojson` | not started | None | Dataset availability |
| Source, URL, version, access date, licence, administrative level, processing, limitations | `SOURCES.md` | not started | None | None |
| District count and names, duplicates, geometry validity, CRS, bounds, simplification | `geo_validation.md` | not started | None | None |

## Member C: UI/UX + QA

Folder `team/member-c-qa/` · branch `feature/ui-qa` · formats and the full test list in that folder's `README.md`. Report bugs; do not change backend or risk-engine code. Code proposals go on a separate `feature/ui-fixes` branch for review.

| Task | Deliverable | Status | Dependency | Blocker |
|---|---|---|---|---|
| UX review of the dashboard for a government audience: hierarchy, wording, readability from a projector, what to simplify | `UI_REVIEW.md` and screenshots | not started | Phase 3 (done) | None |
| Test live, cached and offline data; cloudy imagery; missing NDVI or weather; SAMPLE data and PLACEHOLDER labels; questions (including ambiguous and unknown ones); map interactions; loading and error states; 1280×720, 1600×900 and the projector; light and dark | `TEST_MATRIX.md` | not started | Phase 3 (done) | None |
| One entry per bug: ID, severity, page, steps, expected, actual, screenshot | `QA_REPORT.md` | not started | Testing above | None |

## Member D: Pitch + demo

Folder `team/member-d-pitch/` · branch `feature/pitch` · the facts to state accurately are in that folder's `README.md`. Never present SAMPLE data or PLACEHOLDER thresholds as validated findings, and never claim unbuilt features.

| Task | Deliverable | Status | Dependency | Blocker |
|---|---|---|---|---|
| Deck around Technical Trust (35%), Government Relevance (30%) and Industry Potential (35%), matching the implemented product | `AG04_Pitch.pptx` | not started | None | None |
| Demo storyline following the real product:<br>1. Dashboard and Priority areas.<br>2. "Which areas are high risk?"<br>3. Click Bishnupur (district), its zone, then "Why is this area at risk?"<br>4. **Kakching** zone, then "Check crop health here" (Bishnupur's scene is too cloudy today; that refusal is itself a trust point).<br>5. Layers.<br>6. Manipuri only if integrated.<br>7. Roadmap, honest limits | `DEMO_SCRIPT.md` | not started | Dashboard (done 8 Oct) | None |
| Likely judge questions and accurate answers (data sources, rules not ML, SAMPLE data, placeholder thresholds, confidence, cost, scale, deployment, adoption path) | `JUDGE_QA.md` | not started | None | None |
| Screenshots and a backup recording of the stable build; links to large videos in `media/LINKS.md` | `media/` | not started | Stable build | None |

## Integration (Claude)

- Reviews each member's branch: changed files, cited sources, `python team/check_deliverables.py`, full tests, typecheck and build. Then integrates through the existing configuration (`SATQUERY_AGRI_PEST_RULES`, `SATQUERY_AGRI_RISK_MODEL`, `SATQUERY_AGRI_AREAS`).
- Never changes the risk method to fit a contribution, and never merges blindly.
- Order: B's districts and A's thresholds as they arrive, then Manipuri, then C's QA on the integrated build, then Phase 4 demo hardening (only after approval).
- AG-01 and other optional features have not started.

## Claude (implementation)

| Task | Status |
|---|---|
| Repository migration to AG-04 | **done**: `ag04-prototype` pushed to AG-04; the SIH repo is `sih-frozen`, push disabled |
| Phase 1: audit + NDVI foundation | **done**, approved and committed (`418fe58`) |
| Phase 2: agricultural data + risk engine | **done**, approved and committed (`082cd27`); thresholds are PLACEHOLDER until Member A verifies them |
| Phase 3: AG-04 dashboard | **done**, approved and committed (`5c966f6`) |
| Phase 4: demo hardening (offline snapshot, warm start) and the district → zone dashboard | **done** 8 Oct. Pre-demo routine: `python -m satquery.agri warm --save-snapshot --crop-health`, then start the server |
| Pest/disease data investigation + integration + risk-engine validation | **done** 8 Oct (evening):<br>- `data/agri/SOURCES.md`: no accessible Manipur observation dataset, so Strategy 3 (SAMPLE observations, labelled).<br>- Real-observation ingestion is ready (`SATQUERY_AGRI_OBSERVATIONS`, template in `data/agri/`).<br>- Per-pest scoring; missing data never raises a score; completeness counts real data only; SAMPLE sensitivity shown.<br>- **Second pass (9 Oct):** real-evidence score band; "no observations available" vs "no pest observed" (`evidence_state`); `pests_not_assessed`; `calibration: UNCALIBRATED`; inspectable weather index. Backend 808 tests pass.<br>- **Open:**<br>&nbsp;&nbsp;- data-sharing requests to the Department of Agriculture, Manipur (pest-scout / AESA / KVK records) and to DPPQ&S / ICAR-NRIIPM (NPSS Manipur rice observations)<br>&nbsp;&nbsp;- Copernicus credentials for a live NDVI run<br>&nbsp;&nbsp;- web tests, typecheck and build on a machine with Node.js<br>&nbsp;&nbsp;- Git review and merge (this copy has no `.git`) |
| Phase 3 backend/API readiness | **done** 9 Oct, backend only:<br>- read-only summary, priorities, explanation, history and vocabulary endpoints, with trust labels<br>- append-only live history<br>- escalation facts (no policy)<br>- inspection data contract<br>Documented in `docs/AG04_API.md`. **Member C:** the endpoints and TypeScript types are ready to wire into the dashboard. |
| Phase 5: government workflow (login, monitor area, alerts, inspections, audit) | not started (the inspection *data contract* exists; no workflow, store or authentication) |
| Phase 6: Manipuri (needs Member A's verified sentences) | blocked |
| Phase 7: optional extras | not started |
