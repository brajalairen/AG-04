"""The explainable risk score: factors, points, missing data, levels, confidence, wording, ranking."""

import re
from datetime import date, timedelta

import pytest

from agri_helpers import TODAY, FakeStatsProvider, area, humid_day, rect, risk_model_dict, stats_response, \
    verified_model, verified_rules, weather
from satquery.agri import risk
from satquery.agri.config import RiskModelConfig, load_pest_rules, load_risk_model
from satquery.agri.models import DISCLAIMER, PLACEHOLDER_NOTE, SAMPLE_LABEL, FactorResult, PestReport, Provenance
from satquery.agri.ndvi import NdviClient
from satquery.agri.rules import evaluate

RULES, MODEL = load_pest_rules(), load_risk_model()
AS_OF = "2026-10-08T06:00:00+00:00"
FORBIDDEN = re.compile(r"\b(detected|detects|confirmed|outbreak)\b", re.I)


def factor(fid, score, *, availability=1.0, sample=False, weight=None) -> FactorResult:
    weight = MODEL.weights[fid] if weight is None else weight
    if score is None:
        return risk._unavailable(fid, weight, "test reason")
    return FactorResult(id=fid, name=risk.FACTOR_NAMES[fid], status="ok" if availability == 1 else "partial",
                        score=score, weight=weight, availability=availability, summary=f"{fid} summary",
                        reasons=[f"{fid} reason"], sample_data=sample,
                        provenance=[Provenance(source=f"{fid} source", state="SAMPLE" if sample else "LIVE")])


def assess(weather_score, ndvi_score, report_score, *, name="Test area", rules=RULES, model=MODEL, sample=False):
    factors = [factor("weather_pest", weather_score), factor("ndvi_anomaly", ndvi_score),
               factor("report_pressure", report_score, sample=sample)]
    return risk.combine(area(name=name), factors, [], rules, model, AS_OF)


# ------------------------------------------------------------------------------- combination

def test_the_score_is_the_sum_of_its_visible_factor_points():
    result = assess(0.8, 0.5, 0.25)
    points = {f.id: f.points for f in result.factors}
    assert points == {"weather_pest": 40.0, "ndvi_anomaly": 15.0, "report_pressure": 5.0}
    assert result.score == 60.0 == sum(points.values()) and result.level == "HIGH"
    assert result.top_factors == ["weather_pest", "ndvi_anomaly", "report_pressure"]


def test_a_missing_factor_is_named_left_out_and_lowers_completeness():
    result = assess(0.8, None, 0.25)
    ndvi = next(f for f in result.factors if f.id == "ndvi_anomaly")
    assert ndvi.score is None and ndvi.points is None and ndvi.status == "unavailable"
    assert result.score == 45.0, "lower bound: (0.5 x 0.8 + 0.2 x 0.25) / 1.0; missing NDVI adds nothing"
    assert result.score_range == (45.0, 75.0), "the upper end treats the missing NDVI as fully adverse"
    assert result.confidence.data_completeness == 0.7
    assert any("is unavailable: test reason. It adds no points and is not estimated." in r for r in result.reasons)
    assert ("Not backed by real data: vegetation condition vs earlier years (ndvi) (unavailable). Real evidence alone "
            "gives 45/100; if the missing input were fully adverse the score could reach 75/100 (HIGH). Missing data "
            "never raises the score.") in result.reasons


def test_losing_an_input_never_raises_the_score():
    """The Phase 2 renormalisation filled a missing factor with the average of the others; a cloudy
    NDVI then lifted a 50/100 area to 71/100. Losing data must never raise a score."""
    complete = assess(1.0, 0.0, 0.0)
    cloudy = assess(1.0, None, 0.0)
    assert complete.score == 50.0 and cloudy.score == 50.0 and cloudy.level == complete.level == "MODERATE"
    legacy = risk_model_dict() | {"missing_inputs": "renormalise"}
    renormalised = assess(1.0, None, 0.0, model=RiskModelConfig.model_validate(legacy))
    assert renormalised.score == pytest.approx(71.4, abs=0.05) and renormalised.level == "HIGH"
    assert renormalised.score_range is None


