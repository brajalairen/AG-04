"""Phase 3 read-only API views: area status, priorities, explanation, history and vocabulary.

Built only from the engine's assessments and the service snapshot: nothing is scored here. Each
input carries trust labels that keep four questions apart:

  origin        REAL (from a named external source) / SAMPLE (synthetic) / UNAVAILABLE
  freshness     LIVE / CACHED / STALE / SNAPSHOT / SAMPLE / UNAVAILABLE
  verification  VERIFIED / UNVERIFIED (field observations) or NOT_APPLICABLE (weather, satellite)
  calibration   UNCALIBRATED until the score is validated against outcomes

so real weather is REAL but not "verified pest evidence", a SAMPLE record is never VERIFIED, and a
KVK-verified observation is REAL + VERIFIED. Limitations carry stable codes (with English text) so
the dashboard and a future Manipuri layer can translate them without parsing sentences.
"""

from typing import Literal

from pydantic import BaseModel

from satquery import geo
from satquery.agri import escalation
from satquery.agri.areas import extent_km
from satquery.agri.config import ObservationRulesConfig, load_observation_rules
from satquery.agri.escalation import AttentionStatus
from satquery.agri.history import AssessmentHistory, HistoryEntry
from satquery.agri.inspections import VERIFICATION_MEANING
from satquery.agri.models import (DISCLAIMER, SAMPLE_LABEL, FactorResult, FactorStatus, MonitoredArea, NdviWindow,
                                  Provenance, RiskAssessment, RiskLevel, ThresholdStatus)
from satquery.agri.risk import EVIDENCE_STATES, NDVI_CAVEAT, weather_calculation

Origin = Literal["REAL", "SAMPLE", "UNAVAILABLE"]
Freshness = Literal["LIVE", "CACHED", "STALE", "SNAPSHOT", "SAMPLE", "UNAVAILABLE"]
Verification = Literal["VERIFIED", "UNVERIFIED", "NOT_APPLICABLE"]
Confidence = Literal["low", "medium", "high"]
LANGUAGE = "en"
RANKING_BASIS = ("Engine order: risk level, then score, then data completeness (at equal scores the area with more "
                 "real data comes first, so missing data never lifts an area), then name. Areas with too little real "
                 "data are listed last, without a rank.")
RANKING_NOTE = ("A rank orders areas by how much attention the available evidence suggests. It is not evidence that a "
                "pest or disease is present, and the score is an uncalibrated prototype indication.")
WEATHER_NOTE = ("Open-Meteo model data: past days are the weather model's analyses and short-range forecasts for one "
                "grid cell, not station observations; forecast days are forecasts.")
INSPECTION_NOTE = ("No field-inspection workflow is connected yet (checklist P1.4). Verified observations can only come "
                   "from a REAL dataset whose records are marked verified; none is connected.")


# ------------------------------------------------------------------------------------- models

class TrustLabels(BaseModel):
    origin: Origin
    synthetic: bool
    freshness: Freshness
    verification: Verification
    labels: list[str]


class InputStatus(BaseModel):
    input: Literal["weather", "ndvi", "pest_observations"]
    status: FactorStatus
    trust: TrustLabels
    source: str | None
    retrieved_at: str | None
    covers: str | None
    unavailable_reason: str | None


class RulesStatus(BaseModel):
    weather_rules: ThresholdStatus
    weather_rules_version: str
    observation_rules: ThresholdStatus | None  # None: the file could not be loaded
    observation_rules_version: str | None
    risk_model: ThresholdStatus
    risk_model_version: str
    calibration: Literal["UNCALIBRATED", "VALIDATED"]
    missing_inputs_policy: str


class BoundaryStatus(BaseModel):
    kind: Literal["district", "custom", "demo"]
    official: bool
    status: Literal["OFFICIAL_SOURCED", "DEMO_NOT_OFFICIAL", "USER_DRAWN_NOT_OFFICIAL"]
    source: str
    note: str


class Limitation(BaseModel):
    code: str
    severity: Literal["info", "caution", "warning"]
    message: str


class AreaStatus(BaseModel):
    id: str
    name: str
    district: str | None
    state: str | None
    boundary: BoundaryStatus
    label_point: tuple[float, float]
    bounds: tuple[float, float, float, float]
    rank: int | None
    rank_of: int | None
    level: RiskLevel
    score: float | None
    score_range: tuple[float, float] | None
    score_without_sample: float | None
    level_without_sample: RiskLevel | None
    confidence: Confidence
    data_completeness: float
    assessed_at: str
    computed_at: str
    mode: Literal["live", "snapshot"]
    freshness: Freshness
    driver_pest: str | None
    includes_sample_data: bool
    calibration: Literal["UNCALIBRATED", "VALIDATED"]
    thresholds_status: ThresholdStatus
    inputs: list[InputStatus]
    labels: list[str]
    summary: str
    limitations: list[Limitation]


