"""Pest and disease field observations: loading, checking, matching to areas, and reading them against ETLs.

No public, machine-readable pest or disease observation dataset for Manipur was found (see
data/agri/SOURCES.md), so the prototype runs on SAMPLE observations (`reports.py`). This module is
the path for real ones: a dataset file in the schema below is loaded with
SATQUERY_AGRI_OBSERVATIONS=<file> and then replaces the SAMPLE generator.

A dataset file is JSON:  {"dataset": {...metadata...}, "observations": [{...PestObservation...}, ...]}
or CSV (one observation per row, PestObservation field names as columns) with the metadata in a
sidecar `<name>.dataset.json` holding {"dataset": {...}}.

Rules that keep it honest:
- A dataset is REAL or SAMPLE as a whole: records take its status, and one that states another is refused.
- A REAL record names its source (inherited from the dataset when the record has none).
- Records keep the resolution the source gives. A district-level record matches the zones of that
  district (weaker evidence, weighted down); it is never given coordinates.
- Records older than the look-back window are historical: they are counted and shown, never used as
  current evidence.
- No records for an area means "no evidence" only when the dataset states that it surveys that
  district (and pest). Otherwise the factor is unavailable: absence of records is not absence of pests.
"""

import csv
import json
import os
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, ValidationError

from satquery.agri import areas as geometry
from satquery.agri.config import ObservationRulesConfig
from satquery.agri.models import (MonitoredArea, ObservationStatus, PestObservation, Provenance, Severity,
                                  SpatialResolution)

Match = Literal["inside_area", "same_district"]
Coverage = Literal["covered", "unknown", "not_covered"]


class ObservationFileError(ValueError):
    """The observation dataset cannot be used; the message says which record or field and why."""


