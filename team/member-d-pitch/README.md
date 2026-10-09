# Member D: Pitch and demo

Deliver `AG04_Pitch.pptx`, `DEMO_SCRIPT.md`, `JUDGE_QA.md` and `media/`. Put large recordings in shared storage and the links in `media/LINKS.md`; don't commit them.

**Represent only what exists.** Before the deck is final, check every claim against `AG04_CHECKLIST.md` (what is done) and the running app.

## Facts to state accurately

- **What it is:** a **decision-support** prototype for Department of Agriculture officials. It says "Indicators suggest HIGH risk". It never says "pest detected" or "outbreak confirmed".
- **Data:**
  - Sentinel-2 NDVI compared with the same dates in 2023–2025 (Copernicus Statistical API; cloud, shadow and water masked).
  - Weather is Open-Meteo hourly model data, 14 days past plus a 7-day forecast. It is not station observations.
  - Pest/disease field observations are **SAMPLE DATA — PROTOTYPE SIMULATION (synthetic)**.
  - We searched for real ones (NPSS, ICAR-NRIIPM e-pest surveillance including Tripura, AICRP-Rice surveys, data.gov.in, Manipur institutions). **No public, machine-readable observation dataset for Manipur exists** (`data/agri/SOURCES.md`). The engine is ready to ingest one when the Department or NPSS shares records.
- **Thresholds are PLACEHOLDER** until Member A's verified rules are integrated. The current ranking is therefore *not* a validated finding; say so if asked.
  - In the 2026-10-08 run the placeholder blast rule held almost everywhere.
  - Bishnupur's HIGH rests on SAMPLE data: the dashboard's "Why" says it would be MODERATE without it.
- **Explainability:**
  - Each pest is scored separately and the area takes its highest.
  - The score is the visible sum of three factors (weather, NDVI, field observations).
  - Missing data is named and never raises a score; the possible range is shown.
  - SAMPLE data is never counted as data.
  - NDVI is supporting evidence of vegetation change, **not pest detection**.
  - Confidence is a rule-based label, not a probability.
- **No machine-learning model is trained or claimed.** A future model would learn only from verified field inspections.
- **Areas:** today these are demo rectangles, not administrative boundaries, until Member B's verified districts are integrated. The engine accepts any polygon.
- **Not built yet** (roadmap only): field-inspection workflow, login and roles, alerts, Manipuri queries (until integrated), AG-01 disease detection, farmer mode, SMS/WhatsApp, voice.

## Demo flow (follow the real product)

1. The problem.
2. The Manipur dashboard, with the PLACEHOLDER/SAMPLE strip.
3. The risk map.
4. Priority areas.
5. "Why is this area at risk?": weather, NDVI against earlier years, pest indicators, provenance.
6. "Which areas are high risk?", then "Which should we inspect first?"
7. A crop-health NDVI question on the Kakching rectangle (93.95, 24.45, 94.03, 24.52).
8. A Manipuri query, *only if integrated by then*.
9. The inspection workflow as roadmap.
10. Honest limits.

Record a backup video of the stable build.

**Do not modify** `satquery/`, `web/` or any other member's folder.
