"""Latin Manipuri and English questions reach the same common intent, and the existing router answers it.

Manipuri words come from Member A's files, never from this test: the verified-for-routing examples are the
entries of manipuri_queries.json, and where no sentence exists yet (crop health, pest risk) a question is a
word sequence built from the lexicon's own forms. Those sequences exercise the rules; they are not presented
as verified Manipuri sentences.
"""

import json
from pathlib import Path

import pytest

from satquery.agent.intents import classify, needs_weather, route_query
from satquery.agent.language import INTENTS, LATIN_MANIPURI, normalize
from satquery.agri import query as agri_query
from test_agri_api import client_for

MEMBER_A = Path(__file__).resolve().parent.parent / "Member_A"
QUERIES = json.loads((MEMBER_A / "manipuri_queries.json").read_text(encoding="utf-8"))["queries"]
LEXICON = json.loads((MEMBER_A / "agri_terms_manipuri.json").read_text(encoding="utf-8"))
SELECTED = "demo-thoubal-chaobok"


def form(entry_id: str) -> str:
    """The first Latin form of a lexicon term or cue word."""
    entry = next(e for e in LEXICON["terms"] + LEXICON["cue_words"] if e["id"] == entry_id)
    return next(f["text"] for f in entry["manipuri"] if f["script"] == "Latn")


def built(*entry_ids: str) -> str:
    return " ".join(form(i) for i in entry_ids) + "?"


def labelled(intent: str) -> str:
    return next(q["text"] for q in QUERIES if q["intent"] == intent)


@pytest.fixture
def client(tmp_path, monkeypatch):
    return client_for(tmp_path, monkeypatch)[0]


def route(client, query):
    return client.post("/api/route", json={"query": query}).json()


def ask(client, query, **extra):
    return client.post("/api/agri/query", json={"query": query} | extra).json()


# ------------------------------------------------------------------------- the data file itself

@pytest.mark.parametrize("entry", QUERIES, ids=[q["id"] for q in QUERIES])
def test_every_manipuri_query_in_the_data_file_routes_as_labelled(client, entry):
    norm = normalize(entry["text"])
    assert norm.language == LATIN_MANIPURI and norm.intent == entry["intent"], norm.rule
    routed = route(client, entry["text"])
    assert routed["route"] == INTENTS[entry["intent"]][0] and routed["language"] == LATIN_MANIPURI
    assert routed["intent"] == entry["intent"]


def test_the_rule_says_the_manipuri_lexicon_is_not_yet_verified():
    assert "not yet verified by a fluent speaker" in normalize(labelled("INSPECTION_PRIORITY")).rule


# ------------------------------------------------------------------------- Latin Manipuri -> risk engine

def test_1_latin_manipuri_high_risk_question_goes_to_the_risk_engine(client):
    for query in ("Kanagumba area high risk da lei?", built("cue-which", "term-area", "term-risk")):
        assert normalize(query).as_dict() == {"language": LATIN_MANIPURI, "intent": "AREA_RISK_QUERY", "entities": {}}
        routed = route(client, query)
        assert (routed["route"], routed["intent"]) == ("agri", "AREA_RISK_QUERY"), routed
        found = ask(client, query)
        assert found["intent"] == "rank" and found["answer"].startswith("Indicators suggest")


def test_2_latin_manipuri_why_risk_question_is_explained(client):
    selected = labelled("AREA_EXPLANATION")  # "How is it dangerous?" in the data file
    assert route(client, selected)["intent"] == "AREA_EXPLANATION"
    found = ask(client, selected, selected_area_id=SELECTED)
    assert found["intent"] == "explain" and found["focus_area_id"] == SELECTED and "Why:" in found["answer"]
    named = built("place-bishnupur", "cue-why", "term-risk")
    assert normalize(named).entities == {"places": ["Bishnupur"]}
    assert route(client, named)["intent"] == "AREA_SPECIFIC_RISK"
    assert ask(client, named)["focus_area_id"] == "demo-bishnupur-nambol"


