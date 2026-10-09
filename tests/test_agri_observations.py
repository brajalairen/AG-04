"""Pest and disease observations: parsing, honesty checks, area matching, ETL reading, coverage, quality.

Every REAL record here is a unit-test fixture written for these tests, not a real observation.
"""

import json
from datetime import timedelta

import pytest
from pydantic import ValidationError

from agri_helpers import TODAY, area, rect
from satquery.agri import __main__ as cli
from satquery.agri.config import ObservationRulesConfig, load_observation_rules, load_risk_model
from satquery.agri.models import SAMPLE_LABEL, PestObservation
from satquery.agri.observations import (ObservationDataset, ObservationFileError, ObservationFileSource,
                                        ObservationSet, area_observations, load_observations, quality_report,
                                        resolve_severity)
from satquery.agri.risk import observation_factor

RULES = load_observation_rules()
MODEL = load_risk_model()
KAKCHING = area("z1", "Kakching zone", district="Kakching")  # rect 93.95-94.03 E, 24.45-24.52 N
INSIDE = {"latitude": 24.48, "longitude": 93.99}
DATASET = {"id": "test-ds", "title": "Unit-test surveillance fixture", "publisher": "Test publisher",
           "source_url": "https://example.org/test-dataset", "licence": "test only", "access_date": "2026-10-08",
           "status": "REAL", "geographic_coverage": "test", "temporal_coverage": "2026", "spatial_resolution": "point",
           "observation_method": "weekly scout survey (test fixture)", "limitations": "test fixture, not real data",
           "coverage_districts": ["Kakching"], "pests_surveyed": None}


def record(n=1, days_ago=2, **fields):
    return {"id": f"obs-{n}", "status": "REAL", "observed_on": (TODAY - timedelta(days=days_ago)).isoformat(),
            "crop": "rice", "pest": "brown_planthopper", "district": "Kakching"} | INSIDE | fields


def write(tmp_path, records, **meta):
    path = tmp_path / "observations.json"
    path.write_text(json.dumps({"dataset": DATASET | meta, "observations": records}), encoding="utf-8")
    return path


def obs_set(records, **meta):
    observations = [PestObservation.model_validate(
        {"source": "Test publisher: Unit-test surveillance fixture", "source_url": DATASET["source_url"]} | r)
        for r in records]
    return ObservationSet(dataset=ObservationDataset.model_validate(DATASET | meta), observations=observations)


# ------------------------------------------------------------------------------------ parsing

def test_a_pest_observation_is_parsed_with_its_provenance_inherited_from_the_dataset(tmp_path):
    path = write(tmp_path, [record(metric="hoppers_per_hill", value=12, unit="hoppers/hill", crop_stage="tillering")])
    loaded = load_observations(path)
    observation = loaded.observations[0]
    assert observation.status == "REAL" and observation.synthetic is False and observation.label is None
    assert observation.source == "Test publisher: Unit-test surveillance fixture"
    assert observation.source_url == "https://example.org/test-dataset" and observation.source_date == "2026-10-08"
    assert observation.observation_type == "field_survey" and observation.value == 12.0


def test_a_disease_observation_is_parsed_and_read_against_its_etl(tmp_path):
    path = write(tmp_path, [record(1, pest="rice_blast", metric="lesions_per_leaf", value=4, unit="lesions/leaf",
                                   crop_stage="tillering"),
                            record(2, pest="rice_blast", metric="neck_infected_plants_per_m2", value=6,
                                   unit="plants/m2", crop_stage="panicle_initiation_to_booting")])
    leaf, neck = load_observations(path).observations
    assert resolve_severity(leaf, RULES)[0] == "moderate", "4 lesions/leaf is within the 3-5 ETL"
    severity, basis = resolve_severity(neck, RULES)
    assert severity == "high" and "at or above the ETL neck blast 2-5" in basis and "PLACEHOLDER ETL" in basis


@pytest.mark.parametrize("value, stage, expected", [
    (5, "tillering", "low"), (10, "tillering", "moderate"), (15, "tillering", "high"),
    (15, "panicle_initiation_to_booting", "moderate"), (25, "panicle_initiation_to_booting", "high")])
def test_planthopper_counts_follow_the_stage_specific_etl(value, stage, expected):
    observation = PestObservation.model_validate(record(metric="hoppers_per_hill", value=value, unit="hoppers/hill",
                                                        crop_stage=stage, source="test", source_date="2026-10-08"))
    assert resolve_severity(observation, RULES)[0] == expected


