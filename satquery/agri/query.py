"""Agricultural questions in the command bar, answered from the risk engine's assessments.

Rule-based, like the rest of the agent: the wording picks one of three intents, and the rule that
matched is returned with the answer. Nothing is scored here; every figure is read from the ranked
assessments, and every answer keeps the engine's wording ("indicators suggest") and its caveats.

  rank     "Which areas are high risk?"
  inspect  "Which should we inspect first?"
  explain  "Why is Bishnupur flagged?" (a named area, or the area selected on the map)

Latin Manipuri questions, and English wording the cue rules below miss ("Where should I begin?"), are first
normalised to a common intent (satquery.agent.language) and then answered by the same three behaviours. A question
that is about crop & pest risk but matches no intent is asked to be rephrased, never sent to satellite analysis.
"""

import re
from dataclasses import dataclass, field

from satquery.agent.intents import IMAGERY_CUES, find_target
from satquery.agent.language import ENGLISH, INTENTS, LATIN_MANIPURI, NormalizedQuery, normalize
from satquery.agri import answer_language as mni
from satquery.agri.models import SAMPLE_LABEL, MonitoredArea, RiskAssessment

INSPECT = re.compile(r"\b(?:inspect\w*|field[- ](?:visit|check|inspection)s?|visit first|go first|look first|"
                     r"prioriti[sz]\w*|where should we (?:go|look|start))\b", re.I)
RANK = re.compile(r"\b(?:which|what|list|show|rank\w*)\b[^?]*\b(?:high|highest|critical|most|top|elevated|risky)\b"
                  r"[^?]*\brisk|\bhigh[- ]risk\b|\briskiest\b|\bmost at risk\b|\brisk ranking\b|\bpriority areas?\b",
                  re.I)
EXPLAIN = re.compile(r"\b(?:why|explain|reasons?)\b|\bflagged\b|\bwhat(?:'s| is) the risk\b|\bhow risky\b", re.I)
AGRI_CONTEXT = re.compile(r"\b(?:risk\w*|flagged|pests?|blast|planthoppers?|infestation|alerts?)\b", re.I)
HERE = re.compile(r"\b(?:this|selected|that) area\b|\bhere\b", re.I)
EXAMPLES = ["Which areas are high risk?", "Why is Bishnupur flagged?", "Which should we inspect first?"]
SEVERE = ("CRITICAL", "HIGH")
# Concepts that make a question about crop & pest risk even when no intent rule applies to it.
RISK_CONCEPTS = frozenset({"risk", "pest", "inspect"})  # "safe" alone is too generic (e.g. "safe to irrigate")
REPHRASE = ("This question could not be matched with confidence to a crop & pest risk question, so it was not sent "
            "to satellite image analysis either. The risk engine answers which areas are at high risk, why a named or "
            "selected area is flagged, and which areas to inspect first. For example: " + "; ".join(EXAMPLES))


@dataclass
class AgriAnswer:
    intent: str  # rank | inspect | explain | unmatched
    matched_rule: str
    answer: str
    area_ids: list[str] = field(default_factory=list)
    focus_area_id: str | None = None
    language: str = ENGLISH
    common_intent: str | None = None  # a key of satquery.agent.language.INTENTS


@dataclass
class AgriIntent:
    """How a crop & pest risk question is answered. `kind` is None when it must be rephrased."""
    kind: str | None  # rank | inspect | explain | None
    rule: str
    common_intent: str | None = None
    language: str = ENGLISH
    places: tuple[str, ...] = ()  # place names a Latin Manipuri question gives, in English
    refers_to_selection: bool = False  # "this" without an area word: the area selected on the map


def aliases(area: MonitoredArea) -> list[str]:
    """Place names that refer to an area: its district and the capitalised place names in its name."""
    names = re.findall(r"[A-Z][a-z]+(?: [A-Z][a-z]+)*", area.name)
    return list(dict.fromkeys(n.lower() for n in ([area.district] if area.district else []) + names))


def resolve_area(query: str, areas: list[MonitoredArea]) -> tuple[list[MonitoredArea], str | None]:
    """Areas the query names. Whole place names first ("Imphal West"); failing that, a first word
    ("Imphal"), which may match several. Returns (matches, the text that matched)."""
    text = query.lower()
    for whole in (True, False):
        found, phrase = [], None
        for area in areas:
            for alias in aliases(area):
                target = alias if whole else alias.split()[0]
                if re.search(rf"\b{re.escape(target)}\b", text):
                    found.append(area)
                    phrase = phrase or target
                    break
        if found:
            return found, phrase
    return [], None


