"""Read-only /api/agri/* endpoints: the risk engine's assessments, shaped for the dashboard.

Agricultural data -> risk engine -> this API -> dashboard. Nothing here computes a risk figure:
ranks, levels, scores, points, reasons, confidence and provenance are copied from the engine's
`RiskAssessment`; this module only adds geometry for the map and the dashboard-wide notices
(placeholder thresholds, SAMPLE data, demo areas vs official boundaries).

  GET  /api/agri/overview          every monitored area, ranked, with level counts and notices
  GET  /api/agri/areas/{area_id}   one area's full assessment, for the "Why is this area at risk?" drawer
  POST /api/agri/query             an agricultural question in plain words (read-only: nothing is changed)
"""

from typing import Literal

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from satquery import geo
from satquery.agri import query as agri_query
from satquery.agri.models import (DISCLAIMER, PLACEHOLDER_NOTE, SAMPLE_LABEL, DataState, FactorStatus,
                                  MonitoredArea, RiskAssessment, RiskLevel, ThresholdStatus)
from satquery.agri.service import AgriUnavailable, AssessmentService, Snapshot

LEVELS = ("CRITICAL", "HIGH", "MODERATE", "LOW", "INSUFFICIENT_DATA")


class AreaSummary(BaseModel):
    """One monitored area as the map and the priority list show it. Figures come from the engine."""

    id: str
    name: str
    kind: Literal["district", "custom", "demo"]
    official_boundary: bool  # True only for an administrative district from a named dataset
    boundary_source: str
    district: str | None
    state: str | None
    geometry: dict
    label_point: tuple[float, float]  # (longitude, latitude) inside the area
    bounds: tuple[float, float, float, float]
    rank: int | None
    rank_of: int | None
    level: RiskLevel
    score: float | None
    headline: str
    confidence: Literal["low", "medium", "high"]
    data_completeness: float
    top_factors: list[str]
    factor_points: dict[str, float | None]
    factor_status: dict[str, FactorStatus]
    includes_sample_data: bool
    thresholds_status: ThresholdStatus


class AgriOverview(BaseModel):
    computed_at: str
    as_of: str | None
    region: str
    view_bounds: tuple[float, float, float, float] | None
    thresholds_status: ThresholdStatus
    thresholds_note: str | None  # set while thresholds are placeholders
    includes_sample_data: bool
    sample_label: str
    disclaimer: str
    area_note: str
    official_boundaries: bool
    offline: bool
    data_states: list[DataState]
    counts: dict[str, int]
    examples: list[str]
    areas: list[AreaSummary]


class AgriAreaDetail(BaseModel):
    area: AreaSummary
    assessment: RiskAssessment
    boundary_note: str
    thresholds_note: str | None
    sample_label: str


class AgriQueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    selected_area_id: str | None = None


class AgriQueryResult(BaseModel):
    intent: Literal["rank", "inspect", "explain", "unmatched"]
    matched_rule: str
    answer: str
    area_ids: list[str]
    focus_area_id: str | None
    computed_at: str
    thresholds_status: ThresholdStatus
    includes_sample_data: bool
    disclaimer: str
    language: Literal["english", "latin_manipuri"] = "english"
    common_intent: str | None = None  # satquery.agent.language.INTENTS; None when the question must be rephrased


def summarise(area: MonitoredArea, a: RiskAssessment) -> AreaSummary:
    return AreaSummary(
        id=area.id, name=area.name, kind=area.kind, official_boundary=area.kind == "district",
        boundary_source=area.boundary_source, district=area.district, state=area.state, geometry=area.geometry,
        label_point=geo.representative_point(area.geometry), bounds=geo.geometry_bounds(area.geometry),
        rank=a.rank, rank_of=a.rank_of, level=a.level, score=a.score, headline=a.headline,
        confidence=a.confidence.level, data_completeness=a.confidence.data_completeness, top_factors=a.top_factors,
        factor_points={f.id: f.points for f in a.factors}, factor_status={f.id: f.status for f in a.factors},
        includes_sample_data=a.includes_sample_data, thresholds_status=a.thresholds_status)