class ObservationDataset(BaseModel):
    """What a dataset is, who published it, and what it covers (data quality and provenance)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    publisher: str
    source_url: str | None = None
    licence: str
    access_date: str  # ISO date the data was obtained
    status: ObservationStatus
    geographic_coverage: str
    temporal_coverage: str
    spatial_resolution: SpatialResolution  # the coarsest resolution in the file
    observation_method: str
    limitations: str
    coverage_districts: list[str] | None = None  # districts actually surveyed; None: not stated
    pests_surveyed: list[str] | None = None      # pest ids actually surveyed; None: not stated


class ObservationSet(BaseModel):
    dataset: ObservationDataset
    observations: list[PestObservation]
    path: str | None = None


class AreaObservation(BaseModel):
    """An observation matched to one monitored area, with the severity the engine weights."""

    observation: PestObservation
    match: Match
    severity: Severity | None  # None: the record cannot be scored (reason in severity_basis)
    severity_basis: str

    def flat(self) -> dict:
        """The record with its match and severity, in the shape the dashboard lists."""
        return self.observation.model_dump() | {"match": self.match, "severity": self.severity,
                                                "severity_basis": self.severity_basis}


@dataclass
class AreaObservations:
    """Everything an observation source knows about one area for the look-back window."""

    items: list[AreaObservation]
    provenance: Provenance
    sample: bool
    coverage: Coverage
    coverage_note: str
    lookback_days: int
    pests_surveyed: list[str] | None = None
    historical_count: int = 0          # matching records older than the window (not used as evidence)
    latest_historical: str | None = None
    notes: list[str] = field(default_factory=list)
    historical: list[PestObservation] = field(default_factory=list)  # those older records, for context only

    def for_pest(self, pest_id: str) -> list[AreaObservation]:
        return [item for item in self.items if item.observation.pest == pest_id]

    def historical_for(self, pest_id: str) -> list[PestObservation]:
        return [o for o in self.historical if o.pest == pest_id]

    def surveys(self, pest_id: str) -> bool | None:
        """True / False when the source states which pests it surveys, None when it does not say."""
        return None if self.pests_surveyed is None else pest_id in self.pests_surveyed


# ------------------------------------------------------------------------------------ loading

_NUMBERS = ("latitude", "longitude", "value", "prevalence_pct")


def _row(raw: dict) -> dict:
    """A CSV row as PestObservation fields: blanks dropped, numbers and booleans parsed."""
    out = {}
    for key, value in raw.items():
        if key is None or value is None or not str(value).strip():
            continue
        value = str(value).strip()
        if key in _NUMBERS:
            out[key] = float(value)
        elif key in ("verified", "synthetic"):
            out[key] = value.lower() in ("1", "true", "yes")
        else:
            out[key] = value
    return out


def _read(path: Path) -> tuple[dict, list[dict]]:
    if path.suffix.lower() == ".csv":
        sidecar = path.with_suffix(".dataset.json")
        if not sidecar.is_file():
            raise ObservationFileError(f"{path.name}: a CSV needs its metadata in {sidecar.name}")
        meta = json.loads(sidecar.read_text(encoding="utf-8")).get("dataset")
        with path.open(encoding="utf-8-sig", newline="") as handle:
            rows = [_row(r) for r in csv.DictReader(handle)]
        return meta, rows
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ObservationFileError(f"{path.name}: expected an object with 'dataset' and 'observations'")
    return data.get("dataset"), data.get("observations") or []


def load_observations(path: str | Path) -> ObservationSet:
    """A dataset file, checked as a whole: one bad record refuses the file, so a half-loaded dataset
    is never scored as if it were complete."""
    path = Path(path)
    try:
        meta, rows = _read(path)
    except (OSError, ValueError) as error:
        if isinstance(error, ObservationFileError):
            raise
        raise ObservationFileError(f"{path.name}: not readable ({error})") from error
    try:
        dataset = ObservationDataset.model_validate(meta or {})
    except ValidationError as error:
        raise ObservationFileError(f"{path.name}: dataset metadata invalid: {error}") from error
    observations, seen = [], set()
    for index, row in enumerate(rows):
        where = f"{path.name}, record {index} ({row.get('id', 'no id')})"
        status = row.get("status") or dataset.status  # a record without a status takes the dataset's declared one
        if status != dataset.status:
            raise ObservationFileError(f"{where}: status {status} in a {dataset.status} dataset (REAL and SAMPLE "
                                       "records are never mixed)")
        row = row | {"status": status}
        if status == "REAL":  # provenance chain: a record without its own source inherits the dataset's
            row = {"source": f"{dataset.publisher}: {dataset.title}", "source_url": dataset.source_url,
                   "source_date": dataset.access_date} | row
        try:
            observation = PestObservation.model_validate(row)
        except ValidationError as error:
            raise ObservationFileError(f"{where}: {error.errors()[0]['msg']}") from error
        try:
            date.fromisoformat(observation.observed_on)
        except ValueError as error:
            raise ObservationFileError(f"{where}: observed_on must be an ISO date") from error
        if observation.id in seen:
            raise ObservationFileError(f"{where}: duplicate id '{observation.id}'")
        seen.add(observation.id)
        observations.append(observation)
    return ObservationSet(dataset=dataset, observations=observations, path=str(path))


# -------------------------------------------------------------------------------- reading ETLs

def resolve_severity(observation: PestObservation, rules: ObservationRulesConfig | None) -> tuple[Severity | None, str]:
    """The severity to weight: the source's own category, else the measured value read against the
    pest's ETL for the recorded crop stage. Never guessed: an unreadable record says why."""
    if observation.severity is not None:
        return observation.severity, "severity recorded by the source"
    if observation.value is None:
        return None, "prevalence recorded, but no ETL reading is configured for prevalence"
    rule = rules.rule(observation.pest) if rules else None
    if rule is None:
        return None, f"no ETL is configured for {observation.pest.replace('_', ' ')}"
    criteria = [c for c in rule.etl if c.metric == observation.metric
                and (observation.crop_stage is None or observation.crop_stage in c.crop_stages)]
    if not criteria:
        stage = f" at {observation.crop_stage.replace('_', ' ')}" if observation.crop_stage else ""
        return None, f"no ETL for {observation.metric}{stage}"
    if len({c.between for c in criteria}) > 1:
        return None, (f"the ETL for {observation.metric} depends on the crop stage, which the record does not give")
    criterion, mapping = criteria[0], rules.severity_from_etl
    low, high = criterion.between
    value = observation.value
    band = (mapping.at_or_above, "at or above") if value >= high else \
        (mapping.within, "within") if value >= low else (mapping.below, "below")
    return band[0], (f"{value:g} {criterion.unit} is {band[1]} the ETL {criterion.label} "
                     f"[{rule.status} ETL; {mapping.status} severity mapping]")


# ------------------------------------------------------------------------------- area matching

def _same(a: str | None, b: str | None) -> bool:
    return bool(a and b and a.strip().lower() == b.strip().lower())


def match(observation: PestObservation, area: MonitoredArea) -> Match | None:
    """Located records must fall inside the area; area-level records match the area's district."""
    if observation.latitude is not None:
        return "inside_area" if geometry.contains(area.geometry, observation.longitude, observation.latitude) else None
    return "same_district" if _same(observation.district, area.district) else None


def coverage_of(dataset: ObservationDataset, area: MonitoredArea) -> tuple[Coverage, str]:
    if dataset.coverage_districts is None:
        return "unknown", "The dataset does not state which districts it surveys."
    if any(_same(d, area.district) for d in dataset.coverage_districts):
        return "covered", f"{area.district} is among the districts the dataset surveys."
    return "not_covered", f"The dataset does not survey {area.district or 'this area'}."


def provenance_of(dataset: ObservationDataset) -> Provenance:
    state = "SAMPLE" if dataset.status == "SAMPLE" else "CACHED"
    return Provenance(source=f"{dataset.publisher}: {dataset.title}", state=state, retrieved_at=dataset.access_date,
                      covers=dataset.temporal_coverage, licence=dataset.licence,
                      note=(f"{dataset.status} pest/disease observations ({dataset.observation_method}); "
                            f"{dataset.spatial_resolution}-level; obtained {dataset.access_date}. "
                            f"Limitations: {dataset.limitations}"))


