# Member C: UI/UX and QA

Deliver `UI_REVIEW.md`, `QA_REPORT.md`, `TEST_MATRIX.md` and `screenshots/`. **Report bugs; do not change backend or risk-engine code.** If you want to propose frontend changes, put them on a separate `feature/ui-fixes` branch for review.

## How to run it

```bash
uvicorn satquery.server:app --port 8000      # then open http://127.0.0.1:8000
SATQUERY_AGRI_OFFLINE=1 uvicorn satquery.server:app --port 8000   # cached data only
```

The first load after a start runs the assessment: about 9 s with warm caches, up to about 1 minute cold. That's a known Phase 4 item.

## What to test (put each in `TEST_MATRIX.md`)

- **Data states:**
  - live data; cached data; offline mode (`SATQUERY_AGRI_OFFLINE=1`, network off)
  - the labels must say CACHED or offline, never present stale data as live
- **Honest gaps:**
  - a cloudy area: crop-health question on south of Imphal (93.90, 24.55, 93.98, 24.62)
  - missing NDVI, missing weather (network off with no cache)
  - SAMPLE reports (labelled everywhere?)
  - PLACEHOLDER thresholds (visible strip, panel, drawer, answers)
  - low confidence
- **Questions:**
  - "Which areas are high risk?", "Why is Bishnupur flagged?", "Which should we inspect first?"
  - "Why is Imphal flagged?": should ask which one
  - "Is there pest risk in this area?" with no area selected
  - an unknown place; weather and imagery questions still routed correctly
- **Map:**
  - hover, click, rank badges, legend, dashed demo outlines vs solid district outlines
  - selected-area framing; light/dark; the satellite basemap
- **States:** loading, error with retry (stop the server mid-way), empty
- **Sizes:** 1280×720, 1600×900, the projector's real resolution, and a phone (best effort)
- **Readability:** from 3–4 m away on a projector. Font sizes, contrast, and whether levels are readable without colour

## `TEST_MATRIX.md` columns

| ID | Area | Scenario | Steps | Expected | Result (pass/fail) | Bug ID | Notes |
|---|---|---|---|---|---|---|---|

## `QA_REPORT.md`: one entry per bug

```
ID:        QA-001
Severity:  critical | major | minor | cosmetic
Page:      priority panel / map / drawer / command bar / ...
Steps to reproduce:
Expected:
Actual:
Screenshot: screenshots/QA-001.png (if useful)
```

Severity guide:
- **Critical:** wrong or misleading information (for example a SAMPLE or PLACEHOLDER label missing, or cached data shown as live), or a demo-blocking failure.
- **Major:** a broken feature.
- **Minor:** a workaround exists.
- **Cosmetic:** visual only.

**Do not modify** `satquery/`, `web/` (except on `feature/ui-fixes` for review) or any other member's folder.
