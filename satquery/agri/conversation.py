"""Conversation follow-ups: turn "Why?" or "What about Thoubal?" into the complete question the router already answers.

AG-04 answers one question at a time, and a follow-up on its own ("Why?") would be read without the question before
it. This module adds nothing to the answering: it only rewrites a follow-up into a complete English question
("Why is Thoubal flagged?"), using the context the client sends back from the previous answer (its intent, the area
it was about and the areas it listed), and the client then asks that question exactly as if it had been typed.
Routing, the risk engine, the answer text and every figure and warning stay those of the existing system.

Stateless: the server keeps no conversation; the context travels with each message. Rule-based, like the rest of the
agent, with no language model. A follow-up that cannot be tied to one area gets a clarifying question, never a guess,
and is never sent on to satellite analysis. Complete questions, and every Latin Manipuri question, pass through
unchanged (v1 resolves English follow-ups only).
"""

import difflib
import re

from fastapi import APIRouter
from pydantic import BaseModel, Field

from satquery.agent.language import LATIN_MANIPURI, normalize
from satquery.agri.models import MonitoredArea
from satquery.agri.query import aliases, resolve_area
from satquery.agri.service import AssessmentService

LEAD = r"^(?:(?:and|but|so|ok|okay|then)[ ,]+)*"
END = r"[\s?.!]*$"
# "Why?", "Why is that?", "Why is it so high?", "Explain", "Tell me more", "What are the reasons?"
WHY = re.compile(LEAD + r"(?:why(?: (?:is|was) (?:it|that|this|that one)| so| that| there| that one)?"
                 r"(?: (?:so )?(?:high|risky|flagged|at risk|prioriti[sz]ed|first|ranked (?:first|high)))?(?: there)?"
                 r"|how come|explain(?: (?:it|that|this|that one))?|tell me more(?: about (?:it|that|this|that one))?"
                 r"|tell me why|more details|(?:what are )?the reasons?)" + END, re.I)
# "What about Thoubal?", "How about the second one?": always a follow-up about the named thing.
ABOUT = re.compile(LEAD + r"(?:what|how) about (?:the )?(?P<target>.+?)" + END, re.I)
# "And Kakching?", "And the second one?": a follow-up only when what follows is an area or a list position.
AND = re.compile(r"^(?:and|then)(?: in| for| at)? (?:the )?(?P<target>.+?)" + END, re.I)
ORDINAL = re.compile(r"^(?:the )?(?:(?P<word>first|second|third|fourth|fifth|top|last|1st|2nd|3rd|4th|5th)"
                     r"(?: one| area| zone)?|(?:number|no\.?|#) ?(?P<number>\d+))$", re.I)
ORDINALS = {"first": 0, "1st": 0, "top": 0, "second": 1, "2nd": 1, "third": 2, "3rd": 2, "fourth": 3, "4th": 3,
            "fifth": 4, "5th": 4, "last": -1}
# "Is there pest risk there?": a trailing "there" / "that area" stands for the area in focus.
THERE = re.compile(r"\b(?:in that (?:area|place|zone)|that (?:area|place|zone)|there)(?=" + END[:-1] + r"$)", re.I)
NEEDS_AN_AREA = {"WEATHER_RISK": "weather forecast", "CROP_HEALTH": "crop-health (NDVI) analysis",
                 "IMAGERY": "satellite image analysis"}


class ChatContext(BaseModel):
    """What the previous answer was about, as the client read it from that answer."""
    last_query: str | None = None
    last_intent: str | None = None  # a satquery.agent.language.INTENTS key, or "IMAGERY"
    focus_area_id: str | None = None
    area_ids: list[str] = Field(default_factory=list)  # the areas the last ranking or inspection list gave, in order
    language: str | None = None


class ChatResolveRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    context: ChatContext = Field(default_factory=ChatContext)


class ChatResolveResult(BaseModel):
    query: str | None  # the complete question to ask; None when a clarification is needed instead
    rewritten: bool  # True when `query` differs from the message
    rule: str  # how the message was read
    clarification: str | None  # asked back to the user instead of guessing
    area_id: str | None  # the area a follow-up was tied to


def display_name(area: MonitoredArea, areas: list[MonitoredArea]) -> str:
    """The shortest place name that the existing area matcher resolves to this area alone."""
    for alias in aliases(area):
        if resolve_area(alias, areas)[0] == [area]:
            return alias.title()
    return area.name


def find_areas(phrase: str, areas: list[MonitoredArea]) -> list[MonitoredArea]:
    """Areas a spoken or typed name refers to; a close misspelling ("Thobal") counts when only one name is close."""
    found = resolve_area(phrase, areas)[0]
    if found:
        return found
    names = {alias: area for area in areas for alias in aliases(area)}
    close = difflib.get_close_matches(phrase.lower().strip(), list(names), n=2, cutoff=0.75)
    return [names[close[0]]] if len(close) == 1 else []


