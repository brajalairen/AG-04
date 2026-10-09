"""The read-only /api/agri/* endpoints and agricultural routing: engine results, shaped, never recomputed."""

import re
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from agri_helpers import TODAY, FakeStatsProvider, FakeWeather, area, humid_day, rect, stats_response
from satquery.agri import query as agri_query
from satquery.agri.areas import demo_areas
from satquery.agri.cache import JsonCache
from satquery.agri.ndvi import NdviClient
from satquery.agri.pipeline import Sources, assess_areas
from satquery.agri.reports import SampleReportSource
from satquery.agri.service import AssessmentService
from satquery.agri.weather import HourlyWeatherClient
from satquery.server import create_app
from satquery.settings import Settings

HUMID = {TODAY + timedelta(days=n): humid_day() for n in range(-7, 3)}
FORBIDDEN = re.compile(r"\b(?:detected|detects|confirmed|outbreak)\b", re.I)


def ndvi(current=0.60, baseline=(0.75, 0.75, 0.75)):
    return NdviClient(FakeStatsProvider({2026: stats_response(current)}
                                        | {2025 - i: stats_response(v) for i, v in enumerate(baseline)}))


def sources(**changes):
    return Sources(**({"weather": FakeWeather(HUMID), "ndvi": ndvi(), "reports": SampleReportSource()} | changes))


def client_for(tmp_path, monkeypatch, *, areas=None, **source_changes):
    monkeypatch.setenv("SATQUERY_RUNS_DIR", str(tmp_path))
    service = AssessmentService(Settings(runs_dir=tmp_path), sources=sources(**source_changes), areas=areas)
    return TestClient(create_app(agri_service=service)), service


@pytest.fixture
def client(tmp_path, monkeypatch):
    return client_for(tmp_path, monkeypatch)[0]


# ------------------------------------------------------------------------------- overview

def test_the_overview_ranks_every_monitored_area_with_its_notices(client):
    body = client.get("/api/agri/overview").json()
    assert body["region"] == "Manipur" and len(body["areas"]) == 7
    assert [a["rank"] for a in body["areas"]] == list(range(1, 8))
    assert sum(body["counts"].values()) == 7
    assert body["thresholds_status"] == "PLACEHOLDER" and "PLACEHOLDERS" in body["thresholds_note"]
    assert body["includes_sample_data"] and body["sample_label"] == "SAMPLE DATA — PROTOTYPE SIMULATION"
    assert body["disclaimer"].startswith("Decision support only")
    assert body["official_boundaries"] is False
    assert "not administrative boundaries" in body["area_note"] and "not loaded yet" in body["area_note"]
    assert body["examples"] == agri_query.EXAMPLES
    west, south, east, north = body["view_bounds"]
    assert 93.0 < west < east < 94.1 and 24.2 < south < north < 25.0, "inside Manipur"


def test_every_figure_is_the_engines_own_not_recomputed(client):
    body = client.get("/api/agri/overview").json()
    engine = {a.area_id: a for a in assess_areas(demo_areas(), sources())}
    for summary in body["areas"]:
        a = engine[summary["id"]]
        assert (summary["rank"], summary["level"], summary["score"], summary["headline"]) == (
            a.rank, a.level, a.score, a.headline)
        assert summary["confidence"] == a.confidence.level
        assert summary["data_completeness"] == a.confidence.data_completeness
        assert summary["factor_points"] == {f.id: f.points for f in a.factors}


def test_each_area_carries_its_outline_kind_and_a_label_point_inside_it(client):
    from satquery.agri.areas import contains

    for summary in client.get("/api/agri/overview").json()["areas"]:
        assert summary["kind"] == "demo" and summary["official_boundary"] is False
        assert "not an administrative boundary" in summary["boundary_source"]
        assert contains(summary["geometry"], *summary["label_point"])


def test_an_official_district_file_is_marked_as_official(tmp_path, monkeypatch):
    district = area("d-1", "Test District", kind="district", boundary_source="Test boundaries v1",
                    district="Test District")
    client, _ = client_for(tmp_path, monkeypatch, areas=[district])
    body = client.get("/api/agri/overview").json()
    assert body["official_boundaries"] is True and body["areas"][0]["official_boundary"] is True
    assert "administrative outlines from a named dataset" in body["area_note"]
    detail = client.get("/api/agri/areas/d-1").json()
    assert detail["boundary_note"] == "Administrative district outline from: Test boundaries v1."


