# AG-04 Master Checklist: AI-Based Crop & Pest Risk Monitoring System

The source of truth for what we intend to build. Update it after every phase.

| | |
|---|---|
| **Objective** | Build a working prototype for **AG-04** (AI4SEVA Hackathon 2026, Department of Agriculture, Manipur). It combines crop/satellite, weather, pest and geographical data to find areas at increased risk, and gives agricultural officials an early-warning dashboard. Showcase: Manipur. Engine: works on arbitrary areas. |
| **Judging** | Technical Trust 35% · Government Relevance 30% · Industry Potential 35%. Reliability > feature count. |
| **Pitch** | 9 Oct 2026, from 09:30 IST |
| **Active repo** | **AG-04**, https://github.com/brajalairen/AG-04.git (git remote `origin`). This is the authoritative repository for all AG-04 work. |
| **Active branch** | `ag04-prototype`, tracking `origin/ag04-prototype`. `main` has not been pushed to AG-04. |
| **Frozen repos** | **SatQuery-AI** (https://github.com/brajalairen/SatQuery-AI.git) is the frozen SIH submission. Locally its remote is `sih-frozen`: fetch only, push disabled (a test push fails). Never push, merge into it or change its `main` (still at `1433e7d`). SatV2 is a reference copy only; do not modify it. |
| **Last application commit** | `5c966f6`, Phase 3 (on top of `082cd27` Phase 2 and `418fe58` Phase 1). Later commits are documentation-only unless the change log says otherwise. |
| **Current phase** | **Phases 1–3 complete. Phase 4 reliability and the district → zone dashboard are implemented** (8 Oct). Teammate data (thresholds, boundaries, Manipuri) not yet integrated. |
| **Overall status** | Phases 1–3 work. Phase 3 adds the government-facing dashboard over the unchanged risk engine (read-only `/api/agri/*`, risk map, priority panel, "Why is this area at risk?" drawer, agri command-bar questions). Tests: backend 720 passed, web 106 passed, typecheck clean, build OK. Checked in Chrome at 1600×900 and 1280×720, light and dark, with no page errors. |
| **Known blockers** | (1) Trustworthy 16-district boundaries are not yet sourced (Member B). OpenStreetMap already has the current districts; this is a lead to verify. (2) **Pest thresholds are PLACEHOLDERS** (Member A). In Oct 2026 the placeholder blast rule held on every day in every area, so weather does not separate areas until verified values replace it. (3) Advisory text is not yet verified (Member A). (4) No verified Manipuri sentence yet (Member A). |
| **Demo-critical unfinished** | Verified thresholds (Member A); verified district boundaries (Member B); advice / whom to consult (Member A); 9 Oct morning: run the pre-demo routine (below). |
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
- [x] **P0.6 Risk map (choropleth).** Status: **done** (Phase 3).
  - Each area is filled by its engine-given level (status palette: Low, Moderate, High, Critical, Not enough data) with a legend; the level is never shown by colour alone.
  - **Demo rectangles are outlined dashed, official district outlines solid**, and the legend says so ("none loaded" until Member B's file arrives).
  - Rank markers (#1…); hover shows name, level, score and the demo tag; a click opens the drawer. Selected and answer-highlighted areas are outlined blue.
  - The map opens on Manipur and frames the monitored areas. Outlines follow the theme and basemap. Layers are re-added on every style load.
  - Files: `web/src/agri/RiskLayer.tsx`, `RiskLegend.tsx`, `format.ts`; `web/src/map/basemap.ts` (`INITIAL_VIEW` = Manipur).
- [x] **P0.7 Area risk drawer.** Status: **done** (Phase 3); headed "Why is this area at risk?".
  - Shows the level, score, rank, headline, confidence, data completeness and as-of time, with the full PLACEHOLDER notice.
  - Score breakdown: the engine's factor points as a stacked bar plus rows (weather, NDVI, SAMPLE reports); unavailable factors carry their reason.
  - Also: the engine's reasons; NDVI against each baseline year (unusable windows show why); weather for the last and next 7 days (labelled model data); per-pest day strips (favourable / not / no data, values on hover; PLACEHOLDER tags); SAMPLE reports list; every data source with LIVE / CACHED / SAMPLE state, period and fetch time; the boundary note; the disclaimer.
  - Not yet: recommended actions and whom to consult. That needs Member A's verified advisory text and contacts; nothing is invented.
  - Files: `web/src/agri/AreaRiskDrawer.tsx`, `badges.tsx`.
- [x] **P0.8 Priority / early-warning panel.** Status: **done** (Phase 3); opens by default.
  - Lists areas in the engine's rank order, with level, score, confidence, data completeness and the demo tag. Shows counts by level and filters (All / High+ / Moderate / Low / No data).
  - Also: the as-of time and data-state chips, the PLACEHOLDER and SAMPLE notices, the area note, the disclaimer and a reload button.
  - Has loading, error-with-retry and empty states.
  - Files: `web/src/agri/PriorityPanel.tsx`, `useAgriStore.ts`; `web/src/sidebar/Sidebar.tsx` (the new "priority" section).
- [x] **P0.9 Natural-language agricultural queries.** Status: **done for Phase 3 scope.** Advice and whom-to-consult wait for Member A's content.
  - "Which areas are high risk?", "Why is Bishnupur flagged?" and "Which should we inspect first?" are answered from the engine's assessments (`satquery/agri/query.py`, `POST /api/agri/query`).
  - Also handled: "this area" (the selected area); ambiguous places ("Imphal" asks which one); unknown places (lists the monitored areas).
  - `/api/route` returns `agri` for these questions first, so they never reach the VLM. Crop-health, weather and imagery questions keep their Phase 1 routes.
  - The answer card shows the rule that matched and the caveats; an explanation also opens the drawer.
  - Remaining: a pest-risk assessment for a newly drawn area (P1.2) and advice (Member A).
- [x] **P0.10 Explainability / provenance / responsible AI.** Status: **done** (backend and UI).
  - An always-visible strip reads "Prototype · PLACEHOLDER thresholds · SAMPLE pest reports".
  - PLACEHOLDER notices appear in the panel, drawer and answers; "SAMPLE DATA — Prototype Simulation" labels appear wherever synthetic reports do; data-state chips appear on every source.
  - Wording stays "Indicators suggest…", never "detected" or "outbreak"; tests check this.
  - Phase 3 also fixed one Phase 2 wording bug: an old weather copy in offline mode used to say "the provider could not be reached". It now states its real reason. Methodology and thresholds are unchanged.
- [x] **P0.11 Offline demo snapshot.** Status: **done** (Phase 4).
  - **Warm-up:** the server computes the assessment in the background at start, so the dashboard was ready in about 2.5 s instead of up to a minute (`SATQUERY_AGRI_WARMUP=0` turns it off).
  - **Frozen snapshot:** `python -m satquery.agri warm --save-snapshot` writes `runs/agri/snapshot.json` (gitignored).
  - **Fallback:** live first. The snapshot is shown automatically when live data is less complete than the snapshot (for example, the venue network is down), or always with `SATQUERY_AGRI_MODE=snapshot`.
  - **Labelling:** every snapshot source is relabelled SNAPSHOT, with its original state and time kept in a note. The strip and the panel say "Frozen SNAPSHOT of …, not live data" and give the reason. It is never shown as LIVE.
  - **Crop-health warm-up:** `--crop-health` also fetches today's Sentinel-2 scene for each rectangular zone.
  - **Stable SAMPLE scenario:** reports are seeded by area, not by date, with dates relative to today, so the ranking no longer reshuffles daily. They stay labelled SAMPLE.
  - Files: `satquery/agri/service.py`, `__main__.py` (`warm`), `server.py` (lifespan warm-up), `settings.py`, `models.py` (`SNAPSHOT` state), `reports.py`; tests in `tests/test_agri_snapshot.py`.
- [x] **District → zone dashboard** (8 Oct; extends P0.6–P0.8).
  - **Districts are context, never scored or coloured.** The API groups the engine's ranked zones by district (`satquery/agri/districts.py`, overview `districts`). A district's level, score and confidence are those of its top zone, and the UI says "it does not mean the whole district is affected".
  - **District list:** 16 names from OpenStreetMap (names only, to be confirmed by Member B). Districts without a zone show "Monitoring coverage not yet available" (not "no risk").
  - **Priority panel:** districts in engine order (rank, level, score, confidence, zone count; filters All/High/Moderate/Low). The drill-down shows the district's zones, and a zone opens the existing drawer.
  - **Layers control** (base map, district boundaries, monitoring zones, priority markers):
    - District boundaries stay disabled until verified outlines are loaded (`SATQUERY_AGRI_DISTRICTS`).
    - There is no block layer (no verified data).
    - The legend moved to the top strip, so eastern Manipur is clear at 1280×720.
  - **"Check crop health here · Sentinel-2"** in the zone drawer reuses the Phase 1 NDVI flow on the zone's rectangle; the result card says it is separate from the risk score.
  - **Statuses shown separately:** "Pest thresholds" and "Risk weighting" have their own status lines (PLACEHOLDER until Member A's verified rules).
  - Files: `web/src/agri/PriorityPanel.tsx`, `MapLayersControl.tsx`, `StatusStrip.tsx`, `RiskLayer.tsx`, `AreaRiskDrawer.tsx`, `badges.tsx`, `format.ts`, `useAgriStore.ts`; `satquery/agri/routes.py`; tests in `tests/test_agri_districts.py` and the web tests.

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

## Phase 4 / dashboard notes (8 Oct)

**Pre-demo routine (9 Oct about 07:30, with network):**
1. `.venv\Scripts\python -m satquery.agri warm --save-snapshot --crop-health` (about 6 min). This fetches today's data, freezes the snapshot and warms the crop-health scenes.
2. `.venv\Scripts\python -m uvicorn satquery.server:app --port 8000`. It warms itself at start. If the venue network fails, it falls back to the snapshot automatically. To force the snapshot: `SATQUERY_AGRI_MODE=snapshot`.

**Live check, 8 Oct 15:20 IST (stable SAMPLE seed):**
- Ranking: Bishnupur 73, Thoubal 65 and Kakching 62 (HIGH); Imphal West 52; Churachandpur, Imphal East and Jiribam 50 (MODERATE).
- Crop health had a clear scene for Kakching, Imphal West, Imphal East and Jiribam. **Bishnupur, Thoubal and Churachandpur were refused as too cloudy** (honest refusal), so the demo's crop-health step should use Kakching (HIGH, #3).

**Known limits:**
- With no network the basemap tiles do not load (plain background); the zones and panel still work.
- District membership comes from each zone's own properties (OpenStreetMap reverse geocoding) until Member B's verified boundaries arrive.

## Phase 3 notes

**Architecture:** agricultural data → risk engine (`satquery/agri`, unchanged method) → `AssessmentService` (one assessment of all areas, reused for `SATQUERY_AGRI_REFRESH_S`, default 30 min) → read-only `/api/agri/*` → dashboard (`web/src/agri/*`). The frontend computes no risk figure: ranks, levels, scores, points, reasons, confidence and completeness come from the API; the frontend only filters by level and formats.

**Endpoints:**
- `GET /api/agri/overview` → `AgriOverview`: areas as `AreaSummary` with geometry, counts, notices and view bounds.
- `GET /api/agri/areas/{id}` → `AgriAreaDetail` (the full `RiskAssessment`). An unknown id gives 404 `unknown_area`.
- `POST /api/agri/query` → `AgriQueryResult`.
- An invalid areas file gives 503 `agri_unavailable`.
- `/api/route` can now answer `agri`. `/api/example-queries` lists the three AG-04 questions first.

**Settings:** `SATQUERY_AGRI_AREAS` (`demo` or a GeoJSON path), `SATQUERY_AGRI_OFFLINE`, `SATQUERY_AGRI_REFRESH_S`.

**Known limitations:**
- The first page load after a server start runs the assessment: about 9 s with a warm NDVI cache, about 1 minute cold. The panel shows a loading state meanwhile. A pre-demo warm-up is Phase 4.
- The rank currently follows SAMPLE reports, because the placeholder weather rule saturates (Phase 2 finding).
- No advice or whom-to-consult section yet (Member A content).
- Pest risk for a newly drawn area is not assessed yet; the bar says so.
- At 1280×720 the legend can sit over the easternmost areas, and the answer card can cover part of the map (it can be dismissed).
- On phone width the panel and drawer take most of the screen. The demo targets projector sizes.

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
- **2026-10-08, Phase 4 reliability + district dashboard:**
  - Warm-up at server start; frozen snapshot with live-first fallback and SNAPSHOT labelling; `warm` CLI; stable SAMPLE seed.
  - District context API; district → zone priority panel; Layers control; crop-health action; separate threshold statuses; legend moved to the top strip.
  - Risk engine methodology, weights and thresholds unchanged.
- **2026-10-08, team intake** (no application change):
  - `team/` holds one folder per member with exact formats and templates, plus `team/check_deliverables.py`, which validates deliverables with the engine's own loaders.
  - TEAM_TASKS.md now uses the agreed deliverables: A `manipuri_queries.json`, `agri_terms_manipuri.json`, verified thresholds, `advisory.json`, `SOURCES.md`; B `manipur_districts.geojson`, `SOURCES.md`, `geo_validation.md`; C `UI_REVIEW.md`, `QA_REPORT.md`, `TEST_MATRIX.md`; D `AG04_Pitch.pptx`, `DEMO_SCRIPT.md`, `JUDGE_QA.md`.
  - Phase 4 and AG-01 have not started.
- **2026-10-08, repository migration** (documentation only):
  - AG-04 (https://github.com/brajalairen/AG-04.git) is now `origin`, and `ag04-prototype` (Phases 1–3, `5c966f6`) is pushed to it.
  - The SatQuery-AI SIH repository was renamed locally to `sih-frozen`, with its push URL disabled. Nothing was pushed to it.
  - Phase 4 not started.
- **2026-10-08, Phase 1:**
  - Audit.
  - Added the `crop_health` task and the `optical.vegetation_health` tool, with an NDVI class map.
  - SCL cloud check and masking for crop-health retrieval, plus a bounded search for a clearer scene by the area's own cloud, cached per day. Honest refusal when no scene is usable.
  - Daily cache refresh; RGB and SAR refusals; temporal cues for crop decline.
  - Frontend: task label, optical-check wording and the list of scenes judged.
  - 43 new tests. Backend 544 passed (baseline 501); web 83 passed; build OK.
  - pytest was installed into `.venv` (`uv pip install pytest`).
  - Created this checklist and TEAM_TASKS.md.
- **2026-10-08, Phase 3** (committed as `5c966f6`):
  - Read-only `/api/agri/*` (`satquery/agri/routes.py`, `service.py`, `query.py`) and the agri route in `/api/route`.
  - Dashboard: risk map, legend, priority panel, area drawer, answer card, prototype strip; Manipur default view; the command bar routes every question.
  - 53 new backend tests (API, queries, routing, stale wording, contract types) and 23 new frontend tests.
  - Backend 720 passed, web 106 passed, typecheck and build OK. Browser-checked.
- **2026-10-08, Phase 2:**
  - New package `satquery/agri/`: models, config (thresholds as data, PLACEHOLDER status gating), areas, hourly weather, NDVI baseline via the Statistical API, SAMPLE reports, pest rules, the risk engine, pipeline, district context and a CLI.
  - Assets: `pest_rules.json`, `risk_model.json`, `sample_scenario.json` and `demo_areas.geojson`.
  - `CopernicusSentinelProvider.statistics()`; package-data entry in `pyproject.toml`; config overrides documented in `.env.example`.
  - 125 new tests: 123 offline plus 2 opt-in `live`. Backend 667 passed, web 83 passed, build OK, live 2 passed.
  - No UI, auth, inspections, AG-01 or other P1/P2 work.
