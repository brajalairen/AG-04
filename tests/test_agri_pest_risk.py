"""Risk-engine validation: controlled scenarios (Step 15), per-pest risk, saturation checks, determinism.

Scenarios run end to end through the pipeline with fake weather / NDVI providers. Every REAL
observation here is a unit-test fixture, never a real field record.
"""

import re
from datetime import datetime, timedelta, timezone

import pytest

from agri_helpers import TODAY, FakeStatsProvider, FakeWeather, area, humid_day, stats_response, verified_model, \
    verified_rules
from satquery.agri.config import load_observation_rules
from satquery.agri.models import PestObservation, SAMPLE_LABEL
from satquery.agri.ndvi import NdviClient
from satquery.agri.observations import ObservationDataset, ObservationFileSource, ObservationSet
from satquery.agri.pipeline import Sources, assess_areas
from satquery.agri.reports import SampleReportSource

NOW = datetime(2026, 10, 8, 6, 0, tzinfo=timezone.utc)
ZONE = area("z1", "Kakching zone", district="Kakching")  # rect 93.95-94.03 E, 24.45-24.52 N
FORBIDDEN = re.compile(r"\b(?:detected|detects|confirmed|outbreak)\b", re.I)
DATASET = ObservationDataset(id="test-ds", title="Unit-test surveillance fixture", publisher="Test publisher",
                             source_url="https://example.org/test", licence="test only", access_date="2026-10-08",
                             status="REAL", geographic_coverage="test", temporal_coverage="2026",
                             spatial_resolution="point", observation_method="scout survey (test fixture)",
                             limitations="test fixture, not real data", coverage_districts=["Kakching"])


def warm_humid_day():
    """Favourable for the placeholder brown planthopper rule (mean 27 °C, RH 85%), not for blast (no RH >= 90%)."""
    return {"temperature_2m": [27.0] * 24, "relative_humidity_2m": [85.0] * 24, "dew_point_2m": [24.0] * 24,
            "precipitation": [0.0] * 24}


def days(spec, favourable_days):
    """`favourable_days` of the 7 past + 3 forecast days get `spec`; the rest are dry."""
    window = [TODAY + timedelta(days=n) for n in range(-7, 3)]
    return {d: spec() for d in window[:favourable_days]}


def ndvi(current, baseline=(0.75, 0.75, 0.75), **current_kw):
    return NdviClient(FakeStatsProvider({2026: stats_response(current, **current_kw)}
                                        | {2025 - i: stats_response(v) for i, v in enumerate(baseline)}))


def observed(*records):
    observations = [PestObservation.model_validate(
        {"id": f"t{n}", "status": "REAL", "observed_on": (TODAY - timedelta(days=2)).isoformat(), "crop": "rice",
         "district": "Kakching", "latitude": 24.48, "longitude": 93.99, "source": "Test publisher: fixture",
         "source_url": "https://example.org/test"} | r) for n, r in enumerate(records)]
    return ObservationFileSource(ObservationSet(dataset=DATASET, observations=observations))


def run(weather_days=None, ndvi_client=None, reports=None, *, rules=None, model=None, zones=None):
    sources = Sources(weather=FakeWeather(weather_days or {}), ndvi=ndvi_client or ndvi(0.75), reports=reports)
    kwargs = {k: v for k, v in (("rules", rules), ("model", model)) if v is not None}
    ranked = assess_areas(zones or [ZONE], sources, now=NOW, observation_rules=load_observation_rules(), **kwargs)
    return ranked if zones else ranked[0]


def factor(assessment, fid):
    return next(f for f in assessment.factors if f.id == fid)


# --------------------------------------------------------------------------- Step 15 scenarios

def test_scenario_a_favourable_weather_vegetation_drop_and_real_observations_is_high():
    result = run(days(humid_day, 10), ndvi(0.675),  # NDVI 10% below the baseline
                 observed({"pest": "rice_blast", "severity": "high"}, {"pest": "rice_blast", "severity": "high"}),
                 rules=verified_rules(), model=verified_model())
    assert result.driver_pest == "rice_blast" and result.level == "HIGH"
    points = {f.id: f.points for f in result.factors}
    assert points == {"weather_pest": 50.0, "ndvi_anomaly": 12.4, "report_pressure": 13.3}
    assert result.score == pytest.approx(75.7, abs=0.05) and result.score == pytest.approx(sum(points.values()), abs=0.1)
    assert result.confidence.data_completeness == 1.0 and result.confidence.level == "high"
    assert not result.includes_sample_data and result.score_range is None and result.level_without_sample is None
    assert result.headline.startswith("Indicators suggest HIGH risk (76/100) for Kakching zone, led by rice blast")
    assert not FORBIDDEN.search(" ".join([result.headline] + result.reasons))


