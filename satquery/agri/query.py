"""Agricultural questions in the command bar, answered from the risk engine's assessments.

Rule-based, like the rest of the agent: the wording picks one of three intents, and the rule that
matched is returned with the answer. Nothing is scored here; every figure is read from the ranked
assessments, and every answer keeps the engine's wording ("indicators suggest") and its caveats.

  rank     "Which areas are high risk?"
  inspect  "Which should we inspect first?"
  explain  "Why is Bishnupur flagged?" (a named area, or the area selected on the map)
"""

import re
from dataclasses import dataclass, field

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


@dataclass
class AgriAnswer:
    intent: str  # rank | inspect | explain | unmatched
    matched_rule: str
    answer: str
    area_ids: list[str] = field(default_factory=list)
    focus_area_id: str | None = None


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


def is_agri(query: str, areas: list[MonitoredArea]) -> str | None:
    """The rule that makes `query` an agricultural risk question, or None. Wording only."""
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
    rule = is_agri(query, areas) or "no agricultural cue"
    ranked = [a for a in assessments if a.rank is not None]
    unranked = [a for a in assessments if a.rank is None]
    caveats = _caveats(assessments)

    if INSPECT.search(query):
        if not ranked:
            return AgriAnswer("inspect", rule, "No monitored area has enough data for a risk estimate, so no inspection "
                              "order can be suggested.\n" + caveats, [a.area_id for a in unranked])
        top = ranked[:3]
        lines = ["Suggested order for field inspection, by risk rank (decision support; the final choice rests with "
                 "the Department):"]
        lines += [f"{i}. {a.area_name}: {a.level}, {a.score:.0f}/100, mainly {_drivers(a)}; confidence "
                  f"{a.confidence.level}" for i, a in enumerate(top, 1)]
        if unranked:
            lines.append(f"Not ranked for lack of data: {', '.join(a.area_name for a in unranked)}.")
        return AgriAnswer("inspect", rule, "\n".join(lines) + "\n" + caveats, [a.area_id for a in top],
                          top[0].area_id)

    named, phrase = resolve_area(query, areas)
    here = HERE.search(query)
    if not named and selected_area_id and here:
        named = [area for area in areas if area.id == selected_area_id]
    # One area in view (named, or selected and referred to) is explained; "why ... high risk" over all
    # areas is a ranking question.
    wants_explain = (bool(named) or bool(EXPLAIN.search(query) and not RANK.search(query))
                     or bool(here and AGRI_CONTEXT.search(query)))
    if wants_explain:
        if len(named) == 1:
            a = next((x for x in assessments if x.area_id == named[0].id), None)
            if a is not None:
                rank = f"Rank #{a.rank} of {a.rank_of} assessed areas." if a.rank else "Not ranked: not enough data."
                reasons = "\n".join(f"- {r}" for r in a.reasons[:5])
                return AgriAnswer("explain", rule, f"{a.headline} {rank}\nWhy:\n{reasons}\n{caveats}",
                                  [a.area_id], a.area_id)
        names = ", ".join(area.name for area in areas)
        if len(named) > 1:
            text = (f"'{phrase}' matches several monitored areas: {', '.join(n.name for n in named)}. "
                    "Please name one.")
        elif HERE.search(query):
            text = ("Select one of the monitored areas on the map (or name it) to see why it is flagged. "
                    "Assessing a newly drawn area is planned for a later phase.")
        else:
            text = f"No monitored area matches this question. Monitored areas: {names}."
        return AgriAnswer("unmatched", rule, text, [n.id for n in named])

    severe = [a for a in ranked if a.level in SEVERE]
    counts = {level: sum(1 for a in assessments if a.level == level)
              for level in ("CRITICAL", "HIGH", "MODERATE", "LOW", "INSUFFICIENT_DATA")}
    tally = (f"Moderate: {counts['MODERATE']}, low: {counts['LOW']}, not enough data: "
             f"{counts['INSUFFICIENT_DATA']} of {len(assessments)} monitored areas.")
    if severe:
        head = (f"Indicators suggest HIGH or CRITICAL risk in {len(severe)} of {len(assessments)} monitored areas:")
        body = "\n".join(_line(a) for a in severe)
        return AgriAnswer("rank", rule, f"{head}\n{body}\n{tally}\n{caveats}", [a.area_id for a in severe],
                          severe[0].area_id)
    if ranked:
        return AgriAnswer("rank", rule, "No monitored area is at HIGH or CRITICAL risk by the current indicators. "
                          f"Highest: {_line(ranked[0])}.\n{tally}\n{caveats}", [ranked[0].area_id], ranked[0].area_id)
    return AgriAnswer("rank", rule, "No monitored area has enough data for a risk estimate.\n" + caveats,
                      [a.area_id for a in unranked])
