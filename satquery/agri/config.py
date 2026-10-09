"""Thresholds and weights of the risk engine, kept as reviewable data apart from the scoring code.

`assets/pest_rules.json` (pest-favourable weather) and `assets/risk_model.json` (weights, level
cut-points, NDVI and report scoring) ship as PLACEHOLDER values for development. An agronomist
replaces them with verified values without touching code: point SATQUERY_AGRI_PEST_RULES /
SATQUERY_AGRI_RISK_MODEL at the reviewed files, or edit the assets.

A file or pest marked VERIFIED must name its sources, each with who verified it and when; otherwise
loading fails. Nothing is ever shown as verified by default.
"""

import json
import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from satquery.agri.models import ThresholdStatus

ASSETS = Path(__file__).resolve().parent / "assets"
WEATHER_VARIABLES = ("temperature_2m", "relative_humidity_2m", "dew_point_2m", "precipitation")


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Source(Strict):
    title: str
    url: str | None = None
    note: str | None = None
    verified_by: str | None = None
    verified_on: str | None = None  # ISO date


def _require_verified_sources(status: str, sources: list[Source], what: str) -> None:
    if status != "VERIFIED":
        return
    if not sources:
        raise ValueError(f"{what} is marked VERIFIED but names no source")
    for source in sources:
        if not (source.verified_by and source.verified_on):
            raise ValueError(f"{what} is marked VERIFIED but source '{source.title}' has no verified_by/verified_on")


class Condition(Strict):
    """One test a day must pass. `mean`/`min`/`max`/`sum` aggregate the day's hourly values and
    compare with `between`, `at_least` or `at_most`; `hours_at_or_above` counts the hours at or above
    `threshold` and needs `at_least` of them; `hours_between` counts the hours inside `between`."""

    variable: Literal["temperature_2m", "relative_humidity_2m", "dew_point_2m", "precipitation"]
    aggregate: Literal["mean", "min", "max", "sum", "hours_at_or_above", "hours_between"]
    threshold: float | None = None
    between: tuple[float, float] | None = None
    at_least: float | None = None
    at_most: float | None = None
    label: str

    @model_validator(mode="after")
    def _shape(self):
        if self.between is not None and self.between[0] > self.between[1]:
            raise ValueError(f"'{self.label}': between must be [low, high]")
        if self.aggregate == "hours_at_or_above":
            if self.threshold is None or self.at_least is None:
                raise ValueError(f"'{self.label}': hours_at_or_above needs threshold and at_least (hours)")
        elif self.aggregate == "hours_between":
            if self.between is None or self.at_least is None:
                raise ValueError(f"'{self.label}': hours_between needs between and at_least (hours)")
        elif self.between is None and self.at_least is None and self.at_most is None:
            raise ValueError(f"'{self.label}': {self.aggregate} needs between, at_least or at_most")
        return self


class PestRule(Strict):
    id: str
    name: str
    crop: str
    status: ThresholdStatus
    sources: list[Source] = Field(default_factory=list)
    conditions: list[Condition] = Field(min_length=1)
    past_days: int = Field(7, ge=1, le=14)
    forecast_days: int = Field(3, ge=0, le=7)
    full_score_days: int = Field(5, ge=1, le=21)

    @model_validator(mode="after")
    def _verified(self):
        _require_verified_sources(self.status, self.sources, f"pest rule '{self.id}'")
        return self


class PestRulesConfig(Strict):
    version: str
    status: ThresholdStatus
    note: str
    min_hours_per_day: int = Field(20, ge=1, le=24)
    pests: list[PestRule] = Field(min_length=1)

    @model_validator(mode="after")
    def _consistent(self):
        ids = [p.id for p in self.pests]
        if len(ids) != len(set(ids)):
            raise ValueError("pest rule ids must be unique")
        if self.status == "VERIFIED" and any(p.status != "VERIFIED" for p in self.pests):
            raise ValueError("pest_rules is marked VERIFIED but some pest rules are still PLACEHOLDER")
        return self