def test_too_little_data_gives_no_level_and_no_score():
    result = assess(None, None, 0.9)
    assert result.level == "INSUFFICIENT_DATA" and result.score is None
    assert result.headline.startswith("Not enough data to estimate risk for Test area")
    assert "Only 20% of the model's inputs are backed by real data (minimum 50%)" in result.reasons[0]


def test_sample_evidence_is_scored_but_never_counted_as_data():
    result = assess(0.6, 0.0, 1.0, sample=True)
    assert result.score == 50.0 and result.level == "MODERATE"
    assert result.confidence.data_completeness == 0.8, "the SAMPLE factor's 20% weight is not real data"
    assert (result.score_without_sample, result.level_without_sample) == (30.0, "LOW")
    assert any("Without the SAMPLE field observations this area would be LOW (30/100): the MODERATE level depends "
               "on synthetic data." in r for r in result.reasons)
    real = assess(0.6, 0.0, 1.0)
    assert real.score_without_sample is None and real.level_without_sample is None


@pytest.mark.parametrize("score, level", [(0.0, "LOW"), (0.34, "LOW"), (0.35, "MODERATE"), (0.59, "MODERATE"),
                                          (0.6, "HIGH"), (0.79, "HIGH"), (0.8, "CRITICAL"), (1.0, "CRITICAL")])
def test_level_cut_points(score, level):
    assert assess(score, score, score).level == level


def test_critical_needs_two_independent_indicators():
    weights = {"weather_pest": 0.8, "ndvi_anomaly": 0.1, "report_pressure": 0.1}
    factors = [factor(fid, score, weight=weights[fid])
               for fid, score in (("weather_pest", 1.0), ("ndvi_anomaly", 0.5), ("report_pressure", 0.5))]
    single = risk.combine(area(), factors, [], RULES, verified_model(weights=weights), AS_OF)
    # score 0.9, but only the weather indicator is strong
    assert single.level == "HIGH" and single.score == 90.0
    assert "Critical needs at least 2 independent real indicators" in single.reasons[0]


def test_sample_evidence_is_never_an_independent_indicator_for_critical():
    result = assess(0.9, 0.5, 1.0, sample=True)  # critical band, but the second strong factor is SAMPLE
    assert result.score == 80.0 and result.level == "HIGH"
    assert "Critical needs at least 2 independent real indicators" in result.reasons[0]
    assert result.confidence.data_completeness == 0.8


def test_critical_also_needs_near_complete_data():
    assert assess(1.0, None, 1.0).level == "HIGH", "two strong indicators but only 70% of the data"
    critical = assess(0.9, 0.8, 0.7)
    assert critical.level == "CRITICAL" and critical.reasons[0].startswith("Critical: the score is in the critical band")


@pytest.mark.parametrize("weather_score, ndvi_score, sample, rules, model, expected", [
    (0.5, 0.5, False, RULES, MODEL, "low"),                              # placeholders cap at low
    (0.5, 0.5, False, verified_rules(), verified_model(), "high"),
    (0.5, 0.5, True, verified_rules(), verified_model(), "medium"),     # SAMPLE data caps at medium
    (0.5, None, False, verified_rules(), verified_model(), "medium"),   # 70% completeness
    (None, 0.5, False, verified_rules(), verified_model(), "low"),      # 50% completeness
])
def test_confidence_follows_completeness_and_is_capped_by_sample_data_and_placeholders(
        weather_score, ndvi_score, sample, rules, model, expected):
    result = assess(weather_score, ndvi_score, 0.5, sample=sample, rules=rules, model=model)
    assert result.confidence.level == expected and result.confidence.calibrated is False
    assert "not a calibrated probability" in result.confidence.method


def test_placeholder_and_sample_status_are_stated_in_the_reasons():
    result = assess(0.5, 0.5, 0.5, sample=True)
    assert result.thresholds_status == "PLACEHOLDER" and result.reasons[-1] == PLACEHOLDER_NOTE
    assert f"Includes {SAMPLE_LABEL}: the field-observation figures are synthetic." in result.reasons
    assert result.includes_sample_data
    assert any("PLACEHOLDERS" in note for note in result.confidence.notes)


