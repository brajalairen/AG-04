"""Districts as administrative context for the monitored agricultural zones.

The risk engine scores monitoring ZONES; a district is never scored or coloured itself. Here the
engine's ranked zones are only grouped by the district each zone is associated with, and districts
are ordered by their highest-priority zone's engine rank. Nothing is recomputed: a district's level
and score are those of that zone, and the wording says so ("a monitored zone in this district needs
attention", never "the district is affected"). A district with no zone has no level at all:
monitoring coverage is not available there, which is not the same as no risk.

Names come from `assets/manipur_district_names.json` (OpenStreetMap, to be confirmed). Verified
district boundaries are optional: `SATQUERY_AGRI_DISTRICTS` (or `assets/manipur_districts.geojson`)
adds outlines as context only once Member B delivers them; none are drawn without that file.
"""

import json
import os
from pathlib import Path

from satquery import geo
from satquery.agri.areas import load_areas
from satquery.agri.config import ASSETS
from satquery.agri.models import MonitoredArea, RiskAssessment

NAMES_FILE = ASSETS / "manipur_district_names.json"
BOUNDARIES_FILE = ASSETS / "manipur_districts.geojson"
LEVELS = ("CRITICAL", "HIGH", "MODERATE", "LOW", "INSUFFICIENT_DATA")


def normalise(name: str | None) -> str:
    return " ".join((name or "").lower().replace(" district", "").split())


def load_names() -> dict:
    return json.loads(NAMES_FILE.read_text(encoding="utf-8"))


def load_boundaries(path: str | Path | None = None) -> dict[str, MonitoredArea]:
    """Verified district outlines by normalised name, or {} when none have been delivered."""
    chosen = path or os.environ.get("SATQUERY_AGRI_DISTRICTS") or (BOUNDARIES_FILE if BOUNDARIES_FILE.is_file() else None)
    if not chosen:
        return {}
    return {normalise(a.district or a.name): a for a in load_areas(chosen) if a.kind == "district"}


def summarise(assessments: list[RiskAssessment], areas: dict[str, MonitoredArea],
              boundaries: dict[str, MonitoredArea] | None = None) -> list[dict]:
    """One entry per district: listed districts plus any district a zone names that is not listed.
    Ordered by the best engine rank among its zones; districts without coverage come last."""
    boundaries = boundaries or {}
    listed = [d["name"] for d in load_names()["districts"]]
    by_key: dict[str, dict] = {}
    for name in listed:
        by_key[normalise(name)] = {"name": name, "listed": True, "zones": []}
    for a in assessments:  # already in engine rank order
        area = areas.get(a.area_id)
        key = normalise(area.district if area else None) or "unassigned"
        entry = by_key.setdefault(key, {"name": area.district if area and area.district else "Unassigned",
                                        "listed": False, "zones": []})
        entry["zones"].append((a, area))

    out = []
    for key, entry in by_key.items():
        zones = entry["zones"]
        ranked = [a for a, _ in zones if a.rank is not None]
        top = min(ranked, key=lambda a: a.rank) if ranked else (zones[0][0] if zones else None)
        boundary = boundaries.get(key)
        zone_bounds = [geo.geometry_bounds(area.geometry) for _, area in zones if area]
        bounds = (geo.geometry_bounds(boundary.geometry) if boundary else
                  (min(b[0] for b in zone_bounds), min(b[1] for b in zone_bounds),
                   max(b[2] for b in zone_bounds), max(b[3] for b in zone_bounds)) if zone_bounds else None)
        out.append({
            "name": entry["name"], "listed": entry["listed"],
            "coverage": "monitored" if zones else "not_monitored",
            "zone_count": len(zones), "zone_ids": [a.area_id for a, _ in zones],
            "level_counts": {level: sum(1 for a, _ in zones if a.level == level) for level in LEVELS},
            "top_zone_id": top.area_id if top else None,
            "level": top.level if top else None, "score": top.score if top else None,
            "confidence": top.confidence.level if top else None,
            "best_zone_rank": top.rank if top else None,
            "has_boundary": boundary is not None,
            "boundary_source": boundary.boundary_source if boundary else None,
            "geometry": boundary.geometry if boundary else None,
            "bounds": bounds,
        })
    covered = sorted((d for d in out if d["coverage"] == "monitored"),
                     key=lambda d: (d["best_zone_rank"] is None, d["best_zone_rank"] or 0, d["name"]))
    uncovered = sorted((d for d in out if d["coverage"] != "monitored"), key=lambda d: d["name"])
    for i, district in enumerate(covered, 1):
        district["rank"] = i if district["best_zone_rank"] is not None else None
    for district in uncovered:
        district["rank"] = None
    return covered + uncovered
