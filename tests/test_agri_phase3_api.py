"""Phase 3 decision-support API: area status, priorities, explanation, history, vocabulary, and the
trust rules behind them (REAL vs SAMPLE vs VERIFIED, no fabricated history, no claims of detection).

Every REAL observation here is a unit-test fixture, never a real field record.
"""

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from agri_helpers import TODAY, FakeStatsProvider, FakeWeather, area, humid_day, hourly_payload, stats_response
from satquery.agri import risk, views
from satquery.agri.areas import demo_areas
from satquery.agri.cache import JsonCache
from satquery.agri.config import load_pest_rules, load_risk_model
from satquery.agri.history import AssessmentHistory
from satquery.agri.inspections import InspectionRecord, InvalidTransition, advance, to_observation
from satquery.agri.models import FactorResult, PestObservation
from satquery.agri.ndvi import NdviClient
from satquery.agri.observations import ObservationDataset, ObservationFileSource, ObservationSet
from satquery.agri.pipeline import Sources, assess_areas, default_sources
from satquery.agri.reports import SampleReportSource
from satquery.agri.service import AssessmentService
from satquery.agri.weather import HourlyWeatherClient
from satquery.server import create_app
from satquery.settings import Settings

HUMID = {TODAY + timedelta(days=n): humid_day() for n in range(-14, 8)}  # wide: these tests use the real date
BISHNUPUR = "demo-bishnupur-nambol"
CLAIMS = re.compile(r"\b(?:detected|detects|confirmed|confirms|outbreaks?)\b", re.I)
ENDPOINTS = ["/api/agri/areas", f"/api/agri/areas/{BISHNUPUR}/summary", f"/api/agri/areas/{BISHNUPUR}/explanation",
             f"/api/agri/areas/{BISHNUPUR}/history", "/api/agri/priorities", "/api/agri/vocabulary"]


def ndvi(current=0.60):
    return NdviClient(FakeStatsProvider({2026: stats_response(current)}
                                        | {y: stats_response(0.75) for y in (2023, 2024, 2025)}))


def client_for(tmp_path, *, settings=None, history=None, areas=None, **changes):
    sources = Sources(**({"weather": FakeWeather(HUMID), "ndvi": ndvi(), "reports": SampleReportSource()} | changes))
    service = AssessmentService(settings or Settings(runs_dir=tmp_path), sources=sources, areas=areas, history=history)
    return TestClient(create_app(agri_service=service)), service


@pytest.fixture
def client(tmp_path):
    return client_for(tmp_path)[0]


def get(client, path, status=200):
    response = client.get(path)
    assert response.status_code == status, response.text
    return response.json()


def inputs_of(body):
    return {i["input"]: i for i in body["inputs"]}


# ------------------------------------------------------------------------------------- endpoints

def test_the_area_list_gives_every_area_with_trust_labels_and_its_boundary_status(client):
    body = get(client, "/api/agri/areas")
    assert body["mode"] == "live" and body["region"] == "Manipur" and body["language"] == "en"
    assert body["sample_label"] == "SAMPLE DATA — PROTOTYPE SIMULATION"
    assert body["rules"] == {"weather_rules": "PLACEHOLDER", "weather_rules_version": "0.1-placeholder",
                             "observation_rules": "PLACEHOLDER", "observation_rules_version": "0.1-candidate",
                             "risk_model": "PLACEHOLDER", "risk_model_version": "0.1-placeholder",
                             "calibration": "UNCALIBRATED", "missing_inputs_policy": "lower_bound"}
    assert len(body["areas"]) == 7 and [a["rank"] for a in body["areas"]] == list(range(1, 8))
    for item in body["areas"]:
        assert item["boundary"]["status"] == "DEMO_NOT_OFFICIAL" and item["boundary"]["official"] is False
        assert {"DEMO_AREA", "PLACEHOLDER", "UNCALIBRATED", "SAMPLE"} <= set(item["labels"])
        assert "AREA_NOT_OFFICIAL" in {l["code"] for l in item["limitations"]}