def test_scenario_b_unfavourable_weather_normal_vegetation_and_no_observations_is_low():
    result = run({}, ndvi(0.75), observed(), rules=verified_rules(), model=verified_model())
    assert result.level == "LOW" and result.score == 0.0
    assert {f.id: f.points for f in result.factors} == {"weather_pest": 0.0, "ndvi_anomaly": 0.0, "report_pressure": 0.0}
    assert factor(result, "report_pressure").status == "ok", "a surveyed district with no records is zero evidence"
    assert result.confidence.level == "high"


def test_scenario_c_some_favourable_days_and_weak_evidence_is_moderate():
    result = run(days(humid_day, 4), ndvi(0.7125),  # 4 blast days; NDVI 5% below
                 observed({"pest": "rice_blast", "severity": "low"}), rules=verified_rules(), model=verified_model())
    assert result.level == "MODERATE" and 35 <= result.score < 60
    assert result.score == pytest.approx(40 + 3.5 + 1.7, abs=0.15)


def test_scenario_d_missing_observations_are_not_fabricated_and_lower_completeness():
    result = run(days(humid_day, 10), ndvi(0.75), None)
    observations = factor(result, "report_pressure")
    assert observations.status == "unavailable" and observations.unavailable_reason == \
        "no pest-observation source is connected"
    assert observations.details["evidence_state"] == "NO_SOURCE" and "reports" not in observations.details
    assert all(p.observation_count == 0 for p in result.pest_risks)
    assert result.confidence.data_completeness == 0.8 and result.score == 50.0
    assert result.score_range == (50.0, 70.0) and not result.includes_sample_data


def test_scenario_d_records_without_stated_coverage_are_unknown_not_zero():
    unknown = ObservationFileSource(ObservationSet(dataset=DATASET.model_copy(update={"coverage_districts": None}),
                                                   observations=[]))
    result = run(days(humid_day, 10), ndvi(0.75), unknown)
    assert factor(result, "report_pressure").status == "unavailable"
    assert result.confidence.data_completeness == 0.8


def test_scenario_e_missing_ndvi_is_named_and_never_raises_the_score():
    with_ndvi = run(days(humid_day, 10), ndvi(0.75), observed())
    without = run(days(humid_day, 10), NdviClient(None), observed())
    ndvi_factor = factor(without, "ndvi_anomaly")
    assert ndvi_factor.status == "unavailable" and ndvi_factor.unavailable_reason == \
        "Copernicus credentials are not configured"
    assert ndvi_factor.score is None and ndvi_factor.details == {}
    assert without.score == with_ndvi.score == 50.0, "losing NDVI must not lift the score"
    assert without.score_range == (50.0, 80.0) and without.confidence.data_completeness == 0.7


def test_scenario_f_a_cloudy_satellite_window_gives_no_ndvi_value():
    cloudy = run(days(humid_day, 10), ndvi(0.40, pixels=1000, nodata=900), observed())
    ndvi_factor = factor(cloudy, "ndvi_anomaly")
    assert ndvi_factor.status == "unavailable" and ndvi_factor.score is None
    assert "only 10% of the area had a clear observation" in ndvi_factor.unavailable_reason
    assert ndvi_factor.details["anomaly"]["current"]["usable"] is False
    assert cloudy.score == 50.0, "the cloudy 0.40 mean is never used"


def test_a_level_that_rests_on_sample_data_says_so_in_answers():
    from satquery.agri import query as agri_query

    zone = area("demo-bishnupur-nambol", "Bishnupur zone", district="Bishnupur")
    ranked = run(days(humid_day, 10), ndvi(0.75), SampleReportSource(), zones=[zone])
    assert (ranked[0].level, ranked[0].level_without_sample) == ("HIGH", "MODERATE")
    answer = agri_query.answer("Which areas are high risk?", ranked, [zone]).answer
    assert "#1 Bishnupur zone: HIGH, 63/100 (confidence low; MODERATE without the SAMPLE data)" in answer
    assert any("the HIGH level depends on synthetic data" in r for r in ranked[0].reasons)