def _from_common(norm: NormalizedQuery) -> AgriIntent | None:
    route, kind = INTENTS.get(norm.intent, (None, None))
    if route != "agri":
        return None
    deictic = norm.intent in ("AREA_EXPLANATION", "PEST_RISK") and not norm.places
    return AgriIntent(kind, norm.rule, norm.intent, norm.language, norm.places, deictic)


def decide(query: str, areas: list[MonitoredArea], selected_area_id: str | None = None) -> AgriIntent | None:
    """How `query` is answered by the risk engine, or None when it is not a crop & pest risk question (weather and
    imagery questions, which keep their own routes). Wording only."""
    norm = normalize(query)
    if norm.language == LATIN_MANIPURI:
        found = _from_common(norm)
        if found or norm.intent or IMAGERY_CUES.search(query):  # weather, NDVI and image questions route elsewhere
            return found
        return AgriIntent(None, norm.rule, None, norm.language)
    rule = _cue_rule(query, areas)
    if rule:  # the English cue rules, unchanged
        named = resolve_area(query, areas)[0]
        here = HERE.search(query)
        if INSPECT.search(query):
            kind = "inspect"
        elif (named or (here and any(a.id == selected_area_id for a in areas))
              or (EXPLAIN.search(query) and not RANK.search(query))
              or (here and AGRI_CONTEXT.search(query))):
            kind = "explain"
        else:
            kind = "rank"
        common = {"inspect": "INSPECTION_PRIORITY", "rank": "AREA_RISK_QUERY"}.get(kind) or (
            "PEST_RISK" if "pest" in norm.concepts else "AREA_SPECIFIC_RISK" if named else "AREA_EXPLANATION")
        return AgriIntent(kind, rule, common)
    # Wording the cue rules miss ("Where should I begin?") gets the concept rules, unless it asks about imagery.
    if IMAGERY_CUES.search(query) or find_target(query)[0]:
        return None
    found = _from_common(norm)
    if found or not norm.concepts & RISK_CONCEPTS or norm.intent:
        return found
    return AgriIntent(None, norm.rule)


def is_agri(query: str, areas: list[MonitoredArea]) -> str | None:
    """The rule that makes `query` a crop & pest risk question (to answer or to ask to rephrase), or None."""
    found = decide(query, areas)
    return found.rule if found else None


def _cue_rule(query: str, areas: list[MonitoredArea]) -> str | None:
    """The English cue rule that makes `query` an agricultural risk question, or None. Wording only."""
    if INSPECT.search(query):
        return f"inspection cue '{INSPECT.search(query).group(0)}'"
    named, phrase = resolve_area(query, areas)
    explain = EXPLAIN.search(query)
    if explain and (named or AGRI_CONTEXT.search(query)):
        return f"explanation cue '{explain.group(0)}'" + (f" + area '{phrase}'" if named else " + risk wording")
    rank = RANK.search(query)
    if rank:
        return f"ranking cue '{rank.group(0)}'"
    context = AGRI_CONTEXT.search(query)
    if context and (named or HERE.search(query)):
        return f"risk cue '{context.group(0)}'" + (f" + area '{phrase}'" if named else " + this area")
    return None


def _caveats(assessments: list[RiskAssessment]) -> str:
    lines = []
    if any(a.thresholds_status == "PLACEHOLDER" for a in assessments):
        lines.append("PLACEHOLDER thresholds: prototype scores, not validated agricultural findings.")
    if any(a.includes_sample_data for a in assessments):
        lines.append(f"Pest-report figures are {SAMPLE_LABEL}.")
    lines.append("Decision support only; the final assessment rests with the Department of Agriculture.")
    return "\n".join(lines)


def _line(a: RiskAssessment) -> str:
    score = f"{a.score:.0f}/100" if a.score is not None else "no score"
    return f"#{a.rank} {a.area_name}: {a.level}, {score} (confidence {a.confidence.level})"


def _drivers(a: RiskAssessment) -> str:
    names = {f.id: f.name.lower() for f in a.factors}
    return " and ".join(names[f] for f in a.top_factors[:2]) or "no single indicator"


