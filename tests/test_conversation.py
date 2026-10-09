"""Conversation follow-ups become complete questions that the existing router and risk engine answer.

The resolver adds no answering of its own: each test sends the rewritten question back through the real /api/route
and /api/agri/query, so the answer, its figures and its warnings are the risk engine's. A follow-up that cannot be
tied to one area is asked back, and nothing a follow-up becomes is sent to satellite analysis.
"""

import pytest

from satquery.agri.areas import demo_areas
from satquery.agri.conversation import ChatContext, display_name, resolve
from test_agri_api import client_for

AREAS = demo_areas()
THOUBAL, KAKCHING, BISHNUPUR = "demo-thoubal-chaobok", "demo-kakching-khangshim", "demo-bishnupur-nambol"


@pytest.fixture
def client(tmp_path, monkeypatch):
    return client_for(tmp_path, monkeypatch)[0]


def chat(client, message, **context):
    return client.post("/api/chat/resolve", json={"message": message, "context": context}).json()


def ranking(client):
    """The first turn of a conversation: the ranking, and the context the client keeps from it."""
    found = client.post("/api/agri/query", json={"query": "Which areas are at high risk?"}).json()
    assert found["intent"] == "rank" and found["area_ids"]
    return found, {"last_query": "Which areas are at high risk?", "last_intent": found["common_intent"],
                   "focus_area_id": found["focus_area_id"], "area_ids": found["area_ids"], "language": "english"}


def asked(client, query):
    """The resolved question, asked through the existing router and risk engine."""
    routed = client.post("/api/route", json={"query": query}).json()
    assert routed["route"] == "agri", routed  # never satellite analysis
    return routed, client.post("/api/agri/query", json={"query": query}).json()


def test_why_after_a_ranking_explains_its_top_area(client):
    first, context = ranking(client)
    turn = chat(client, "Why?", **context)
    top = next(a for a in AREAS if a.id == first["focus_area_id"])
    assert turn["query"] == f"Why is {display_name(top, AREAS)} flagged?" and turn["rewritten"]
    assert turn["area_id"] == top.id and turn["clarification"] is None
    routed, found = asked(client, turn["query"])
    assert routed["intent"] == "AREA_SPECIFIC_RISK" and found["intent"] == "explain"
    assert found["focus_area_id"] == top.id
    assert "PLACEHOLDER" in found["answer"]  # the engine's own warnings come with the answer


@pytest.mark.parametrize("message", ["Why?", "why", "And why is that?", "Why is it so high?", "Tell me more",
                                     "Explain", "What are the reasons?", "Why that one?"])
def test_why_wordings(client, message):
    _, context = ranking(client)
    assert chat(client, message, **context)["query"].startswith("Why is ")


@pytest.mark.parametrize("message", ["What about Thoubal?", "How about Thoubal", "And Thoubal?", "Thoubal?",
                                     "what about thobal?"])  # the last one misspelt, as speech recognition may
def test_what_about_a_named_area_asks_the_same_about_it(client, message):
    _, context = ranking(client)
    turn = chat(client, message, **context)
    assert turn["query"] == "Why is Thoubal flagged?" and turn["area_id"] == THOUBAL
    assert asked(client, turn["query"])[1]["focus_area_id"] == THOUBAL


def test_a_list_position_refers_to_the_last_list(client):
    context = {"last_intent": "INSPECTION_PRIORITY", "area_ids": [BISHNUPUR, KAKCHING, THOUBAL]}
    turn = chat(client, "And the second one?", **context)
    assert turn["query"] == "Why is Kakching flagged?" and turn["area_id"] == KAKCHING
    assert chat(client, "what about the last one", **context)["area_id"] == THOUBAL
    assert "only 3 areas" in chat(client, "the fifth one?", **context)["clarification"]  # no fifth in a list of three


def test_a_pest_follow_up_stays_a_pest_question(client):
    turn = chat(client, "What about Kakching?", last_intent="PEST_RISK", focus_area_id=THOUBAL)
    assert turn["query"] == "Is there pest risk in Kakching?"
    routed, found = asked(client, turn["query"])
    assert routed["intent"] == "PEST_RISK" and found["focus_area_id"] == KAKCHING


def test_there_means_the_area_in_focus(client):
    turn = chat(client, "Is there pest risk there?", last_intent="AREA_SPECIFIC_RISK", focus_area_id=THOUBAL)
    assert turn["query"] == "Is there pest risk in Thoubal?" and turn["area_id"] == THOUBAL
    assert asked(client, turn["query"])[1]["focus_area_id"] == THOUBAL


@pytest.mark.parametrize("message", ["Which areas are at high risk?", "Which should we inspect first?",
                                     "And which should we inspect first?", "Why is Bishnupur flagged?",
                                     "How is the weather?", "Show water bodies in this image"])
def test_a_complete_question_is_asked_as_it_is(client, message):
    _, context = ranking(client)
    turn = chat(client, message, **context)
    assert turn["query"] == message and not turn["rewritten"] and turn["clarification"] is None


def test_a_latin_manipuri_question_is_asked_as_it_is(client):
    turn = chat(client, "Karmba mafam high risk ta lei?")
    assert turn["query"] == "Karmba mafam high risk ta lei?" and "Latin Manipuri" in turn["rule"]


@pytest.mark.parametrize("message, context, says", [
    ("Why?", {}, "Which area do you mean?"),  # nothing asked yet
    ("What about Atlantis?", {"last_intent": "AREA_RISK_QUERY"}, "couldn't find a monitored area called 'Atlantis'"),
    ("What about Imphal?", {"last_intent": "AREA_RISK_QUERY"}, "matches several monitored areas"),
    ("What about Thoubal?", {"last_intent": "WEATHER_RISK"}, "needs an area drawn on the map"),
    ("And the second one?", {}, "Which list do you mean?"),
])
def test_an_unclear_follow_up_is_asked_back_never_guessed(client, message, context, says):
    turn = chat(client, message, **context)
    assert turn["query"] is None and says in turn["clarification"]


def test_the_resolver_needs_no_server_state():
    first = resolve("What about Thoubal?", ChatContext(last_intent="AREA_RISK_QUERY"), AREAS)
    again = resolve("What about Thoubal?", ChatContext(last_intent="AREA_RISK_QUERY"), AREAS)
    assert first == again and first.query == "Why is Thoubal flagged?"


def test_every_area_has_a_name_that_resolves_to_it_alone(client):
    for area in AREAS:
        query = f"Why is {display_name(area, AREAS)} flagged?"
        assert asked(client, query)[1]["focus_area_id"] == area.id, query