class AreaList(BaseModel):
    computed_at: str
    mode: Literal["live", "snapshot"]
    offline: bool
    snapshot_saved_at: str | None
    fallback_reason: str | None
    region: str
    rules: RulesStatus
    sample_label: str
    disclaimer: str
    language: str
    areas: list[AreaStatus]


class FactorPoints(BaseModel):
    weather: float | None
    ndvi: float | None
    pest_observations: float | None


class PriorityItem(BaseModel):
    rank: int | None
    rank_of: int | None
    area_id: str
    area_name: str
    district: str | None
    official_boundary: bool
    level: RiskLevel
    score: float | None
    score_range: tuple[float, float] | None
    confidence: Confidence
    data_completeness: float
    driver_pest: str | None
    contributions: FactorPoints
    evidence_summary: str
    labels: list[str]
    attention: AttentionStatus


class PriorityList(BaseModel):
    computed_at: str
    mode: Literal["live", "snapshot"]
    ranking_basis: str
    note: str
    disclaimer: str
    items: list[PriorityItem]


class AreaRef(BaseModel):
    id: str
    name: str
    district: str | None
    state: str | None
    boundary: BoundaryStatus
    label_point: tuple[float, float]
    bounds: tuple[float, float, float, float]


class OverallView(BaseModel):
    level: RiskLevel
    score: float | None
    score_range: tuple[float, float] | None
    score_without_sample: float | None
    level_without_sample: RiskLevel | None
    rank: int | None
    rank_of: int | None
    confidence: Confidence
    confidence_method: str
    confidence_notes: list[str]
    data_completeness: float
    assessed_at: str
    computed_at: str
    mode: Literal["live", "snapshot"]
    freshness: Freshness
    calibration: Literal["UNCALIBRATED", "VALIDATED"]
    thresholds_status: ThresholdStatus
    driver_pest: str | None
    headline: str
    summary: str


class WeatherDay(BaseModel):
    date: str
    period: Literal["past", "forecast"]
    data_kind: Literal["MODEL_ANALYSIS", "FORECAST"]
    favourable: bool | None
    values: dict[str, float | None]
    unmet: list[str]


class WeatherPest(BaseModel):
    pest_id: str
    name: str
    rule_status: ThresholdStatus
    conditions: list[str]
    index: float | None
    calculation: dict
    days: list[WeatherDay]


class WeatherView(BaseModel):
    status: FactorStatus
    points: float | None   # the driving pest's weather points in the area score
    weight: float
    trust: TrustLabels
    unavailable_reason: str | None
    grid_point: dict | None
    summary: dict | None   # past and next 7 days: temperature, humidity, rainfall
    data_note: str
    pests: list[WeatherPest]
    provenance: list[Provenance]


class NdviView(BaseModel):
    status: FactorStatus
    points: float | None
    weight: float
    trust: TrustLabels
    unavailable_reason: str | None
    current: NdviWindow | None
    baseline: list[NdviWindow]
    baseline_mean: float | None
    baseline_range: tuple[float, float] | None
    relative_change: float | None
    absolute_change: float | None
    within_baseline_range: bool | None
    method: str | None
    caveat: str
    provenance: list[Provenance]


class ObservationView(BaseModel):
    id: str
    pest: str
    observed_on: str
    status: Literal["REAL", "SAMPLE"]
    synthetic: bool
    verification: Literal["VERIFIED", "UNVERIFIED"]
    severity: str | None
    severity_basis: str | None
    metric: str | None
    value: float | None
    unit: str | None
    match: str | None
    spatial_resolution: str | None
    district: str | None
    source: str
    source_url: str | None
    label: str | None


class PestView(BaseModel):
    pest_id: str
    name: str
    crop: str
    assessment: Literal["ASSESSED", "INSUFFICIENT_DATA"]
    level: RiskLevel
    score: float | None
    score_range: tuple[float, float] | None
    data_completeness: float
    has_weather_rule: bool
    weather_rule_status: ThresholdStatus | None
    contributions: FactorPoints
    evidence_state: str | None
    evidence: str | None
    observation_trust: TrustLabels
    observations: list[ObservationView]
    historical_count: int
    summary: str


class NotAssessedView(BaseModel):
    pest_id: str
    name: str
    assessment: Literal["NOT_ASSESSED"]
    reason: str


class PestsView(BaseModel):
    assessed: list[PestView]
    not_assessed: list[NotAssessedView]


class RuleSource(BaseModel):
    kind: Literal["weather_rule", "etl"]
    pest_id: str
    status: ThresholdStatus
    sources: list[dict]


class FieldVerification(BaseModel):
    status: Literal["NO_INSPECTION_WORKFLOW"]
    verified_observations: int
    unverified_real_observations: int
    sample_observations: int
    note: str


