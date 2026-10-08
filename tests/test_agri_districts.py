"""Districts as context for the monitored zones, and the dashboard overview built on them."""

import json
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from agri_helpers import TODAY, FakeStatsProvider, FakeWeather, area, humid_day, stats_response
from satquery.agri import districts as agri_districts
from satquery.agri.areas import demo_areas
from satquery.agri.ndvi import NdviClient
from satquery.agri.pipeline import Sources, assess_areas
from satquery.agri.reports import SampleReportSource, generate
from satquery.agri.service import AgriUnavailable, AssessmentService
from satquery.server import create_app
from satquery.settings import Settings

HUMID = {TODAY + timedelta(days=n): humid_day() for n in range(-7, 3)}


def ndvi(current=0.60):
    return NdviClient(FakeStatsProvider({2026: stats_response(current)}
                                        | {y: stats_response(0.75) for y in (2023, 2024, 2025)}))


def sources(**changes):
    return Sources(**({"weather": FakeWeather(HUMID), "ndvi": ndvi(), "reports": SampleReportSource()} | changes))


def service(tmp_path, *, mode="live", **source_changes):
    settings = Settings(runs_dir=tmp_path, agri_mode=mode, agri_refresh_s=0.0)
    return AssessmentService(settings, sources=sources(**source_changes))


def test_districts_are_grouped_from_the_engines_ranking_without_rescoring():
    zones = demo_areas()
    assessed = assess_areas(zones, sources())
    summary = agri_districts.summarise(assessed, {a.id: a for a in zones})
    covered = [d for d in summary if d["coverage"] == "monitored"]
    uncovered = [d for d in summary if d["coverage"] == "not_monitored"]
    assert len(summary) == 16 and len(covered) == 7 and len(uncovered) == 9, "16 listed districts, 7 with a zone"
    assert [d["rank"] for d in covered] == list(range(1, 8))
    by_zone = {a.area_id: a for a in assessed}
    for d in covered:
        top = by_zone[d["top_zone_id"]]
        assert (d["level"], d["score"], d["confidence"], d["best_zone_rank"]) == (
            top.level, top.score, top.confidence.level, top.rank), "copied from the top zone, not recomputed"
        assert d["geometry"] is None and d["has_boundary"] is False, "no outline without verified data"
    for d in uncovered:
        assert d["level"] is None and d["score"] is None and d["zone_count"] == 0 and d["bounds"] is None


def test_a_zone_naming_an_unlisted_district_is_kept_not_dropped():
    zone = area("z1", "Zone", district="Somewhere Else")
    assessed = assess_areas([zone], sources())
    summary = agri_districts.summarise(assessed, {zone.id: zone})
    extra = next(d for d in summary if d["name"] == "Somewhere Else")
    assert extra["listed"] is False and extra["zone_ids"] == ["z1"]


def test_verified_district_outlines_are_context_only(tmp_path, monkeypatch):
    path = tmp_path / "districts.geojson"
    path.write_text(json.dumps({"type": "FeatureCollection", "features": [{
        "type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[93.7, 24.6], [93.9, 24.6], [93.9, 24.75],
                                                                          [93.7, 24.75], [93.7, 24.6]]]},
        "properties": {"id": "mn-bishnupur", "name": "Bishnupur", "kind": "district", "district": "Bishnupur",
                       "state": "Manipur", "boundary_source": "Test boundaries v1"}}]}), encoding="utf-8")
    monkeypatch.setenv("SATQUERY_AGRI_DISTRICTS", str(path))
    zones = demo_areas()
    summary = agri_districts.summarise(assess_areas(zones, sources()), {a.id: a for a in zones},
                                       agri_districts.load_boundaries())
    bishnupur = next(d for d in summary if d["name"] == "Bishnupur")
    assert bishnupur["has_boundary"] and bishnupur["boundary_source"] == "Test boundaries v1"
    assert bishnupur["bounds"] == (93.7, 24.6, 93.9, 24.75)


def test_the_overview_carries_districts_mode_and_separate_threshold_statuses(tmp_path):
    body = TestClient(create_app(agri_service=service(tmp_path))).get("/api/agri/overview").json()
    assert body["mode"] == "live" and body["snapshot_saved_at"] is None and body["fallback_reason"] is None
    assert body["pest_thresholds_status"] == "PLACEHOLDER" and body["risk_weights_status"] == "PLACEHOLDER"
    assert body["zone_count"] == 7 and len(body["districts"]) == 16
    assert "does not mean the whole district is affected" in body["district_note"]
    assert body["official_boundaries"] is False


def test_the_overview_says_when_it_shows_a_snapshot(tmp_path):
    service(tmp_path).save_snapshot()
    body = TestClient(create_app(agri_service=service(tmp_path, mode="snapshot"))).get("/api/agri/overview").json()
    assert body["mode"] == "snapshot" and body["snapshot_saved_at"] and "SNAPSHOT" in body["data_states"]
    assert "LIVE" not in body["data_states"]
