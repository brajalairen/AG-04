"""Thresholds and weights are data, PLACEHOLDER until verified, and cannot claim VERIFIED without sources."""

import json

import pytest
from pydantic import ValidationError

from agri_helpers import VERIFIED_SOURCE, pest_rules_dict, risk_model_dict, verified_model, verified_rules
from satquery.agri.config import (PestRulesConfig, RiskModelConfig, load_pest_rules, load_risk_model,
                                  thresholds_status)


def test_the_shipped_thresholds_are_placeholders_with_no_claimed_source():
    rules, model = load_pest_rules(), load_risk_model()
    assert rules.status == "PLACEHOLDER" and model.status == "PLACEHOLDER"
    assert all(p.status == "PLACEHOLDER" and p.sources == [] for p in rules.pests)
    assert "NOT taken from a verified agronomic source" in rules.note
    assert thresholds_status(rules, model) == "PLACEHOLDER"
    assert {p.id for p in rules.pests} == {"rice_blast", "brown_planthopper"}


def test_verified_needs_every_part_verified():
    assert thresholds_status(verified_rules(), verified_model()) == "VERIFIED"
    assert thresholds_status(verified_rules(), load_risk_model()) == "PLACEHOLDER"
    assert thresholds_status(load_pest_rules(), verified_model()) == "PLACEHOLDER"


@pytest.mark.parametrize("sources", [[], [{"title": "A paper"}], [{"title": "A paper", "verified_by": "X"}]])
def test_a_pest_rule_cannot_be_verified_without_a_verified_source(sources):
    data = pest_rules_dict()
    data["pests"][0] |= {"status": "VERIFIED", "sources": sources}
    with pytest.raises(ValidationError, match="VERIFIED"):
        PestRulesConfig.model_validate(data)


def test_a_file_cannot_be_verified_while_a_pest_is_still_a_placeholder():
    data = pest_rules_dict()
    data["status"] = "VERIFIED"
    data["pests"][0] |= {"status": "VERIFIED", "sources": [VERIFIED_SOURCE]}
    with pytest.raises(ValidationError, match="still PLACEHOLDER"):
        PestRulesConfig.model_validate(data)


@pytest.mark.parametrize("condition, message", [
    ({"variable": "relative_humidity_2m", "aggregate": "hours_at_or_above", "at_least": 8, "label": "x"}, "threshold"),
    ({"variable": "temperature_2m", "aggregate": "mean", "label": "x"}, "between, at_least or at_most"),
    ({"variable": "temperature_2m", "aggregate": "mean", "between": [28, 20], "label": "x"}, r"\[low, high\]"),
    ({"variable": "temperature_2m", "aggregate": "median", "between": [20, 28], "label": "x"}, "aggregate"),
    ({"variable": "leaf_wetness", "aggregate": "mean", "at_least": 1, "label": "x"}, "variable"),
    ({"variable": "temperature_2m", "aggregate": "mean", "at_least": 1, "label": "x", "unit": "C"}, "unit"),
])
def test_malformed_conditions_are_refused(condition, message):
    data = pest_rules_dict()
    data["pests"][0]["conditions"] = [condition]
    with pytest.raises(ValidationError, match=message):
        PestRulesConfig.model_validate(data)


def test_duplicate_pest_ids_are_refused():
    data = pest_rules_dict()
    data["pests"].append(data["pests"][0])
    with pytest.raises(ValidationError, match="unique"):
        PestRulesConfig.model_validate(data)


@pytest.mark.parametrize("change, message", [
    ({"levels": {"critical": 0.5, "high": 0.6, "moderate": 0.35}}, "moderate < high < critical"),
    ({"weights": {"weather_pest": 0.5, "ndvi_anomaly": 0.5}}, "weights must name"),
    ({"weights": {"weather_pest": 0, "ndvi_anomaly": 0, "report_pressure": 0}}, "not all zero"),
    ({"status": "VERIFIED"}, "names no source"),
])
def test_an_invalid_risk_model_is_refused(change, message):
    with pytest.raises(ValidationError, match=message):
        RiskModelConfig.model_validate(risk_model_dict() | change)


def test_ndvi_settings_must_be_consistent():
    data = risk_model_dict()
    data["ndvi"] |= {"min_baseline_years": 4, "baseline_years": 3}
    with pytest.raises(ValidationError, match="min_baseline_years"):
        RiskModelConfig.model_validate(data)


def test_reviewed_files_replace_the_placeholders_without_code_changes(tmp_path, monkeypatch):
    rules_file, model_file = tmp_path / "rules.json", tmp_path / "model.json"
    rules_file.write_text(verified_rules().model_dump_json(), encoding="utf-8")
    model_file.write_text(json.dumps(verified_model().model_dump()), encoding="utf-8")
    monkeypatch.setenv("SATQUERY_AGRI_PEST_RULES", str(rules_file))
    monkeypatch.setenv("SATQUERY_AGRI_RISK_MODEL", str(model_file))
    assert thresholds_status(load_pest_rules(), load_risk_model()) == "VERIFIED"
