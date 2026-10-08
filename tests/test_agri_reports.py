"""SAMPLE pest reports: synthetic, deterministic, and labelled so they can never pass as real data."""

from datetime import date, timedelta

import pytest

from agri_helpers import TODAY, area, rect
from satquery.agri.areas import contains
from satquery.agri.models import SAMPLE_LABEL
from satquery.agri.reports import SampleReportSource, generate, in_area, load_scenario


def scenario(**changes):
    return load_scenario() | changes


def test_every_report_and_the_set_are_labelled_sample():
    report_set = generate([area("demo-bishnupur-nambol")], TODAY)
    assert report_set.reports, "the 'high' scenario area has reports"
    for report in report_set.reports:
        assert report.source == "SAMPLE" and report.synthetic is True and report.verified is False
        assert report.label == SAMPLE_LABEL == "SAMPLE DATA — Prototype Simulation"
        assert report.id.startswith("sample-")
    assert report_set.label == SAMPLE_LABEL and report_set.provenance.state == "SAMPLE"
    assert "not real government or field observations" in report_set.provenance.note


def test_generation_is_deterministic_and_moves_with_the_end_date():
    areas = [area("demo-bishnupur-nambol"), area("other")]
    assert generate(areas, TODAY) == generate(areas, TODAY)
    assert generate(areas, TODAY).reports != generate(areas, TODAY + timedelta(days=1)).reports


def test_reports_lie_inside_their_area_and_window():
    shape = area("demo-bishnupur-nambol", geometry=rect(93.76, 24.63, 93.84, 24.70))
    for report in generate([shape], TODAY).reports:
        assert contains(shape.geometry, report.longitude, report.latitude)
        assert TODAY - timedelta(days=20) <= date.fromisoformat(report.observed_on) <= TODAY


@pytest.mark.parametrize("pressure, low, high", [("background", 0, 2), ("elevated", 3, 6), ("high", 6, 10)])
def test_counts_follow_the_scenario_pressure(pressure, low, high):
    custom = scenario(area_pressure={"x": pressure})
    for n in range(10):
        count = len(generate([area("x")], TODAY + timedelta(days=n), custom).reports)
        assert low <= count <= high


def test_the_lookback_filter_keeps_only_recent_reports_inside_the_area():
    shape = area("demo-bishnupur-nambol")
    report_set = generate([shape], TODAY)
    recent = in_area(report_set, shape, TODAY, 7)
    assert all(r.observed_on >= (TODAY - timedelta(days=6)).isoformat() for r in recent)
    assert in_area(report_set, area("far", geometry=rect(10, 10, 10.1, 10.1)), TODAY, 14) == []


def test_the_source_returns_sample_provenance_with_the_reports():
    reports, provenance = SampleReportSource().for_area(area("demo-bishnupur-nambol"), TODAY, 14)
    assert provenance.state == "SAMPLE" and all(r.source == "SAMPLE" for r in reports)


def test_a_scenario_must_declare_itself_sample(tmp_path):
    path = tmp_path / "scenario.json"
    path.write_text('{"status": "REAL"}', encoding="utf-8")
    with pytest.raises(ValueError, match="SAMPLE"):
        load_scenario(path)
