# AG-04 decision-support API (Phase 3, backend)

Read-only endpoints under `/api/agri`. They present the risk engine's assessments; **nothing is scored in the API**. All responses use the engine's wording ("indicators suggest"). None says a pest is detected or present: the score is an **uncalibrated prototype indication**, not a probability.

Status on 2026-10-09: implemented and tested on the backend (pytest, FastAPI TestClient). The dashboard (Member C) does not consume the new endpoints yet. TypeScript types for them are in `web/src/state/types.ts` (the `Agri…` interfaces after `AgriQueryResult`), kept in step by `tests/test_contract.py`.

## Endpoints

| Method and path | Returns (model) | Purpose |
|---|---|---|
| `GET /api/agri/areas` | `AreaList` | Every monitored area's status, plus rule/model status |
| `GET /api/agri/areas/{id}/summary` | `AreaStatus` | One area's status |
| `GET /api/agri/areas/{id}/explanation` | `AreaExplanation` | Overall, weather, NDVI, per-pest evidence, provenance, limitations, escalation facts |
| `GET /api/agri/areas/{id}/history?limit=N` | `AreaHistory` | Recorded live assessments, oldest first (`limit` 1–5000: the most recent N) |
| `GET /api/agri/priorities` | `PriorityList` | Areas in engine rank order, with an evidence summary and escalation-readiness facts |
| `GET /api/agri/vocabulary` | `Vocabulary` | Every code (trust labels, evidence states, verification, escalation stages, limitations) with its English meaning |

Unchanged endpoints: `GET /api/agri/overview`, `GET /api/agri/areas/{id}` (the full `RiskAssessment`) and `POST /api/agri/query`.

**Errors** (same as the existing endpoints):
- 404 `{"code": "unknown_area", "message": …}` for an unknown area id
- 503 `{"code": "agri_unavailable", "message": …}` when the areas or configuration cannot be loaded (or snapshot mode has no snapshot)
- 422 for an invalid `limit`

Models: `satquery/agri/views.py`, `escalation.py`, `history.py`.

## Trust labels (`TrustLabels`, one per input)

These four are kept separate and never merged:

| Field | Values | Notes |
|---|---|---|
| `origin` | REAL / SAMPLE / UNAVAILABLE | REAL: from a named external source |
| `synthetic` | true / false | true only for SAMPLE |
| `freshness` | LIVE / CACHED / STALE / SNAPSHOT / SAMPLE / UNAVAILABLE | STALE: an old cached copy shown because the provider failed or offline mode is on |
| `verification` | VERIFIED / UNVERIFIED / NOT_APPLICABLE | Applies to field observations only |

Examples:

| Input | Trust |
|---|---|
| Real weather | REAL, LIVE or CACHED, NOT_APPLICABLE, plus the label MODEL_DATA (model analyses and forecasts, not station data) |
| Real satellite NDVI | REAL, NOT_APPLICABLE, plus the label SATELLITE |
| SAMPLE pest records | SAMPLE, synthetic, UNVERIFIED. A SAMPLE record can never be VERIFIED; the model refuses it. |
| An expert-verified observation from a REAL dataset or an inspection | REAL + VERIFIED |

Score-wide fields:
- `calibration` is UNCALIBRATED until the weights and bands are validated against field outcomes. This holds even when the thresholds are VERIFIED.
- `thresholds_status` is PLACEHOLDER or VERIFIED.

**Limitations** are `{code, severity, message}`. Translate by `code`. The English `message` may change, but codes are stable (`/vocabulary`).

## Semantics

- **Area summary:**
  - `summary` is one sentence, e.g. "HIGH risk assessment (63/100) from the indicators currently available, led by rice blast (leaf / neck); weather is model data; NDVI is unavailable; pest evidence is SAMPLE (synthetic); the level depends on SAMPLE data (MODERATE without it); uncalibrated prototype."
  - `boundary.status` is DEMO_NOT_OFFICIAL for the team's rectangles, USER_DRAWN_NOT_OFFICIAL for drawn areas, and OFFICIAL_SOURCED only for `kind: district` areas loaded from a named dataset (Member B).
- **Ranking:** engine order (level, then score, then data completeness, then name). At equal scores, the area backed by more real data comes first, so missing data can never lift an area. A rank means "deserves attention first on the available evidence", not that a pest is present.
- **Missing data:** a missing input adds no points and keeps its weight, so it can never raise a score. `score_range` is the band the real evidence allows. Below 50% real-data completeness the level is INSUFFICIENT_DATA.
- **Per-pest evidence:**
  - `pests.assessed` holds rice blast and brown planthopper, the pests with weather rules, plus any pest with field evidence.
  - `pests.not_assessed` lists known rice pests with neither a rule nor evidence (assessment NOT_ASSESSED, no score).
  - `evidence_state` keeps "no observations available" apart from "no pest observed".