def test_the_summary_matches_the_engine_and_the_list(client):
    summary = get(client, f"/api/agri/areas/{BISHNUPUR}/summary")
    listed = next(a for a in get(client, "/api/agri/areas")["areas"] if a["id"] == BISHNUPUR)
    engine = next(a for a in assess_areas(demo_areas(), Sources(weather=FakeWeather(HUMID), ndvi=ndvi(),
                                                                 reports=SampleReportSource())) if a.area_id == BISHNUPUR)
    assert summary == listed
    assert (summary["level"], summary["score"], summary["confidence"], summary["data_completeness"]) == (
        engine.level, engine.score, engine.confidence.level, engine.confidence.data_completeness)
    assert summary["summary"].startswith(f"{engine.level} risk assessment ({engine.score:.0f}/100) from the indicators "
                                         "currently available")
    assert "pest evidence is SAMPLE (synthetic)" in summary["summary"] and "uncalibrated prototype" in summary["summary"]


def test_the_explanation_separates_weather_ndvi_pests_provenance_and_limits(client):
    body = get(client, f"/api/agri/areas/{BISHNUPUR}/explanation")
    assert body["overall"]["calibration"] == "UNCALIBRATED" and body["overall"]["freshness"] == "LIVE"
    weather = body["weather"]
    assert weather["trust"]["labels"] == ["REAL", "LIVE", "MODEL_DATA"] and "not station observations" in weather["data_note"]
    blast = next(p for p in weather["pests"] if p["pest_id"] == "rice_blast")
    assert [d["data_kind"] for d in blast["days"]] == ["MODEL_ANALYSIS"] * 7 + ["FORECAST"] * 3
    assert blast["calculation"]["uncapped_ratio"] == 2.0 and blast["calculation"]["saturated"] is True
    ndvi_view = body["ndvi"]
    assert ndvi_view["current"]["mean"] == 0.6 and ndvi_view["baseline_mean"] == pytest.approx(0.75)
    assert ndvi_view["relative_change"] == -0.2 and len(ndvi_view["baseline"]) == 3
    assert "not pest or disease detection" in ndvi_view["caveat"]
    pests = body["pests"]
    assert {p["pest_id"] for p in pests["assessed"]} == {"rice_blast", "brown_planthopper"}
    assert all(p["assessment"] == "ASSESSED" for p in pests["assessed"])
    observations = [o for p in pests["assessed"] for o in p["observations"]]
    assert observations and all(o["status"] == "SAMPLE" and o["verification"] == "UNVERIFIED" and o["synthetic"]
                                for o in observations)
    kinds = {(r["kind"], r["pest_id"]) for r in body["provenance"]["rule_sources"]}
    assert ("weather_rule", "rice_blast") in kinds and ("etl", "brown_planthopper") in kinds
    assert body["field_verification"]["status"] == "NO_INSPECTION_WORKFLOW"
    assert body["field_verification"]["sample_observations"] == len({o["id"] for o in observations})
    codes = {l["code"] for l in body["limitations"]}
    assert {"NOT_A_DETECTION", "PEST_EVIDENCE_SAMPLE", "PLACEHOLDER_THRESHOLDS", "UNCALIBRATED_SCORE",
            "WEATHER_INDEX_SATURATED", "NDVI_NOT_PEST_DETECTION"} <= codes


def test_priorities_follow_the_engine_rank_with_facts_not_an_escalation_policy(client):
    body = get(client, "/api/agri/priorities")
    assert [i["area_id"] for i in body["items"]] == [a["id"] for a in get(client, "/api/agri/areas")["areas"]]
    assert "not evidence that a pest or disease is present" in body["note"]
    for item in body["items"]:
        attention = item["attention"]
        assert attention["stage"] is None and attention["policy"] == "NOT_CONFIGURED"
        assert attention["facts"]["evidence_types"]["pest_observations"] == "SAMPLE"
        assert attention["facts"]["verified_observations"] == 0
        assert attention["facts"]["indicator_cut_status"] == "PLACEHOLDER"
    top = body["items"][0]
    assert top["evidence_summary"].startswith("Rice blast (leaf / neck): weather 50 (REAL), NDVI 30 (REAL), field "
                                              "observations")


