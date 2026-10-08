"""A question in Meitei Mayek is read in its Latin spelling, so it reaches the same intent, engine and answer as
the Latin Manipuri question. The Meitei Mayek texts are the dataset's own (dataset_ref.meiteiscript in
manipuri_queries.json), never written in this test.
"""

import pytest

from satquery.agent.language import LATIN_MANIPURI, fold, normalize
from satquery.agent.meitei_mayek import has_meitei_mayek, to_latin
from test_agri_api import client_for
from test_language_routing import QUERIES

WITH_SCRIPT = [q for q in QUERIES if (q.get("dataset_ref") or {}).get("meiteiscript")]


@pytest.fixture
def client(tmp_path, monkeypatch):
    return client_for(tmp_path, monkeypatch)[0]


@pytest.mark.parametrize("entry", WITH_SCRIPT, ids=[q["id"] for q in WITH_SCRIPT])
def test_the_dataset_meitei_mayek_reads_as_its_latin_twin(entry):
    meitei = entry["dataset_ref"]["meiteiscript"]
    assert to_latin(meitei) == entry["text"]
    assert normalize(meitei).as_dict() == normalize(entry["text"]).as_dict()


@pytest.mark.parametrize("entry", WITH_SCRIPT, ids=[q["id"] for q in WITH_SCRIPT])
def test_a_meitei_mayek_question_takes_the_same_route(client, entry):
    meitei, latin = entry["dataset_ref"]["meiteiscript"], entry["text"]
    routed = client.post("/api/route", json={"query": meitei}).json()
    assert routed["language"] == LATIN_MANIPURI and routed["intent"] == entry["intent"]
    assert routed["route"] == client.post("/api/route", json={"query": latin}).json()["route"]


def test_a_meitei_mayek_risk_question_is_answered_like_the_latin_one(client):
    entry = next(q for q in WITH_SCRIPT if q["intent"] == "INSPECTION_PRIORITY")
    ask = lambda query: client.post("/api/agri/query", json={"query": query}).json()
    meitei, latin = ask(entry["dataset_ref"]["meiteiscript"]), ask(entry["text"])
    assert meitei["answer"] == latin["answer"] and meitei["language"] == LATIN_MANIPURI


@pytest.mark.parametrize("meitei, latin", [
    ("ꯑꯩ", "ei"),                 # atiya carries the vowel sign
    ("ꯀꯔꯝꯅ", "karamna"),          # inherent a; lonsum m has none
    ("ꯑꯣꯏꯕ꯭ꯔꯥ", "oibrā"),          # apun: no vowel inside the cluster
    ("ꯐꯥꯎꯕ", "phaoba"),            # ā + U is written ao
    ("ꯏꯡ", "eeng"),               # word-initial I is written ee
    ("ꯀꯗꯥꯏꯗꯒꯤ", "kadāidagi"),       # I inside a word stays i
])
def test_letter_rules(meitei, latin):
    assert to_latin(meitei) == latin


def test_other_scripts_pass_through_unchanged():
    for text in ("Which areas are at high risk?", "Kanagumba area high risk da lei?", "জোন্ গাল্ৎকী"):
        assert not has_meitei_mayek(text) and to_latin(text) == text


def test_a_lexicon_form_matches_with_or_without_the_cluster_vowel():
    # dataset row 28625: meiteiscript ꯄ꯭ꯔꯥꯏꯑꯣꯔꯤꯇꯤ, romanstandard parāioriti ("priority"); the conversion gives prāioriti
    assert fold(to_latin("ꯄ꯭ꯔꯥꯏꯑꯣꯔꯤꯇꯤ")) == "praioriti"
    assert normalize("parāioriti").cue("inspect") and normalize("ꯄ꯭ꯔꯥꯏꯑꯣꯔꯤꯇꯤ").cue("inspect")