- **Weather:** each day is marked `data_kind` MODEL_ANALYSIS (past) or FORECAST. `calculation` shows the index arithmetic and whether the cap hides differences (`saturated`).
- **NDVI:** current window, baseline windows and change, clear-area fraction and the unavailable reason. It is described as vegetation evidence, never pest detection.

## Satellite / NDVI: reuse of SatQueryAI

AG-04 builds no second Copernicus integration:
- `satquery/agri/ndvi.py` calls `CopernicusSentinelProvider.statistics()` from `satquery/providers/copernicus.py`, SatQueryAI's provider. It shares the OAuth token cache, request handling, typed errors, and the `COPERNICUS_CLIENT_ID` / `COPERNICUS_CLIENT_SECRET` settings.
- It sends a Statistical API evalscript (per-pixel median NDVI over SCL-masked clear land, for the current 30-day window and the same dates in 3 earlier years), cached on disk.
- The Phase 1 single-scene crop-health flow (`optical.vegetation_health`) is unchanged, and the zone drawer's "Check crop health here" still uses it.
- Tests pin this: `test_ag04_ndvi_uses_the_satquery_copernicus_provider` and `test_no_second_copernicus_integration_exists_in_the_agri_package`.

## History and persistence

- Before Phase 3, nothing kept past assessments (`snapshot.json` holds only the latest frozen one).
- Now each **live** assessment that is served is appended to `runs/agri/history.jsonl` (gitignored), one line per area.
- Snapshots and offline re-scores are not recorded, and nothing is backfilled. History starts at the first live run after deployment.
- Each entry records level, score and range, the score without SAMPLE data, confidence, completeness, per-pest levels, input states, and rule/model versions.
- `field_outcome` is reserved for a later verified inspection result; it stays null until that workflow exists.
- Switch history off with `SATQUERY_AGRI_HISTORY=0`. The API then says `enabled: false`, which is not the same as "no history".

## Escalation readiness (no policy)

`attention` (in `/priorities` and `/explanation`) holds the facts a WATCH / PRIORITIZE / FIELD_INSPECTION_RECOMMENDED policy would weigh:

- **Persistence:** consecutive elevated recorded assessments. This is null when history is off, never estimated.
- **Independent real indicators:** REAL factors at or above the configured cut. The cut is PLACEHOLDER.
- **Evidence types**
- **Observation counts:** verified, unverified and SAMPLE
- **Data completeness and freshness**

**No escalation policy is configured.** The only stage assigned is VERIFIED_OBSERVATION, which is a fact: an expert-verified observation exists. The other stages wait for a verified policy, to be plugged in through `escalation.EscalationPolicy`. Nothing like "HIGH once → send officials" is coded.

## Field inspection and verification (contract only)

`satquery/agri/inspections.py` defines `InspectionRecord`:
- fields: area/district, on-site coordinates (never derived), crop, suspected pest, date/time, source type, inspector, evidence references, observation, measurement, severity, verification status, expert reviewer, verification date, finding, notes, status history
- verification states: UNVERIFIED → REPORTED → INITIAL_IDENTIFICATION → EXPERT_REVIEW → VERIFIED, forward only
- VERIFIED needs a reviewer, a date and a finding (PRESENT / ABSENT / INCONCLUSIVE). A PRESENT finding also needs a severity or a measured value.
- Only VERIFIED + PRESENT becomes field evidence (`to_observation`: REAL, verified, type `inspection`).

There is **no inspection store, workflow, write API or authentication yet** (checklist P1.1 and P1.4).

## Future evidence providers

`observations.PestObservationProvider` is the interface for field evidence. Today's providers are the SAMPLE generator and a REAL dataset file (`SATQUERY_AGRI_OBSERVATIONS`). Future providers:

- **NPSS:** only through authorised access; no public API exists.
- **Department of Agriculture / KVK record exports**
- **Verified inspections**

News, social media and other unverified reports are not field evidence and must not be wrapped as a provider.

## Localisation (Manipuri)

The Manipuri conversation/input feature exists on a teammate's branch and is **not** duplicated here. The new endpoints carry stable codes (limitations, labels, states, stages) plus `language: "en"`, so translations can key on codes without parsing sentences. `POST /api/agri/query` and `/api/route` are unchanged by Phase 3.

## Dependencies

- **Member A:** verified weather rules and ETLs (all PLACEHOLDER), advisory text, and any escalation policy.
- **Member B:** official district GeoJSON. Until it arrives, every area is DEMO_NOT_OFFICIAL.
- **Member C:** wiring the dashboard to these endpoints.
- **External:** Copernicus credentials for live NDVI, and authorised access to real pest observations.
