# Member A: Manipuri and agronomy

**Most urgent:** verified thresholds that replace the PLACEHOLDER rules. In the live run on 2026-10-08 the placeholder blast rule held on every day in every demo area, so weather currently cannot separate areas, and the ranking follows the SAMPLE reports. The dashboard says so until verified rules arrive.

Copy each `*.template.json` to the real file name, fill it in, and run `python team/check_deliverables.py`.

## 1. `verified_pest_rules.json`: thresholds (most urgent)

Use **exactly the schema of** `satquery/agri/assets/pest_rules.json` (start from a copy of it). The checking script loads your file with the risk engine's own loader.

- Each pest rule has `id`, `name`, `crop`, `status` and `sources`, plus `conditions`, `past_days`, `forecast_days` and `full_score_days`.
- Each condition has:
  - `variable`: `temperature_2m`, `relative_humidity_2m`, `dew_point_2m` or `precipitation`
  - `aggregate`: `mean`, `min`, `max`, `sum`, `hours_at_or_above` or `hours_between`
  - one of `between`, `at_least`, `at_most` or `threshold` (as the aggregate needs)
  - a plain-language `label`
- Units: °C, % relative humidity, mm, and hours per day.
- `"status": "VERIFIED"` **only** when every number is traceable. Each source needs `title`, `url`, `verified_by` and `verified_on` (YYYY-MM-DD); otherwise loading fails. A pest you cannot verify stays `PLACEHOLDER`.
- Record each threshold's applicability and limits (crop stage, region, season) in `SOURCES.md`.
- Optional `verified_risk_model.json` follows `satquery/agri/assets/risk_model.json` (weights, level cut-points). Change it only with a cited reason.

## 2. `manipuri_queries.json`: start with 5–10 reliable queries

```json
{
  "status": "DRAFT",
  "queries": [
    {
      "id": "mni-001",
      "language": "mni",
      "script": "Mtei",
      "text": "<the verified Manipuri sentence>",
      "romanization": "<optional>",
      "english_meaning": "Which areas are at high risk?",
      "intent": "AREA_RISK_QUERY",
      "area": null,
      "verified_by": "<name>",
      "verified_on": "YYYY-MM-DD",
      "notes": ""
    }
  ]
}
```

- `script` is one of `Mtei` (Meitei Mayek), `Beng` (Bengali script) or `Latn` (romanised).
- Allowed intents, and the existing AG-04 behaviour each maps to:

| Intent | Existing AG-04 behaviour |
|---|---|
| `AREA_RISK_QUERY` | Ranking ("Which areas are high risk?") |
| `INSPECTION_PRIORITY` | Inspection order ("Which should we inspect first?") |
| `AREA_EXPLANATION` | Why a selected area is flagged |
| `AREA_SPECIFIC_RISK` | Why a named area is flagged. Set `area` to the district name |
| `PEST_RISK` | Pest risk in a named or selected area |
| `CROP_HEALTH` | The Phase 1 NDVI crop-health answer for a drawn area |
| `WEATHER_RISK` | The weather forecast for a drawn area |

- An entry counts only when its text is verified by a fluent speaker (`verified_by`, `verified_on`).

## 3. `agri_terms_manipuri.json`: terminology

```json
{
  "status": "DRAFT",
  "terms": [
    {
      "id": "term-rice",
      "category": "crop",
      "english": "rice / paddy",
      "manipuri": [{"script": "Mtei", "text": "<verified>", "romanization": "<optional>"}],
      "source": "<dictionary or expert>",
      "verified_by": "<name>",
      "verified_on": "YYYY-MM-DD",
      "notes": ""
    }
  ]
}
```

`category` is one of: `crop`, `pest`, `disease`, `weather`, `crop_health`, `inspection`, `risk` or `place`.

## 4. `advisory.json` (only verified content)

For each pest: symptoms, why it happens (the weather link), preventive/IPM steps, and when to contact the Department or KVK. Every item needs a `source`. Chemical advice stays conservative ("as advised by the Department of Agriculture / KVK"). **No invented contacts or helpline numbers.** Leave contacts out rather than guess.

## 5. `SOURCES.md`

For every threshold, term and advisory item: the source (title, URL, publisher, date accessed), who verified it and when, and its applicability and limitations.

**Do not modify** `satquery/`, `web/` or any other member's folder.