def is_area_or_position(phrase: str, areas: list[MonitoredArea]) -> bool:
    """Whether a whole phrase is just a place name or a list position ("Thoubal", "the second one")."""
    phrase = phrase.strip().lower()
    names = {alias for area in areas for alias in aliases(area)}
    return bool(ORDINAL.match(phrase)) or phrase in names or len(difflib.get_close_matches(phrase, list(names),
                                                                                         n=2, cutoff=0.8)) == 1


def _known(areas: list[MonitoredArea]) -> str:
    return ", ".join(display_name(a, areas) for a in areas)


def _clarify(rule: str, text: str) -> ChatResolveResult:
    return ChatResolveResult(query=None, rewritten=False, rule=rule, clarification=text, area_id=None)


def _ask(message: str, query: str, rule: str, area: MonitoredArea | None) -> ChatResolveResult:
    return ChatResolveResult(query=query, rewritten=query != message, rule=rule, clarification=None,
                             area_id=area.id if area else None)


def _question_about(area: MonitoredArea, areas: list[MonitoredArea], context: ChatContext) -> tuple[str | None, str]:
    """The complete question that asks the previous question again, about `area`."""
    name = display_name(area, areas)
    if context.last_intent in NEEDS_AN_AREA:
        what = NEEDS_AN_AREA[context.last_intent]
        return None, (f"The {what} needs an area drawn on the map (or an image). Draw one over {name} and ask "
                      f"again, or ask about its crop & pest risk, e.g. 'Why is {name} flagged?'")
    if context.last_intent == "PEST_RISK":
        return f"Is there pest risk in {name}?", "pest-risk follow-up"
    return f"Why is {name} flagged?", "area follow-up"


def resolve(message: str, context: ChatContext, areas: list[MonitoredArea]) -> ChatResolveResult:
    text = message.strip()
    if normalize(text).language == LATIN_MANIPURI:
        return _ask(message, text, "Latin Manipuri question: asked as it is (v1 resolves English follow-ups only)",
                    None)
    by_id = {a.id: a for a in areas}
    listed = [by_id[i] for i in context.area_ids if i in by_id]
    focus = by_id.get(context.focus_area_id or "") or (listed[0] if listed else None)

    if WHY.match(text):
        if not focus:
            return _clarify("'why' follow-up without an area", "Which area do you mean? Ask 'Which areas are at "
                            f"high risk?' first, or name one of the monitored areas: {_known(areas)}.")
        name = display_name(focus, areas)
        return _ask(message, f"Why is {name} flagged?", f"'why' follow-up about {name}", focus)

    about = ABOUT.match(text)
    joined = AND.match(text)
    bare = text.rstrip(" ?.!")
    if about:
        target = about.group("target")
    elif joined and is_area_or_position(joined.group("target"), areas):
        target = joined.group("target")
    elif is_area_or_position(bare, areas):
        target = bare
    else:
        target = None
    if target:
        ordinal = ORDINAL.match(target.strip())
        if ordinal:
            word = ordinal.group("word")
            index = ORDINALS[word.lower()] if word else int(ordinal.group("number")) - 1
            if not listed:
                return _clarify("list follow-up without a list", "Which list do you mean? Ask 'Which areas are at "
                                "high risk?' or 'Which should we inspect first?' first.")
            if not -len(listed) <= index < len(listed):
                names = ", ".join(display_name(a, areas) for a in listed)
                return _clarify("list follow-up beyond the list", f"The last list had only {len(listed)} "
                                f"area{'s' if len(listed) != 1 else ''}: {names}. Which one do you mean?")
            area = listed[index]
            query, rule = _question_about(area, areas, context)
            if not query:
                return _clarify("follow-up needs a drawn area", rule)
            return _ask(message, query, f"{rule} ('{ordinal.group(0)}' in the last list)", area)
        found = find_areas(target, areas)
        if len(found) == 1:
            query, rule = _question_about(found[0], areas, context)
            return _ask(message, query, rule, found[0]) if query else _clarify("follow-up needs a drawn area", rule)
        if len(found) > 1:
            return _clarify("follow-up matches several areas", f"'{target}' matches several monitored areas: "
                            f"{_known(found)}. Which one?")
        if about:
            return _clarify("follow-up about an unknown area", f"I couldn't find a monitored area called "
                            f"'{target}'. Monitored areas: {_known(areas)}.")

    there = THERE.search(text)
    if there and focus and not resolve_area(text, areas)[0]:
        name = display_name(focus, areas)
        query = text[:there.start()] + f"in {name}" + text[there.end():]
        return _ask(message, query, f"'{there.group(0)}' read as {name}", focus)

    return _ask(message, text, "complete question: asked as it is", None)


def chat_router(service: AssessmentService) -> APIRouter:
    router = APIRouter(prefix="/api/chat", tags=["chat"])

    @router.post("/resolve", response_model=ChatResolveResult)
    def resolve_message(request: ChatResolveRequest) -> ChatResolveResult:
        return resolve(request.message, request.context, service.areas())

    return router
