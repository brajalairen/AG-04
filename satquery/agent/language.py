"""Language and intent normalisation for agricultural questions, before the existing router (D-006).

A question is read as concepts ("risk", "where", "first", ...): Latin Manipuri forms come from Member A's lexicon
(team/member-a-agronomy/agri_terms_manipuri.json: its terms by category, and its cue words), English forms from the
word classes below. The intent rules are written on concepts only, so one rule serves English, Latin Manipuri and
code-mixed questions ("Kanagumba area high risk da lei?"), and no sentence is listed anywhere.

The result is a common intent (the team's vocabulary, team/member-a-agronomy/README.md); INTENTS maps each one onto
the existing AG-04 behaviour that answers it. Wording only: no I/O beyond reading the lexicon once.
"""

import json
import os
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

LATIN_MANIPURI, ENGLISH = "latin_manipuri", "english"
DEFAULT_LEXICON = Path(__file__).resolve().parents[2] / "team" / "member-a-agronomy" / "agri_terms_manipuri.json"

# Common intent -> (route, existing behaviour): "agri" is the risk engine (rank / inspect / explain in
# satquery.agri.query), "weather" the weather specialist, "imagery" the NDVI crop-health analysis.
INTENTS = {
    "AREA_RISK_QUERY": ("agri", "rank"),
    "INSPECTION_PRIORITY": ("agri", "inspect"),
    "AREA_EXPLANATION": ("agri", "explain"),
    "AREA_SPECIFIC_RISK": ("agri", "explain"),
    "PEST_RISK": ("agri", "explain"),
    "CROP_HEALTH": ("imagery", "crop_health"),
    "WEATHER_RISK": ("weather", "weather_forecast"),
}

# English word classes, one per concept. Weather and crop-health wording is not here: the English cue rules in
# satquery.agent.intents already decide it, and this table only catches agricultural wording those rules miss.
ENGLISH_WORDS = {
    "risk": r"risk\w*|danger\w*|threat\w*|hazard\w*|unsafe|vulnerab\w*|flagged|alerts?|warnings?",
    "safe": r"safe|safety",
    "pest": r"pests?|insects?|blast|planthoppers?|infest\w*|diseases?|outbreaks?",
    "crop": r"crops?|paddy|paddies|rice|plants?|fields?|farm\w*|harvest\w*",
    "health": r"health\w*|stress\w*|condition|damage\w*",
    "inspect": r"inspect\w*|visit\w*|survey\w*|prioriti[sz]\w*|priority|priorities",
    "why": r"why|reasons?|explain\w*|causes?",
    "how": r"how",
    "which": r"which|what|any",
    "where": r"where",
    "begin": r"begin\w*|began|begun|start\w*",
    "first": r"first",
    "high": r"high|higher|highest|most|top|worst",
    "here": r"here|this|that|it|selected",
    "area": r"areas?|places?|districts?|villages?|regions?|locations?|zones?",
}
CONCEPTS = frozenset(ENGLISH_WORDS) | {"weather", "place", "exist"}  # "exist" (lei): only marks the language
ENGLISH_PATTERNS = {concept: re.compile(rf"\b(?:{words})\b") for concept, words in ENGLISH_WORDS.items()}
# English function words: a question built on them is English, even if one word also exists in Manipuri.
FUNCTION_WORDS = frozenset(
    "a an the is are was were be been am there this that these those it its in on at of for to from with by which what "
    "why how where when who should could would will can shall may might must do does did i we you they he she my our "
    "your their me us them and or not no any some all if then than so here about show tell please".split())

# How a Manipuri term's category reads as a concept; a term's own "concept" field overrides it.
CATEGORY_CONCEPT = {"crop": "crop", "pest": "pest", "disease": "pest", "weather": "weather", "crop_health": "health",
                    "risk": "risk", "inspection": "inspect", "place": "place"}
# Case, plural and question endings that may follow a short form (masi -> masigi, kayā -> kayāno, lei -> leibrā);
# longer forms match as stems.
SHORT_FORM_ENDINGS = r"(?:sing|gi|ki|da|ta|dagi|tagi|na|bu|pu|ga|ka|su|di|ti|ni|damak|no|bano|bra|ra|ge|bage)*"

# First match wins. A rule names the concepts it needs; the words that supplied them are quoted in the trace.
RULES = (
    ("INSPECTION_PRIORITY", lambda c: "inspect" in c or ("where" in c and bool(c & {"begin", "first"}))
                                      or ({"which", "first"} <= c and bool(c & {"area", "place", "risk"}))),
    ("PEST_RISK", lambda c: "pest" in c and bool(c & {"risk", "here", "area", "place", "why", "how", "which", "high"})),
    ("AREA_SPECIFIC_RISK", lambda c: "place" in c and bool(c & {"risk", "safe"})),
    ("AREA_EXPLANATION", lambda c: bool(c & {"risk", "safe"}) and bool(c & {"why", "how", "here"})),
    ("AREA_RISK_QUERY", lambda c: "risk" in c and bool(c & {"which", "high", "area"})),
    ("CROP_HEALTH", lambda c: "crop" in c and bool(c & {"health", "how"})),
    ("WEATHER_RISK", lambda c: "weather" in c),
)


