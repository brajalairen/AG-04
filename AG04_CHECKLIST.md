# AG-04 Master Checklist: AI-Based Crop & Pest Risk Monitoring System

The source of truth for what we intend to build. Update it after every phase.

| | |
|---|---|
| **Objective** | Build a working prototype for **AG-04** (AI4SEVA Hackathon 2026, Department of Agriculture, Manipur). It combines crop/satellite, weather, pest and geographical data to find areas at increased risk, and gives agricultural officials an early-warning dashboard. Showcase: Manipur. Engine: works on arbitrary areas. |
| **Judging** | Technical Trust 35% · Government Relevance 30% · Industry Potential 35%. Reliability > feature count. |
| **Pitch** | 9 Oct 2026, from 09:30 IST |
| **Active repo** | `SatQuery-AI` (this repository). SatV2 is reference only; do not modify it. |
| **Current phase** | **Phase 2: Agricultural data + risk engine.** Done; awaiting approval for Phase 3 (dashboard). |
| **Overall status** | Phase 1 NDVI path plus the Phase 2 data layer and explainable risk engine work. Tests: backend 667 passed, web 83 passed, build OK, plus 2 opt-in live tests passed. Verified live on 7 Manipur demo areas. No dashboard UI yet. |
| **Known blockers** | (1) Trustworthy 16-district boundaries are not yet sourced (Member B). OpenStreetMap already has the current districts; this is a lead to verify. (2) **Pest thresholds are PLACEHOLDERS** (Member A). In Oct 2026 the placeholder blast rule held on every day in every area, so weather does not separate areas until verified values replace it. (3) Advisory text is not yet verified (Member A). (4) No verified Manipuri sentence yet (Member A). |
| **Demo-critical unfinished** | P0.3 district boundaries; P0.6 risk map; P0.7 drawer; P0.8 priority panel; P0.9 agri NL queries; P0.10 provenance UI; P0.11 offline snapshot UI and fallback. Verified thresholds are needed before the final demo. |
| **Known-good demo rectangle** | Thoubal–Kakching farmland, W 93.95, S 24.45, E 94.03, N 24.52. As of 2026-10-08, the 2026-09-14 Sentinel-2 scene is 91% clear over it. |

Status legend: `done` · `in progress` · `not started` · `blocked` · `dropped`

---

## P0: Core / demo-critical

