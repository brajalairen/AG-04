"""Vegetation condition of a monitored area against its own past: NDVI now vs the same dates in earlier years.

Computed by the Copernicus Sentinel Hub Statistical API over the area's polygon, so a whole district
works (the Process API's 400 km2 box does not apply). Per pixel, every Sentinel-2 L2A acquisition in
the window is considered; cloud, cloud shadow, cirrus, saturated, no-data, water and snow pixels are
dropped using Sentinel-2's own scene classification (SCL), and the pixel's value is the MEDIAN NDVI of
its remaining clear land observations. The area figure is the mean over pixels with at least one
clear observation. The same method runs on every window, so this year and the baseline compare like
with like. Verified live on 2026-10-08 (Kakching rectangle: 0.37 processing units per 30-day window).

A window is usable only when enough of the area was actually observed; otherwise it says why and no
value is substituted.
"""

import math
from datetime import date, timedelta

from satquery.agri.areas import area_km2
from satquery.agri.cache import JsonCache, cache_key
from satquery.agri.config import NdviConfig
from satquery.agri.models import MonitoredArea, NdviAnomaly, NdviWindow, Provenance
from satquery.providers.errors import RetrievalError

EVALSCRIPT_VERSION = "ndvi-orbit-median-scl-v1"  # part of every cache key: a method change refetches
SCL_EXCLUDED = (0, 1, 3, 6, 8, 9, 10, 11)  # no data, defective, cloud shadow, water, cloud med/high, cirrus, snow
SOURCE = "Copernicus Sentinel Hub Statistical API, Sentinel-2 L2A"
LICENCE = "Contains modified Copernicus Sentinel data (free, full and open access)"
METHOD = ("Per pixel: median NDVI of all clear land observations in the window (Sentinel-2 SCL classes "
          f"{', '.join(map(str, SCL_EXCLUDED))} dropped: cloud, shadow, cirrus, water, snow, no data). Area value: "
          "mean over pixels with at least one clear observation. Same method for every year.")
CRS84 = "http://www.opengis.net/def/crs/OGC/1.3/CRS84"

EVALSCRIPT = """//VERSION=3
function setup() {
  return {
    input: [{bands: ["B04", "B08", "SCL", "dataMask"]}],
    output: [{id: "ndvi", bands: 1, sampleType: "FLOAT32"}, {id: "dataMask", bands: 1}],
    mosaicking: "ORBIT"
  };
}
var EXCLUDED = [%s];
function evaluatePixel(samples) {
  var values = [];
  for (var i = 0; i < samples.length; i++) {
    var s = samples[i];
    if (s.dataMask !== 1 || EXCLUDED.indexOf(s.SCL) !== -1) continue;
    var sum = s.B08 + s.B04;
    if (!(sum > 0)) continue;
    values.push((s.B08 - s.B04) / sum);
  }
  if (values.length === 0) return {ndvi: [NaN], dataMask: [0]};
  values.sort(function (a, b) { return a - b; });
  var mid = Math.floor(values.length / 2);
  var median = values.length %% 2 ? values[mid] : (values[mid - 1] + values[mid]) / 2;
  return {ndvi: [median], dataMask: [1]};
}""" % ", ".join(map(str, SCL_EXCLUDED))


def _same_day(day: date, year: int) -> date:
    try:
        return day.replace(year=year)
    except ValueError:  # 29 February in a non-leap year
        return day.replace(year=year, day=28)


def windows(today: date, cfg: NdviConfig) -> list[tuple[str, date, date]]:
    """[(label, start, end_exclusive)]: the current window ending today, then the same dates in earlier years."""
    start = today - timedelta(days=cfg.window_days)
    out = [("current", start, today)]
    for back in range(1, cfg.baseline_years + 1):
        out.append((str(today.year - back), _same_day(start, start.year - back), _same_day(today, today.year - back)))
    return out


def resolution_deg(area: MonitoredArea, cfg: NdviConfig) -> float:
    """A pixel size that keeps the area under `max_pixels` (cost and speed), never finer than the minimum."""
    latitude = sum(p[1] for p in _first_ring(area.geometry)) / len(_first_ring(area.geometry))
    km2_per_deg2 = 110.57 * 111.32 * math.cos(math.radians(latitude))
    needed = math.sqrt(max(area_km2(area.geometry), 1e-6) / km2_per_deg2 / cfg.max_pixels)
    return round(max(cfg.min_resolution_deg, needed), 6)


def _first_ring(geometry: dict) -> list:
    return geometry["coordinates"][0] if geometry["type"] == "Polygon" else geometry["coordinates"][0][0]


def statistics_payload(area: MonitoredArea, start: date, end: date, resolution: float) -> dict:
    return {
        "input": {"bounds": {"geometry": area.geometry, "properties": {"crs": CRS84}},
                  "data": [{"type": "sentinel-2-l2a", "dataFilter": {"maxCloudCoverage": 100}}]},
        "aggregation": {"timeRange": {"from": f"{start.isoformat()}T00:00:00Z", "to": f"{end.isoformat()}T00:00:00Z"},
                        "aggregationInterval": {"of": f"P{(end - start).days}D", "lastIntervalBehavior": "EXTEND"},
                        "evalscript": EVALSCRIPT, "resx": resolution, "resy": resolution},
        "calculations": {"ndvi": {"statistics": {"default": {"percentiles": {"k": [10, 50, 90]}}}}},
    }