def test_scenario_g_sample_observations_stay_labelled_through_every_layer():
    result = run(days(humid_day, 10), ndvi(0.75), SampleReportSource(),
                 zones=[area("demo-bishnupur-nambol", "Bishnupur zone", district="Bishnupur")])[0]
    observations = factor(result, "report_pressure")
    assert result.includes_sample_data and observations.sample_data
    assert observations.name == "Pest/disease field observations (SAMPLE)"
    assert observations.provenance[0].state == "SAMPLE"
    reports = [r for p in result.pest_risks for f in p.factors if f.id == "report_pressure"
               for r in f.details.get("reports", [])]
    assert reports and all(r["status"] == "SAMPLE" and r["label"] == SAMPLE_LABEL and r["synthetic"] for r in reports)
    assert SAMPLE_LABEL == "SAMPLE DATA — PROTOTYPE SIMULATION"
    assert f"Includes {SAMPLE_LABEL}: the field-observation figures are synthetic." in result.reasons
    assert result.confidence.data_completeness == 0.8, "SAMPLE evidence is never counted as data"
    assert result.level_without_sample is not None and result.score_without_sample <= result.score


# -------------------------------------------------------------------------------- per pest

def test_each_pest_is_assessed_on_its_own_evidence_and_the_area_takes_the_highest():
    result = run(days(warm_humid_day, 10), ndvi(0.75),
                 observed({"pest": "rice_blast", "severity": "high"}, {"pest": "yellow_stem_borer", "severity": "high"},
                          {"pest": "yellow_stem_borer", "metric": "percent_dead_heart", "value": 12, "unit": "%",
                           "crop_stage": "tillering"}))
    risks = {p.pest_id: p for p in result.pest_risks}
    assert list(risks) == ["brown_planthopper", "yellow_stem_borer", "rice_blast"], "most urgent first"
    assert result.driver_pest == "brown_planthopper" and result.score == risks["brown_planthopper"].score == 50.0
    assert risks["rice_blast"].score == 6.7, "blast reports do not add to planthopper risk"
    stem_borer = risks["yellow_stem_borer"]
    assert not stem_borer.has_weather_rule and stem_borer.observation_count == 2
    weather = next(f for f in stem_borer.factors if f.id == "weather_pest")
    assert weather.unavailable_reason == "no weather rule is configured for yellow stem borer"
    assert stem_borer.score == 13.3, "two high records (one read from the 10% dead-heart ETL); no weather rule"
    assert ("Per pest/disease: Brown planthopper MODERATE (50/100); Yellow stem borer LOW (13/100); Rice blast "
            "(leaf / neck) LOW (7/100). The area takes the highest, Brown planthopper.") in result.reasons


def test_only_pests_with_a_rule_or_evidence_are_shown():
    result = run({}, ndvi(0.75), observed())
    assert {p.pest_id for p in result.pest_risks} == {"rice_blast", "brown_planthopper"}


def test_ndvi_is_described_as_supporting_evidence_never_as_detection():
    result = run(days(humid_day, 10), ndvi(0.6), observed())
    text = " ".join(factor(result, "ndvi_anomaly").reasons)
    assert "supporting evidence of a change in vegetation condition, not pest or disease detection" in text
    assert not FORBIDDEN.search(text)


# ------------------------------------------------------------------- saturation and stability

def test_different_evidence_gives_different_scores():
    scores = {run(days(humid_day, n), ndvi(0.75), observed()).score for n in (0, 2, 4, 5)}
    assert scores == {0.0, 20.0, 40.0, 50.0}


def test_sample_observations_alone_never_produce_a_level():
    sources = Sources(weather=FakeWeather({}, fail_inside=(93.0, 24.0, 95.0, 25.0)), ndvi=NdviClient(None),
                      reports=SampleReportSource())
    result = assess_areas([area("demo-bishnupur-nambol", district="Bishnupur")], sources, now=NOW)[0]
    assert result.level == "INSUFFICIENT_DATA" and result.score is None and result.rank is None


def test_scoring_is_deterministic():
    first = run(days(humid_day, 6), ndvi(0.7), SampleReportSource()).model_dump()
    second = run(days(humid_day, 6), ndvi(0.7), SampleReportSource()).model_dump()
    assert first == second


