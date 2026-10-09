"""Data contracts of the agricultural risk engine (AG-04).

Every number that reaches a user carries where it came from (`Provenance`) and in what state it is:
LIVE (fetched now), CACHED (fetched earlier, with its time), SAMPLE (synthetic, prototype only) or
UNAVAILABLE. Thresholds carry their own status: PLACEHOLDER until an agronomist has verified them
against a cited source, VERIFIED after.
"""

from typing import Literal

from pydantic import BaseModel, Field, model_validator

# SNAPSHOT: from a frozen, known-good assessment file (Phase 4), never shown as live.
DataState = Literal["LIVE", "CACHED", "SNAPSHOT", "SAMPLE", "UNAVAILABLE"]
ThresholdStatus = Literal["PLACEHOLDER", "VERIFIED"]
FactorStatus = Literal["ok", "partial", "unavailable"]
RiskLevel = Literal["LOW", "MODERATE", "HIGH", "CRITICAL", "INSUFFICIENT_DATA"]
Severity = Literal["low", "moderate", "high"]
ObservationStatus = Literal["REAL", "SAMPLE"]
ObservationType = Literal["field_survey", "light_trap", "pheromone_trap", "inspection", "farmer_report",
                          "sample_simulation"]
SpatialResolution = Literal["point", "village", "block", "district"]

SAMPLE_LABEL = "SAMPLE DATA — PROTOTYPE SIMULATION"
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


class PestObservation(BaseModel):
    """One pest or disease observation in a field: REAL (from a named source) or SAMPLE (synthetic).

    Only what the source records is filled in; nothing is derived to look more precise than it is.
    A district-level record keeps district resolution and carries no coordinates (none are invented).
    A record is SAMPLE unless it says otherwise, and a REAL record must name its source.
    """

    id: str                                   # observation_id, unique within its dataset
    area_id: str | None = None                # set only by a generator that places a record in an area
    observed_on: str                          # ISO date of the field observation
    district: str | None = None
    block: str | None = None
    village: str | None = None
    latitude: float | None = None             # only for point / village records that the source locates
    longitude: float | None = None
    spatial_resolution: SpatialResolution = "point"
    crop: str
    pest: str                                 # pest or disease id, e.g. "brown_planthopper", "rice_blast"
    crop_stage: str | None = None             # as recorded, e.g. "tillering", "panicle_initiation_to_booting"
    observation_type: ObservationType = "sample_simulation"
    metric: str | None = None                 # what `value` counts, e.g. "hoppers_per_hill", "percent_dead_heart"
    value: float | None = None
    unit: str | None = None
    severity: Severity | None = None          # the source's own category, if it gives one
    prevalence_pct: float | None = Field(None, ge=0, le=100)  # share of fields / plants affected, if recorded
    source: str = "SAMPLE"
    source_url: str | None = None
    source_date: str | None = None            # publication / extraction date of the source record
    verified: bool = False                    # the source states the record was verified (e.g. an inspection)
    status: ObservationStatus = "SAMPLE"
    synthetic: bool = True
    label: str | None = SAMPLE_LABEL
    notes: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _real_defaults(cls, data):
        if isinstance(data, dict) and data.get("status") == "REAL":  # a REAL record is not synthetic or labelled SAMPLE
            data = {"synthetic": False, "label": None, "observation_type": "field_survey"} | data
        return data

    @model_validator(mode="after")
    def _honest(self):
        where = f"observation '{self.id}'"
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError(f"{where}: latitude and longitude must be given together")
        located = self.latitude is not None
        if located and self.spatial_resolution in ("block", "district"):
            raise ValueError(f"{where}: a {self.spatial_resolution}-level record must not carry coordinates "
                             "(no point is invented for an area-level record)")
        if not located and self.spatial_resolution in ("point", "village") and not self.district:
            raise ValueError(f"{where}: needs coordinates or at least a district")
        if self.spatial_resolution in ("block", "district") and not self.district:
            raise ValueError(f"{where}: a {self.spatial_resolution}-level record needs its district")
        if self.severity is None and self.value is None and self.prevalence_pct is None:
            raise ValueError(f"{where}: records no severity, value or prevalence")
        if (self.value is None) != (self.metric is None):
            raise ValueError(f"{where}: value and metric must be given together")
        if self.status == "SAMPLE":
            if not self.synthetic or self.label != SAMPLE_LABEL or self.verified:
                raise ValueError(f"{where}: a SAMPLE record must be synthetic, unverified and labelled "
                                 f"'{SAMPLE_LABEL}'")
        else:
            if self.synthetic or self.observation_type == "sample_simulation":
                raise ValueError(f"{where}: a REAL record cannot be synthetic")
            if not self.source or self.source.strip().upper() == "SAMPLE" or not (self.source_url or
                                                                                 self.source_date):
                raise ValueError(f"{where}: a REAL record must name its source and give source_url or "
                                 "source_date")
            if self.label == SAMPLE_LABEL:
                raise ValueError(f"{where}: a REAL record cannot carry the SAMPLE label")
        return self


PestReport = PestObservation  # the earlier name; reports and observations are one model


class SampleReportSet(BaseModel):
    reports: list[PestObservation]
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


class PestRiskAssessment(BaseModel):
    """One pest or disease in one area: its own weather suitability and field evidence, plus the area's
    vegetation evidence, scored like the area. The area's figure is that of its highest pest."""

    pest_id: str
    name: str
    crop: str
    score: float | None  # 0-100, lower bound when inputs are missing; None when not enough data
    score_range: tuple[float, float] | None = None
    level: RiskLevel
    factors: list[FactorResult]
    data_completeness: float
    includes_sample_data: bool
    has_weather_rule: bool
    observation_count: int
    summary: str


class PestNotAssessed(BaseModel):
    """A known rice pest or disease with neither a weather rule nor field evidence for this area:
    listed so that silence is never read as 'no risk', and given no score."""

    pest_id: str
    name: str
    reason: str


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
    # Per-pest breakdown: `factors` above are those of `driver_pest`, the pest with the highest score.
    pest_risks: list[PestRiskAssessment] = Field(default_factory=list)
    driver_pest: str | None = None
    # The band the REAL evidence allows: from the points of real inputs alone to that plus the full
    # weight of every input not backed by real data (unavailable, or SAMPLE). None when all are real.
    score_range: tuple[float, float] | None = None
    # The same figures with the SAMPLE (synthetic) evidence removed: shows how far the level rests on it.
    score_without_sample: float | None = None
    level_without_sample: RiskLevel | None = None
    pests_not_assessed: list[PestNotAssessed] = Field(default_factory=list)
    # UNCALIBRATED until the weights and bands are validated against field outcomes; independent of
    # whether the thresholds are VERIFIED.
    calibration: Literal["UNCALIBRATED", "VALIDATED"] = "UNCALIBRATED"