class LevelCuts(Strict):
    critical: float = Field(ge=0, le=1)
    high: float = Field(ge=0, le=1)
    moderate: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def _ordered(self):
        if not self.moderate < self.high < self.critical:
            raise ValueError("level cut-points must satisfy moderate < high < critical")
        return self


class Corroboration(Strict):
    min_factors: int = Field(2, ge=1, le=3)
    factor_score_at_least: float = Field(0.6, ge=0, le=1)
    min_completeness: float = Field(0.9, ge=0, le=1)


class NdviConfig(Strict):
    window_days: int = Field(30, ge=5, le=90)
    baseline_years: int = Field(3, ge=1, le=8)
    min_baseline_years: int = Field(2, ge=1, le=8)
    min_observed_fraction: float = Field(0.3, gt=0, le=1)
    ignore_relative_drop_below: float = Field(0.03, ge=0, lt=1)
    relative_drop_for_full_score: float = Field(0.2, gt=0, le=1)
    max_pixels: int = Field(100_000, ge=1_000, le=2_000_000)
    min_resolution_deg: float = Field(0.0005, gt=0, le=0.01)

    @model_validator(mode="after")
    def _consistent(self):
        if self.min_baseline_years > self.baseline_years:
            raise ValueError("ndvi.min_baseline_years cannot exceed ndvi.baseline_years")
        if self.ignore_relative_drop_below >= self.relative_drop_for_full_score:
            raise ValueError("ndvi.ignore_relative_drop_below must be below relative_drop_for_full_score")
        return self


class ReportConfig(Strict):
    lookback_days: int = Field(14, ge=1, le=90)
    severity_weights: dict[Literal["low", "moderate", "high"], float]
    weighted_count_for_full_score: float = Field(6.0, gt=0)
    # A district-level record only says the pest was seen somewhere in the zone's district, which is
    # weaker evidence for the zone than a record located inside it: its severity weight is scaled by this.
    district_match_weight: float = Field(0.5, ge=0, le=1)


class ConfidenceConfig(Strict):
    high_min_completeness: float = Field(0.9, ge=0, le=1)
    medium_min_completeness: float = Field(0.6, ge=0, le=1)


CALIBRATION_NOTE = ("The weights, level bands and scoring breakpoints are engineering choices. They have not been "
                    "validated against field outcomes (verified inspections or surveillance), so a score is a "
                    "rule-based indication, not a calibrated risk or probability.")


class CalibrationConfig(Strict):
    """Whether the score as a whole has been validated against outcomes. This is separate from the
    thresholds' VERIFIED status: verified thresholds do not make the weights or bands validated."""

    status: Literal["UNCALIBRATED", "VALIDATED"] = "UNCALIBRATED"
    note: str = CALIBRATION_NOTE
    evidence: list[Source] = Field(default_factory=list)  # the validation study / outcome data, when VALIDATED

    @model_validator(mode="after")
    def _validated(self):
        if self.status == "VALIDATED":
            if not self.evidence:
                raise ValueError("risk_model calibration is marked VALIDATED but names no validation evidence")
            _require_verified_sources("VERIFIED", self.evidence, "risk_model calibration")
        return self


class RiskModelConfig(Strict):
    version: str
    status: ThresholdStatus
    note: str
    sources: list[Source] = Field(default_factory=list)
    weights: dict[Literal["weather_pest", "ndvi_anomaly", "report_pressure"], float]
    levels: LevelCuts
    critical_corroboration: Corroboration
    min_completeness_for_level: float = Field(0.5, ge=0, le=1)
    ndvi: NdviConfig
    reports: ReportConfig
    confidence: ConfidenceConfig
    weather_point_span_km: float = Field(10.0, gt=0)
    # How a missing input enters the score. "lower_bound": it adds no points and keeps its weight, so
    # missing data can never raise a score; the upper end of the range is reported. "renormalise" (the
    # Phase 2 method): the score is the weighted mean of the inputs present, which in effect fills a
    # missing input with the average of the others and can raise the score when data is lost.
    missing_inputs: Literal["lower_bound", "renormalise"] = "lower_bound"
    calibration: CalibrationConfig = Field(default_factory=CalibrationConfig)

    @model_validator(mode="after")
    def _valid(self):
        if set(self.weights) != {"weather_pest", "ndvi_anomaly", "report_pressure"}:
            raise ValueError("weights must name weather_pest, ndvi_anomaly and report_pressure")
        if any(w < 0 for w in self.weights.values()) or sum(self.weights.values()) <= 0:
            raise ValueError("weights must be non-negative and not all zero")
        _require_verified_sources(self.status, self.sources, "risk_model")
        return self


