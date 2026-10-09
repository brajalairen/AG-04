"""Answers in the asker's language: a Latin Manipuri question gets a Latin Manipuri answer (English is unchanged).

AG-04's answers are written by code from the engine's results, not by a language model (the only model, the
Falcon remote-sensing VLM, writes no Manipuri), so this is a template layer. The Latin Manipuri sentences are
data: Member_A/manipuri_responses.json, one template per message, with slots ({level}, {score},
{confidence}, ...) that code fills with the engine's own values. Nothing numerical or scientific passes through
a template unfilled or reworded: scores, levels, confidence, the engine's reasons (its evidence) and the NDVI
figures are inserted exactly as the engine gives them.

A message without a usable template stays in English, so an unwritten sentence never drops a value or a warning.
A template is unusable when its slots differ from the English message's, when it leaves out a word the message
must keep (PLACEHOLDER, SAMPLE), or when it claims what the engine cannot (a confirmed diagnosis).
"""

import json
import os
import re
from functools import lru_cache
from pathlib import Path

from satquery.agent.language import LATIN_MANIPURI
from satquery.agri.models import SAMPLE_LABEL

DEFAULT_RESPONSES = Path(__file__).resolve().parent / "assets" / "manipuri_responses.json"

# Every message the Latin Manipuri answers use, in English: the fallback, and the source for a translator.
MESSAGES = {
    "area_risk": "Indicators suggest {level} risk for this area.",
    "area_pest_risk": "Indicators suggest {level} pest risk for this area.",
    "score": "Risk score: {score}.",
    "confidence": "Data confidence: {confidence}.",
    "rank_position": "Rank #{rank} of {rank_of} assessed areas.",
    "not_ranked": "Not ranked: not enough data.",
    "why": "Why:",
    "ranking_head": "Indicators suggest HIGH or CRITICAL risk in {count} of {total} monitored areas:",
    "ranking_none": "No monitored area is at HIGH or CRITICAL risk by the current indicators. Highest:",
    "no_estimate": "No monitored area has enough data for a risk estimate.",
    "tally": "Moderate: {moderate}, low: {low}, not enough data: {no_data} of {total} monitored areas.",
    "inspect_head": "Suggested order for field inspection, by risk rank (decision support; the final choice rests "
                    "with the Department):",
    "inspect_none": "No monitored area has enough data for a risk estimate, so no inspection order can be suggested.",
    "not_ranked_list": "Not ranked for lack of data: {names}.",
    "mainly": "mainly {drivers}",
    "caveat_placeholder": "PLACEHOLDER thresholds: prototype scores, not validated agricultural findings.",
    "caveat_sample": "Pest-report figures are " + SAMPLE_LABEL + ".",
    "caveat_decision": "Decision support only; the final assessment rests with the Department of Agriculture.",
    "verify_advice": "Field inspection and verification by an agricultural expert are recommended.",
    "select_area": "Select one of the monitored areas on the map (or name it) to see why it is flagged. Assessing a "
                   "newly drawn area is planned for a later phase.",
    "ambiguous_area": "'{phrase}' matches several monitored areas: {names}. Please name one.",
    "no_area_match": "No monitored area matches this question. Monitored areas: {names}.",
    "rephrase": "This question could not be matched with confidence to a crop & pest risk question, so it was not "
                "sent to satellite image analysis either. The risk engine answers which areas are at high risk, why "
                "a named or selected area is flagged, and which areas to inspect first. For example: {examples}",
    "crop_health_head": "Crop health of this area from satellite NDVI (an indicator of vegetation vigour, not a "
                        "diagnosis):",
}
# Words a template must keep, because the warning is in them.
REQUIRED = {"caveat_placeholder": ("PLACEHOLDER",), "caveat_sample": ("SAMPLE",)}
# Claims the engine never makes: a template saying them is refused.
UNSUPPORTED = re.compile(r"confirm|detected|outbreak", re.I)
SLOT = re.compile(r"\{(\w+)\}")


def usable(key: str, text: str | None) -> bool:
    """Whether a template may stand in for MESSAGES[key] (see the module docstring)."""
    if key not in MESSAGES or not text or not text.strip() or "<" in text:
        return False
    if set(SLOT.findall(text)) != set(SLOT.findall(MESSAGES[key])):
        return False
    if any(word not in text for word in REQUIRED.get(key, ())):
        return False
    return not UNSUPPORTED.search(text)