class ProvenanceView(BaseModel):
    inputs: list[InputStatus]
    sources: list[Provenance]
    rules: RulesStatus
    rule_sources: list[RuleSource]


class AreaExplanation(BaseModel):
    area: AreaRef
    overall: OverallView
    weather: WeatherView
    ndvi: NdviView
    pests: PestsView
    attention: AttentionStatus
    field_verification: FieldVerification
    provenance: ProvenanceView
    limitations: list[Limitation]
    reasons: list[str]
    disclaimer: str
    sample_label: str
    language: str


class AreaHistory(BaseModel):
    area_id: str
    enabled: bool
    entries: list[HistoryEntry]  # oldest first
    note: str


class Vocabulary(BaseModel):
    language: str
    trust_labels: dict[str, str]
    evidence_states: dict[str, str]
    verification_statuses: dict[str, str]
    escalation_stages: dict[str, str]
    limitations: dict[str, str]
    pest_assessment: dict[str, str]
    risk_levels: dict[str, str]


# ------------------------------------------------------------------------------- vocabulary

TRUST_LABELS = {
    "REAL": "from a named external source (weather model, satellite, or a field-observation dataset)",
    "SAMPLE": "synthetic prototype data, labelled " + SAMPLE_LABEL,
    "SYNTHETIC": "generated, not observed",
    "UNAVAILABLE": "no usable data; the input adds nothing to the score and is never estimated",
    "LIVE": "fetched for this assessment",
    "CACHED": "fetched earlier and reused within its freshness limit",
    "STALE": "an older cached copy shown because the provider could not be reached or offline mode is on",
    "SNAPSHOT": "from a frozen earlier assessment, not live",
    "VERIFIED": "a rule or field observation checked and accepted by a named verifier on a recorded date",
    "UNVERIFIED": "a field observation not yet checked and accepted by a named expert",
    "NOT_APPLICABLE": "verification does not apply (weather and satellite data are measurements or model output)",
    "MODEL_DATA": "weather model analyses and forecasts, not station observations",
    "SATELLITE": "Copernicus Sentinel-2 imagery through SatQueryAI",
    "PLACEHOLDER": "thresholds or weights not yet verified against a cited source",
    "UNCALIBRATED": "the score is not validated against field outcomes",
    "DEMO_AREA": "a demo monitoring rectangle, not an administrative boundary",
    "USER_AREA": "an area drawn by a user, not an administrative boundary",
    "INSUFFICIENT_DATA": "too little real data for a risk level",
}
LIMITATIONS = {
    "INSUFFICIENT_DATA": "Too little real data for a risk level.",
    "NOT_A_DETECTION": "Indicators suggest a level of risk; this assessment does not establish that a pest or disease "
                       "is present. Decision support only.",
    "WEATHER_UNAVAILABLE": "Weather is unavailable, so no weather points are given.",
    "WEATHER_MODEL_DATA": WEATHER_NOTE,
    "WEATHER_STALE": "Weather is an older cached copy.",
    "WEATHER_SINGLE_POINT": "Weather is for one point inside the area; conditions can differ across it.",
    "WEATHER_INDEX_SATURATED": "The weather index is capped: zones with different numbers of favourable days get the "
                               "same weather points.",
    "NDVI_UNAVAILABLE": "Vegetation (NDVI) is unavailable, so no NDVI points are given.",
    "NDVI_PARTIAL_BASELINE": "Fewer earlier years than configured could be observed clearly for the NDVI baseline.",
    "NDVI_NOT_PEST_DETECTION": NDVI_CAVEAT,
    "PEST_EVIDENCE_SAMPLE": "Pest/disease field evidence is " + SAMPLE_LABEL + ": synthetic, not real observations.",
    "NO_REAL_PEST_EVIDENCE": "No real pest/disease field observations are available for this area.",
    "UNVERIFIED_PEST_EVIDENCE": "Real field observations are present but not verified by a named expert.",
    "LEVEL_DEPENDS_ON_SAMPLE": "Without the SAMPLE evidence the risk level would be lower.",
    "PESTS_NOT_ASSESSED": "Some known pests/diseases have no weather rule and no field evidence, so they are not assessed.",
    "PLACEHOLDER_THRESHOLDS": "Thresholds are PLACEHOLDERS awaiting agronomic verification.",
    "UNCALIBRATED_SCORE": "The score is an uncalibrated prototype: weights and bands are not validated against field "
                          "outcomes, and it is not a probability.",
    "AREA_NOT_OFFICIAL": "This area is not an official administrative boundary.",
    "SNAPSHOT_DATA": "A frozen snapshot is shown, not live data.",
    "OFFLINE_CACHED": "Offline mode: only cached data is used.",
}
PEST_ASSESSMENT = {
    "ASSESSED": "scored from its weather rule, the area's NDVI and its field evidence",
    "INSUFFICIENT_DATA": "considered, but too little real data for a level",
    "NOT_ASSESSED": "a known pest/disease with no weather rule and no field evidence: no score is given",
}
RISK_LEVELS = {
    "LOW": "indicators suggest low risk",
    "MODERATE": "indicators suggest moderate risk",
    "HIGH": "indicators suggest high risk",
    "CRITICAL": "indicators suggest critical risk, with two independent real indicators and near-complete data",
    "INSUFFICIENT_DATA": "no level: too little real data",
}