def test_ranking_follows_level_then_score_with_real_observations():
    zones = [area("z1", "Alpha zone", district="Kakching"),
             area("z2", "Beta zone", district="Kakching", geometry={"type": "Polygon", "coordinates": [
                 [[94.10, 24.45], [94.18, 24.45], [94.18, 24.52], [94.10, 24.52], [94.10, 24.45]]]})]
    ranked = run(days(humid_day, 10), ndvi(0.75), observed({"pest": "rice_blast", "severity": "high"},
                                                            {"pest": "rice_blast", "severity": "high"}), zones=zones)
    assert [(a.area_name, a.rank, a.level) for a in ranked] == [("Alpha zone", 1, "HIGH"), ("Beta zone", 2, "MODERATE")]
    assert ranked[0].score == pytest.approx(63.3, abs=0.05) and ranked[1].score == 50.0


# ------------------------------------------------------------- missing evidence never raises risk

def _factors(weather, ndvi_score, observations, *, drop=(), sample=False):
    from satquery.agri import risk
    from satquery.agri.config import load_risk_model
    from satquery.agri.models import FactorResult

    model = load_risk_model()
    out = []
    for fid, score in (("weather_pest", weather), ("ndvi_anomaly", ndvi_score), ("report_pressure", observations)):
        if fid in drop:
            out.append(risk._unavailable(fid, model.weights[fid], "dropped"))
        else:
            out.append(FactorResult(id=fid, name=risk.FACTOR_NAMES[fid], status="ok", score=score,
                                    weight=model.weights[fid], availability=1.0, summary=fid,
                                    sample_data=sample and fid == "report_pressure"))
    return out


def _combine(factors, model=None):
    from satquery.agri import risk
    from satquery.agri.config import load_pest_rules, load_risk_model

    return risk.combine(ZONE, factors, [], load_pest_rules(), model or load_risk_model(), "2026-10-08T06:00:00+00:00")


def test_removing_any_input_never_raises_the_score():
    from itertools import combinations, product

    values = (0.0, 0.3, 0.7, 1.0)
    ids = ("weather_pest", "ndvi_anomaly", "report_pressure")
    for scores in product(values, repeat=3):
        full = _combine(_factors(*scores))
        for size in (1, 2):
            for drop in combinations(ids, size):
                partial = _combine(_factors(*scores, drop=drop))
                assert (partial.score or 0.0) <= full.score, (scores, drop)
                if partial.score is not None:
                    low, high = partial.score_range
                    assert low <= full.score <= high, "the band always contains what the full data shows"
        sampled = _combine(_factors(*scores, sample=True))
        assert (sampled.score_without_sample or 0.0) <= (sampled.score or 0.0)


def test_the_phase_2_renormalisation_did_raise_scores():
    from satquery.agri.config import RiskModelConfig
    from agri_helpers import risk_model_dict

    legacy = RiskModelConfig.model_validate(risk_model_dict() | {"missing_inputs": "renormalise"})
    full = _combine(_factors(1.0, 0.0, 0.0), legacy)
    cloudy = _combine(_factors(1.0, 0.0, 0.0, drop=("ndvi_anomaly",)), legacy)
    assert (full.score, full.level) == (50.0, "MODERATE") and (cloudy.score, cloudy.level) == (71.4, "HIGH")


def test_the_band_counts_sample_and_missing_inputs_as_not_real():
    result = _combine(_factors(1.0, None, 0.667, drop=("ndvi_anomaly",), sample=True))
    assert result.score == pytest.approx(63.3, abs=0.05) and result.level == "HIGH"
    assert result.score_range == (50.0, 100.0) and result.level_without_sample == "MODERATE"
    assert result.confidence.data_completeness == 0.5
    assert any(r.startswith("Not backed by real data: vegetation condition vs earlier years (ndvi) (unavailable) and "
                            "pest/disease field observations. Real evidence alone gives 50/100") for r in result.reasons)


# --------------------------------------------------- no observations available vs no pest observed