def test_wording_is_decision_support_never_detection():
    for scores in [(0.9, 0.8, 0.7), (0.6, 0.6, 0.6), (0.1, 0.0, 0.0), (None, None, 0.5)]:
        result = assess(*scores)
        assert not FORBIDDEN.search(result.headline), result.headline
        assert result.disclaimer == DISCLAIMER and "Decision support only" in DISCLAIMER
    assert assess(0.6, 0.6, 0.6).headline.startswith("Indicators suggest HIGH risk (60/100) for Test area, mainly from")


def test_provenance_is_the_union_of_the_factors_sources_without_duplicates():
    result = assess(0.5, 0.5, 0.5, sample=True)
    assert [(p.source, p.state) for p in result.provenance] == [
        ("weather_pest source", "LIVE"), ("ndvi_anomaly source", "LIVE"), ("report_pressure source", "SAMPLE")]
    assert result.as_of == AS_OF


# ------------------------------------------------------------------------------------ factors

def pests(days):
    found = weather(days)
    return [evaluate(rule, found, TODAY) for rule in RULES.pests], found


def test_the_weather_factor_is_driven_by_the_most_favourable_pest():
    evaluations, found = pests({TODAY - timedelta(days=n): humid_day() for n in range(1, 8)})
    result = risk.weather_factor(evaluations, found, None, MODEL, area(), TODAY)
    assert result.score == 1.0 and result.details["driver"] == "rice_blast" and result.status == "ok"
    assert result.reasons[0].startswith("Rice blast (leaf / neck): favourable conditions on 7 of the last 7 days")
    assert result.thresholds == "PLACEHOLDER" and result.provenance[0].state == "LIVE"
    assert result.details["weather_summary"]["past_7_days"]["hours_rh_at_or_above_90"] == 7 * 12


def test_missing_weather_is_unavailable_with_its_reason():
    result = risk.weather_factor([], None, "The weather provider could not be reached.", MODEL, area(), TODAY)
    assert result.status == "unavailable" and result.score is None and result.availability == 0
    assert result.unavailable_reason == "The weather provider could not be reached."
    assert result.provenance[0].state == "UNAVAILABLE"


def test_partly_missing_weather_lowers_availability():
    evaluations, found = pests({})
    evaluations[0] = evaluations[0].model_copy(update={"known_past": 4, "status": "partial"})
    result = risk.weather_factor(evaluations, found, None, MODEL, area(), TODAY)
    assert result.status == "partial" and result.availability == pytest.approx((7 / 10 + 1) / 2)


def test_a_large_area_says_one_weather_point_stands_for_it():
    evaluations, found = pests({})
    large = area(geometry=rect(93.0, 24.0, 93.5, 24.5))
    reasons = risk.weather_factor(evaluations, found, None, MODEL, large, TODAY).reasons
    assert any(r.startswith("Weather is for one point inside the area, which spans about 51 x 55 km") for r in reasons)
    assert not any("one point" in r for r in risk.weather_factor(evaluations, found, None, MODEL, area(), TODAY).reasons)


def anomaly(current, baseline=(0.75, 0.75, 0.75), **current_kw):
    by_year = {2026: stats_response(current, **current_kw)} | {2025 - i: stats_response(v) for i, v in enumerate(baseline)}
    return NdviClient(FakeStatsProvider(by_year)).anomaly(area(), TODAY, MODEL.ndvi)


@pytest.mark.parametrize("current, score", [(0.735, 0.0), (0.66375, 0.5), (0.5, 1.0), (0.85, 0.0)])
def test_ndvi_scores_only_drops_beyond_the_ignore_band(current, score):
    result = risk.ndvi_factor(anomaly(current), None, MODEL)
    assert result.score == pytest.approx(score, abs=0.01) and result.status == "ok"


def test_the_ndvi_reasons_give_the_numbers_years_coverage_and_caveat():
    reasons = risk.ndvi_factor(anomaly(0.6, (0.70, 0.75, 0.80)), None, MODEL).reasons
    assert reasons[0] == ("NDVI over the observed land in the last 30 days is 0.60, 20% below the 0.75 average for "
                          "the same dates in 2025, 2024, 2023.")
    assert reasons[1] == "100% of the area had at least one clear Sentinel-2 view in the window."
    assert reasons[2] == "That is outside the range of those years (0.70-0.80)."
    assert "not cropland alone" in reasons[3]