def test_a_value_is_not_read_when_the_etl_depends_on_a_stage_the_record_lacks():
    observation = PestObservation.model_validate(record(metric="hoppers_per_hill", value=12, unit="hoppers/hill",
                                                        source="test", source_date="2026-10-08"))
    severity, basis = resolve_severity(observation, RULES)
    assert severity is None and "depends on the crop stage" in basis


def test_a_source_severity_is_used_as_given_and_unknown_measures_are_not_guessed():
    given = PestObservation.model_validate(record(severity="high", source="test", source_date="2026-10-08"))
    assert resolve_severity(given, RULES) == ("high", "severity recorded by the source")
    prevalence = PestObservation.model_validate(record(prevalence_pct=30, source="test", source_date="2026-10-08"))
    assert resolve_severity(prevalence, RULES)[0] is None
    unknown = PestObservation.model_validate(record(pest="rice_hispa", metric="adults_per_hill", value=3,
                                                    source="test", source_date="2026-10-08"))
    assert resolve_severity(unknown, RULES) == (None, "no ETL is configured for rice hispa")


def test_a_csv_dataset_needs_its_metadata_sidecar(tmp_path):
    path = tmp_path / "obs.csv"
    path.write_text("id,status,observed_on,crop,pest,district,spatial_resolution,severity\n"
                    f"c1,REAL,{(TODAY - timedelta(days=1)).isoformat()},rice,rice_blast,Kakching,district,high\n",
                    encoding="utf-8")
    with pytest.raises(ObservationFileError, match="obs.dataset.json"):
        load_observations(path)
    (tmp_path / "obs.dataset.json").write_text(json.dumps({"dataset": DATASET | {"spatial_resolution": "district"}}),
                                               encoding="utf-8")
    observation = load_observations(path).observations[0]
    assert observation.spatial_resolution == "district" and observation.latitude is None
    assert observation.severity == "high" and observation.status == "REAL"


# --------------------------------------------------------------------------- honesty checks

@pytest.mark.parametrize("change, message", [
    ({"status": "SAMPLE"}, "never mixed"),
    ({"spatial_resolution": "district"}, "must not carry coordinates"),
    ({"metric": "hoppers_per_hill"}, "value and metric must be given together"),
    ({"severity": None, "latitude": None, "longitude": None}, "records no severity"),
    ({"observed_on": "08/10/2026", "severity": "low"}, "ISO date"),
])
def test_a_dishonest_or_incomplete_record_refuses_the_whole_file(tmp_path, change, message):
    good = record(1, severity="low")
    bad = record(2, severity="low") | change
    with pytest.raises(ObservationFileError, match=message):
        load_observations(write(tmp_path, [good, bad]))


def test_a_record_without_a_status_takes_the_datasets(tmp_path):
    bare = record(severity="high")
    del bare["status"]
    observation = load_observations(write(tmp_path, [bare])).observations[0]
    assert observation.status == "REAL" and observation.synthetic is False and observation.label is None


def test_an_etl_reading_is_placeholder_until_the_etl_is_verified():
    from agri_helpers import VERIFIED_SOURCE, verified_model

    data = json.loads(json.dumps(RULES.model_dump()))
    data["severity_from_etl"]["status"] = "VERIFIED"
    for rule in data["pests"]:
        rule["status"], rule["sources"] = "VERIFIED", [VERIFIED_SOURCE]
    verified = ObservationRulesConfig.model_validate(data)
    counted = [record(metric="hoppers_per_hill", value=18, unit="hoppers/hill", crop_stage="tillering")]
    for rules, expected in ((RULES, "PLACEHOLDER"), (verified, "VERIFIED")):
        factor = observation_factor("brown_planthopper", area_observations(obs_set(counted), KAKCHING, TODAY, 14,
                                                                           rules), verified_model())
        assert factor.details["by_severity"]["high"] == 1 and factor.thresholds == expected


def test_duplicate_ids_are_refused(tmp_path):
    with pytest.raises(ObservationFileError, match="duplicate id"):
        load_observations(write(tmp_path, [record(1, severity="low"), record(1, severity="high")]))


