"""SAMPLE pest reports for the prototype: synthetic, seeded, and labelled so they cannot be mistaken.

No operational pest-report feed is connected yet, so the report-pressure factor runs on reports made
up by this generator from `assets/sample_scenario.json`. Every report says `source: "SAMPLE"`,
`synthetic: true` and carries the label "SAMPLE DATA — Prototype Simulation"; the set's provenance
state is SAMPLE. They are never real government or field observations and must not be shown as such.

Deterministic and stable from day to day: an area's reports are seeded by the scenario and the area
alone, and their dates are kept as days before the window's end. The same area therefore gets the
same reports (count, pest, severity, place, how many days ago) every day, so a demo ranking does not
reshuffle overnight, while the dates stay relative to today.
"""

import json
import random
from datetime import date, timedelta
from pathlib import Path

from satquery.agri import areas as geometry
from satquery.agri.config import ASSETS
from satquery.agri.models import MonitoredArea, PestReport, Provenance, SampleReportSet

SOURCE = "SatQuery sample-report generator (seeded, deterministic)"
NOTE = "SYNTHETIC reports for prototype demonstration only; not real government or field observations."


def load_scenario(path: str | Path | None = None) -> dict:
    scenario = json.loads(Path(path or ASSETS / "sample_scenario.json").read_text(encoding="utf-8"))
    if scenario.get("status") != "SAMPLE":
        raise ValueError("a sample-report scenario must declare status SAMPLE")
    return scenario


def _pick(rng: random.Random, weights: dict) -> str:
    names = sorted(weights)
    return rng.choices(names, weights=[weights[n] for n in names])[0]


def _point_inside(rng: random.Random, area: MonitoredArea) -> tuple[float, float]:
    from satquery import geo

    west, south, east, north = geo.geometry_bounds(area.geometry)
    for _ in range(1000):
        lon, lat = rng.uniform(west, east), rng.uniform(south, north)
        if geometry.contains(area.geometry, lon, lat):
            return lon, lat
    return geometry.representative_point(area)  # a sliver of an area: its own inside point


def generate(areas: list[MonitoredArea], end: date, scenario: dict | None = None) -> SampleReportSet:
    """SAMPLE reports for each area over the scenario's window ending on `end` (inclusive)."""
    scenario = scenario or load_scenario()
    reports = []
    for area in areas:
        rng = random.Random(f"{scenario['seed']}:{area.id}")  # not the date: stable day to day
        level = scenario["pressure_levels"][scenario["area_pressure"].get(area.id, scenario["default_pressure"])]
        low, high = level["reports"]
        for n in range(rng.randint(low, high)):
            lon, lat = _point_inside(rng, area)
            observed = end - timedelta(days=rng.randrange(scenario["window_days"]))
            reports.append(PestReport(id=f"sample-{area.id}-{n + 1}", area_id=area.id,
                                      latitude=round(lat, 5), longitude=round(lon, 5),
                                      observed_on=observed.isoformat(), crop=scenario["crop"],
                                      pest=_pick(rng, scenario["pests"]), severity=_pick(rng, level["severity"])))
    start = end - timedelta(days=scenario["window_days"] - 1)
    provenance = Provenance(source=SOURCE, state="SAMPLE", covers=f"{start.isoformat()} to {end.isoformat()}",
                            note=NOTE)
    return SampleReportSet(reports=reports, provenance=provenance, seed=scenario["seed"], generated_for=end.isoformat())


def in_area(report_set: SampleReportSet, area: MonitoredArea, end: date, lookback_days: int) -> list[PestReport]:
    """Reports located inside the area and observed within the lookback window ending on `end`."""
    first = end - timedelta(days=lookback_days - 1)
    return [r for r in report_set.reports
            if first.isoformat() <= r.observed_on <= end.isoformat()
            and geometry.contains(area.geometry, r.longitude, r.latitude)]


class SampleReportSource:
    """The prototype's report source: SAMPLE reports generated per area. A real feed (field reports,
    verified inspections) replaces it behind the same `for_area` method."""

    def __init__(self, scenario: dict | None = None):
        self.scenario = scenario or load_scenario()

    def for_area(self, area: MonitoredArea, end: date, lookback_days: int) -> tuple[list[PestReport], Provenance]:
        report_set = generate([area], end, self.scenario)
        return in_area(report_set, area, end, lookback_days), report_set.provenance