@pytest.mark.parametrize("make, pest, state, status", [
    (lambda: None, "rice_blast", "NO_SOURCE", "unavailable"),
    (lambda: SampleReportSource(), "brown_planthopper", "SAMPLE_NONE", "ok"),
    (lambda: observed(), "rice_blast", "NONE_OBSERVED", "ok"),
    (lambda: observed({"pest": "rice_blast", "severity": "low"}), "rice_blast", "OBSERVED", "ok"),
    (lambda: ObservationFileSource(ObservationSet(dataset=DATASET.model_copy(update={"coverage_districts": None}),
                                                  observations=[])), "rice_blast", "COVERAGE_UNKNOWN", "unavailable"),
    (lambda: ObservationFileSource(ObservationSet(dataset=DATASET.model_copy(update={"coverage_districts": None}),
                                                  observations=observed({"pest": "rice_blast", "severity": "high",
                                                                         "observed_on": "2026-06-01"}).obs_set.observations)),
     "rice_blast", "HISTORICAL_ONLY", "unavailable"),
    (lambda: ObservationFileSource(ObservationSet(dataset=DATASET.model_copy(update={"coverage_districts": ["Thoubal"]}),
                                                  observations=[])), "rice_blast", "NOT_COVERED", "unavailable"),
    (lambda: ObservationFileSource(ObservationSet(dataset=DATASET.model_copy(update={"pests_surveyed": ["gall_midge"]}),
                                                  observations=[])), "rice_blast", "NOT_SURVEYED", "unavailable"),
])
def test_no_observations_available_is_never_read_as_no_pest_observed(make, pest, state, status):
    zone = area("demo-churachandpur-bungmual", "Kakching zone", district="Kakching")  # a background SAMPLE zone
    result = run({}, ndvi(0.75), make(), zones=[zone])[0]
    risk = next(p for p in result.pest_risks if p.pest_id == pest)
    factor = next(f for f in risk.factors if f.id == "report_pressure")
    assert factor.details["evidence_state"] == state and factor.status == status
    if state in ("NONE_OBSERVED", "OBSERVED"):
        assert risk.data_completeness == 1.0, "real surveillance that covers the area and pest is data"
    else:
        assert risk.data_completeness == 0.8, "no real observation evidence: not counted as data"
    if state == "HISTORICAL_ONLY":
        assert "only HISTORICAL rice blast records for this area (latest 2026-06-01)" in factor.unavailable_reason


# --------------------------------------------------------------------- unassessed pests, calibration

def test_known_pests_without_a_rule_or_evidence_are_listed_not_scored():
    result = run(days(humid_day, 10), ndvi(0.75), observed({"pest": "yellow_stem_borer", "severity": "high"}))
    assessed = {p.pest_id for p in result.pest_risks}
    listed = {p.pest_id: p.reason for p in result.pests_not_assessed}
    assert assessed == {"rice_blast", "brown_planthopper", "yellow_stem_borer"}
    assert set(listed) == {"leaf_folder", "gall_midge", "bacterial_leaf_blight", "gundhi_bug"}
    assert listed["gall_midge"] == "no weather rule is configured, and no observations in the last 14 days"
    assert any(r.startswith("Not assessed, so no score is given (no weather rule and no field evidence): rice leaf "
                            "folder, rice gall midge") for r in result.reasons)


def test_the_score_stays_uncalibrated_even_with_verified_thresholds():
    from pydantic import ValidationError
    from satquery.agri.config import RiskModelConfig
    from agri_helpers import risk_model_dict

    result = run(days(humid_day, 10), ndvi(0.75), observed(), rules=verified_rules(), model=verified_model())
    assert result.thresholds_status == "VERIFIED" and result.calibration == "UNCALIBRATED"
    assert any(r.startswith("The score is UNCALIBRATED: The weights, level bands") for r in result.reasons)
    assert any("UNCALIBRATED" in note for note in result.confidence.notes)
    with pytest.raises(ValidationError, match="calibration is marked VALIDATED but names no validation evidence"):
        RiskModelConfig.model_validate(risk_model_dict() | {"calibration": {"status": "VALIDATED"}})


# ---------------------------------------------------------------------- inspectable weather index

def test_the_weather_index_shows_its_arithmetic_and_when_it_saturates():
    saturated = run(days(humid_day, 10), ndvi(0.75), observed())
    calculation = factor(saturated, "weather_pest").details["calculation"]
    assert calculation == {"formula": "index = min(1, favourable days / full_score_days)", "favourable_past_days": 7,
                           "favourable_forecast_days": 3, "judged_days": 10, "window_days": 10, "full_score_days": 5,
                           "uncapped_ratio": 2.0, "index": 1.0, "saturated": True, "forecast_share": 0.3,
                           "thresholds": "PLACEHOLDER", "calibration": "UNCALIBRATED"}
    reasons = " ".join(factor(saturated, "weather_pest").reasons)
    assert "the index is capped at 1.0. 10 favourable days exceed the 5 that give the full score" in reasons
    assert "3 of the 10 favourable days are forecast days" in reasons
    partial = factor(run(days(humid_day, 4), ndvi(0.75), observed()), "weather_pest").details["calculation"]
    assert (partial["uncapped_ratio"], partial["index"], partial["saturated"], partial["forecast_share"]) == \
        (0.8, 0.8, False, 0.0)