def test_a_real_record_must_name_a_real_source_and_is_never_synthetic():
    with pytest.raises(ValidationError, match="must name its source"):
        PestObservation.model_validate(record(severity="low", source="SAMPLE", source_date="2026-10-08"))
    with pytest.raises(ValidationError, match="must name its source"):
        PestObservation.model_validate(record(severity="low", source="Dept"))
    with pytest.raises(ValidationError, match="cannot be synthetic"):
        PestObservation.model_validate(record(severity="low", source="Dept", source_date="2026-10-08",
                                              synthetic=True))


def test_a_sample_record_must_carry_the_sample_label():
    assert PestObservation(id="s", observed_on="2026-10-07", crop="rice", pest="rice_blast", severity="low",
                           latitude=24.5, longitude=93.9).label == SAMPLE_LABEL == "SAMPLE DATA — PROTOTYPE SIMULATION"
    with pytest.raises(ValidationError, match="labelled"):
        PestObservation(id="s", observed_on="2026-10-07", crop="rice", pest="rice_blast", severity="low",
                        latitude=24.5, longitude=93.9, label="looks real")


def test_no_coordinates_are_invented_for_area_level_records():
    with pytest.raises(ValidationError, match="needs its district"):
        PestObservation.model_validate({"id": "d", "status": "REAL", "observed_on": "2026-10-07", "crop": "rice",
                                        "pest": "rice_blast", "severity": "low", "spatial_resolution": "district",
                                        "source": "Dept", "source_date": "2026-10-08"})


# ------------------------------------------------------------------------- area matching

def test_located_records_match_inside_and_district_records_match_their_district():
    records = [record(1, severity="high"),                                           # inside the zone
               record(2, severity="high", latitude=24.60, longitude=93.99),         # same district, outside the zone
               record(3, severity="moderate", latitude=None, longitude=None, spatial_resolution="district"),
               record(4, severity="high", latitude=None, longitude=None, spatial_resolution="district",
                      district="Thoubal")]
    found = area_observations(obs_set(records), KAKCHING, TODAY, 14, RULES)
    assert [(i.observation.id, i.match) for i in found.items] == [("obs-1", "inside_area"), ("obs-3", "same_district")]


def test_old_records_are_historical_and_future_ones_are_ignored():
    records = [record(1, severity="high", days_ago=40), record(2, severity="high", days_ago=2),
               record(3, severity="high", days_ago=-3)]
    found = area_observations(obs_set(records), KAKCHING, TODAY, 14, RULES)
    assert [i.observation.id for i in found.items] == ["obs-2"]
    assert found.historical_count == 1 and found.latest_historical == (TODAY - timedelta(days=40)).isoformat()
    assert "HISTORICAL and not used as current evidence" in found.notes[0]
    assert [o.id for o in found.historical_for("brown_planthopper")] == ["obs-1"]


def test_a_district_level_record_counts_for_less_than_one_inside_the_zone():
    inside = observation_factor("brown_planthopper", area_observations(obs_set([record(severity="high")]), KAKCHING,
                                                                       TODAY, 14, RULES), MODEL)
    district = observation_factor("brown_planthopper", area_observations(obs_set(
        [record(severity="high", latitude=None, longitude=None, spatial_resolution="district")]), KAKCHING, TODAY,
        14, RULES), MODEL)
    assert inside.details["weighted"] == 2.0 and district.details["weighted"] == 1.0
    assert any("district-level records" in r for r in district.reasons)


# ----------------------------------------------------------------------- coverage and evidence

def test_no_records_where_coverage_is_unknown_is_unavailable_not_zero():
    found = area_observations(obs_set([], coverage_districts=None), KAKCHING, TODAY, 14, RULES)
    factor = observation_factor("brown_planthopper", found, MODEL)
    assert factor.status == "unavailable" and factor.score is None
    assert "no records is not evidence of no pests" in factor.unavailable_reason


def test_no_records_in_a_surveyed_district_is_zero_evidence():
    factor = observation_factor("brown_planthopper", area_observations(obs_set([]), KAKCHING, TODAY, 14, RULES), MODEL)
    assert factor.status == "ok" and factor.score == 0.0 and not factor.sample_data
    assert factor.reasons[0].startswith("No REAL brown planthopper observations in the last 14 days")