def vocabulary() -> Vocabulary:
    return Vocabulary(language=LANGUAGE, trust_labels=TRUST_LABELS, evidence_states=EVIDENCE_STATES,
                      verification_statuses=VERIFICATION_MEANING, escalation_stages=escalation.STAGE_MEANING,
                      limitations=LIMITATIONS, pest_assessment=PEST_ASSESSMENT, risk_levels=RISK_LEVELS)


# ---------------------------------------------------------------------------------- builders

def _factor(assessment: RiskAssessment, factor_id: str) -> FactorResult | None:
    return next((f for f in assessment.factors if f.id == factor_id), None)


def _verification(factor: FactorResult) -> Verification:
    """Verification applies to field observations only: SAMPLE evidence is never verified, and REAL
    evidence is VERIFIED only when every record in the window is."""
    if factor.id != "report_pressure" or factor.score is None:
        return "NOT_APPLICABLE"
    if factor.sample_data:
        return "UNVERIFIED"
    reports = factor.details.get("reports", [])
    if not reports:
        return "NOT_APPLICABLE"  # none observed: nothing to verify
    return "VERIFIED" if all(r.get("verified") for r in reports) else "UNVERIFIED"


def factor_trust(factor: FactorResult | None) -> TrustLabels:
    if factor is None or factor.score is None:
        origin, freshness = "UNAVAILABLE", "UNAVAILABLE"
    elif factor.sample_data:
        origin, freshness = "SAMPLE", "SAMPLE"
    else:
        origin, first = "REAL", factor.provenance[0] if factor.provenance else None
        freshness = ("UNAVAILABLE" if first is None else
                     "STALE" if first.state == "CACHED" and first.note and "STALE" in first.note else first.state)
    synthetic = bool(factor and factor.sample_data)
    verification = _verification(factor) if factor else "NOT_APPLICABLE"
    kind = {"weather_pest": "MODEL_DATA", "ndvi_anomaly": "SATELLITE"}.get(factor.id) if factor else None
    labels = [origin] + (["SYNTHETIC"] if synthetic else []) + [freshness]
    labels += [verification] if verification != "NOT_APPLICABLE" else []
    labels += [kind] if kind and origin != "UNAVAILABLE" else []
    return TrustLabels(origin=origin, synthetic=synthetic, freshness=freshness, verification=verification,
                       labels=list(dict.fromkeys(labels)))


def input_statuses(assessment: RiskAssessment) -> list[InputStatus]:
    out = []
    for name, factor_id in (("weather", "weather_pest"), ("ndvi", "ndvi_anomaly"),
                            ("pest_observations", "report_pressure")):
        factor = _factor(assessment, factor_id)
        first = factor.provenance[0] if factor and factor.provenance else None
        out.append(InputStatus(input=name, status=factor.status if factor else "unavailable", trust=factor_trust(factor),
                               source=first.source if first else None, retrieved_at=first.retrieved_at if first else None,
                               covers=first.covers if first else None,
                               unavailable_reason=factor.unavailable_reason if factor else "not assessed"))
    return out


def overall_freshness(inputs: list[InputStatus], mode: str) -> Freshness:
    if mode == "snapshot":
        return "SNAPSHOT"
    states = {i.trust.freshness for i in inputs if i.trust.origin == "REAL"}
    for state in ("STALE", "CACHED", "LIVE"):
        if state in states:
            return state
    return "UNAVAILABLE"


def rules_status(snapshot) -> RulesStatus:
    observation_rules = _observation_rules()
    rules, model = snapshot.rules, snapshot.model
    return RulesStatus(weather_rules="VERIFIED" if all(p.status == "VERIFIED" for p in rules.pests) else "PLACEHOLDER",
                       weather_rules_version=rules.version,
                       observation_rules=observation_rules.status if observation_rules else None,
                       observation_rules_version=observation_rules.version if observation_rules else None,
                       risk_model=model.status, risk_model_version=model.version,
                       calibration=model.calibration.status, missing_inputs_policy=model.missing_inputs)


def _observation_rules() -> ObservationRulesConfig | None:
    try:
        return load_observation_rules()
    except (OSError, ValueError):
        return None


