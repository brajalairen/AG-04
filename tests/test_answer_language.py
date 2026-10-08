"""A Latin Manipuri question gets a Latin Manipuri answer; an English question keeps its English answer.

The engine stays the source of truth: every level, score, confidence value, reason (evidence) and warning in
the Latin Manipuri answer is the engine's own, inserted unchanged. Latin Manipuri sentences come only from
Member_A/manipuri_responses.json; a message without a usable template stays in English.
"""

import json
import re

import pytest

from satquery.agent.language import LATIN_MANIPURI, normalize
from satquery.agri import answer_language as mni
from satquery.agri.areas import demo_areas
from satquery.agri.pipeline import assess_areas
from satquery.agri import query as agri_query
from test_agri_api import FORBIDDEN, client_for, sources
from test_crop_health import S2, ask as ask_crop_health

TEMPLATES = json.loads(mni.DEFAULT_RESPONSES.read_text(encoding="utf-8"))["templates"]
SELECTED = "demo-thoubal-chaobok"
HIGH_RISK = "Kanagumba area high risk da lei?"           # the three questions of the task request
PEST_RISK = "Area asi da pest risk yamna lei-i?"
CROP_CONDITION = "Eigi field da crop condition kayano?"


@pytest.fixture
def client(tmp_path, monkeypatch):
    return client_for(tmp_path, monkeypatch)[0]


@pytest.fixture(scope="module")
def engine():
    return {a.area_id: a for a in assess_areas(demo_areas(), sources())}


def ask(client, query, **extra):
    return client.post("/api/agri/query", json={"query": query} | extra).json()


def template(key, **slots):
    return TEMPLATES[key]["text"].format(**slots)


# ---------------------------------------------------------------------------- 1. intent

@pytest.mark.parametrize("query, intent", [(HIGH_RISK, "AREA_RISK_QUERY"), (PEST_RISK, "PEST_RISK"),
                                           (CROP_CONDITION, "CROP_HEALTH")])
def test_1_latin_manipuri_questions_get_their_intent(query, intent):
    assert normalize(query).as_dict() == {"language": LATIN_MANIPURI, "intent": intent, "entities": {}}


# ---------------------------------------------------------------------------- 2-7. risk engine -> answer

def test_2_high_risk_flow_risk_engine_to_a_latin_manipuri_answer(client, engine):
    found = ask(client, HIGH_RISK)
    assert (found["intent"], found["language"], found["common_intent"]) == ("rank", LATIN_MANIPURI, "AREA_RISK_QUERY")
    severe = [a for a in engine.values() if a.level in ("HIGH", "CRITICAL")]
    assert severe, "the fixture has high-risk areas"
    for a in severe:  # 4, 5: each area's level, score and confidence, as the engine gives them
        assert f"#{a.rank} {a.area_name}: " + template("area_risk", level=a.level) in found["answer"]
        assert template("score", score=f"{a.score:.0f}/100") in found["answer"]
        assert template("confidence", confidence=a.confidence.level) in found["answer"]
    assert template("verify_advice") in found["answer"]


def test_pest_risk_flow_explains_the_selected_area_in_latin_manipuri(client, engine):
    found = ask(client, PEST_RISK, selected_area_id=SELECTED)
    assert (found["intent"], found["common_intent"], found["focus_area_id"]) == ("explain", "PEST_RISK", SELECTED)
    a = engine[SELECTED]
    answer = found["answer"]
    assert template("area_pest_risk", level=a.level) in answer                       # level
    assert template("score", score=f"{a.score:.0f}/100") in answer                    # 4. score
    assert template("confidence", confidence=a.confidence.level) in answer            # 5. confidence
    for reason in a.reasons[:5]:                                                       # 6. evidence, verbatim
        assert f"- {reason}" in answer


def test_7_placeholder_and_sample_warnings_are_kept(client):
    for query, extra in ((HIGH_RISK, {}), (PEST_RISK, {"selected_area_id": SELECTED}),
                         ("ei kadāidagi hougadage?", {})):
        answer = ask(client, query, **extra)["answer"]
        assert "PLACEHOLDER" in answer and "SAMPLE DATA — Prototype Simulation" in answer, query
        assert mni.say("caveat_decision", LATIN_MANIPURI) in answer


def test_8_no_unsupported_claims(client):
    for query, extra in ((HIGH_RISK, {}), (PEST_RISK, {"selected_area_id": SELECTED}),
                         ("ei kadāidagi hougadage?", {}), ("masi karamna khudongthiningngāi oibano?", {})):
        assert not FORBIDDEN.search(ask(client, query, **extra)["answer"]), query
    for key, entry in TEMPLATES.items():  # what the data file says
        assert not entry["text"] or not mni.UNSUPPORTED.search(entry["text"]), key


def test_a_template_that_drops_a_value_or_a_warning_or_claims_too_much_is_refused():
    assert mni.usable("score", "Risk score asi {score} ni.")
    assert not mni.usable("score", "Risk score asi yāmna wāngba ni.")             # the {score} slot is gone
    assert not mni.usable("caveat_placeholder", "Thresholds asi verify toudri.")    # PLACEHOLDER is gone
    assert not mni.usable("area_risk", "Rice blast confirm oirammi {level}.")      # a diagnosis the engine never makes


def test_an_unwritten_template_falls_back_to_the_english_message():
    missing = next(key for key, entry in TEMPLATES.items() if not entry["text"])
    assert mni.say(missing, LATIN_MANIPURI, **{s: "x" for s in mni.SLOT.findall(mni.MESSAGES[missing])}) == \
        mni.MESSAGES[missing].format(**{s: "x" for s in mni.SLOT.findall(mni.MESSAGES[missing])})


def test_the_data_file_lists_every_message_with_its_english_text():
    assert set(TEMPLATES) == set(mni.MESSAGES)
    assert all(TEMPLATES[key]["english"] == text for key, text in mni.MESSAGES.items())
    assert mni.MESSAGES["caveat_placeholder"] in agri_query._caveats(list(assess_areas(demo_areas(), sources())))


# ---------------------------------------------------------------------------- 3. English unchanged

def test_3_english_question_keeps_its_english_answer(client):
    found = ask(client, "Which areas are high risk?")
    assert found["language"] == "english" and found["answer"].startswith("Indicators suggest HIGH or CRITICAL risk")
    assert template("area_risk", level="HIGH") not in found["answer"]
    assert template("verify_advice") not in found["answer"]


# ---------------------------------------------------------------------------- crop health (NDVI)

def test_crop_condition_flow_ndvi_figures_unchanged_framing_in_latin_manipuri(tmp_path, write_tiff, optical_scene):
    from satquery.settings import Settings
    settings = Settings(vlm_backend="fake", runs_dir=tmp_path / "runs")
    path = write_tiff("s2.tif", optical_scene, band_names=S2)
    english = ask_crop_health(settings, path, "How is the crop condition in my field?")
    latin = ask_crop_health(settings, path, CROP_CONDITION)
    assert english.task == latin.task == "crop_health" and latin.status == "ok"
    assert english.answer in latin.answer  # every NDVI figure and caveat, exactly as measured
    assert latin.answer.endswith(template("verify_advice"))
    assert re.search(r"Mean NDVI \d\.\d\d", latin.answer)