def test_an_unsurveyed_district_or_pest_is_unavailable():
    elsewhere = area("z2", "Jiribam zone", district="Jiribam", geometry=rect(93.08, 24.77, 93.16, 24.84))
    factor = observation_factor("rice_blast", area_observations(obs_set([]), elsewhere, TODAY, 14, RULES), MODEL)
    assert factor.status == "unavailable" and "does not survey Jiribam" in factor.unavailable_reason
    found = area_observations(obs_set([], pests_surveyed=["brown_planthopper"]), KAKCHING, TODAY, 14, RULES)
    assert observation_factor("rice_blast", found, MODEL).unavailable_reason == \
        "the observation source does not survey rice blast"


def test_unreadable_records_are_listed_but_add_nothing():
    found = area_observations(obs_set([record(metric="hoppers_per_hill", value=40, unit="hoppers/hill")]), KAKCHING,
                              TODAY, 14, RULES)
    factor = observation_factor("brown_planthopper", found, MODEL)
    assert factor.score == 0.0 and factor.details["count"] == 1
    assert any("no severity the engine can read" in r for r in factor.reasons)
    assert factor.details["reports"][0]["severity"] is None and factor.details["reports"][0]["status"] == "REAL"


def test_real_observations_carry_their_dataset_provenance():
    found = area_observations(obs_set([record(severity="high")]), KAKCHING, TODAY, 14, RULES)
    factor = observation_factor("brown_planthopper", found, MODEL)
    provenance = factor.provenance[0]
    assert provenance.source == "Test publisher: Unit-test surveillance fixture" and provenance.state == "CACHED"
    assert provenance.retrieved_at == "2026-10-08" and provenance.licence == "test only"
    assert "REAL pest/disease observations" in provenance.note and "test fixture, not real data" in provenance.note
    assert factor.name == "Pest/disease field observations" and not factor.sample_data


def test_the_file_source_serves_the_loaded_dataset(tmp_path):
    source = ObservationFileSource.from_file(write(tmp_path, [record(severity="moderate")]))
    found = source.observations(KAKCHING, TODAY, 14, RULES)
    assert len(found.items) == 1 and found.coverage == "covered" and not found.sample


# ------------------------------------------------------------------------------ data quality

def test_the_quality_report_flags_historical_coarse_and_unstated_coverage(tmp_path):
    records = [record(1, severity="high", days_ago=60),
               record(2, severity="low", days_ago=50, latitude=None, longitude=None, spatial_resolution="district")]
    report = quality_report(load_observations(write(tmp_path, records, coverage_districts=None)), TODAY, 14, RULES)
    assert report["records"] == 2 and report["current_records"] == 0 and report["days_since_last"] == 50
    assert report["spatial_resolution"] == {"point": 1, "district": 1}
    assert report["missing"]["latitude"] == 1 and report["missing"]["crop_stage"] == 2
    warnings = " ".join(report["warnings"])
    assert "historical" in warnings and "district- or block-level" in warnings and "not stated" in warnings


def test_the_command_line_checks_a_dataset(tmp_path, capsys):
    assert cli.main(["observations", str(write(tmp_path, [record(severity="high", days_ago=60)]))]) == 0
    out = capsys.readouterr().out
    assert "Unit-test surveillance fixture (Test publisher), REAL" in out and "WARNING: No record in the last" in out
    assert cli.main(["observations", str(write(tmp_path, [record(severity="high", status="SAMPLE")]))]) == 1
    assert "REJECTED" in capsys.readouterr().out


# ------------------------------------------------------------------------ observation rules

def test_observation_rules_cite_their_source_and_stay_placeholder_until_verified():
    assert RULES.status == "PLACEHOLDER" and RULES.severity_from_etl.status == "PLACEHOLDER"
    for rule in RULES.pests:
        assert rule.status == "PLACEHOLDER" and rule.etl, rule.id
        assert all(s.url == "https://niphm.gov.in/IPMPackages/Rice.pdf" and s.verified_by is None for s in rule.sources)
        assert "Manipur" in rule.applicability
    assert {r.id for r in RULES.pests} >= {"brown_planthopper", "rice_blast", "yellow_stem_borer"}


def test_a_verified_observation_rule_must_name_its_verifier():
    data = json.loads(json.dumps(RULES.model_dump()))
    data["pests"][0]["status"] = "VERIFIED"
    with pytest.raises(ValidationError, match="has no verified_by/verified_on"):
        ObservationRulesConfig.model_validate(data)