def test_the_vocabulary_defines_every_code_the_api_uses(client):
    vocabulary = get(client, "/api/agri/vocabulary")
    explanation = get(client, f"/api/agri/areas/{BISHNUPUR}/explanation")
    assert {l["code"] for l in explanation["limitations"]} <= set(vocabulary["limitations"])
    assert set(vocabulary["evidence_states"]) >= {"NO_SOURCE", "NONE_OBSERVED", "SAMPLE_NONE", "HISTORICAL_ONLY"}
    assert list(vocabulary["verification_statuses"]) == ["UNVERIFIED", "REPORTED", "INITIAL_IDENTIFICATION",
                                                         "EXPERT_REVIEW", "VERIFIED"]
    assert set(vocabulary["escalation_stages"]) == {"WATCH", "PRIORITIZE", "FIELD_INSPECTION_RECOMMENDED",
                                                    "VERIFIED_OBSERVATION"}
    labels = {label for a in get(client, "/api/agri/areas")["areas"] for label in a["labels"]}
    labels |= {label for a in get(client, "/api/agri/areas")["areas"] for i in a["inputs"] for label in i["trust"]["labels"]}
    assert labels <= set(vocabulary["trust_labels"]) | {"NDVI_UNAVAILABLE", "WEATHER_UNAVAILABLE",
                                                        "NO_REAL_PEST_EVIDENCE", "VERIFIED_PEST_EVIDENCE",
                                                        "VERIFIED_RULES"}


@pytest.mark.parametrize("path", [f"/api/agri/areas/nowhere/{part}" for part in ("summary", "explanation", "history")])
def test_an_unknown_area_is_a_404_with_a_code(client, path):
    assert get(client, path, 404) == {"code": "unknown_area", "message": "No monitored area has the id 'nowhere'."}


@pytest.mark.parametrize("path", ENDPOINTS[:-1])
def test_an_unusable_areas_file_is_a_503_with_a_code(tmp_path, path):
    broken = tmp_path / "areas.geojson"
    broken.write_text('{"type": "FeatureCollection", "features": []}', encoding="utf-8")
    client, _ = client_for(tmp_path, settings=Settings(runs_dir=tmp_path, agri_areas=str(broken)))
    assert get(client, path, 503)["code"] == "agri_unavailable"


def test_a_bad_history_limit_is_refused(client):
    assert client.get(f"/api/agri/areas/{BISHNUPUR}/history?limit=0").status_code == 422


# ------------------------------------------------------------------------------------ data trust

def test_real_weather_and_satellite_are_real_but_not_pest_verification(client):
    inputs = inputs_of(get(client, f"/api/agri/areas/{BISHNUPUR}/summary"))
    assert inputs["weather"]["trust"] == {"origin": "REAL", "synthetic": False, "freshness": "LIVE",
                                          "verification": "NOT_APPLICABLE", "labels": ["REAL", "LIVE", "MODEL_DATA"]}
    assert inputs["ndvi"]["trust"]["origin"] == "REAL" and inputs["ndvi"]["trust"]["verification"] == "NOT_APPLICABLE"
    assert inputs["pest_observations"]["trust"] == {"origin": "SAMPLE", "synthetic": True, "freshness": "SAMPLE",
                                                    "verification": "UNVERIFIED",
                                                    "labels": ["SAMPLE", "SYNTHETIC", "UNVERIFIED"]}


def test_missing_ndvi_is_unavailable_with_its_reason_everywhere(tmp_path):
    client, _ = client_for(tmp_path, ndvi=NdviClient(None))
    summary = get(client, f"/api/agri/areas/{BISHNUPUR}/summary")
    ndvi_input = inputs_of(summary)["ndvi"]
    assert ndvi_input["trust"]["origin"] == "UNAVAILABLE" and ndvi_input["status"] == "unavailable"
    assert ndvi_input["unavailable_reason"] == "Copernicus credentials are not configured"
    assert "NDVI_UNAVAILABLE" in summary["labels"] and "NDVI is unavailable" in summary["summary"]
    explanation = get(client, f"/api/agri/areas/{BISHNUPUR}/explanation")
    assert explanation["ndvi"]["current"] is None and explanation["ndvi"]["points"] is None