def answer(query: str, assessments: list[RiskAssessment], areas: list[MonitoredArea],
           selected_area_id: str | None = None) -> AgriAnswer:
    found = decide(query, areas, selected_area_id)
    rule = found.rule if found else "no agricultural cue"
    ranked = [a for a in assessments if a.rank is not None]
    unranked = [a for a in assessments if a.rank is None]
    caveats = _caveats(assessments)

    # A Latin Manipuri question is answered in Latin Manipuri (satquery.agri.answer_language): the same
    # results, inserted as the engine gives them. The English text below is unchanged for English questions.
    latin = found is not None and found.language == LATIN_MANIPURI

    def reply(intent, text, area_ids=(), focus=None, manipuri=None):
        return AgriAnswer(intent, rule, manipuri() if latin and manipuri else text, list(area_ids), focus,
                          found.language if found else ENGLISH, found.common_intent if found else None)

    if found is None or found.kind is None:
        return reply("unmatched", REPHRASE,
                     manipuri=lambda: mni.say("rephrase", LATIN_MANIPURI, examples="; ".join(EXAMPLES)))

    if found.kind == "inspect":
        if not ranked:
            return reply("inspect", "No monitored area has enough data for a risk estimate, so no inspection "
                         "order can be suggested.\n" + caveats, [a.area_id for a in unranked],
                         manipuri=lambda: mni.inspect(assessments, [], unranked, _drivers))
        top = ranked[:3]
        lines = ["Suggested order for field inspection, by risk rank (decision support; the final choice rests with "
                 "the Department):"]
        lines += [f"{i}. {a.area_name}: {a.level}, {a.score:.0f}/100, mainly {_drivers(a)}; confidence "
                  f"{a.confidence.level}" for i, a in enumerate(top, 1)]
        if unranked:
            lines.append(f"Not ranked for lack of data: {', '.join(a.area_name for a in unranked)}.")
        return reply("inspect", "\n".join(lines) + "\n" + caveats, [a.area_id for a in top], top[0].area_id,
                     manipuri=lambda: mni.inspect(assessments, top, unranked, _drivers))

    # A Latin Manipuri question names its place in Manipuri; the area is found from the English name.
    named, phrase = resolve_area(" ".join(found.places) if found.places else query, areas)
    here = HERE.search(query) or found.refers_to_selection
    if not named and selected_area_id and here:
        named = [area for area in areas if area.id == selected_area_id]
    # One area in view (named, or selected and referred to) is explained; "why ... high risk" over all
    # areas is a ranking question.
    if found.kind == "explain":
        if len(named) == 1:
            a = next((x for x in assessments if x.area_id == named[0].id), None)
            if a is not None:
                rank = f"Rank #{a.rank} of {a.rank_of} assessed areas." if a.rank else "Not ranked: not enough data."
                reasons = "\n".join(f"- {r}" for r in a.reasons[:5])
                pest = found.common_intent == "PEST_RISK"
                return reply("explain", f"{a.headline} {rank}\nWhy:\n{reasons}\n{caveats}", [a.area_id], a.area_id,
                             manipuri=lambda: mni.explain(a, assessments, pest))
        names = ", ".join(area.name for area in areas)
        if len(named) > 1:
            text = (f"'{phrase}' matches several monitored areas: {', '.join(n.name for n in named)}. "
                    "Please name one.")
            key, slots = "ambiguous_area", {"phrase": phrase, "names": ", ".join(n.name for n in named)}
        elif here:
            text = ("Select one of the monitored areas on the map (or name it) to see why it is flagged. "
                    "Assessing a newly drawn area is planned for a later phase.")
            key, slots = "select_area", {}
        else:
            text = f"No monitored area matches this question. Monitored areas: {names}."
            key, slots = "no_area_match", {"names": names}
        return reply("unmatched", text, [n.id for n in named],
                     manipuri=lambda: mni.say(key, LATIN_MANIPURI, **slots))

    severe = [a for a in ranked if a.level in SEVERE]
    counts = {level: sum(1 for a in assessments if a.level == level)
              for level in ("CRITICAL", "HIGH", "MODERATE", "LOW", "INSUFFICIENT_DATA")}
    tally = (f"Moderate: {counts['MODERATE']}, low: {counts['LOW']}, not enough data: "
             f"{counts['INSUFFICIENT_DATA']} of {len(assessments)} monitored areas.")
    if severe:
        head = (f"Indicators suggest HIGH or CRITICAL risk in {len(severe)} of {len(assessments)} monitored areas:")
        body = "\n".join(_line(a) for a in severe)
        return reply("rank", f"{head}\n{body}\n{tally}\n{caveats}", [a.area_id for a in severe], severe[0].area_id,
                     manipuri=lambda: mni.rank(assessments, ranked, severe))
    if ranked:
        return reply("rank", "No monitored area is at HIGH or CRITICAL risk by the current indicators. "
                     f"Highest: {_line(ranked[0])}.\n{tally}\n{caveats}", [ranked[0].area_id], ranked[0].area_id,
                     manipuri=lambda: mni.rank(assessments, ranked, severe))
    return reply("rank", "No monitored area has enough data for a risk estimate.\n" + caveats,
                 [a.area_id for a in unranked], manipuri=lambda: mni.rank(assessments, ranked, severe))