def test_one_assessment_serves_many_requests_until_the_refresh_period(tmp_path, monkeypatch):
    client, service = client_for(tmp_path, monkeypatch)
    weather = service._sources.weather
    client.get("/api/agri/overview")
    client.get("/api/agri/areas/demo-bishnupur-nambol")
    client.post("/api/agri/query", json={"query": "Which areas are high risk?"})
    assert len(weather.calls) == 7, "one weather fetch per area, once"


# --------------------------------------------------------------------------------- detail

def test_the_detail_is_the_full_assessment_with_its_notes(client):
    detail = client.get("/api/agri/areas/demo-bishnupur-nambol").json()
    assert detail["area"]["id"] == detail["assessment"]["area_id"] == "demo-bishnupur-nambol"
    assert detail["boundary_note"] == "Demo monitoring rectangle drawn by the team: not an administrative boundary."
    assert detail["thresholds_note"] and detail["sample_label"] == "SAMPLE DATA — PROTOTYPE SIMULATION"
    factors = {f["id"]: f for f in detail["assessment"]["factors"]}
    assert set(factors) == {"weather_pest", "ndvi_anomaly", "report_pressure"}
    assert factors["report_pressure"]["sample_data"] is True
    assert detail["assessment"]["pests"][0]["days"], "per-day indicators for the drawer"


def test_an_unknown_area_is_a_404_with_a_reason(client):
    response = client.get("/api/agri/areas/nowhere")
    assert response.status_code == 404 and response.json()["code"] == "unknown_area"


def test_an_unusable_areas_file_is_a_503_with_a_reason(tmp_path, monkeypatch):
    broken = tmp_path / "areas.geojson"
    broken.write_text('{"type": "FeatureCollection", "features": []}', encoding="utf-8")
    service = AssessmentService(Settings(runs_dir=tmp_path, agri_areas=str(broken)), sources=sources())
    response = TestClient(create_app(agri_service=service)).get("/api/agri/overview")
    assert response.status_code == 503 and response.json()["code"] == "agri_unavailable"
    assert "could not be loaded" in response.json()["message"]


# ------------------------------------------------------------------------- honest gaps

def test_a_weather_outage_reaches_the_dashboard_as_unavailable(tmp_path, monkeypatch):
    client, _ = client_for(tmp_path, monkeypatch, weather=FakeWeather(HUMID, fail_inside=(93.95, 24.45, 94.03, 24.52)))
    kakching = next(a for a in client.get("/api/agri/overview").json()["areas"]
                    if a["id"] == "demo-kakching-khangshim")
    assert kakching["factor_status"]["weather_pest"] == "unavailable"
    # Only NDVI (30%) is real: NDVI is supporting evidence and SAMPLE observations are not data, so no level.
    assert kakching["factor_points"]["weather_pest"] is None and kakching["data_completeness"] == 0.3
    assert kakching["level"] == "INSUFFICIENT_DATA" and kakching["rank"] is None


def test_cloudy_ndvi_reaches_the_dashboard_as_unavailable(tmp_path, monkeypatch):
    cloudy = NdviClient(FakeStatsProvider({2026: stats_response(0.6, pixels=1000, nodata=900)}
                                          | {y: stats_response(0.75) for y in (2023, 2024, 2025)}))
    client, _ = client_for(tmp_path, monkeypatch, ndvi=cloudy)
    detail = client.get("/api/agri/areas/demo-bishnupur-nambol").json()
    ndvi_factor = next(f for f in detail["assessment"]["factors"] if f["id"] == "ndvi_anomaly")
    assert ndvi_factor["status"] == "unavailable" and "only 10% of the area" in ndvi_factor["unavailable_reason"]


def test_offline_without_cached_data_gives_no_estimates(tmp_path, monkeypatch):
    cache = JsonCache(tmp_path / "cache")
    client, _ = client_for(tmp_path, monkeypatch, weather=HourlyWeatherClient(cache, offline=True),
                           ndvi=NdviClient(None, cache, offline=True))
    body = client.get("/api/agri/overview").json()
    assert body["counts"]["INSUFFICIENT_DATA"] == 7
    assert all(a["rank"] is None and a["score"] is None for a in body["areas"])