def test_cached_and_stale_weather_are_labelled(tmp_path, monkeypatch):
    cache = JsonCache(tmp_path / "cache")
    monkeypatch.setattr(HourlyWeatherClient, "_get", lambda self, lat, lon: hourly_payload(HUMID))
    zone = [area(BISHNUPUR, "Bishnupur zone", district="Bishnupur")]
    live, _ = client_for(tmp_path / "live", areas=zone, weather=HourlyWeatherClient(cache))
    assert inputs_of(get(live, f"/api/agri/areas/{BISHNUPUR}/summary"))["weather"]["trust"]["freshness"] == "LIVE"
    offline = Settings(runs_dir=tmp_path / "offline", agri_offline=True)
    cached, _ = client_for(tmp_path, settings=offline, areas=zone, weather=HourlyWeatherClient(cache, offline=True))
    summary = get(cached, f"/api/agri/areas/{BISHNUPUR}/summary")
    assert inputs_of(summary)["weather"]["trust"]["labels"] == ["REAL", "CACHED", "MODEL_DATA"]
    assert "OFFLINE_CACHED" in {l["code"] for l in summary["limitations"]} and summary["freshness"] == "CACHED"
    stale, _ = client_for(tmp_path, settings=offline, areas=zone,
                          weather=HourlyWeatherClient(cache, offline=True, max_age_s=0))
    summary = get(stale, f"/api/agri/areas/{BISHNUPUR}/summary")
    assert inputs_of(summary)["weather"]["trust"]["freshness"] == "STALE" and summary["freshness"] == "STALE"
    assert "WEATHER_STALE" in {l["code"] for l in summary["limitations"]}


def test_an_unavailable_input_is_named_and_adds_nothing(tmp_path):
    client, _ = client_for(tmp_path, weather=FakeWeather(HUMID, fail_inside=(90, 20, 100, 30)))
    summary = get(client, f"/api/agri/areas/{BISHNUPUR}/summary")
    assert inputs_of(summary)["weather"]["trust"]["origin"] == "UNAVAILABLE"
    assert summary["level"] == "INSUFFICIENT_DATA" and summary["score"] is None
    assert {"WEATHER_UNAVAILABLE", "INSUFFICIENT_DATA"} <= {l["code"] for l in summary["limitations"]}


def test_snapshot_mode_is_labelled_snapshot_and_not_recorded_as_history(tmp_path):
    live, live_service = client_for(tmp_path, settings=Settings(runs_dir=tmp_path, agri_refresh_s=0.0))
    live_service.save_snapshot()
    recorded = len(live_service.history().for_area(BISHNUPUR))
    frozen, frozen_service = client_for(tmp_path, settings=Settings(runs_dir=tmp_path, agri_mode="snapshot",
                                                                    agri_refresh_s=0.0))
    summary = get(frozen, f"/api/agri/areas/{BISHNUPUR}/summary")
    assert summary["mode"] == "snapshot" and summary["freshness"] == "SNAPSHOT"
    assert "SNAPSHOT_DATA" in {l["code"] for l in summary["limitations"]}
    assert len(frozen_service.history().for_area(BISHNUPUR)) == recorded, "a snapshot is not a new point in time"


# ---------------------------------------------------------------------------------------- safety

def test_no_endpoint_claims_a_detection_or_confirmation(client):
    for path in ENDPOINTS:
        text = json.dumps(get(client, path), ensure_ascii=False)
        assert not CLAIMS.search(text), (path, CLAIMS.search(text).group(0))