@lru_cache(maxsize=4)
def _templates(path: str) -> tuple[str | None, dict[str, str]]:
    file = Path(path)
    if not file.is_file():
        return None, {}
    data = json.loads(file.read_text(encoding="utf-8"))
    found = {key: entry.get("text") for key, entry in (data.get("templates") or {}).items()}
    return data.get("status"), {key: text for key, text in found.items() if usable(key, text)}


def templates() -> tuple[str | None, dict[str, str]]:
    return _templates(os.environ.get("SATQUERY_MANIPURI_RESPONSES") or str(DEFAULT_RESPONSES))


def say(key: str, language: str, **slots) -> str:
    """MESSAGES[key] in `language`, with its slots filled; English when no usable template exists."""
    template = templates()[1].get(key) if language == LATIN_MANIPURI else None
    return (template or MESSAGES[key]).format(**slots)


# ----------------------------------------------------------------------- answers (Latin Manipuri only)

def _score(a) -> str:
    return f"{a.score:.0f}/100" if a.score is not None else "no score"


def _area(a, pest: bool = False) -> str:
    """Level, score and confidence of one assessment, exactly as the engine gives them."""
    return " ".join([say("area_pest_risk" if pest else "area_risk", LATIN_MANIPURI, level=a.level),
                     say("score", LATIN_MANIPURI, score=_score(a)),
                     say("confidence", LATIN_MANIPURI, confidence=a.confidence.level)])


def _caveats(assessments) -> list[str]:
    lines = [say("caveat_placeholder", LATIN_MANIPURI)] if any(a.thresholds_status == "PLACEHOLDER"
                                                                for a in assessments) else []
    if any(a.includes_sample_data for a in assessments):
        lines.append(say("caveat_sample", LATIN_MANIPURI))
    return lines + [say("caveat_decision", LATIN_MANIPURI)]


def _close(assessments) -> list[str]:
    return _caveats(assessments) + [say("verify_advice", LATIN_MANIPURI)]


def explain(a, assessments, pest: bool) -> str:
    rank = (say("rank_position", LATIN_MANIPURI, rank=a.rank, rank_of=a.rank_of) if a.rank
            else say("not_ranked", LATIN_MANIPURI))
    reasons = [f"- {r}" for r in a.reasons[:5]]  # the engine's evidence, verbatim
    return "\n".join([f"{a.area_name}: {_area(a, pest)} {rank}", say("why", LATIN_MANIPURI), *reasons,
                      *_close(assessments)])


def rank(assessments, ranked, severe) -> str:
    counts = {level: sum(1 for a in assessments if a.level == level)
              for level in ("MODERATE", "LOW", "INSUFFICIENT_DATA")}
    tally = say("tally", LATIN_MANIPURI, moderate=counts["MODERATE"], low=counts["LOW"],
                no_data=counts["INSUFFICIENT_DATA"], total=len(assessments))
    if severe:
        lines = [say("ranking_head", LATIN_MANIPURI, count=len(severe), total=len(assessments))]
        lines += [f"#{a.rank} {a.area_name}: {_area(a)}" for a in severe]
    elif ranked:
        lines = [say("ranking_none", LATIN_MANIPURI), f"#{ranked[0].rank} {ranked[0].area_name}: {_area(ranked[0])}"]
    else:
        return "\n".join([say("no_estimate", LATIN_MANIPURI), *_caveats(assessments)])
    return "\n".join([*lines, tally, *_close(assessments)])


def inspect(assessments, top, unranked, drivers) -> str:
    if not top:
        return "\n".join([say("inspect_none", LATIN_MANIPURI), *_caveats(assessments)])
    lines = [say("inspect_head", LATIN_MANIPURI)]
    lines += [f"{i}. {a.area_name}: {_area(a)} ({say('mainly', LATIN_MANIPURI, drivers=drivers(a))})"
              for i, a in enumerate(top, 1)]
    if unranked:
        lines.append(say("not_ranked_list", LATIN_MANIPURI, names=", ".join(a.area_name for a in unranked)))
    return "\n".join([*lines, *_close(assessments)])


def crop_health(english_answer: str) -> str:
    """The NDVI figures and their caveats stay exactly as measured; the framing is in Latin Manipuri."""
    return "\n".join([say("crop_health_head", LATIN_MANIPURI), english_answer,
                      say("verify_advice", LATIN_MANIPURI)])