- [x] **P0.1 Repository and existing-system audit.** Status: **done** (Phase 1).
  - Reusable infrastructure is recorded in [Audit notes](#audit-notes-phase-1) below.
  - Files: whole repo.
- [x] **P0.2 Real NDVI / crop-health path.** Status: **done** (Phase 1); verified live.
  - "What is the NDVI?", "How healthy is the crop here?" and "Is vegetation stressed here?" now run a new `crop_health` task. Its single tool, `optical.vegetation_health`, computes NDVI from the red and NIR bands over clear **land**: water (NDWI > 0) and cloud are excluded. It reports the mean, median, 10th–90th percentile and vigour classes (heuristic breaks 0.2 / 0.4 / 0.6), locates low-vigour areas, and draws an NDVI class map on the map. There is no VLM call.
  - Refusals are explicit for RGB-only input (no NIR) and for SAR input. When too little clear land remains, the answer says so and no value is given.
  - **Cloud handling:** Sentinel-2 scenes fetched for crop health are judged by their scene classification (SCL) *over the drawn area*, and cloud, shadow and no-data pixels are masked.
    - If the least-cloudy tile hides the area, up to `SATQUERY_OPTICAL_MAX_SCENES` (4) recent dates are checked by SCL alone (one cheap band each). Bands are downloaded for the usable one only.
    - When none is usable, the refusal lists every date with its measured cloud share. No radar fallback: SAR cannot measure NDVI.
    - The outcome is cached for the day.
  - **Daily cache refresh:** the search date is part of the single-date, SAR and optical+SAR cache keys, so a "last 30 days" search is never served stale.
  - **Routing:** "Has crop health declined / worsened / is it deteriorating?" now take the two-date path (one image cannot show change). "Is the rain stressing the crops?" asks the user to split weather from crop health.
  - Files: `satquery/agent/intents.py`, `agent/planner.py`, `agent/aggregator.py`, `specialists/tools.py`, `api.py`, `schemas.py`, `server.py`, `settings.py`, `providers/copernicus.py`, `providers/errors.py`, `evidence.py`, `.env.example`, `web/src/state/types.ts`, `web/src/results/ResultOverlay.tsx`, `web/src/results/SceneProvenance.tsx`, `tests/test_crop_health.py`, `tests/test_server.py`, `tests/test_contract.py`.
  - **Live result (2026-10-08):** Thoubal–Kakching gave mean NDVI 0.76, 83% dense, on the 2026-09-14 scene (4 Oct and 19 Sep were too cloudy over the area). South of Imphal (93.90, 24.55, 93.98, 24.62) was honestly refused: the 3 recent scenes were 60%, 31% and 24% obscured.
  - Notes and risks:
    - A single-date NDVI shows vigour, not stress. The answer says so, and names settlements, roads, harvested fields and young crops as other causes of low NDVI. Stress needs the baseline (P0.4).
    - SCL misses some thin cloud and cloud edges, so a few low-vigour patches can be residual haze. A cloud-mask buffer is a possible follow-up.
    - The two-date crop path still compares the NDVI > 0.3 *area*, not mean NDVI, and is not SCL-masked (unchanged from before).
- [ ] **P0.3 Manipur showcase.** Status: **partly done** (data side, Phase 2); boundaries are blocked.
  - **Done:** the engine scores *any* GeoJSON polygon (`satquery/agri/areas.py`). An area file is refused unless every feature names its `boundary_source`.
  - **Done:** 7 demo monitoring **rectangles** over valley farmland (`satquery/agri/assets/demo_areas.geojson`): Kakching, Bishnupur, Imphal West, Imphal East, Thoubal, Jiribam and Churachandpur. Each is labelled "not an administrative boundary" and named from OpenStreetMap reverse geocoding.
  - **Done:** district context for any drawn area via OpenStreetMap Nominatim (`agri/context.py`; cached and rate-limited, labelled ODbL).
  - **Remaining:** verified district boundaries (Member B), plus the default map view and limitation notice (Phase 3).
  - Lead: OSM already returns the post-2016 districts (Kakching, Jiribam). Verify before use. Never invent boundaries.
- [x] **P0.4 Agricultural data layer.** Status: **done** (Phase 2); verified live.
  - **Weather** (`agri/weather.py`): Open-Meteo hourly temperature, RH, dew point and precipitation, for 14 past days plus 7 forecast days, in local time.
    - Labelled as *model data, not station observations*.
    - Disk cache (3 h): LIVE / CACHED. On a provider failure an older copy is served, marked **STALE**; with no copy it fails loudly.
  - **NDVI baseline** (`agri/ndvi.py`): Copernicus **Statistical API** over the area polygon (no 400 km² limit).
    - Per pixel: the median NDVI of all *clear land* observations in the window. SCL classes 0, 1, 3, 6, 8, 9, 10 and 11 are dropped (cloud, shadow, cirrus, water, snow, no data).
    - Compares the last 30 days with the same dates in each of the 3 previous years.
    - A window counts only if at least 30% of the area was observed clear; otherwise it carries a reason and no value.
    - Past-year windows are cached for good; the current window is refreshed daily. Resolution adapts to stay under 100k pixels.
    - Cost measured at about 0.37 processing units per window for 60 km².
  - **SAMPLE reports** (`agri/reports.py`, `assets/sample_scenario.json`): seeded and deterministic. Every record is `source: SAMPLE`, `synthetic: true` and labelled "SAMPLE DATA — Prototype Simulation". `SampleReportSource` is swappable for a real feed.
  - `--offline` serves cached data only (0.5 s for 7 areas).
  - Files: `satquery/agri/{weather,ndvi,reports,cache,areas,context}.py`, `providers/copernicus.py` (`statistics()`).
- [x] **P0.5 Explainable risk engine.** Status: **done with PLACEHOLDER thresholds** (Phase 2). The final demo needs Member A's verified values.
  - **Thresholds as data:**
    - Files: `assets/pest_rules.json` (rice blast, brown planthopper) and `assets/risk_model.json` (weights 0.5 / 0.3 / 0.2, level cut-points 0.35 / 0.60 / 0.80, NDVI and report scoring).
    - Both are status **PLACEHOLDER** and name no source.
    - Marking anything VERIFIED without a source, `verified_by` and `verified_on` fails to load.
    - Swap the files via `SATQUERY_AGRI_PEST_RULES` / `SATQUERY_AGRI_RISK_MODEL`.
  - **Rules** (`agri/rules.py`): checked day by day over the last 7 days plus 3 forecast days. A day with too few hours is **unknown**, not unfavourable.
  - **Score** (`agri/risk.py`): a weighted mean over *available* factors, shown as 0–100 points per factor (they sum to the score).
    - A missing factor is named and left out, never estimated.
    - **Data completeness** is the share of the weight backed by data. Below 50% the level is **INSUFFICIENT_DATA** and there is no score.
    - **Critical** needs two indicators at 0.6 or more and 90% completeness.
  - **Confidence:** a rule-based label (high / medium / low from completeness), not a probability. Capped at *medium* when any input is SAMPLE data, and at *low* while any threshold is a PLACEHOLDER.
  - **Ranking:** by level, then score, then name. Areas with no estimate are listed last without a rank number.
  - **Wording:** "Indicators suggest HIGH risk (67/100) …", never "detected" or "outbreak". The disclaimer is on every assessment.
  - **No ML model, fake or otherwise.**
  - CLI: `python -m satquery.agri assess [--offline] [--areas FILE] [--json OUT]` and `python -m satquery.agri thresholds`.
- [ ] **P0.6 Risk map (choropleth).** Status: **not started.**
  - Coloured polygons, a legend, click-to-inspect, hover; works in both themes.
  - Files (planned): `web/src/map/RiskLayer.tsx`.
  - Must follow the `syncAoi` re-add-on-`styleReady` pattern in `MapView.tsx`.
- [ ] **P0.7 Area risk drawer.** Status: **not started.**
  - Hero section "WHY IS THIS AREA AT HIGH RISK?". Also: NDVI and anomaly, weather contribution, report pressure, per-pest breakdown, recent reports, provenance, actions, whom to consult, disclaimer.
  - Files (planned): `web/src/results/AreaRiskDrawer.tsx` (reuse `Block`/`Pair` from `DetailsDrawer.tsx`).
- [ ] **P0.8 Priority / early-warning panel.** Status: **not started.**
  - Ranked areas, level, score, severity filters, totals.
  - Files (planned): `web/src/sidebar/AlertsPanel.tsx`.
- [ ] **P0.9 Natural-language agricultural queries.** Status: **partly done.**
  - Phase 1 covers the crop-health/NDVI questions.
  - Remaining: risk ranking, "why is X flagged", advice, "whom to consult", "inspect first", and pest risk for a drawn area.
  - Files (planned): an agri route in `agent/intents.py` and `satquery/agri/`.
  - Notes: "Is rain hurting the crops?" now asks to split the question, because rain is a weather cue and crop health an imagery cue. A real agri route comes with P0.9.
- [ ] **P0.10 Explainability / provenance / responsible AI.** Status: **backend done, UI remaining.**
  - Done in the backend:
    - Every factor and assessment carries provenance (source, LIVE / CACHED / SAMPLE / UNAVAILABLE, fetch time, period, licence).
    - Each assessment has an as-of time, reasons, top factors, the confidence method, the thresholds status, an `includes_sample_data` flag and the disclaimer.
  - Remaining (Phase 3): show these as chips and text in the UI.
- [ ] **P0.11 Offline demo snapshot.** Status: **foundation done.**
  - The disk cache plus `--offline` reproduce the last assessment without network, labelled CACHED.
  - Remaining (Phase 4): a frozen snapshot file, an automatic fallback in the API, and the as-of time in the UI.

## P1: Important government workflow (start only when P0 is stable)

- [ ] **P1.1 Demo login and roles** (State Agri Officer, District Agri Officer, KVK Expert). scrypt password hashes, HttpOnly cookie, role checks, no secrets in git. Status: not started.
- [ ] **P1.2 Monitor any area.** Draw, analyse, "Monitor this area", saved and ranked server-side. Today saved areas live in localStorage only (`useAppStore.saveArea`). Status: not started.
- [ ] **P1.3 Jurisdiction-scoped alerts.** In-app first; email optional (P2.1). Status: not started.
- [ ] **P1.4 Field-inspection workflow.** Request, assign, inspect, then confirmed / not found / severity / notes, a map update, and an audit record. Verified results influence scoring. Status: not started.
- [ ] **P1.5 Audit log.** Logins, monitored areas, requests, assignment, verification, status changes. Status: not started.
- [ ] **P1.6 Manipuri input.** At least one verified query (Meitei Mayek, Bengali script or romanised), from a curated lexicon. Status: **blocked** until Member A delivers verified sentences. Do not invent Manipuri text.

## P2: Nice-to-have (only after P0 and P1 work reliably)

- [ ] **P2.1 Email alerts.** Non-blocking SMTP, with status recorded. Status: not started.
- [ ] **P2.2 AG-01 crop disease detection.** Strictly time-boxed; drop it if no credible model is found. Owner: Member D. Status: not started.
- [ ] **P2.3 Historical risk time slider.** Status: not started.
- [ ] **P2.4 Block / sub-division boundaries.** Only from a trustworthy dataset. Status: not started.
- [ ] **P2.5 Printable advisory / report.** Status: not started.

## P3: Future roadmap (pitch only)

- [ ] P3.1 Farmer mode: geotagged reports, photos, advice in Manipuri.
- [ ] P3.2 Hands-free voice conversation and TTS (the voice *input* that exists is `web/src/command/VoiceInput.tsx`).
- [ ] P3.3 A learned risk model trained on **verified inspection outcomes**, never fabricated labels, with SHAP explanations.
- [ ] P3.4 SMS / WhatsApp notifications.
- [ ] P3.5 National pest-surveillance integration, once the source and API are verified.

---

## Audit notes (Phase 1)

**Architecture:**
- FastAPI (`satquery/server.py`) serves `/api/*` and the built React client (`web/dist`) on one port.
- Analysis runs one deterministic agent: `api.analyze` → `agent/intents.classify` (rule-based, records `matched_rule`) → `agent/planner.build_plan` → `agent/executor.execute` → `agent/aggregator.aggregate`. Reports are written to `runs/<run_id>/` as HTML and JSON.
- Tools are registered in `specialists/tools.py` `REGISTRY`; each `Params` model uses `extra="forbid"`.

**Reusable for AG-04:**
- MapLibre map with Terra Draw rectangle/polygon/circle drawing (`web/src/map/`).
- Vector-layer pattern for a choropleth: `syncAoi` in `MapView.tsx`.
- Sidebar rail (`Sidebar.tsx` `ITEMS`/`TITLES`).
- Result card and execution-trace drawer (`results/ResultOverlay.tsx`, `results/DetailsDrawer.tsx`).
- Saved areas (localStorage), voice input, UI primitives, Tailwind tokens with dark mode.
- Zustand store (`state/useAppStore.ts`) and API client (`state/api.ts`).
- Copernicus OAuth, catalogue and Process API (`providers/copernicus.py`).
- SCL cloud assessment and masking (`providers/quality.py`).
- NDVI/NDWI (`raster_analysis.spectral_indices`).
- Open-Meteo client with cache and typed errors (`specialists/weather.py`).
- Confidence-with-method and trace models (`schemas.py`).
- Test fakes for the providers.

**Not present:**
- Database, auth, users, alerts, pest data, district boundaries, Manipur default view, i18n.
- scikit-learn, shapely and geopandas; geometry is hand-written in `geo.py`.

**Imagery:**
- Sentinel-2 L2A, bands B02/B03/B04/B08 as FLOAT32 reflectance at **10 m**, EPSG:4326.
- The least cloudy (whole-tile) scene in the last 30 days, then the newest.
- Bounding box only, at most 400 km², at most 2,500 px per side.
- Suitable for field-scale NDVI over drawn areas. It is not suitable for district-wide statistics; those need the Statistical API in P0.4.

**NDVI problem found (fixed in Phase 1):**
1. `classify()` had no crop-health intent, so "How healthy is the crop?", "What is the NDVI?" and "Is vegetation stressed?" fell through to `vqa`. The plan was `vlm.vqa` alone: a VLM yes/no and **no NDVI**. NDVI ran only for "highlight/describe vegetation" phrasings.
2. Cloud (SCL) assessment and masking ran only for water questions, so vegetation figures could include cloud.
   - Live, the scene chosen for south of Imphal was 60% cloud over the area. The old path would have averaged NDVI through that cloud.
3. The scene was chosen by *whole-tile* cloud cover, which often hides a small area; a clearer date three ranks down went unused.
4. The single-scene cache key had no date, so a cached scene was reused indefinitely for the same rectangle. That is stale for monitoring.
5. Mean NDVI was averaged over every pixel, water included, so a lake dragged "crop health" down.
6. Crop-change wording ("declined", "worsened", "deteriorating") was not recognised as needing two dates.

## Phase 2 notes

**Live result, 2026-10-08 04:05 IST** (`python -m satquery.agri assess`; PLACEHOLDER thresholds, SAMPLE reports):

| # | Demo area | Level | Score | Weather | NDVI | Reports (SAMPLE) |
|---|---|---|---|---|---|---|
| 1 | Bishnupur near Keinou Thongkha | HIGH | 67 | 50 | 3.4 (0.61 vs 0.64; below the 2023–25 range) | 13.3 |
| 2 | Thoubal near Chaobok | HIGH | 62 | 50 | 0 | 11.7 |
| 3 | Kakching near Khangshim | MODERATE | 58 | 50 | 0 | 8.3 |
| 4–7 | Imphal East, Churachandpur, Imphal West, Jiribam | MODERATE | 50–53 | 50 | 0 | 0–3.3 |

All areas have 100% data completeness and *low* confidence, because the thresholds are placeholders.

**Known limitations:**
- **Thresholds are placeholders.** The placeholder blast rule (8 h or more at RH ≥ 90% with a mean of 20–28 °C) held on 10 of 10 days everywhere, so weather saturates and does not separate areas. Verified, sourced values are needed (Member A).
- **One weather point per area** (its representative point). Areas wider than 10 km say so; multi-point sampling is a later improvement.
- **Weather history is model data** (Open-Meteo analyses and short-range forecasts), not station observations. It is labelled as such.
- **NDVI covers all clear land** (crops, trees, grass), not cropland alone. A drop can also reflect sowing or harvest timing; the reasons say so. A cropland mask (for example ESA WorldCover) is a later improvement.
- **Report pressure is SAMPLE data**, counted per area and not normalised by area size or reporting effort.
- **Rank depends on the configured weights.** With the weather factor saturated, rank currently follows the SAMPLE reports. That is a placeholder artefact, not a finding.
- **Copernicus quota:** about 0.37 processing units per 30-day window for 60 km². A district at the 100k-pixel cap costs roughly 5× that per window. The baseline is cached permanently, so a daily refresh costs one window per area.

---

## Change log
- **2026-10-08, Phase 1:**
  - Audit.
  - Added the `crop_health` task and the `optical.vegetation_health` tool, with an NDVI class map.
  - SCL cloud check and masking for crop-health retrieval, plus a bounded search for a clearer scene by the area's own cloud, cached per day. Honest refusal when no scene is usable.
  - Daily cache refresh; RGB and SAR refusals; temporal cues for crop decline.
  - Frontend: task label, optical-check wording and the list of scenes judged.
  - 43 new tests. Backend 544 passed (baseline 501); web 83 passed; build OK.
  - pytest was installed into `.venv` (`uv pip install pytest`).
  - Created this checklist and TEAM_TASKS.md.
- **2026-10-08, Phase 2:**
  - New package `satquery/agri/`: models, config (thresholds as data, PLACEHOLDER status gating), areas, hourly weather, NDVI baseline via the Statistical API, SAMPLE reports, pest rules, the risk engine, pipeline, district context and a CLI.
  - Assets: `pest_rules.json`, `risk_model.json`, `sample_scenario.json` and `demo_areas.geojson`.
  - `CopernicusSentinelProvider.statistics()`; package-data entry in `pyproject.toml`; config overrides documented in `.env.example`.
  - 125 new tests: 123 offline plus 2 opt-in `live`. Backend 667 passed, web 83 passed, build OK, live 2 passed.
  - No UI, auth, inspections, AG-01 or other P1/P2 work.
