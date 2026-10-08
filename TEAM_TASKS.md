# AG-04 Team Tasks

## Repository and Git rules (read first)

- **Authoritative repository:** **AG-04**, https://github.com/brajalairen/AG-04.git. Clone it and work from branch `ag04-prototype`.
- **Frozen:** **SatQuery-AI** (https://github.com/brajalairen/SatQuery-AI.git) is the original SIH submission. Never push to it, merge into it or change its `main`. In the integration clone its remote is `sih-frozen`, with push disabled.
- **Your own branch:** create one from `ag04-prototype` (for example `feature/manipuri`, `feature/district-boundaries`, `feature/ui-qa`, `feature/pitch`) and hand it over for review. Only the integration lead merges into `ag04-prototype`, after `git diff`, the tests and the build.
- **Never commit:** `.env`, credentials or API keys, `runs/` (caches), `.venv`, `node_modules`, `web/dist`, or large datasets.
- **Status:** Phases 1–3 are complete and committed; the last application commit is `5c966f6`. Phase 4 has not started.

Who owns what while Claude does the main implementation in this repository. Roles are a suggested split: help each other, but each person keeps a clear primary area. Update the **Status** and **Blocker** columns as you go. The master feature list is [AG04_CHECKLIST.md](AG04_CHECKLIST.md).

**Hand-off rule:** put deliverables in `satquery/agri/assets/` (it now exists). The file schemas are enforced by `satquery/agri/config.py` and `satquery/agri/areas.py`. A wrong file fails to load, with a message saying which field is wrong. Check your thresholds file with `python -m satquery.agri thresholds`. Do not commit secrets, real personal data, or unverified "official" information.

**How to hand in verified thresholds (Member A):**
- Edit `satquery/agri/assets/pest_rules.json` (or a copy pointed to by `SATQUERY_AGRI_PEST_RULES`).
- For each pest, set `"status": "VERIFIED"` and list `sources`, each with `title`, `url`, `verified_by` and `verified_on`.
- The loader refuses VERIFIED without them.
- Conditions use `variable` (temperature_2m, relative_humidity_2m, dew_point_2m, precipitation), `aggregate` (mean, min, max, sum, hours_at_or_above, hours_between) and `between` / `at_least` / `at_most` / `threshold`, plus a plain-language `label`.
- The weights and level cut-points live in `risk_model.json` (status PLACEHOLDER too).

**Trust rules for everyone:** never invent Manipuri text, official phone numbers, district boundaries, outbreak statistics or scientific sources. Anything synthetic is labelled **SAMPLE / SYNTHETIC**.

---

## Member A: Manipuri + agronomy

| Task | Deliverable | Status | Dependency | Blocker |
|---|---|---|---|---|
| Write 3–8 candidate Manipuri agricultural demo sentences and **verify at least 1** for the final demo. Example intents: "Which districts are at high pest risk?", "Why is Bishnupur flagged?", "What should farmers in Thoubal do?" | `mni_demo_queries.md`: for each sentence, the Meitei Mayek, Bengali-script and romanised forms, an English meaning, the intended intent, and who verified it | not started | None | None |
| Build a lexicon of the key agri words and district names in each script | `mni_lexicon.json`: `{ "term": "...", "script": "mtei|beng|latn", "meaning": "...", "maps_to": "intent or district" }` | not started | Sentences above | None |
| Write Manipuri answer headlines for the demo answers (short, 1 line each) | Section in `mni_demo_queries.md` | not started | Final intents (Phase 2) | None |
| Verify pest-risk thresholds for **rice blast** (leaf/neck) and **brown planthopper**: temperature band, RH, hours of leaf wetness, days. Record the source of each number. **Urgent and demo-critical:** the live run on 2026-10-08 showed the PLACEHOLDER blast rule (8 h or more at RH ≥ 90%, mean 20–28 °C) held on 10 of 10 days in all 7 areas, so weather currently does not separate areas | `pest_rules_sources.md`, plus a VERIFIED `pest_rules.json` (format above) with each threshold cited (ICAR-NRRI, the Rice Knowledge Management Portal, a state agriculture university or KVK advisories, and so on) | not started | None | **Blocks the final demo's credibility** |
| Review the risk-model weights (weather 0.5, NDVI 0.3, reports 0.2) and level cut-points (0.35 / 0.60 / 0.80) with the team, ideally with an extension officer | Comments, or a VERIFIED `risk_model.json` with sources | not started | None | None |
| Write advisory content for each pest: symptoms, *why* it happens (the weather link), preventive/IPM steps, and when to call the DAO/KVK. Chemical advice stays conservative ("as advised by the DAO/KVK") | `advisory.json` (schema provided in Phase 2) | not started | None | None |
| Verify crop/pest terminology and the crop calendar for Manipur valley and hill districts (what is in the field in October) | `terminology_notes.md` | not started | None | None |
| Collect **verified** public contact points (district agriculture offices, KVKs, Kisan Call Centre) with a source link for each. Leave unverified ones blank | `contacts.json` | not started | None | None |

## Member B: geo + data

| Task | Deliverable | Status | Dependency | Blocker |
|---|---|---|---|---|
| Source a trustworthy Manipur **district** boundary dataset. Check whether it has the current **16 districts** or the older 9-district structure. **Lead:** OpenStreetMap already places points in the post-2016 districts (Kakching, Jiribam; checked 2026-10-08). Its admin boundaries are ODbL-licensed and need checking against the official district list | `manipur_districts.geojson`: a WGS84 FeatureCollection. Each feature needs properties `id`, `name` and `boundary_source` (the dataset name and version); optional `district`, `state` and `note`. Load it with `python -m satquery.agri assess --areas manipur_districts.geojson`. Also `boundaries_provenance.md` (source URL, licence, date, structure, known limits) | not started | None | Dataset availability |
| Optional: sub-division / block boundaries, from a trustworthy source only | `manipur_subdivisions.geojson` and provenance | not started | District file | Dataset availability |
| Check the Copernicus quota on our account (dashboard) against the measured cost: **about 0.37 processing units per 30-day NDVI window for 60 km²**, 4 windows per area on the first run, then 1 per area per day (the baseline is cached). Open-Meteo: 1 call per area per 3 h | Note in `data_notes.md` | not started | None | None |
| Help define the crop/vegetation features: what NDVI baseline window to use (the same 10-day window in previous years?), the cropland focus, and the valley vs hill split | Section in `data_notes.md` | not started | P0.4 design | None |
| Review the **SAMPLE** pest-report scenario: plausible pests by area and season, counts, severity mix. The seeded generator exists; its inputs are in `satquery/agri/assets/sample_scenario.json`, with per-area pressure background / elevated / high | Edits to `sample_scenario.json`, or `sample_reports_spec.md` | not started | None | None |
| QA: data ranges, units, timestamps, timezones (IST vs UTC), and that SAMPLE labels appear everywhere | Bug list in the team chat | not started | Phase 2 build | None |

## Member C: product / UI / QA

| Task | Deliverable | Status | Dependency | Blocker |
|---|---|---|---|---|
| Review the current SatQuery UI: what to keep (map, drawing, result card, trace drawer, voice input) and what to redesign for a government agricultural dashboard | `ux_review.md` with screenshots | not started | App running locally | None |
| Sketch the dashboard information hierarchy: Manipur overview → risk map → priority areas → selected-area explanation → recommended action → ask the AI | Sketch or wireframe in `ux_review.md` | not started | None | None |
| Browser QA of each phase: the demo flow, loading/error/empty states, light and dark themes, projector size (1280×720 and 1920×1080) | Bug list with steps to reproduce | not started | Each phase | None |
| **Phase 3 dashboard QA:** start the server, open http://127.0.0.1:8000.<br>- Check the priority panel, the map (hover, click, dashed demo outlines), the drawer "Why is this area at risk?" and the three chips (high risk, why Bishnupur, inspect first).<br>- Try "Why is Imphal flagged?" (should ask which) and "Is there pest risk in this area?" with no area selected.<br>- Check dark mode, the satellite basemap and 1280×720.<br>- Stop the network and run with `SATQUERY_AGRI_OFFLINE=1`: the labels must say cached or offline | Bug list | not started | Phase 3 (done) | None |
| Before the dashboard is built, review the risk engine's wording: run `python -m satquery.agri assess` and read the reasons and headlines in `runs/agri/assessment-*.json`. Are they clear to an agriculture officer? | Wording notes | not started | Phase 2 (done) | None |
| Test the Phase 1 crop-health queries on a drawn rectangle over Manipur valley farmland: "What is the NDVI?", "How healthy is the crop here?", "Is vegetation stressed here?". Known-good rectangle: Thoubal–Kakching, W 93.95, S 24.45, E 94.03, N 24.52. Also try a cloudy area (e.g. south of Imphal: 93.90, 24.55, 93.98, 24.62) and check that the refusal reads well | QA notes | not started | Phase 1 (done) | Copernicus credentials in `.env` |

## Member D: pitch / demo / optional AG-01

| Task | Deliverable | Status | Dependency | Blocker |
|---|---|---|---|---|
| Pitch deck structured around **Technical Trust (35%)**, **Government Relevance (30%)** and **Industry Potential (35%)** | Deck | not started | None | None |
| Main demo storyline (3–5 minutes), with exact clicks and queries. Phase 3 flow:<br>1. Opens on Manipur with the priority list.<br>2. Point at the PLACEHOLDER/SAMPLE strip.<br>3. "Which areas are high risk?"<br>4. Click #1, then "Why is this area at risk?" (score breakdown, NDVI vs 2023–25, day strips, sources).<br>5. "Which should we inspect first?"<br>6. Show a crop-health NDVI question on the Kakching rectangle (Phase 1).<br>7. Close with the honest limits | `demo_script.md` | not started | Phase 3 UI (done) | None |
| Prepare answers to likely judge questions: data sources, why rules and not ML, accuracy, synthetic data, privacy, cost, scale, deployment, government adoption path. Facts from Phase 2:<br>- Hybrid design: satellite NDVI baseline (Copernicus Statistical API), model weather (Open-Meteo), SAMPLE reports, rule thresholds as reviewable data.<br>- The score is the visible sum of factor points; missing data lowers confidence instead of being filled in.<br>- Confidence is a rule-based label, not a probability.<br>- The future ML model learns only from verified inspections | `judge_qa.md` | not started | None | None |
| Record backup demo videos after each stable milestone (end of Phase 4, Phase 5 and the final freeze) | Video files | not started | Stable builds | None |
| **Only after P0/P1 are stable:** a time-boxed AG-01 investigation (rice leaf disease classifier, CPU-runnable, licence OK, tested on real photos). Drop it if it isn't credible | `ag01_findings.md` | not started | P0 and P1 stable | Time |

## Claude (implementation)

| Task | Status |
|---|---|
| Repository migration to AG-04 | **done**: `ag04-prototype` pushed to AG-04; the SIH repo is `sih-frozen`, push disabled |
| Phase 1: audit + NDVI foundation | **done**, approved and committed (`418fe58`) |
| Phase 2: agricultural data + risk engine | **done**, approved and committed (`082cd27`); thresholds are PLACEHOLDER until Member A verifies them |
| Phase 3: AG-04 dashboard | **done**, approved and committed (`5c966f6`) |
| Phase 4: demo hardening (offline snapshot, warm start) | **not started**; waits for approval |
| Phase 5: government workflow (login, monitor area, alerts, inspections, audit) | not started |
| Phase 6: Manipuri (needs Member A's verified sentences) | blocked |
| Phase 7: optional extras | not started |
