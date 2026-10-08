"""The team deliverable checker: it must accept good files and catch unverified or invented content."""

import importlib.util
import json
from pathlib import Path

from agri_helpers import VERIFIED_SOURCE, pest_rules_dict, rect

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("check_deliverables", ROOT / "team" / "check_deliverables.py")
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


def run_a(folder):
    report = checker.Report()
    checker.check_member_a(report, folder)
    return report


def run_b(folder):
    report = checker.Report()
    checker.check_member_b(report, folder)
    return report


def messages(report, level):
    return [text for lvl, text in report.lines if lvl == level]


def write(folder, name, data):
    (folder / name).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def query(**changes):
    return {"id": "mni-001", "language": "mni", "script": "Latn", "text": "a verified sentence",
            "english_meaning": "Which areas are at high risk?", "intent": "AREA_RISK_QUERY", "area": None,
            "verified_by": "Speaker", "verified_on": "2026-10-08"} | changes


def test_nothing_delivered_is_warnings_not_errors(tmp_path):
    a, b = run_a(tmp_path), run_b(tmp_path)
    assert a.errors == 0 and b.errors == 0
    assert any("most urgent" in w for w in messages(a, "WARN"))


def test_the_shipped_templates_pass_only_as_templates(tmp_path):
    folder = ROOT / "team" / "member-a-agronomy"
    data = json.loads((folder / "manipuri_queries.template.json").read_text(encoding="utf-8"))
    write(tmp_path, "manipuri_queries.json", data)
    assert any("still a template placeholder" in e for e in messages(run_a(tmp_path), "ERROR"))


def test_thresholds_go_through_the_engines_own_loader(tmp_path):
    write(tmp_path, "verified_pest_rules.json", pest_rules_dict())
    report = run_a(tmp_path)
    assert report.errors == 0 and any("not fully VERIFIED" in w for w in messages(report, "WARN"))

    claimed = pest_rules_dict()
    claimed["pests"][0] |= {"status": "VERIFIED", "sources": [{"title": "A paper"}]}
    write(tmp_path, "verified_pest_rules.json", claimed)
    assert any("rejected by the engine's loader" in e for e in messages(run_a(tmp_path), "ERROR"))

    verified = pest_rules_dict()
    verified["status"] = "VERIFIED"
    for pest in verified["pests"]:
        pest |= {"status": "VERIFIED", "sources": [VERIFIED_SOURCE]}
    write(tmp_path, "verified_pest_rules.json", verified)
    assert run_a(tmp_path).errors == 0


def test_queries_need_known_intents_scripts_and_verification(tmp_path):
    write(tmp_path, "manipuri_queries.json", {"status": "VERIFIED", "queries": [query()]})
    assert run_a(tmp_path).errors == 0
    bad = [query(id="q1", intent="SOMETHING"), query(id="q2", script="Deva"),
           query(id="q3", intent="AREA_SPECIFIC_RISK"), query(id="q4", verified_by=None)]
    write(tmp_path, "manipuri_queries.json", {"status": "VERIFIED", "queries": bad})
    errors = " ".join(messages(run_a(tmp_path), "ERROR"))
    assert "q1: intent" in errors and "q2: script" in errors and "q3: AREA_SPECIFIC_RISK needs 'area'" in errors
    assert "q4: 'verified_by' missing" in errors


def district(name, geometry=None, **props):
    return {"type": "Feature", "geometry": geometry or rect(93.8, 24.6, 93.9, 24.7),
            "properties": {"id": f"mn-{name.lower()}", "name": name, "kind": "district", "district": name,
                           "state": "Manipur", "boundary_source": "Test dataset v1"} | props}


def test_districts_load_with_the_engines_area_loader_and_sanity_checks(tmp_path):
    write(tmp_path, "manipur_districts.geojson", {"type": "FeatureCollection", "features": [district("Bishnupur")]})
    report = run_b(tmp_path)
    assert report.errors == 0 and any("16 expected" in w for w in messages(report, "WARN"))

    outside = district("Faraway", geometry=rect(10, 10, 10.1, 10.1))
    demo = district("Demo", kind="demo")
    twin = district("Bishnupur", id="mn-twin")
    write(tmp_path, "manipur_districts.geojson",
          {"type": "FeatureCollection", "features": [district("Bishnupur"), outside, demo, twin]})
    errors = " ".join(messages(run_b(tmp_path), "ERROR"))
    assert "fall outside Manipur" in errors and "kind must be 'district'" in errors and "duplicate district" in errors


def test_a_boundary_file_without_a_named_source_is_refused(tmp_path):
    write(tmp_path, "manipur_districts.geojson",
          {"type": "FeatureCollection", "features": [district("Bishnupur", boundary_source="")]})
    assert any("rejected by the engine's area loader" in e for e in messages(run_b(tmp_path), "ERROR"))