def area_observations(obs_set: ObservationSet, area: MonitoredArea, end: date, lookback_days: int,
                      rules: ObservationRulesConfig | None) -> AreaObservations:
    first = (end - timedelta(days=lookback_days - 1)).isoformat()
    items, historical = [], []
    for observation in obs_set.observations:
        how = match(observation, area)
        if how is None or observation.observed_on > end.isoformat():
            continue
        if observation.observed_on < first:
            historical.append(observation)
            continue
        severity, basis = resolve_severity(observation, rules)
        items.append(AreaObservation(observation=observation, match=how, severity=severity, severity_basis=basis))
    coverage, note = coverage_of(obs_set.dataset, area)
    notes = []
    latest = max((o.observed_on for o in historical), default=None)
    if historical:
        notes.append(f"{len(historical)} older record(s) for this area (latest {latest}) are HISTORICAL and not used "
                     "as current evidence.")
    return AreaObservations(items=items, provenance=provenance_of(obs_set.dataset),
                            sample=obs_set.dataset.status == "SAMPLE", coverage=coverage, coverage_note=note,
                            lookback_days=lookback_days, pests_surveyed=obs_set.dataset.pests_surveyed,
                            historical_count=len(historical), latest_historical=latest, notes=notes,
                            historical=historical)


class PestObservationProvider(Protocol):
    """Anything that supplies field evidence for an area: the SAMPLE generator (`reports.py`), a
    dataset file (`ObservationFileSource`), and in future an authorised NPSS export, Department of
    Agriculture / KVK records, or verified field inspections (`inspections.to_observation`).

    A provider must label its records REAL or SAMPLE, name its source, state what it covers, and
    never bypass access controls. News articles, social media and other unverified reports are not
    field evidence and must not be wrapped as a provider."""

    def observations(self, area: MonitoredArea, end: date, lookback_days: int,
                     rules: ObservationRulesConfig | None) -> AreaObservations: ...


class ObservationFileSource:
    """Real (or SAMPLE) observations from a dataset file, in place of the SAMPLE generator."""

    def __init__(self, obs_set: ObservationSet):
        self.obs_set = obs_set

    @classmethod
    def from_file(cls, path: str | Path) -> "ObservationFileSource":
        return cls(load_observations(path))

    def observations(self, area: MonitoredArea, end: date, lookback_days: int,
                     rules: ObservationRulesConfig | None) -> AreaObservations:
        return area_observations(self.obs_set, area, end, lookback_days, rules)


# --------------------------------------------------------------------------------- data quality

def quality_report(obs_set: ObservationSet, today: date, lookback_days: int = 14,
                   rules: ObservationRulesConfig | None = None) -> dict:
    """What the dataset is and how usable it is for current, area-level risk (Step 19 checks)."""
    records = obs_set.observations
    dates = sorted(o.observed_on for o in records)
    first_current = (today - timedelta(days=lookback_days - 1)).isoformat()
    current = [o for o in records if first_current <= o.observed_on <= today.isoformat()]

    def missing(name):
        return sum(1 for o in records if getattr(o, name) in (None, ""))

    resolution = {}
    for o in records:
        resolution[o.spatial_resolution] = resolution.get(o.spatial_resolution, 0) + 1
    scorable = sum(1 for o in records if resolve_severity(o, rules)[0] is not None)
    warnings = []
    if not records:
        warnings.append("The dataset has no records.")
    elif not current:
        warnings.append(f"No record in the last {lookback_days} days (latest {dates[-1]}): the dataset is historical "
                        "and cannot show current infestation.")
    if resolution.get("district") or resolution.get("block"):
        warnings.append("Some records are only district- or block-level: they cannot place evidence inside a zone.")
    if obs_set.dataset.coverage_districts is None:
        warnings.append("Surveyed districts are not stated, so an area without records is 'unknown', not 'clear'.")
    if records and scorable < len(records):
        warnings.append(f"{len(records) - scorable} record(s) have no severity the engine can read.")
    return {"dataset": obs_set.dataset.model_dump(), "path": obs_set.path, "records": len(records),
            "first_observed": dates[0] if dates else None, "last_observed": dates[-1] if dates else None,
            "days_since_last": (today - date.fromisoformat(dates[-1])).days if dates else None,
            "current_records": len(current), "lookback_days": lookback_days,
            "spatial_resolution": resolution, "pests": sorted({o.pest for o in records}),
            "districts": sorted({o.district for o in records if o.district}),
            "missing": {name: missing(name) for name in ("district", "latitude", "crop_stage", "severity", "value",
                                                         "prevalence_pct", "source_url")},
            "scorable_records": scorable, "warnings": warnings}


def load_default_source() -> "ObservationFileSource | None":
    """The configured real observation file (SATQUERY_AGRI_OBSERVATIONS), or None."""
    path = os.environ.get("SATQUERY_AGRI_OBSERVATIONS", "").strip()
    return ObservationFileSource.from_file(path) if path else None