def boundary_status(area: MonitoredArea) -> BoundaryStatus:
    if area.kind == "district":
        return BoundaryStatus(kind="district", official=True, status="OFFICIAL_SOURCED", source=area.boundary_source,
                              note=f"Administrative district outline from: {area.boundary_source}.")
    if area.kind == "demo":
        return BoundaryStatus(kind="demo", official=False, status="DEMO_NOT_OFFICIAL", source=area.boundary_source,
                              note="Demo monitoring rectangle drawn by the team: not an administrative boundary.")
    return BoundaryStatus(kind="custom", official=False, status="USER_DRAWN_NOT_OFFICIAL", source=area.boundary_source,
                          note="An area drawn by a user: not an administrative boundary.")


def _limit(code: str, severity: str, detail: str | None = None) -> Limitation:
    return Limitation(code=code, severity=severity, message=LIMITATIONS[code] + (f" {detail}" if detail else ""))


def limitations(assessment: RiskAssessment, area: MonitoredArea, snapshot, inputs: list[InputStatus]) -> list[Limitation]:
    by_input = {i.input: i for i in inputs}
    weather, ndvi, observations = by_input["weather"], by_input["ndvi"], by_input["pest_observations"]
    weather_f, ndvi_f = _factor(assessment, "weather_pest"), _factor(assessment, "ndvi_anomaly")
    out = []
    if assessment.level == "INSUFFICIENT_DATA":
        out.append(_limit("INSUFFICIENT_DATA", "warning"))
    out.append(_limit("NOT_A_DETECTION", "info"))
    if weather.trust.origin == "UNAVAILABLE":
        out.append(_limit("WEATHER_UNAVAILABLE", "warning", f"Reason: {weather.unavailable_reason}."))
    else:
        out.append(_limit("WEATHER_MODEL_DATA", "info"))
        if weather.trust.freshness == "STALE":
            out.append(_limit("WEATHER_STALE", "caution"))
        if weather_f and weather_f.details.get("calculation", {}).get("saturated"):
            out.append(_limit("WEATHER_INDEX_SATURATED", "caution"))
        width, height = extent_km(area)
        if max(width, height) > snapshot.model.weather_point_span_km:
            out.append(_limit("WEATHER_SINGLE_POINT", "caution", f"The area spans about {width:.0f} x {height:.0f} km."))
    if ndvi.trust.origin == "UNAVAILABLE":
        out.append(_limit("NDVI_UNAVAILABLE", "caution", f"Reason: {ndvi.unavailable_reason}."))
    elif ndvi_f and ndvi_f.status == "partial":
        out.append(_limit("NDVI_PARTIAL_BASELINE", "caution"))
    out.append(_limit("NDVI_NOT_PEST_DETECTION", "info"))
    if assessment.includes_sample_data:
        out.append(_limit("PEST_EVIDENCE_SAMPLE", "warning"))
    if observations.trust.origin != "REAL":
        out.append(_limit("NO_REAL_PEST_EVIDENCE", "caution"))
    elif observations.trust.verification == "UNVERIFIED":
        out.append(_limit("UNVERIFIED_PEST_EVIDENCE", "caution"))
    if assessment.level_without_sample and assessment.level_without_sample != assessment.level:
        out.append(_limit("LEVEL_DEPENDS_ON_SAMPLE", "warning",
                          f"Without it: {assessment.level_without_sample} ({assessment.score_without_sample:.0f}/100)."))
    if assessment.pests_not_assessed:
        out.append(_limit("PESTS_NOT_ASSESSED", "info",
                          "Not assessed: " + ", ".join(p.name.lower() for p in assessment.pests_not_assessed) + "."))
    if assessment.thresholds_status == "PLACEHOLDER":
        out.append(_limit("PLACEHOLDER_THRESHOLDS", "warning"))
    if assessment.calibration == "UNCALIBRATED":
        out.append(_limit("UNCALIBRATED_SCORE", "caution"))
    if area.kind != "district":
        out.append(_limit("AREA_NOT_OFFICIAL", "info", boundary_status(area).note))
    if snapshot.mode == "snapshot":
        detail = f"Saved {snapshot.snapshot_saved_at}." + (f" {snapshot.fallback_reason}" if snapshot.fallback_reason
                                                           else "")
        out.append(_limit("SNAPSHOT_DATA", "caution", detail))
    if snapshot.offline:
        out.append(_limit("OFFLINE_CACHED", "caution"))
    return out


def _driver_name(assessment: RiskAssessment) -> str | None:
    driver = next((p for p in assessment.pest_risks if p.pest_id == assessment.driver_pest), None)
    return driver.name if driver else None