def test_missing_data_never_lifts_an_area_in_the_ranking():
    model, rules = load_risk_model(), load_pest_rules()

    def assessment(name, ndvi_score):
        factors = [FactorResult(id="weather_pest", name=risk.FACTOR_NAMES["weather_pest"], status="ok", score=1.0,
                                weight=0.5, availability=1.0, summary="w")]
        factors.append(FactorResult(id="ndvi_anomaly", name=risk.FACTOR_NAMES["ndvi_anomaly"], status="ok",
                                    score=ndvi_score, weight=0.3, availability=1.0, summary="n")
                       if ndvi_score is not None else risk._unavailable("ndvi_anomaly", 0.3, "cloudy"))
        factors.append(FactorResult(id="report_pressure", name=risk.FACTOR_NAMES["report_pressure"], status="ok",
                                    score=0.0, weight=0.2, availability=1.0, summary="o"))
        return risk.combine(area(name.lower(), name), factors, [], rules, model, "2026-10-08T06:00:00+00:00")

    ranked = risk.rank([assessment("Alpha zone", None), assessment("Beta zone", 0.0)])
    assert [(a.area_name, a.score) for a in ranked] == [("Beta zone", 50.0), ("Alpha zone", 50.0)], \
        "equal scores: the zone with more real data first, whatever the names"


def test_sample_evidence_can_never_be_verified():
    with pytest.raises(ValidationError, match="SAMPLE record must be synthetic, unverified"):
        PestObservation(id="s", observed_on="2026-10-07", crop="rice", pest="rice_blast", severity="high",
                        latitude=24.5, longitude=93.9, verified=True)


def test_an_unsupported_pest_is_not_assessed_and_has_no_score(client):
    pests = get(client, f"/api/agri/areas/{BISHNUPUR}/explanation")["pests"]
    stem_borer = next(p for p in pests["not_assessed"] if p["pest_id"] == "yellow_stem_borer")
    assert stem_borer == {"pest_id": "yellow_stem_borer", "name": "Yellow stem borer", "assessment": "NOT_ASSESSED",
                          "reason": "no weather rule is configured, and the SAMPLE generator does not simulate it"}
    assert "yellow_stem_borer" not in {p["pest_id"] for p in pests["assessed"]}


# --------------------------------------------------------------------------------------- history

def test_history_holds_only_live_computations_oldest_first(tmp_path):
    client, service = client_for(tmp_path, settings=Settings(runs_dir=tmp_path, agri_refresh_s=0.0))
    assert service.history().for_area(BISHNUPUR) == [], "nothing exists before the first assessment"
    for _ in range(3):
        get(client, f"/api/agri/areas/{BISHNUPUR}/summary")
    body = get(client, f"/api/agri/areas/{BISHNUPUR}/history")  # this request computes a fourth
    entries = body["entries"]
    assert body["enabled"] is True and len(entries) == 4 and "nothing is backfilled" in body["note"]
    assert [e["computed_at"] for e in entries] == sorted(e["computed_at"] for e in entries)
    assert all(e["field_outcome"] is None for e in entries), "no outcome exists until verified inspections do"
    assert entries[-1]["inputs"] == {"weather": "LIVE", "ndvi": "LIVE", "pest_observations": "SAMPLE"}
    assert entries[-1]["config"]["risk_model"] == "0.1-placeholder (PLACEHOLDER, UNCALIBRATED)"
    limited = get(client, f"/api/agri/areas/{BISHNUPUR}/history?limit=2")["entries"]  # computes a fifth
    assert len(limited) == 2 and limited[0]["computed_at"] >= entries[-1]["computed_at"]


def test_offline_runs_and_disabled_history_record_nothing(tmp_path):
    offline = Settings(runs_dir=tmp_path, agri_offline=True, agri_refresh_s=0.0)
    _, service = client_for(tmp_path, settings=offline)
    service.snapshot()
    assert not (tmp_path / "agri" / "history.jsonl").exists()
    disabled = Settings(runs_dir=tmp_path / "off", agri_history=False)
    client, _ = client_for(tmp_path, settings=disabled)
    body = get(client, f"/api/agri/areas/{BISHNUPUR}/history")
    assert body["enabled"] is False and body["entries"] == [] and "switched off" in body["note"]
    persistence = get(client, "/api/agri/priorities")["items"][0]["attention"]["facts"]["persistence"]
    assert persistence == {"history_enabled": False, "recorded_assessments": None, "elevated_streak": None,
                           "elevated_since": None, "first_recorded_at": None}


