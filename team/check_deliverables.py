"""Check team deliverables before they are integrated (read-only: nothing is changed or merged).

    python team/check_deliverables.py

Thresholds and district boundaries are loaded with the application's own loaders, so a file that
passes here is one the risk engine will accept. Manipuri files are checked against the formats in
team/member-a-agronomy/README.md. Exit code 1 when any ERROR is found.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEAM = ROOT / "team"
sys.path.insert(0, str(ROOT))

from satquery.agent.language import CONCEPTS, INTENTS as ROUTED_INTENTS  # noqa: E402  (after the path is set)

INTENTS = set(ROUTED_INTENTS)  # the intents the application's router answers
SCRIPTS = {"Mtei", "Beng", "Latn"}
TERM_CATEGORIES = {"crop", "pest", "disease", "weather", "crop_health", "inspection", "risk", "place"}
MANIPUR_BOX = (92.8, 23.7, 95.0, 25.8)  # generous lon/lat sanity box around Manipur
EXPECTED_DISTRICTS = 16
PLACEHOLDER_TEXT = re.compile(r"<[^>]*>")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class Report:
    def __init__(self):
        self.lines: list[tuple[str, str]] = []

    def error(self, text):
        self.lines.append(("ERROR", text))

    def warn(self, text):
        self.lines.append(("WARN", text))

    def ok(self, text):
        self.lines.append(("OK", text))

    def info(self, text):
        self.lines.append(("--", text))

    @property
    def errors(self):
        return sum(1 for level, _ in self.lines if level == "ERROR")


def _json(path: Path, report: Report):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        report.error(f"{path.relative_to(ROOT)}: not readable JSON ({error})")
        return None


def _verified_entry(entry: dict, where: str, report: Report, file_status: str) -> None:
    for key in ("verified_by", "verified_on"):
        value = entry.get(key)
        if not value or PLACEHOLDER_TEXT.search(str(value)):
            (report.error if file_status == "VERIFIED" else report.warn)(f"{where}: '{key}' missing")
    if entry.get("verified_on") and not PLACEHOLDER_TEXT.search(str(entry["verified_on"])) \
            and not DATE.match(str(entry["verified_on"])):
        report.error(f"{where}: verified_on must be YYYY-MM-DD")


def check_member_a(report: Report, folder: Path = TEAM / "member-a-agronomy") -> None:
    from satquery.agri.config import load_pest_rules, load_risk_model

    report.info("Member A: Manipuri and agronomy")
    rules = folder / "verified_pest_rules.json"
    if rules.is_file():
        try:
            loaded = load_pest_rules(rules)
            statuses = ", ".join(f"{p.id}={p.status} ({len(p.sources)} source(s))" for p in loaded.pests)
            report.ok(f"verified_pest_rules.json loads with the engine's schema: file {loaded.status}; {statuses}")
            if loaded.status != "VERIFIED":
                report.warn("verified_pest_rules.json is not fully VERIFIED: the dashboard will keep saying PLACEHOLDER")
        except Exception as error:  # the engine's own validation message is the useful part
            report.error(f"verified_pest_rules.json is rejected by the engine's loader: {error}")
    else:
        report.warn("verified_pest_rules.json not delivered yet (most urgent)")
    model = folder / "verified_risk_model.json"
    if model.is_file():
        try:
            report.ok(f"verified_risk_model.json loads: {load_risk_model(model).status}")
        except Exception as error:
            report.error(f"verified_risk_model.json is rejected by the engine's loader: {error}")

    queries = folder / "manipuri_queries.json"
    if queries.is_file():
        data = _json(queries, report)
        if data is not None:
            status = data.get("status")
            if status not in ("DRAFT", "VERIFIED"):
                report.error("manipuri_queries.json: status must be DRAFT or VERIFIED")
            items = data.get("queries") or []
            ids = [q.get("id") for q in items]
            if len(ids) != len(set(ids)):
                report.error("manipuri_queries.json: duplicate ids")
            for q in items:
                where = f"manipuri_queries.json {q.get('id', '?')}"
                for key in ("id", "language", "script", "text", "english_meaning", "intent"):
                    if not q.get(key):
                        report.error(f"{where}: '{key}' missing")
                if q.get("text") and PLACEHOLDER_TEXT.search(q["text"]):
                    report.error(f"{where}: text is still a template placeholder")
                if q.get("script") and q["script"] not in SCRIPTS:
                    report.error(f"{where}: script must be one of {sorted(SCRIPTS)}")
                if q.get("intent") and q["intent"] not in INTENTS:
                    report.error(f"{where}: intent must be one of {sorted(INTENTS)}")
                if q.get("intent") == "AREA_SPECIFIC_RISK" and not q.get("area"):
                    report.error(f"{where}: AREA_SPECIFIC_RISK needs 'area'")
                _verified_entry(q, where, report, status)
            report.ok(f"manipuri_queries.json: {len(items)} quer(ies), status {status}")
    else:
        report.warn("manipuri_queries.json not delivered yet")

    terms = folder / "agri_terms_manipuri.json"
    if terms.is_file():
        data = _json(terms, report)
        if data is not None:
            status = data.get("status")
            items = data.get("terms") or []
            for t in items:
                where = f"agri_terms_manipuri.json {t.get('id', '?')}"
                if t.get("category") not in TERM_CATEGORIES:
                    report.error(f"{where}: category must be one of {sorted(TERM_CATEGORIES)}")
                forms = t.get("manipuri") or []
                if not forms:
                    report.error(f"{where}: no Manipuri form")
                for form in forms:
                    if form.get("script") not in SCRIPTS:
                        report.error(f"{where}: script must be one of {sorted(SCRIPTS)}")
                    if not form.get("text") or PLACEHOLDER_TEXT.search(form["text"]):
                        report.error(f"{where}: Manipuri text missing or still a placeholder")
                if not t.get("source"):
                    report.warn(f"{where}: no source")
                _verified_entry(t, where, report, status)
            report.ok(f"agri_terms_manipuri.json: {len(items)} term(s), status {status}")
            cues = data.get("cue_words") or []
            for c in cues:
                where = f"agri_terms_manipuri.json {c.get('id', '?')}"
                if c.get("concept") not in CONCEPTS:
                    report.error(f"{where}: concept must be one of {sorted(CONCEPTS)}")
                for form in c.get("manipuri") or [{}]:
                    if form.get("script") not in SCRIPTS or not form.get("text") or PLACEHOLDER_TEXT.search(form["text"]):
                        report.error(f"{where}: needs a Manipuri form with a known script and real text")
                _verified_entry(c, where, report, status)
            if cues:
                report.ok(f"agri_terms_manipuri.json: {len(cues)} cue word(s) for the router")
    else:
        report.warn("agri_terms_manipuri.json not delivered yet")
    if not (folder / "SOURCES.md").is_file():
        report.warn("SOURCES.md not delivered yet")


def check_member_b(report: Report, folder: Path = TEAM / "member-b-geo") -> None:
    from satquery import geo
    from satquery.agri.areas import area_km2, load_areas

    report.info("Member B: geography")
    path = folder / "manipur_districts.geojson"
    if not path.is_file():
        report.warn("manipur_districts.geojson not delivered yet")
    else:
        try:
            areas = load_areas(path)
        except Exception as error:
            report.error(f"manipur_districts.geojson is rejected by the engine's area loader: {error}")
            areas = []
        if areas:
            names = [a.name.strip().lower() for a in areas]
            if len(names) != len(set(names)):
                report.error("manipur_districts.geojson: duplicate district names")
            for a in areas:
                if a.kind != "district":
                    report.error(f"{a.id}: kind must be 'district' for an official boundary")
                if not a.state or a.state.strip().lower() != "manipur":
                    report.warn(f"{a.id}: state is not 'Manipur'")
                west, south, east, north = geo.geometry_bounds(a.geometry)
                bw, bs, be, bn = MANIPUR_BOX
                if west < bw or south < bs or east > be or north > bn:
                    report.error(f"{a.id}: bounds {west:.3f},{south:.3f},{east:.3f},{north:.3f} fall outside "
                                 "Manipur: check the CRS is WGS84 longitude/latitude")
                if area_km2(a.geometry) <= 0:
                    report.error(f"{a.id}: zero area")
            total = sum(area_km2(a.geometry) for a in areas)
            report.ok(f"manipur_districts.geojson: {len(areas)} district(s), about {total:,.0f} km2 in total")
            if len(areas) != EXPECTED_DISTRICTS:
                report.warn(f"{len(areas)} districts, {EXPECTED_DISTRICTS} expected for the current structure: "
                            "disclose an older structure in SOURCES.md")
    for name in ("SOURCES.md", "geo_validation.md"):
        if not (folder / name).is_file():
            report.warn(f"{name} not delivered yet")


def check_presence(report: Report, title: str, folder: Path, files: list[str]) -> None:
    report.info(title)
    for name in files:
        (report.ok if (folder / name).exists() else report.warn)(
            f"{name} {'present' if (folder / name).exists() else 'not delivered yet'}")


def run() -> Report:
    report = Report()
    check_member_a(report)
    check_member_b(report)
    check_presence(report, "Member C: UI/UX and QA", TEAM / "member-c-qa",
                   ["UI_REVIEW.md", "QA_REPORT.md", "TEST_MATRIX.md"])
    check_presence(report, "Member D: pitch and demo", TEAM / "member-d-pitch",
                   ["AG04_Pitch.pptx", "DEMO_SCRIPT.md", "JUDGE_QA.md"])
    return report


if __name__ == "__main__":
    result = run()
    for level, text in result.lines:
        print(f"{level:5} {text}" if level != "--" else f"\n== {text}")
    print(f"\n{result.errors} error(s)")
    sys.exit(1 if result.errors else 0)
