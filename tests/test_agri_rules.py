"""Pest-favourable weather rules, evaluated day by day on hourly data."""

from datetime import timedelta

import pytest

from agri_helpers import TODAY, dry_day, humid_day, pest_rules_dict, weather
from satquery.agri.config import PestRule, load_pest_rules
from satquery.agri.rules import check_day, evaluate


def blast():
    return next(p for p in load_pest_rules().pests if p.id == "rice_blast")


def rule(conditions, **extra) -> PestRule:
    return PestRule.model_validate({"id": "test", "name": "Test pest", "crop": "rice", "status": "PLACEHOLDER",
                                    "conditions": conditions} | extra)


def window_days():
    return [TODAY + timedelta(days=n) for n in range(-7, 3)]  # 7 past days, today and 2 forecast days


def test_a_humid_window_is_fully_favourable_for_blast():
    result = evaluate(blast(), weather({d: humid_day() for d in window_days()}), TODAY)
    assert (result.favourable_past, result.favourable_forecast) == (7, 3)
    assert result.index == 1.0 and result.status == "ok" and result.longest_run == 10
    assert result.days[0].values == {"at least 8 h with relative humidity >= 90%": 12.0,
                                     "daily mean temperature 20-28 °C": 23.0}


def test_dry_days_are_not_favourable_and_say_which_condition_failed():
    result = evaluate(blast(), weather({}), TODAY)
    assert result.index == 0.0 and result.status == "ok"
    assert all(d.favourable is False and d.unmet == ["at least 8 h with relative humidity >= 90%"] for d in result.days)


def test_the_index_counts_favourable_days_over_the_full_score_days():
    days = {TODAY - timedelta(days=1): humid_day(), TODAY - timedelta(days=3): humid_day()}
    result = evaluate(blast(), weather(days), TODAY)  # 2 favourable days of 5 for full pressure
    assert result.index == 0.4 and result.longest_run == 1 and result.favourable_past == 2


def test_the_window_is_past_days_before_today_then_forecast_from_today():
    result = evaluate(blast(), weather({}), TODAY)
    past = [d.date for d in result.days if d.period == "past"]
    forecast = [d.date for d in result.days if d.period == "forecast"]
    assert past == [(TODAY - timedelta(days=n)).isoformat() for n in range(7, 0, -1)]
    assert forecast == [TODAY.isoformat(), (TODAY + timedelta(days=1)).isoformat(),
                        (TODAY + timedelta(days=2)).isoformat()]


def test_a_day_with_too_few_hours_is_unknown_not_unfavourable():
    gappy = humid_day()
    gappy["relative_humidity_2m"] = gappy["relative_humidity_2m"][:12]  # 12 of 24 hours, then missing
    result = evaluate(blast(), weather({TODAY - timedelta(days=2): gappy}), TODAY)
    unknown = next(d for d in result.days if d.date == (TODAY - timedelta(days=2)).isoformat())
    assert unknown.favourable is None and "not enough hourly data (12 of 20" in unknown.unmet[0]
    assert result.status == "partial" and result.known_past == 6
    assert "1 day(s) could not be judged (missing hourly data)" in result.explanation


def test_days_outside_the_weather_data_are_unknown():
    result = evaluate(blast(), weather({}, start=TODAY - timedelta(days=3), count=4), TODAY)
    assert result.known_past == 3 and result.known_forecast == 1 and result.status == "partial"


def test_no_judgeable_day_makes_the_rule_unavailable_not_zero():
    result = evaluate(blast(), weather({}, start=TODAY + timedelta(days=30), count=2), TODAY)
    assert result.status == "unavailable" and result.index is None
    assert "not evaluated" in result.explanation


@pytest.mark.parametrize("condition, day, favourable", [
    ({"variable": "temperature_2m", "aggregate": "min", "at_least": 18, "label": "min >= 18"}, dry_day(temp=20), True),
    ({"variable": "temperature_2m", "aggregate": "max", "at_most": 30, "label": "max <= 30"}, dry_day(temp=31), False),
    ({"variable": "precipitation", "aggregate": "sum", "at_least": 4, "label": "rain >= 4 mm"}, humid_day(), True),
    ({"variable": "relative_humidity_2m", "aggregate": "hours_between", "between": [90, 100], "at_least": 13,
      "label": "13 h at 90-100%"}, humid_day(rh_high_hours=12), False),
    ({"variable": "dew_point_2m", "aggregate": "mean", "between": [15, 22], "label": "dew 15-22"}, humid_day(), True),
])
def test_each_aggregate_and_comparison(condition, day, favourable):
    hours = {name: values for name, values in day.items()}
    assert check_day(rule([condition]), hours, "2026-10-07", "past", 20).favourable is favourable


def test_the_explanation_flags_placeholder_thresholds_and_names_the_conditions():
    result = evaluate(blast(), weather({}), TODAY)
    assert result.explanation.startswith("Rice blast (leaf / neck): favourable conditions on 0 of the last 7 days "
                                         "and 0 of the next 3 forecast days")
    assert "at least 8 h with relative humidity >= 90%" in result.explanation
    assert result.explanation.endswith("[PLACEHOLDER thresholds, not yet verified]")
    assert result.thresholds == "PLACEHOLDER"


def test_a_verified_rule_carries_its_sources_and_no_placeholder_flag():
    data = pest_rules_dict()["pests"][0] | {"status": "VERIFIED", "sources": [
        {"title": "Source", "verified_by": "Agronomist", "verified_on": "2026-10-08"}]}
    result = evaluate(PestRule.model_validate(data), weather({}), TODAY)
    assert "PLACEHOLDER" not in result.explanation and result.sources[0]["verified_by"] == "Agronomist"