def test_a_damaged_history_line_is_skipped_not_guessed(tmp_path):
    store = AssessmentHistory(tmp_path / "history.jsonl")
    store.path.write_text('{"area_id": "a1", "broken": true}\nnot json\n', encoding="utf-8")
    assert store.for_area("a1") == []


def test_persistence_counts_consecutive_elevated_recorded_assessments(tmp_path):
    client, _ = client_for(tmp_path, settings=Settings(runs_dir=tmp_path, agri_refresh_s=0.0))
    get(client, "/api/agri/areas")
    facts = get(client, "/api/agri/priorities")["items"][0]["attention"]["facts"]
    assert facts["elevated_now"] is True and facts["persistence"]["recorded_assessments"] == 2
    assert facts["persistence"]["elevated_streak"] == 2


# ------------------------------------------------------------------- verified field evidence

DATASET = ObservationDataset(id="test-ds", title="Unit-test surveillance fixture", publisher="Test publisher",
                             source_url="https://example.org/test", licence="test only", access_date="2026-10-08",
                             status="REAL", geographic_coverage="test", temporal_coverage="2026",
                             spatial_resolution="point", observation_method="scout survey (test fixture)",
                             limitations="test fixture, not real data", coverage_districts=["Bishnupur"])


def test_a_verified_real_observation_is_real_and_verified_and_sets_the_factual_stage(tmp_path):
    record = PestObservation.model_validate({
        "id": "t1", "status": "REAL", "observed_on": (TODAY - timedelta(days=2)).isoformat(), "crop": "rice",
        "pest": "rice_blast", "severity": "high", "district": "Bishnupur", "latitude": 24.66, "longitude": 93.80,
        "source": "Test publisher: fixture", "source_url": "https://example.org/test", "verified": True})
    source = ObservationFileSource(ObservationSet(dataset=DATASET, observations=[record]))
    zone = [area(BISHNUPUR, "Bishnupur zone", district="Bishnupur",
                 geometry={"type": "Polygon", "coordinates": [[[93.76, 24.63], [93.84, 24.63], [93.84, 24.70],
                                                               [93.76, 24.70], [93.76, 24.63]]]})]
    client, _ = client_for(tmp_path, areas=zone, reports=source)
    summary = get(client, f"/api/agri/areas/{BISHNUPUR}/summary")
    assert inputs_of(summary)["pest_observations"]["trust"] == {
        "origin": "REAL", "synthetic": False, "freshness": "CACHED", "verification": "VERIFIED",
        "labels": ["REAL", "CACHED", "VERIFIED"]}
    assert "VERIFIED_PEST_EVIDENCE" in summary["labels"] and not summary["includes_sample_data"]
    attention = get(client, "/api/agri/priorities")["items"][0]["attention"]
    assert attention["stage"] == "VERIFIED_OBSERVATION" and attention["facts"]["verified_observations"] == 1
    observation = get(client, f"/api/agri/areas/{BISHNUPUR}/explanation")["pests"]["assessed"][0]["observations"][0]
    assert (observation["status"], observation["verification"], observation["synthetic"]) == ("REAL", "VERIFIED", False)


def inspection(**changes):
    return InspectionRecord.model_validate({"id": "i1", "district": "Bishnupur", "crop": "rice",
                                            "suspected_pest": "brown_planthopper", "observed_at": "2026-10-07T10:00:00",
                                            "source_type": "field_inspector", "inspector": "Test inspector"} | changes)


