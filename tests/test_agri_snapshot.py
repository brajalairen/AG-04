"""Phase 4 reliability: frozen snapshot with live-first fallback, warm-up, day-to-day stable SAMPLE reports."""

import json
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from agri_helpers import TODAY, FakeStatsProvider, FakeWeather, area, humid_day, stats_response
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


def test_a_frozen_snapshot_is_always_labelled_snapshot_never_live(tmp_path):
    live = service(tmp_path)
    path = live.save_snapshot()
    frozen = service(tmp_path, mode="snapshot").snapshot()
    assert frozen.mode == "snapshot" and frozen.snapshot_saved_at and "SATQUERY_AGRI_MODE" in frozen.fallback_reason
    states = {p.state for a in frozen.assessments for p in a.provenance}
    assert "LIVE" not in states and "CACHED" not in states and states == {"SNAPSHOT", "SAMPLE"}
    assert any("originally LIVE" in (p.note or "") for p in frozen.assessments[0].provenance)
    assert [a.score for a in frozen.assessments] == [a.score for a in live.snapshot().assessments]
    assert path.name == "snapshot.json" and path.parent.name == "agri"


def test_live_is_preferred_and_the_snapshot_serves_only_when_live_is_incomplete(tmp_path):
    service(tmp_path).save_snapshot()  # a complete snapshot
    complete = service(tmp_path).snapshot()
    assert complete.mode == "live", "complete live data wins"
    down = service(tmp_path, weather=FakeWeather(HUMID, fail_inside=(90, 20, 100, 30)),
                   ndvi=NdviClient(None)).snapshot()
    assert down.mode == "snapshot" and "Live data is incomplete" in down.fallback_reason


def test_without_a_snapshot_incomplete_live_data_is_shown_honestly(tmp_path):
    down = service(tmp_path, ndvi=NdviClient(None)).snapshot()
    assert down.mode == "live" and all(a.confidence.data_completeness < 1 for a in down.assessments)


def test_snapshot_mode_without_a_file_is_a_clear_error(tmp_path):
    response = TestClient(create_app(agri_service=service(tmp_path, mode="snapshot"))).get("/api/agri/overview")
    assert response.status_code == 503 and "no usable snapshot" in response.json()["message"]


def test_a_snapshot_is_never_refrozen_as_if_it_were_live(tmp_path):
    service(tmp_path).save_snapshot()
    with pytest.raises(AgriUnavailable, match="refusing to re-freeze"):
        service(tmp_path, mode="snapshot").save_snapshot()


def test_warm_up_computes_the_assessment_off_the_request_path(tmp_path):
    warm = service(tmp_path)
    warm.warm_in_background().join(timeout=30)
    assert warm._snapshot is not None and len(warm._snapshot.assessments) == 7


def test_sample_reports_do_not_reshuffle_from_day_to_day():
    zone = area("demo-bishnupur-nambol")
    today, tomorrow = generate([zone], TODAY).reports, generate([zone], TODAY + timedelta(days=1)).reports

    def shape(reports, end):
        return [(r.pest, r.severity, r.latitude, r.longitude, (end - date.fromisoformat(r.observed_on)).days)
                for r in reports]

    assert shape(today, TODAY) == shape(tomorrow, TODAY + timedelta(days=1)), "same reports, dates relative"
    assert all(r.source == "SAMPLE" and r.synthetic for r in today + tomorrow)