def test_a_cloudy_current_window_makes_ndvi_unavailable_not_zero():
    result = risk.ndvi_factor(anomaly(0.6, pixels=1000, nodata=900), None, MODEL)
    assert result.status == "unavailable" and result.score is None
    assert result.unavailable_reason == ("current NDVI unavailable (only 10% of the area had a clear observation "
                                         "(minimum 30%))")


def test_a_thin_baseline_is_partial_and_a_missing_one_unavailable():
    cloudy = stats_response(0.7, pixels=1000, nodata=950)
    two = NdviClient(FakeStatsProvider({2026: stats_response(0.7), 2025: stats_response(0.75),
                                        2024: stats_response(0.75), 2023: cloudy})).anomaly(area(), TODAY, MODEL.ndvi)
    partial = risk.ndvi_factor(two, None, MODEL)
    assert partial.status == "partial" and partial.availability == pytest.approx(2 / 3, abs=0.001)
    one = NdviClient(FakeStatsProvider({2026: stats_response(0.7), 2025: stats_response(0.75),
                                        2024: cloudy, 2023: cloudy})).anomaly(area(), TODAY, MODEL.ndvi)
    missing = risk.ndvi_factor(one, None, MODEL)
    assert missing.status == "unavailable"
    assert missing.unavailable_reason.startswith("baseline unavailable: 1 of 3 earlier years observed clearly, 2 needed")


def test_no_imagery_provider_is_unavailable_with_the_reason():
    result = risk.ndvi_factor(None, "Copernicus credentials are not configured", MODEL)
    assert result.status == "unavailable" and result.unavailable_reason == "Copernicus credentials are not configured"


def report(severity, pest="rice_blast", days_ago=1):
    return PestReport(id=f"r-{severity}-{days_ago}", area_id="a1", latitude=24.5, longitude=93.99,
                      observed_on=(TODAY - timedelta(days=days_ago)).isoformat(), crop="rice", pest=pest,
                      severity=severity)


SAMPLE_PROVENANCE = Provenance(source="generator", state="SAMPLE", note="synthetic")


def test_report_pressure_weights_severity_and_is_labelled_sample():
    result = risk.report_factor([report("high"), report("moderate", "brown_planthopper"), report("low")],
                                SAMPLE_PROVENANCE, MODEL, TODAY)
    assert result.score == pytest.approx(3.5 / 6, abs=0.001) and result.sample_data
    assert result.reasons[0] == ("3 SAMPLE pest/disease observation(s) in the last 14 days in the area (brown "
                                 "planthopper x1, rice blast x2; 1 high severity). SAMPLE DATA — PROTOTYPE SIMULATION: "
                                 "synthetic, not real field observations.")
    assert result.details["by_severity"] == {"low": 1, "moderate": 1, "high": 1}
    assert result.name == "Pest/disease field observations (SAMPLE)"


def test_report_pressure_saturates_at_full_score():
    assert risk.report_factor([report("high", days_ago=n) for n in range(1, 6)], SAMPLE_PROVENANCE, MODEL,
                              TODAY).score == 1.0


def test_no_sample_reports_is_a_zero_still_labelled_sample():
    result = risk.report_factor([], SAMPLE_PROVENANCE, MODEL, TODAY)
    assert result.score == 0.0 and result.sample_data
    assert "No SAMPLE pest/disease observations" in result.reasons[0] and SAMPLE_LABEL in result.reasons[0]


def test_no_report_source_is_unavailable():
    result = risk.report_factor(None, None, MODEL, TODAY)
    assert result.status == "unavailable" and result.unavailable_reason == "no pest-observation source is connected"


# ----------------------------------------------------------------------------------- ranking

def test_ranking_orders_by_level_then_score_then_name_and_leaves_no_estimate_unranked():
    ranked = risk.rank([assess(0.2, 0.2, 0.2, name="Low area"), assess(0.7, 0.7, 0.7, name="Beta"),
                        assess(None, None, 0.9, name="No data"), assess(0.7, 0.7, 0.7, name="Alpha"),
                        assess(0.9, 0.9, 0.9, name="Critical area")])
    assert [(a.area_name, a.rank, a.rank_of) for a in ranked] == [
        ("Critical area", 1, 4), ("Alpha", 2, 4), ("Beta", 3, 4), ("Low area", 4, 4), ("No data", None, 4)]