CropStage = Literal["nursery", "tillering", "panicle_initiation_to_booting", "flowering_to_milky_grain"]


class EtlCriterion(Strict):
    """An economic threshold level (ETL) for one measurement of one pest at given crop stages, as the
    source states it. `between` is the source's range (low = high for a single value)."""

    metric: str
    unit: str
    crop_stages: list[CropStage] = Field(min_length=1)
    between: tuple[float, float]
    label: str

    @model_validator(mode="after")
    def _ordered(self):
        if not 0 <= self.between[0] <= self.between[1]:
            raise ValueError(f"'{self.label}': between must be [low, high] with 0 <= low <= high")
        return self


class ObservationRule(Strict):
    """How field observations of one pest or disease are read: its ETLs, with their source."""

    id: str
    name: str
    crop: str
    kind: Literal["insect_pest", "disease"]
    status: ThresholdStatus
    sources: list[Source] = Field(default_factory=list)
    applicability: str
    etl: list[EtlCriterion] = Field(default_factory=list)
    notes: str | None = None

    @model_validator(mode="after")
    def _verified(self):
        _require_verified_sources(self.status, self.sources, f"observation rule '{self.id}'")
        return self


class EtlSeverityMapping(Strict):
    """Engineering mapping from an ETL to the low / moderate / high severity the engine weights: below
    the ETL's low end, inside its range, at or above its high end. Not an agronomic finding."""

    status: ThresholdStatus
    note: str
    below: Literal["low", "moderate", "high"] = "low"
    within: Literal["low", "moderate", "high"] = "moderate"
    at_or_above: Literal["low", "moderate", "high"] = "high"


class ObservationRulesConfig(Strict):
    version: str
    status: ThresholdStatus
    note: str
    severity_from_etl: EtlSeverityMapping
    pests: list[ObservationRule]

    @model_validator(mode="after")
    def _consistent(self):
        ids = [p.id for p in self.pests]
        if len(ids) != len(set(ids)):
            raise ValueError("observation rule ids must be unique")
        if self.status == "VERIFIED" and any(p.status != "VERIFIED" for p in self.pests):
            raise ValueError("observation_rules is marked VERIFIED but some rules are still PLACEHOLDER")
        return self

    def rule(self, pest_id: str) -> ObservationRule | None:
        return next((p for p in self.pests if p.id == pest_id), None)


def _load(path: Path, model):
    return model.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))


def load_pest_rules(path: str | Path | None = None) -> PestRulesConfig:
    return _load(path or os.environ.get("SATQUERY_AGRI_PEST_RULES") or ASSETS / "pest_rules.json", PestRulesConfig)


def load_risk_model(path: str | Path | None = None) -> RiskModelConfig:
    return _load(path or os.environ.get("SATQUERY_AGRI_RISK_MODEL") or ASSETS / "risk_model.json", RiskModelConfig)


def load_observation_rules(path: str | Path | None = None) -> ObservationRulesConfig:
    return _load(path or os.environ.get("SATQUERY_AGRI_OBSERVATION_RULES") or ASSETS / "observation_rules.json",
                 ObservationRulesConfig)


def thresholds_status(rules: PestRulesConfig, model: RiskModelConfig) -> ThresholdStatus:
    """VERIFIED only when every pest rule and the risk model are verified."""
    verified = model.status == "VERIFIED" and all(p.status == "VERIFIED" for p in rules.pests)
    return "VERIFIED" if verified else "PLACEHOLDER"