# --------------------------------------------------------------------------------- queries

def ask(client, query, **extra):
    response = client.post("/api/agri/query", json={"query": query} | extra)
    assert response.status_code == 200
    return response.json()


def test_which_areas_are_high_risk(client):
    found = ask(client, "Which areas are high risk?")
    assert found["intent"] == "rank" and found["matched_rule"].startswith("ranking cue")
    assert found["answer"].startswith("Indicators suggest HIGH or CRITICAL risk in")
    assert found["focus_area_id"] == found["area_ids"][0]


def test_why_is_bishnupur_flagged(client):
    found = ask(client, "Why is Bishnupur flagged?")
    assert found["intent"] == "explain" and found["focus_area_id"] == "demo-bishnupur-nambol"
    assert "Indicators suggest" in found["answer"] and "Why:" in found["answer"]


def test_which_should_we_inspect_first(client):
    found = ask(client, "Which should we inspect first?")
    assert found["intent"] == "inspect" and len(found["area_ids"]) == 3
    assert found["answer"].startswith("Suggested order for field inspection, by risk rank (decision support")


def test_this_area_uses_the_selected_area_or_asks_for_one(client):
    selected = ask(client, "Why is this area at risk?", selected_area_id="demo-thoubal-chaobok")
    assert selected["intent"] == "explain" and selected["focus_area_id"] == "demo-thoubal-chaobok"
    nothing = ask(client, "Is there pest risk in this area?")
    assert nothing["intent"] == "unmatched" and "Select one of the monitored areas" in nothing["answer"]


def test_an_ambiguous_or_unknown_place_is_said_not_guessed(client):
    ambiguous = ask(client, "Why is Imphal flagged?")
    assert ambiguous["intent"] == "unmatched" and len(ambiguous["area_ids"]) == 2
    assert "matches several monitored areas" in ambiguous["answer"]
    unknown = ask(client, "Explain the risk in Ukhrul")
    assert unknown["intent"] == "unmatched" and "No monitored area matches" in unknown["answer"]


@pytest.mark.parametrize("query", agri_query.EXAMPLES + ["Is Thoubal at high risk?", "Which areas are most at risk?"])
def test_answers_keep_the_caveats_and_never_claim_detection(client, query):
    found = ask(client, query)
    assert not FORBIDDEN.search(found["answer"]), found["answer"]
    if found["intent"] != "unmatched":
        assert "PLACEHOLDER thresholds" in found["answer"]
        assert "SAMPLE DATA — PROTOTYPE SIMULATION" in found["answer"]
        assert "Decision support only" in found["answer"]
    assert found["thresholds_status"] == "PLACEHOLDER" and found["includes_sample_data"]


# --------------------------------------------------------------------------------- routing

@pytest.mark.parametrize("query", agri_query.EXAMPLES + [
    "Is there pest risk in this area?", "What is the risk in Kakching?", "Where should we go first?",
    "Show the high-risk areas", "Why is Imphal East flagged?"])
def test_agricultural_questions_route_to_the_risk_engine(client, query):
    routed = client.post("/api/route", json={"query": query}).json()
    assert routed["route"] == "agri" and routed["rule"].endswith("-> crop & pest risk engine")


@pytest.mark.parametrize("query, route", [
    ("How healthy is the crop here?", "imagery"), ("What is the NDVI?", "imagery"),
    ("Is vegetation stressed here?", "imagery"), ("Highlight the water body in this image.", "imagery"),
    ("Has crop health declined since June?", "imagery"), ("Is there flooding in this area?", "imagery"),
    ("Will it rain here this week?", "weather"), ("Is the rain stressing the crops?", "mixed"),
])
def test_phase_1_and_weather_questions_keep_their_routes(client, query, route):
    assert client.post("/api/route", json={"query": query}).json()["route"] == route


def test_an_empty_query_is_refused(client):
    assert client.post("/api/agri/query", json={"query": ""}).status_code == 422


def test_a_place_name_inside_another_word_does_not_match():
    areas = [area("x", "Thoubal farmland near Chaobok", district="Thoubal", geometry=rect(93.9, 24.6, 94.0, 24.7))]
    assert agri_query.resolve_area("Thoubalgarh risk", areas)[0] == []
    assert agri_query.resolve_area("risk in thoubal?", areas)[0] == areas