def summary_sentence(assessment: RiskAssessment, inputs: list[InputStatus]) -> str:
    """One plain sentence with the level and what it rests on."""
    if assessment.level == "INSUFFICIENT_DATA":
        missing = ", ".join(i.input.replace("_", " ") for i in inputs if i.trust.origin != "REAL") or "real inputs"
        return f"No risk level for {assessment.area_name}: too little real data ({missing} not backed by real data)."
    by_input = {i.input: i for i in inputs}
    head = f"{assessment.level} risk assessment ({assessment.score:.0f}/100) from the indicators currently available"
    if len(assessment.pest_risks) > 1 and _driver_name(assessment):
        head += f", led by {_driver_name(assessment).lower()}"
    parts = [head]
    parts.append("weather is unavailable" if by_input["weather"].trust.origin == "UNAVAILABLE"
                 else "weather is model data")
    if by_input["ndvi"].trust.origin == "UNAVAILABLE":
        parts.append("NDVI is unavailable")
    observations = by_input["pest_observations"].trust
    parts.append({"SAMPLE": "pest evidence is SAMPLE (synthetic)",
                  "UNAVAILABLE": "no real pest evidence is available"}.get(observations.origin)
                 or ("pest evidence includes verified field observations" if observations.verification == "VERIFIED"
                     else "pest evidence is REAL but unverified" if observations.verification == "UNVERIFIED"
                     else "no pest observed by the surveillance that covers this area"))
    if assessment.level_without_sample and assessment.level_without_sample != assessment.level:
        parts.append(f"the level depends on SAMPLE data ({assessment.level_without_sample} without it)")
    if assessment.calibration == "UNCALIBRATED":
        parts.append("uncalibrated prototype")
    return "; ".join(parts) + "."


def area_labels(assessment: RiskAssessment, area: MonitoredArea, inputs: list[InputStatus], mode: str) -> list[str]:
    by_input = {i.input: i for i in inputs}
    labels = []
    if assessment.level == "INSUFFICIENT_DATA":
        labels.append("INSUFFICIENT_DATA")
    if assessment.includes_sample_data:
        labels += ["SAMPLE", "SYNTHETIC"]
    if by_input["weather"].trust.origin == "UNAVAILABLE":
        labels.append("WEATHER_UNAVAILABLE")
    if by_input["ndvi"].trust.origin == "UNAVAILABLE":
        labels.append("NDVI_UNAVAILABLE")
    if by_input["pest_observations"].trust.origin != "REAL":
        labels.append("NO_REAL_PEST_EVIDENCE")
    elif by_input["pest_observations"].trust.verification == "VERIFIED":
        labels.append("VERIFIED_PEST_EVIDENCE")
    labels.append("PLACEHOLDER" if assessment.thresholds_status == "PLACEHOLDER" else "VERIFIED_RULES")
    labels.append(assessment.calibration)
    labels.append(overall_freshness(inputs, mode))
    if area.kind == "demo":
        labels.append("DEMO_AREA")
    elif area.kind == "custom":
        labels.append("USER_AREA")
    return list(dict.fromkeys(labels))


def area_status(snapshot, assessment: RiskAssessment) -> AreaStatus:
    area = snapshot.areas[assessment.area_id]
    inputs = input_statuses(assessment)
    return AreaStatus(
        id=area.id, name=area.name, district=area.district, state=area.state, boundary=boundary_status(area),
        label_point=geo.representative_point(area.geometry), bounds=geo.geometry_bounds(area.geometry),
        rank=assessment.rank, rank_of=assessment.rank_of, level=assessment.level, score=assessment.score,
        score_range=assessment.score_range, score_without_sample=assessment.score_without_sample,
        level_without_sample=assessment.level_without_sample, confidence=assessment.confidence.level,
        data_completeness=assessment.confidence.data_completeness, assessed_at=assessment.as_of,
        computed_at=snapshot.computed_at, mode=snapshot.mode, freshness=overall_freshness(inputs, snapshot.mode),
        driver_pest=assessment.driver_pest, includes_sample_data=assessment.includes_sample_data,
        calibration=assessment.calibration, thresholds_status=assessment.thresholds_status, inputs=inputs,
        labels=area_labels(assessment, area, inputs, snapshot.mode), summary=summary_sentence(assessment, inputs),
        limitations=limitations(assessment, area, snapshot, inputs))


def area_list(snapshot) -> AreaList:
    return AreaList(computed_at=snapshot.computed_at, mode=snapshot.mode, offline=snapshot.offline,
                    snapshot_saved_at=snapshot.snapshot_saved_at, fallback_reason=snapshot.fallback_reason,
                    region="Manipur", rules=rules_status(snapshot), sample_label=SAMPLE_LABEL, disclaimer=DISCLAIMER,
                    language=LANGUAGE, areas=[area_status(snapshot, a) for a in snapshot.assessments])