def test_inspection_verification_moves_forward_only_with_its_evidence():
    record = inspection()
    record = advance(record, "REPORTED", by="Test inspector", at="2026-10-07T10:05:00")
    record = advance(record, "EXPERT_REVIEW", by="Test office", at="2026-10-07T12:00:00")
    with pytest.raises(InvalidTransition, match="cannot move from EXPERT_REVIEW to REPORTED"):
        advance(record, "REPORTED", by="x", at="2026-10-07T13:00:00")
    with pytest.raises(ValidationError, match="VERIFIED needs expert_reviewer, verified_on, finding"):
        advance(record, "VERIFIED", by="x", at="2026-10-08T09:00:00")
    with pytest.raises(ValidationError, match="PRESENT finding needs a severity or a measured value"):
        advance(record, "VERIFIED", by="Test expert", at="2026-10-08T09:00:00", expert_reviewer="Test expert",
                verified_on="2026-10-08", finding="PRESENT")
    verified = advance(record, "VERIFIED", by="Test expert", at="2026-10-08T09:00:00", expert_reviewer="Test expert",
                       verified_on="2026-10-08", finding="PRESENT", metric="hoppers_per_hill", value=18,
                       unit="hoppers/hill", crop_stage="tillering")
    assert [c.status for c in verified.status_history] == ["REPORTED", "EXPERT_REVIEW", "VERIFIED"]
    observation = to_observation(verified)
    assert (observation.status, observation.verified, observation.observation_type) == ("REAL", True, "inspection")
    assert observation.latitude is None and observation.spatial_resolution == "district", "no point is invented"


def test_only_a_verified_present_finding_becomes_field_evidence():
    assert to_observation(inspection()) is None
    assert to_observation(inspection(verification_status="VERIFIED", expert_reviewer="E", verified_on="2026-10-08",
                                     finding="ABSENT")) is None
    with pytest.raises(ValidationError, match="belong to VERIFIED records only"):
        inspection(finding="PRESENT")
    with pytest.raises(ValidationError, match="needs on-site coordinates or a district"):
        inspection(district=None)


# ------------------------------------------------------------------------ satellite integration

def test_ag04_ndvi_uses_the_satquery_copernicus_provider(tmp_path):
    from satquery.providers.copernicus import CopernicusSentinelProvider

    sources = default_sources(Settings(runs_dir=tmp_path, copernicus_client_id="id", copernicus_client_secret="secret"))
    assert type(sources.ndvi.provider) is CopernicusSentinelProvider, "the same provider SatQueryAI uses"


def test_no_second_copernicus_integration_exists_in_the_agri_package():
    agri = Path(__file__).resolve().parent.parent / "satquery" / "agri"
    for path in agri.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "identity.dataspace.copernicus.eu" not in text and "sh.dataspace.copernicus.eu" not in text, path.name


def test_the_ndvi_the_api_shows_is_what_the_satellite_provider_returned(tmp_path):
    provider = FakeStatsProvider({2026: stats_response(0.52, pixels=1000, nodata=100)}
                                 | {y: stats_response(0.70) for y in (2023, 2024, 2025)})
    client, _ = client_for(tmp_path, ndvi=NdviClient(provider))
    current = get(client, f"/api/agri/areas/{BISHNUPUR}/explanation")["ndvi"]["current"]
    assert current["mean"] == 0.52 and current["observed_fraction"] == 0.9 and current["usable"] is True
    assert provider.calls and all(c["aggregation"]["evalscript"].startswith("//VERSION=3") for c in provider.calls)


def test_ranking_is_deterministic(client):
    first = [i["area_id"] for i in get(client, "/api/agri/priorities")["items"]]
    assert first == [i["area_id"] for i in get(client, "/api/agri/priorities")["items"]]


def test_the_history_store_is_append_only_jsonl(tmp_path):
    store = AssessmentHistory(tmp_path / "h.jsonl")
    ranked = assess_areas(demo_areas()[:2], Sources(weather=FakeWeather(HUMID), ndvi=ndvi(),
                                                    reports=SampleReportSource()),
                          now=datetime(2026, 10, 8, 6, 0, tzinfo=timezone.utc))
    assert store.record(ranked, "2026-10-08T06:00:00+00:00", {"risk_model": "x"}) == 2
    assert store.record(ranked, "2026-10-08T06:30:00+00:00", {"risk_model": "x"}) == 2
    assert len(store.path.read_text(encoding="utf-8").splitlines()) == 4
    assert [e.computed_at for e in store.for_area(ranked[0].area_id)] == ["2026-10-08T06:00:00+00:00",
                                                                         "2026-10-08T06:30:00+00:00"]
    assert AssessmentHistory(None).record(ranked, "t", {}) == 0 and not AssessmentHistory(None).enabled