def fold(text: str) -> str:
    """Lower case, no diacritics (ā -> a), hyphens as spaces: people type Latin Manipuri every way."""
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", re.sub(r"[-_]", " ", text)).strip()


@dataclass(frozen=True)
class _Form:
    concept: str
    text: str
    pattern: re.Pattern
    place: str | None  # the English place name, for a place term
    evidence: bool     # counts as evidence that the question is Manipuri


def _pattern(text: str) -> re.Pattern:
    parts = fold(text).split()
    stem = r"[\s-]*".join(re.escape(part) for part in parts)
    return re.compile(rf"\b{stem}" + (r"\w*" if len("".join(parts)) >= 5 else rf"{SHORT_FORM_ENDINGS}\b"))


def _forms(entry: dict, concept: str | None) -> list[_Form]:
    if concept not in CONCEPTS:
        return []
    place = entry.get("english") if concept == "place" else None
    forms = []
    for form in entry.get("manipuri") or []:
        text = form.get("text") or ""
        if form.get("script") != "Latn" or not text.strip() or "<" in text:
            continue
        letters = fold(text).replace(" ", "")
        # Two-letter forms and place names spelled as in English ("jiribam") also occur in English questions; a
        # short form that is also an English word ("tin") is outweighed by the English function words around it.
        evidence = len(letters) >= 3 and not (place and letters == fold(place).replace(" ", ""))
        forms.append(_Form(concept, text, _pattern(text), place, evidence))
    return forms


@lru_cache(maxsize=4)
def _lexicon(path: str) -> tuple[str | None, tuple[_Form, ...]]:
    """(the lexicon file's status, its Latin forms). No file: English only."""
    file = Path(path)
    if not file.is_file():
        return None, ()
    data = json.loads(file.read_text(encoding="utf-8"))
    forms = [f for term in data.get("terms") or []
             for f in _forms(term, term.get("concept") or CATEGORY_CONCEPT.get(term.get("category")))]
    forms += [f for cue in data.get("cue_words") or [] for f in _forms(cue, cue.get("concept"))]
    return data.get("status"), tuple(forms)


def lexicon() -> tuple[str | None, tuple[_Form, ...]]:
    return _lexicon(os.environ.get("SATQUERY_MANIPURI_LEXICON") or str(DEFAULT_LEXICON))


@dataclass(frozen=True)
class NormalizedQuery:
    language: str                         # "latin_manipuri" | "english"
    intent: str | None                    # a key of INTENTS, or None when no rule applies
    places: tuple[str, ...]               # place names the question gives, in English
    concepts: frozenset[str]
    cues: tuple[tuple[str, str], ...]     # (concept, the words that supplied it), in question order
    lexicon_status: str | None = None

    @property
    def entities(self) -> dict:
        return {"places": list(self.places)} if self.places else {}

    def as_dict(self) -> dict:
        return {"language": self.language, "intent": self.intent, "entities": self.entities}

    def cue(self, concept: str) -> str | None:
        return next((text for c, text in self.cues if c == concept), None)

    @property
    def rule(self) -> str:
        cues = ", ".join(f"'{text}' ({concept})" for concept, text in self.cues) or "none"
        rule = f"{'Latin Manipuri' if self.language == LATIN_MANIPURI else 'English'} concept cues {cues}"
        if self.language == LATIN_MANIPURI and self.lexicon_status != "VERIFIED":
            rule += f" [Manipuri lexicon {self.lexicon_status or 'missing'}: not yet verified by a fluent speaker]"
        return rule + (f" -> {self.intent}" if self.intent else " -> intent unclear")


def normalize(query: str) -> NormalizedQuery:
    """The language, common intent and entities of a question, from its words alone."""
    text = fold(query)
    status, forms = lexicon()
    hits = []  # (position, concept, matched words, form)
    for form in forms:
        hits += [(m.start(), form.concept, m.group(0), form) for m in form.pattern.finditer(text)]
    manipuri_evidence = len({(start, words) for start, _, words, form in hits if form.evidence})
    function_words = sum(1 for word in re.findall(r"[a-z]+", text) if word in FUNCTION_WORDS)
    language = LATIN_MANIPURI if manipuri_evidence and manipuri_evidence >= function_words else ENGLISH
    if language == ENGLISH:
        hits = []  # an English question is read with English words only ("tin roofing" is not an insect)
    # English words count in Latin Manipuri too: questions are often code-mixed ("... area high risk da lei?").
    for concept, pattern in ENGLISH_PATTERNS.items():
        hits += [(m.start(), concept, m.group(0), None) for m in pattern.finditer(text)]

    hits.sort(key=lambda hit: hit[0])
    concepts = frozenset(concept for _, concept, _, _ in hits)
    cues = tuple(dict.fromkeys((concept, words) for _, concept, words, _ in hits))
    places = tuple(dict.fromkeys(form.place for _, _, _, form in hits if form and form.place))
    intent = next((name for name, test in RULES if test(concepts)), None)
    return NormalizedQuery(language, intent, places, concepts, cues, status)