def boundary_note(area: MonitoredArea) -> str:
    if area.kind == "district":
        return f"Administrative district outline from: {area.boundary_source}."
    if area.kind == "demo":
        return "Demo monitoring rectangle drawn by the team: not an administrative boundary."
    return "An area drawn by a user: not an administrative boundary."


def overview(snapshot: Snapshot) -> AgriOverview:
    summaries = [summarise(snapshot.areas[a.area_id], a) for a in snapshot.assessments]
    official = [s for s in summaries if s.official_boundary]
    demo = [s for s in summaries if s.kind == "demo"]
    notes = []
    if demo:
        notes.append(f"{len(demo)} demo monitoring rectangle(s) over valley farmland: not administrative boundaries.")
    if official:
        notes.append(f"{len(official)} district(s) with administrative outlines from a named dataset.")
    else:
        notes.append("Verified district boundaries are not loaded yet.")
    bounds = [s.bounds for s in summaries]
    view = (min(b[0] for b in bounds), min(b[1] for b in bounds), max(b[2] for b in bounds),
            max(b[3] for b in bounds)) if bounds else None
    status = snapshot.assessments[0].thresholds_status if snapshot.assessments else "PLACEHOLDER"
    states = sorted({p.state for a in snapshot.assessments for p in a.provenance})
    return AgriOverview(
        computed_at=snapshot.computed_at, as_of=snapshot.assessments[0].as_of if snapshot.assessments else None,
        region="Manipur", view_bounds=view, thresholds_status=status,
        thresholds_note=PLACEHOLDER_NOTE if status == "PLACEHOLDER" else None,
        includes_sample_data=any(a.includes_sample_data for a in snapshot.assessments), sample_label=SAMPLE_LABEL,
        disclaimer=DISCLAIMER, area_note=" ".join(notes), official_boundaries=bool(official), offline=snapshot.offline,
        data_states=states, counts={level: sum(1 for s in summaries if s.level == level) for level in LEVELS},
        examples=agri_query.EXAMPLES, areas=summaries)


def _unavailable(error: AgriUnavailable) -> JSONResponse:
    return JSONResponse(status_code=503, content={"code": "agri_unavailable", "message": str(error)})


def agri_router(service: AssessmentService) -> APIRouter:
    router = APIRouter(prefix="/api/agri", tags=["agri"])

    @router.get("/overview", response_model=AgriOverview)
    def get_overview():
        try:
            return overview(service.snapshot())
        except AgriUnavailable as error:
            return _unavailable(error)

    @router.get("/areas/{area_id}", response_model=AgriAreaDetail)
    def get_area(area_id: str):
        try:
            snapshot = service.snapshot()
        except AgriUnavailable as error:
            return _unavailable(error)
        found = snapshot.assessment(area_id)
        if found is None:
            return JSONResponse(status_code=404, content={"code": "unknown_area",
                                                          "message": f"No monitored area has the id '{area_id}'."})
        area = snapshot.areas[area_id]
        return AgriAreaDetail(area=summarise(area, found), assessment=found, boundary_note=boundary_note(area),
                              thresholds_note=PLACEHOLDER_NOTE if found.thresholds_status == "PLACEHOLDER" else None,
                              sample_label=SAMPLE_LABEL)

    @router.post("/query", response_model=AgriQueryResult)
    def ask(request: AgriQueryRequest):
        try:
            snapshot = service.snapshot()
        except AgriUnavailable as error:
            return _unavailable(error)
        found = agri_query.answer(request.query, snapshot.assessments, list(snapshot.areas.values()),
                                  request.selected_area_id)
        status = snapshot.assessments[0].thresholds_status if snapshot.assessments else "PLACEHOLDER"
        return AgriQueryResult(intent=found.intent, matched_rule=found.matched_rule, answer=found.answer,
                               area_ids=found.area_ids, focus_area_id=found.focus_area_id,
                               computed_at=snapshot.computed_at, thresholds_status=status,
                               includes_sample_data=any(a.includes_sample_data for a in snapshot.assessments),
                               disclaimer=DISCLAIMER, language=found.language, common_intent=found.common_intent)

    return router
