"""AG-04 agricultural risk intelligence: data layer and explainable crop & pest risk engine.

  areas.py     monitored areas (districts, a user's own areas, demo rectangles) and geometry
  weather.py   hourly weather: ~14 days of recent history + 7-day forecast (Open-Meteo)
  ndvi.py      NDVI now vs the same dates in earlier years (Copernicus Statistical API)
  reports.py   pest reports; SAMPLE (synthetic, labelled) in this prototype
  rules.py     pest-favourable weather rules, evaluated day by day
  risk.py      factors -> score, level, confidence, reasons, ranking
  config.py    thresholds and weights as data (assets/*.json), PLACEHOLDER until verified
  pipeline.py  gather inputs, assess and rank areas
  context.py   district context for any area (OpenStreetMap)

Run `python -m satquery.agri --help` for the command line.
"""