def _points(factors: list[FactorResult]) -> FactorPoints:
    points = {f.id: f.points for f in factors}
    return FactorPoints(weather=points.get("weather_pest"), ndvi=points.get("ndvi_anomaly"),
                        pest_observations=points.get("report_pressure"))


def evidence_summary(assessment: RiskAssessment, inputs: list[InputStatus]) -> str:
    by_input = {i.input: i.trust.origin for i in inputs}
    points = _points(assessment.factors)

    def part(label, value, origin):
        return f"{label} {value:g} ({origin})" if value is not None else f"{label} n/a ({origin})"

    head = f"{_driver_name(assessment)}: " if _driver_name(assessment) else ""
    return head + ", ".join([part("weather", points.weather, by_input["weather"]),
                             part("NDVI", points.ndvi, by_input["ndvi"]),
                             part("field observations", points.pest_observations, by_input["pest_observations"])])


def priorities(snapshot, history: AssessmentHistory | None) -> PriorityList:
    items = []
    for assessment in snapshot.assessments:  # already in engine rank order
        area = snapshot.areas[assessment.area_id]
        inputs = input_statuses(assessment)
        freshness = overall_freshness(inputs, snapshot.mode)
        items.append(PriorityItem(
            rank=assessment.rank, rank_of=assessment.rank_of, area_id=area.id, area_name=area.name,
            district=area.district, official_boundary=area.kind == "district", level=assessment.level,
            score=assessment.score, score_range=assessment.score_range, confidence=assessment.confidence.level,
            data_completeness=assessment.confidence.data_completeness, driver_pest=assessment.driver_pest,
            contributions=_points(assessment.factors), evidence_summary=evidence_summary(assessment, inputs),
            labels=area_labels(assessment, area, inputs, snapshot.mode),
            attention=escalation.attention(assessment, snapshot.model, history, freshness)))
    return PriorityList(computed_at=snapshot.computed_at, mode=snapshot.mode, ranking_basis=RANKING_BASIS,
                        note=RANKING_NOTE, disclaimer=DISCLAIMER, items=items)


def _weather_view(assessment: RiskAssessment, calibration: str) -> WeatherView:
    factor = _factor(assessment, "weather_pest")
    pests = []
    for evaluation in assessment.pests:
        days = [WeatherDay(date=d.date, period=d.period, data_kind="MODEL_ANALYSIS" if d.period == "past" else "FORECAST",
                           favourable=d.favourable, values=d.values, unmet=d.unmet) for d in evaluation.days]
        pests.append(WeatherPest(pest_id=evaluation.pest_id, name=evaluation.name, rule_status=evaluation.thresholds,
                                 conditions=evaluation.conditions, index=evaluation.index,
                                 calculation=weather_calculation(evaluation, calibration), days=days))
    return WeatherView(status=factor.status, points=factor.points, weight=factor.weight, trust=factor_trust(factor),
                       unavailable_reason=factor.unavailable_reason, grid_point=factor.details.get("point"),
                       summary=factor.details.get("weather_summary"), data_note=WEATHER_NOTE, pests=pests,
                       provenance=factor.provenance)


def _ndvi_view(assessment: RiskAssessment) -> NdviView:
    factor = _factor(assessment, "ndvi_anomaly")
    anomaly = factor.details.get("anomaly") or {}
    current = NdviWindow.model_validate(anomaly["current"]) if anomaly.get("current") else None
    baseline_range = anomaly.get("baseline_range")
    return NdviView(status=factor.status, points=factor.points, weight=factor.weight, trust=factor_trust(factor),
                    unavailable_reason=factor.unavailable_reason, current=current,
                    baseline=[NdviWindow.model_validate(w) for w in anomaly.get("baseline", [])],
                    baseline_mean=anomaly.get("baseline_mean"),
                    baseline_range=tuple(baseline_range) if baseline_range else None,
                    relative_change=anomaly.get("relative_change"), absolute_change=anomaly.get("absolute_change"),
                    within_baseline_range=anomaly.get("within_baseline_range"), method=anomaly.get("method"),
                    caveat=NDVI_CAVEAT, provenance=factor.provenance)


def _observation(record: dict) -> ObservationView:
    status = record.get("status") or ("SAMPLE" if record.get("synthetic", True) else "REAL")
    return ObservationView(
        id=record["id"], pest=record["pest"], observed_on=record["observed_on"], status=status,
        synthetic=bool(record.get("synthetic", status == "SAMPLE")),
        verification="VERIFIED" if status == "REAL" and record.get("verified") else "UNVERIFIED",
        severity=record.get("severity"), severity_basis=record.get("severity_basis"), metric=record.get("metric"),
        value=record.get("value"), unit=record.get("unit"), match=record.get("match"),
        spatial_resolution=record.get("spatial_resolution"), district=record.get("district"),
        source=record.get("source") or "SAMPLE", source_url=record.get("source_url"), label=record.get("label"))