def test_3_latin_manipuri_inspection_question_gets_the_inspection_order(client):
    query = labelled("INSPECTION_PRIORITY")
    assert route(client, query)["intent"] == "INSPECTION_PRIORITY"
    found = ask(client, query)
    assert found["intent"] == "inspect" and found["answer"].startswith("Suggested order for field inspection")


def test_4_latin_manipuri_crop_health_question_is_the_ndvi_analysis():
    query = built("term-crop", "cue-how")
    assert normalize(query).intent == "CROP_HEALTH"
    assert route_query(query)[0] == "imagery"  # the existing NDVI crop-health path, not the risk engine
    intent = classify(query, "single_optical")
    assert intent.task == "crop_health" and "CROP_HEALTH" in intent.matched_rule


def test_5_latin_manipuri_pest_risk_question_reads_the_selected_area(client):
    query = built("cue-here", "term-pest", "term-risk")
    routed = route(client, query)
    assert (routed["route"], routed["intent"], routed["language"]) == ("agri", "PEST_RISK", LATIN_MANIPURI)
    assert ask(client, query, selected_area_id=SELECTED)["focus_area_id"] == SELECTED
    assert "Select one of the monitored areas" in ask(client, query)["answer"]


def test_latin_manipuri_weather_question_goes_to_the_weather_specialist(client):
    query = labelled("WEATHER_RISK")
    assert needs_weather(query) and route_query(query)[0] == "weather"
    assert route(client, query)["intent"] == "WEATHER_RISK"


# ------------------------------------------------------------------------- English

def test_6_english_high_risk_question_has_the_same_intent_as_the_manipuri_one(client):
    routed = route(client, "Which areas are high risk?")
    assert (routed["route"], routed["intent"]) == ("agri", route(client, "Kanagumba area high risk da lei?")["intent"])
    assert ask(client, "Which areas are high risk?")["intent"] == "rank"


@pytest.mark.parametrize("query, intent, kind", [
    ("Where should I begin?", "INSPECTION_PRIORITY", "inspect"),          # 7
    ("How is it dangerous?", "AREA_EXPLANATION", "explain"),              # 8
    ("Is this a safe area?", "AREA_EXPLANATION", "explain"),              # 9
    ("Where do we start?", "INSPECTION_PRIORITY", "inspect"),
    ("Which places are dangerous?", "AREA_RISK_QUERY", "rank"),
])
def test_7_to_9_english_wording_the_cue_rules_missed(client, query, intent, kind):
    routed = route(client, query)
    assert (routed["route"], routed["intent"]) == ("agri", intent), routed
    found = ask(client, query, selected_area_id=SELECTED)
    assert found["intent"] == kind and found["common_intent"] == intent
    if kind == "explain":
        assert found["focus_area_id"] == SELECTED


def test_the_english_cue_rules_still_decide_first(client):
    assert route(client, "Which areas are high risk?")["rule"].startswith("ranking cue")
    assert route(client, "Why is Bishnupur flagged?")["intent"] == "AREA_SPECIFIC_RISK"
    assert route(client, "Is there pest risk in this area?")["intent"] == "PEST_RISK"


# ------------------------------------------------------------------------- imagery and fallback

@pytest.mark.parametrize("query, intent", [  # 10
    ("Highlight the water body in this image.", None), ("Describe this area", None),
    ("Detect the ships in the harbour", None), ("Where do the buildings start?", None),
    ("Is there tin roofing in this image?", None), ("What is the NDVI?", "CROP_HEALTH"),
    ("How healthy is the crop here?", "CROP_HEALTH"),
])
def test_10_image_questions_still_go_to_satellite_analysis(client, query, intent):
    routed = route(client, query)
    assert (routed["route"], routed["intent"], routed["language"]) == ("imagery", intent, "english"), routed


@pytest.mark.parametrize("query", ["Tell me about pests", "Risk?", built("term-crop", "term-harvest")])
def test_an_unclear_risk_or_manipuri_question_is_asked_to_rephrase_not_sent_to_imagery(client, query):
    routed = route(client, query)
    assert routed["route"] == "agri" and routed["intent"] is None and "intent unclear" in routed["rule"]
    found = ask(client, query)
    assert found["intent"] == "unmatched" and found["answer"] == agri_query.REPHRASE
