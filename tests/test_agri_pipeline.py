"""End to end with fake providers: gather inputs, score, rank; failures stay visible; the command line."""

import json
from datetime import datetime, timedelta, timezone

import pytest

from agri_helpers import TODAY, FakeStatsProvider, FakeWeather, humid_day, stats_response
from satquery.agri import __main__ as cli
from satquery.agri.areas import demo_areas
from satquery.agri.cache import JsonCache
from satquery.agri.ndvi import NdviClient
from satquery.agri.pipeline import Sources, assess_areas, default_sources
from satquery.agri.reports import SampleReportSource

NOW = datetime(2026, 10, 8, 6, 0, tzinfo=timezone.utc)  # 11:30 in Manipur


def ndvi(current=0.60, baseline=(0.75, 0.75, 0.75)):
    by_year = {2026: stats_response(current)} | {2025 - i: stats_response(v) for i, v in enumerate(baseline)}
    return NdviClient(FakeStatsProvider(by_year))


HUMID = {TODAY + timedelta(days=n): humid_day() for n in range(-7, 3)}


def run(sources, areas=None):
    return assess_areas(areas or demo_areas(), sources, now=NOW)


def test_every_demo_area_is_assessed_ranked_and_explained():
    ranked = run(Sources(weather=FakeWeather(HUMID), ndvi=ndvi(), reports=SampleReportSource()))
    assert len(ranked) == 7 and [a.rank for a in ranked] == list(range(1, 8)) and ranked[0].rank_of == 7
    for assessment in ranked:
        assert assessment.as_of == "2026-10-08T06:00:00+00:00" and assessment.score is not None
        assert {f.id for f in assessment.factors} == {"weather_pest", "ndvi_anomaly", "report_pressure"}
        # Weather and NDVI are real (80% of the weight); SAMPLE observations are scored but are not data.
        assert assessment.confidence.data_completeness == 0.8 and assessment.confidence.level == "low"
        assert assessment.thresholds_status == "PLACEHOLDER" and assessment.includes_sample_data
        assert assessment.district_context["state"] == "Manipur"
        assert {p.state for p in assessment.provenance} == {"LIVE", "SAMPLE"}
        assert [p.pest_id for p in assessment.pest_risks][0] == assessment.driver_pest
        assert {p.pest_id for p in assessment.pest_risks} == {"rice_blast", "brown_planthopper"}
        assert assessment.level_without_sample is not None, "how far the level rests on SAMPLE data is shown"
    first = ranked[0]
    assert first.area_id == "demo-bishnupur-nambol", "the 'high' SAMPLE scenario area leads when weather is equal"
    assert sum(f.points or 0 for f in first.factors) == pytest.approx(first.score, abs=0.2)


def test_the_local_day_drives_the_windows():
    sources = Sources(weather=FakeWeather(HUMID), ndvi=ndvi(), reports=SampleReportSource())
    late = datetime(2026, 10, 7, 19, 0, tzinfo=timezone.utc)  # already 8 October in Manipur
    assessment = assess_areas(demo_areas()[:1], sources, now=late)[0]
    blast = next(p for p in assessment.pests if p.pest_id == "rice_blast")
    assert blast.days[-3].date == TODAY.isoformat() and blast.days[-3].period == "forecast"
    assert sources.ndvi.provider.calls[0]["aggregation"]["timeRange"]["to"] == "2026-10-08T00:00:00Z"


def test_a_weather_outage_is_visible_and_the_other_factors_still_report():
    failing = demo_areas()[0]  # Kakching: 93.95-94.03 E, 24.45-24.52 N
    ranked = run(Sources(weather=FakeWeather(HUMID, fail_inside=(93.95, 24.45, 94.03, 24.52)), ndvi=ndvi(),
                         reports=SampleReportSource()))
    hit = next(a for a in ranked if a.area_id == failing.id)
    weather = next(f for f in hit.factors if f.id == "weather_pest")
    assert weather.status == "unavailable" and weather.unavailable_reason == "The weather provider could not be reached."
    # NDVI (30%) is the only real input left: supporting evidence alone gives no pest-risk level.
    assert hit.confidence.data_completeness == 0.3 and hit.level == "INSUFFICIENT_DATA"
    assert hit.pests == [] and any("is unavailable" in r for r in hit.reasons)
    others = [a for a in ranked if a.area_id != failing.id]
    assert all(a.level != "INSUFFICIENT_DATA" for a in others), "the other areas still report"


def test_without_copernicus_credentials_ndvi_is_unavailable_not_estimated():
    sources = Sources(weather=FakeWeather(HUMID), ndvi=NdviClient(None), reports=SampleReportSource())
    ndvi_factor = next(f for f in run(sources)[0].factors if f.id == "ndvi_anomaly")
    assert ndvi_factor.status == "unavailable"
    assert ndvi_factor.unavailable_reason == "Copernicus credentials are not configured"


def test_offline_with_an_empty_cache_gives_no_estimate_anywhere(tmp_path):
    cache = JsonCache(tmp_path)
    from satquery.agri.weather import HourlyWeatherClient

    sources = Sources(weather=HourlyWeatherClient(cache, offline=True),
                      ndvi=NdviClient(None, cache, offline=True), reports=SampleReportSource())
    ranked = run(sources)
    assert {a.level for a in ranked} == {"INSUFFICIENT_DATA"} and all(a.rank is None for a in ranked)
    assert all(a.score is None and a.headline.startswith("Not enough data") for a in ranked)


def test_default_sources_without_credentials_still_run(tmp_path, monkeypatch):
    from satquery.settings import Settings

    sources = default_sources(Settings(runs_dir=tmp_path), offline=True)
    assert sources.ndvi.provider is None and sources.weather.offline and sources.reports is not None


def test_the_command_line_reports_thresholds_and_writes_assessments(tmp_path, monkeypatch, capsys):
    assert cli.main(["thresholds"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("Overall: PLACEHOLDER") and "rice_blast: PLACEHOLDER; sources: 0" in out

    monkeypatch.setenv("SATQUERY_RUNS_DIR", str(tmp_path))
    monkeypatch.setenv("COPERNICUS_CLIENT_ID", "")
    target = tmp_path / "out.json"
    assert cli.main(["assess", "--offline", "--json", str(target)]) == 0
    out = capsys.readouterr().out
    assert "INSUFFICIENT_DATA" in out and "Includes SAMPLE DATA" in out and "Decision support only" in out
    written = json.loads(target.read_text(encoding="utf-8"))
    assert len(written) == 7 and written[0]["disclaimer"].startswith("Decision support only")