def parse_statistics(response: dict) -> dict:
    """{mean, median, p10, p90, pixels, nodata} from a Statistical API response, or ValueError."""
    if not isinstance(response, dict) or response.get("status") not in (None, "OK"):
        raise ValueError(f"statistics status {response.get('status') if isinstance(response, dict) else '?'}")
    data = response.get("data") or []
    if not data:
        raise ValueError("no interval in the response (no Sentinel-2 acquisition in the window)")
    interval = data[0]
    if interval.get("error"):
        raise ValueError(str(interval["error"].get("message") or interval["error"])[:200])
    stats = interval["outputs"]["ndvi"]["bands"]["B0"]["stats"]
    percentiles = stats.get("percentiles") or {}

    def number(value):
        return float(value) if isinstance(value, (int, float)) and math.isfinite(value) else None

    return {"mean": number(stats.get("mean")), "median": number(percentiles.get("50.0")),
            "p10": number(percentiles.get("10.0")), "p90": number(percentiles.get("90.0")),
            "pixels": int(stats.get("sampleCount") or 0), "nodata": int(stats.get("noDataCount") or 0)}


class NdviClient:
    """NDVI windows for an area, from the Statistical API, cached on disk.

    Past-year windows never change, so their cache entries never expire. The current window's key
    includes its end date (today), so it refreshes daily. `offline=True` serves the cache only.
    """

    def __init__(self, provider, cache: JsonCache | None = None, *, offline: bool = False):
        self.provider = provider  # anything with `statistics(payload) -> dict` (CopernicusSentinelProvider)
        self.cache = cache
        self.offline = offline

    def window(self, area: MonitoredArea, label: str, start: date, end: date, resolution: float,
               cfg: NdviConfig) -> NdviWindow:
        base = NdviWindow(label=label, start=start.isoformat(), end=end.isoformat())
        key = cache_key("ndvi", area.geometry, start.isoformat(), end.isoformat(), resolution, EVALSCRIPT_VERSION)
        hit = self.cache.get("ndvi", key) if self.cache else None
        if hit:
            stats, state, retrieved_at = hit.value, "CACHED", hit.retrieved_at
        elif self.offline or self.provider is None:
            return base.model_copy(update={"reason": "offline: no cached NDVI for this window"
                                           if self.offline else "imagery provider not configured"})
        else:
            try:
                stats = parse_statistics(self.provider.statistics(statistics_payload(area, start, end, resolution)))
            except RetrievalError as error:
                return base.model_copy(update={"reason": f"imagery provider error: {error.message}"})
            except (ValueError, KeyError, TypeError) as error:
                return base.model_copy(update={"reason": f"no usable statistics: {error}"})
            entry = self.cache.put("ndvi", key, stats) if self.cache else None
            state, retrieved_at = "LIVE", entry.retrieved_at if entry else None
        pixels, nodata = stats["pixels"], stats["nodata"]
        observed = (pixels - nodata) / pixels if pixels else 0.0
        result = base.model_copy(update={"mean": stats["mean"], "median": stats["median"], "p10": stats["p10"],
                                         "p90": stats["p90"], "pixels": pixels, "observed_fraction": round(observed, 4),
                                         "state": state, "retrieved_at": retrieved_at})
        if stats["mean"] is None:
            return result.model_copy(update={"reason": "no clear land observation in the window"})
        if observed < cfg.min_observed_fraction:
            return result.model_copy(update={"reason": f"only {observed:.0%} of the area had a clear observation "
                                                        f"(minimum {cfg.min_observed_fraction:.0%})"})
        return result.model_copy(update={"usable": True})

    def anomaly(self, area: MonitoredArea, today: date, cfg: NdviConfig) -> NdviAnomaly:
        resolution = resolution_deg(area, cfg)
        found = [self.window(area, label, start, end, resolution, cfg) for label, start, end in windows(today, cfg)]
        current, baseline = found[0], found[1:]
        usable = [w for w in baseline if w.usable]
        baseline_mean = sum(w.mean for w in usable) / len(usable) if usable else None
        result = NdviAnomaly(current=current, baseline=baseline, baseline_mean=baseline_mean,
                             baseline_range=(min(w.mean for w in usable), max(w.mean for w in usable)) if usable else None,
                             baseline_years_used=len(usable), relative_change=None, absolute_change=None,
                             within_baseline_range=None, resolution_deg=resolution, method=METHOD)
        if current.usable and baseline_mean and len(usable) >= cfg.min_baseline_years:
            low, high = result.baseline_range
            result = result.model_copy(update={
                "absolute_change": round(current.mean - baseline_mean, 4),
                "relative_change": round((current.mean - baseline_mean) / baseline_mean, 4),
                "within_baseline_range": low <= current.mean <= high})
        return result

    @staticmethod
    def provenance(anomaly: NdviAnomaly) -> list[Provenance]:
        out = []
        for w in [anomaly.current, *anomaly.baseline]:
            if w.state != "UNAVAILABLE":
                out.append(Provenance(source=SOURCE, state=w.state, retrieved_at=w.retrieved_at,
                                      covers=f"{w.start} to {w.end} (end exclusive)", licence=LICENCE,
                                      note=f"{w.label} window, {w.observed_fraction:.0%} of the area observed clear"))
        return out
