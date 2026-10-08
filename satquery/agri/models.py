"""Data contracts of the agricultural risk engine (AG-04).

Every number that reaches a user carries where it came from (`Provenance`) and in what state it is:
LIVE (fetched now), CACHED (fetched earlier, with its time), SAMPLE (synthetic, prototype only) or
UNAVAILABLE. Thresholds carry their own status: PLACEHOLDER until an agronomist has verified them
against a cited source, VERIFIED after.
"""

from typing import Literal

from pydantic import BaseModel, Field

DataState = Literal["LIVE", "CACHED", "SAMPLE", "UNAVAILABLE"]
ThresholdStatus = Literal["PLACEHOLDER", "VERIFIED"]
FactorStatus = Literal["ok", "partial", "unavailable"]
RiskLevel = Literal["LOW", "MODERATE", "HIGH", "CRITICAL", "INSUFFICIENT_DATA"]
Severity = Literal["low", "moderate", "high"]

SAMPLE_LABEL = "SAMPLE DATA — Prototype Simulation"
DISCLAIMER = ("Decision support only. Final assessment should be performed by the relevant Department of "
              "Agriculture / qualified expert.")
PLACEHOLDER_NOTE = ("Thresholds are PLACEHOLDERS for development, not verified agronomic values; this score is not "
                    "scientifically validated.")


class Provenance(BaseModel):
    source: str
    state: DataState
    retrieved_at: str | None = None  # ISO UTC time the data was fetched (for CACHED: the original fetch)
    covers: str | None = None        # the period the data describes
    licence: str | None = None
    note: str | None = None


class MonitoredArea(BaseModel):
    """An area the engine scores: an administrative district, a user's own area, or a demo rectangle."""

    id: str
    name: str
    kind: Literal["district", "custom", "demo"]
    geometry: dict  # GeoJSON Polygon or MultiPolygon, WGS84
    boundary_source: str  # where the outline comes from; a demo rectangle says it is not a boundary
    district: str | None = None
    state: str | None = None
    note: str | None = None


class PestReport(BaseModel):
    """A pest or disease report. In this prototype every report is SAMPLE (synthetic)."""

    id: str
    area_id: str | None
    latitude: float
    longitude: float
    observed_on: str  # ISO date
    crop: str
    pest: str  # pest rule id, e.g. "rice_blast"
    severity: Severity
    source: Literal["SAMPLE"] = "SAMPLE"
    synthetic: bool = True
    verified: bool = False
    label: str = SAMPLE_LABEL


class SampleReportSet(BaseModel):
    reports: list[PestReport]
    provenance: Provenance
    seed: int
    generated_for: str  # the date the window ends on, ISO
    label: str = SAMPLE_LABEL


class DayCheck(BaseModel):
    date: str
    period: Literal["past", "forecast"]
    favourable: bool | None  # None: not enough hourly data that day to judge
    values: dict[str, float | None] = Field(default_factory=dict)  # condition label -> the day's value
    unmet: list[str] = Field(default_factory=list)


class PestEvaluation(BaseModel):
    pest_id: str
    name: str
    crop: str
    status: FactorStatus
    index: float | None  # 0..1: favourable days / full_score_days, capped
    favourable_past: int
    known_past: int
    past_days: int
    favourable_forecast: int
    known_forecast: int
    forecast_days: int
    longest_run: int  # longest run of consecutive favourable days in the window
    full_score_days: int
    conditions: list[str]
    thresholds: ThresholdStatus
    sources: list[dict] = Field(default_factory=list)
    explanation: str
    days: list[DayCheck] = Field(default_factory=list)


class NdviWindow(BaseModel):
    label: str  # "current" or the baseline year
    start: str  # ISO date, inclusive
    end: str    # ISO date, exclusive
    mean: float | None = None
    median: float | None = None
    p10: float | None = None
    p90: float | None = None
    pixels: int = 0
    observed_fraction: float = 0.0  # share of the area with at least one clear land observation
    usable: bool = False
    reason: str | None = None
    state: DataState = "UNAVAILABLE"
    retrieved_at: str | None = None


class NdviAnomaly(BaseModel):
    current: NdviWindow
    baseline: list[NdviWindow]
    baseline_mean: float | None
    baseline_range: tuple[float, float] | None
    baseline_years_used: int
    relative_change: float | None  # (current - baseline) / baseline
    absolute_change: float | None
    within_baseline_range: bool | None
    resolution_deg: float
    method: str


class FactorResult(BaseModel):
    id: Literal["weather_pest", "ndvi_anomaly", "report_pressure"]
    name: str
    status: FactorStatus
    score: float | None  # 0..1; None when unavailable
    weight: float
    availability: float  # 1 ok, the known share when partial, 0 unavailable
    points: float | None = None  # this factor's share of the final 0-100 score
    summary: str
    reasons: list[str] = Field(default_factory=list)
    details: dict = Field(default_factory=dict)
    provenance: list[Provenance] = Field(default_factory=list)
    thresholds: ThresholdStatus | None = None
    unavailable_reason: str | None = None
    sample_data: bool = False


class RiskConfidence(BaseModel):
    level: Literal["low", "medium", "high"]
    data_completeness: float  # share of the model's weight backed by available data
    method: str
    calibrated: bool = False
    notes: list[str] = Field(default_factory=list)


class RiskAssessment(BaseModel):
    area_id: str
    area_name: str
    area_kind: str
    as_of: str  # ISO UTC time of the assessment
    score: float | None  # 0-100; None when there is not enough data to estimate
    level: RiskLevel
    headline: str
    reasons: list[str]
    top_factors: list[str]
    factors: list[FactorResult]
    pests: list[PestEvaluation]
    confidence: RiskConfidence
    provenance: list[Provenance]
    thresholds_status: ThresholdStatus
    includes_sample_data: bool
    disclaimer: str = DISCLAIMER
    rank: int | None = None
    rank_of: int | None = None
    district_context: dict | None = None