def _pests_view(assessment: RiskAssessment) -> PestsView:
    rule_status = {e.pest_id: e.thresholds for e in assessment.pests}
    assessed = []
    for pest in assessment.pest_risks:
        observation_f = next(f for f in pest.factors if f.id == "report_pressure")
        details = observation_f.details
        assessed.append(PestView(
            pest_id=pest.pest_id, name=pest.name, crop=pest.crop,
            assessment="INSUFFICIENT_DATA" if pest.level == "INSUFFICIENT_DATA" else "ASSESSED", level=pest.level,
            score=pest.score, score_range=pest.score_range, data_completeness=pest.data_completeness,
            has_weather_rule=pest.has_weather_rule, weather_rule_status=rule_status.get(pest.pest_id),
            contributions=_points(pest.factors), evidence_state=details.get("evidence_state"),
            evidence=details.get("evidence") or observation_f.unavailable_reason,
            observation_trust=factor_trust(observation_f),
            observations=[_observation(r) for r in details.get("reports", [])],
            historical_count=details.get("historical_count", 0), summary=pest.summary))
    not_assessed = [NotAssessedView(pest_id=p.pest_id, name=p.name, assessment="NOT_ASSESSED", reason=p.reason)
                    for p in assessment.pests_not_assessed]
    return PestsView(assessed=assessed, not_assessed=not_assessed)


def _rule_sources(snapshot) -> list[RuleSource]:
    out = [RuleSource(kind="weather_rule", pest_id=p.id, status=p.status, sources=[s.model_dump() for s in p.sources])
           for p in snapshot.rules.pests]
    observation_rules = _observation_rules()
    if observation_rules:
        out += [RuleSource(kind="etl", pest_id=p.id, status=p.status, sources=[s.model_dump() for s in p.sources])
                for p in observation_rules.pests]
    return out


def explanation(snapshot, assessment: RiskAssessment, history: AssessmentHistory | None) -> AreaExplanation:
    area = snapshot.areas[assessment.area_id]
    inputs = input_statuses(assessment)
    freshness = overall_freshness(inputs, snapshot.mode)
    verified, unverified, sample = escalation.observation_counts(assessment)
    return AreaExplanation(
        area=AreaRef(id=area.id, name=area.name, district=area.district, state=area.state,
                     boundary=boundary_status(area), label_point=geo.representative_point(area.geometry),
                     bounds=geo.geometry_bounds(area.geometry)),
        overall=OverallView(
            level=assessment.level, score=assessment.score, score_range=assessment.score_range,
            score_without_sample=assessment.score_without_sample, level_without_sample=assessment.level_without_sample,
            rank=assessment.rank, rank_of=assessment.rank_of, confidence=assessment.confidence.level,
            confidence_method=assessment.confidence.method, confidence_notes=assessment.confidence.notes,
            data_completeness=assessment.confidence.data_completeness, assessed_at=assessment.as_of,
            computed_at=snapshot.computed_at, mode=snapshot.mode, freshness=freshness,
            calibration=assessment.calibration, thresholds_status=assessment.thresholds_status,
            driver_pest=assessment.driver_pest, headline=assessment.headline,
            summary=summary_sentence(assessment, inputs)),
        weather=_weather_view(assessment, snapshot.model.calibration.status), ndvi=_ndvi_view(assessment),
        pests=_pests_view(assessment),
        attention=escalation.attention(assessment, snapshot.model, history, freshness),
        field_verification=FieldVerification(status="NO_INSPECTION_WORKFLOW", verified_observations=verified,
                                             unverified_real_observations=unverified, sample_observations=sample,
                                             note=INSPECTION_NOTE),
        provenance=ProvenanceView(inputs=inputs, sources=assessment.provenance, rules=rules_status(snapshot),
                                  rule_sources=_rule_sources(snapshot)),
        limitations=limitations(assessment, area, snapshot, inputs), reasons=assessment.reasons,
        disclaimer=DISCLAIMER, sample_label=SAMPLE_LABEL, language=LANGUAGE)


def area_history(history: AssessmentHistory, area_id: str, limit: int | None = None) -> AreaHistory:
    if not history.enabled:
        return AreaHistory(area_id=area_id, enabled=False, entries=[],
                           note="Assessment history is switched off (SATQUERY_AGRI_HISTORY); nothing is recorded.")
    entries = history.for_area(area_id, limit)
    return AreaHistory(area_id=area_id, enabled=True, entries=entries,
                       note=("Live assessments recorded since history was switched on; nothing earlier exists and "
                             "nothing is backfilled. Snapshots and offline re-scores are not recorded. field_outcome "
                             "stays empty until a verified inspection workflow exists."))
