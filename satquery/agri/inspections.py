"""Field inspection and verification: the record a future inspection workflow will produce.

There is no inspection workflow, store or write API yet (checklist P1.4). This module only fixes the
data contract and its rules, so that when inspections exist they flow into the engine without
weakening it:

- A record moves forward through UNVERIFIED -> REPORTED -> INITIAL_IDENTIFICATION -> EXPERT_REVIEW
  -> VERIFIED, never backwards. VERIFIED needs a named expert reviewer, a verification date and a
  finding (PRESENT / ABSENT / INCONCLUSIVE).
- Only a VERIFIED record with finding PRESENT becomes field evidence (`to_observation`): a REAL,
  verified PestObservation of type "inspection". Unverified reports are kept, but are not scored.
- A VERIFIED ABSENT finding is an outcome for later calibration (`history.HistoryEntry.field_outcome`),
  not a pest observation.

Nothing here creates inspections; no record is ever made up.
"""

from typing import Literal, Protocol

from pydantic import BaseModel, Field, model_validator

from satquery.agri.models import MonitoredArea, PestObservation, Severity

VerificationStatus = Literal["UNVERIFIED", "REPORTED", "INITIAL_IDENTIFICATION", "EXPERT_REVIEW", "VERIFIED"]
VERIFICATION_ORDER: tuple[VerificationStatus, ...] = ("UNVERIFIED", "REPORTED", "INITIAL_IDENTIFICATION",
                                                     "EXPERT_REVIEW", "VERIFIED")
VERIFICATION_MEANING = {
    "UNVERIFIED": "recorded, not yet reviewed by anyone",
    "REPORTED": "reported from the field (farmer, field staff or KVK); not yet identified",
    "INITIAL_IDENTIFICATION": "identified by field staff; awaiting expert review",
    "EXPERT_REVIEW": "under review by a named expert",
    "VERIFIED": "reviewed and accepted by a named expert on a recorded date, with a finding",
}
Finding = Literal["PRESENT", "ABSENT", "INCONCLUSIVE"]
SourceType = Literal["field_inspector", "kvk", "department_of_agriculture", "farmer_report", "npss"]


class StatusChange(BaseModel):
    status: VerificationStatus
    at: str  # ISO date-time
    by: str  # who made the change


class InspectionRecord(BaseModel):
    id: str
    area_id: str | None = None
    district: str | None = None
    latitude: float | None = None       # only when recorded on site (GPS); never derived from a place name
    longitude: float | None = None
    crop: str
    suspected_pest: str                  # pest or disease id, e.g. "brown_planthopper"
    crop_stage: str | None = None
    observed_at: str                     # ISO date-time of the field visit or report
    source_type: SourceType
    inspector: str                       # person or office that observed / reported
    evidence_refs: list[str] = Field(default_factory=list)  # photo / sample references
    observation: str | None = None       # what was seen, in the inspector's words
    metric: str | None = None
    value: float | None = None
    unit: str | None = None
    severity: Severity | None = None
    verification_status: VerificationStatus = "UNVERIFIED"
    expert_reviewer: str | None = None
    verified_on: str | None = None       # ISO date
    finding: Finding | None = None
    notes: str | None = None
    status_history: list[StatusChange] = Field(default_factory=list)

    @model_validator(mode="after")
    def _consistent(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError(f"inspection '{self.id}': latitude and longitude must be given together")
        if self.latitude is None and not self.district:
            raise ValueError(f"inspection '{self.id}': needs on-site coordinates or a district")
        if (self.value is None) != (self.metric is None):
            raise ValueError(f"inspection '{self.id}': value and metric must be given together")
        if self.verification_status == "VERIFIED":
            missing = [name for name in ("expert_reviewer", "verified_on", "finding") if not getattr(self, name)]
            if missing:
                raise ValueError(f"inspection '{self.id}': VERIFIED needs {', '.join(missing)}")
            if self.finding == "PRESENT" and self.severity is None and self.value is None:
                raise ValueError(f"inspection '{self.id}': a PRESENT finding needs a severity or a measured value")
        elif self.finding is not None or self.verified_on is not None:
            raise ValueError(f"inspection '{self.id}': a finding and verification date belong to VERIFIED records only")
        return self


class InvalidTransition(ValueError):
    """A verification status change that the workflow does not allow."""


def advance(record: InspectionRecord, status: VerificationStatus, *, by: str, at: str, **fields) -> InspectionRecord:
    """The record moved forward to `status` (fields such as expert_reviewer / verified_on / finding
    are set with it). Moving backwards or staying put is refused."""
    current, target = VERIFICATION_ORDER.index(record.verification_status), VERIFICATION_ORDER.index(status)
    if target <= current:
        raise InvalidTransition(f"inspection '{record.id}': cannot move from {record.verification_status} to {status}")
    data = record.model_dump() | fields | {"verification_status": status}
    data["status_history"] = [*data["status_history"], StatusChange(status=status, at=at, by=by).model_dump()]
    return InspectionRecord.model_validate(data)


def to_observation(record: InspectionRecord) -> PestObservation | None:
    """Field evidence from a VERIFIED record with finding PRESENT; None for anything else."""
    if record.verification_status != "VERIFIED" or record.finding != "PRESENT":
        return None
    located = record.latitude is not None
    return PestObservation(
        id=f"inspection-{record.id}", status="REAL", observed_on=record.observed_at[:10], area_id=record.area_id,
        district=record.district, latitude=record.latitude, longitude=record.longitude,
        spatial_resolution="point" if located else "district", crop=record.crop, pest=record.suspected_pest,
        crop_stage=record.crop_stage, observation_type="inspection", metric=record.metric, value=record.value,
        unit=record.unit, severity=record.severity,
        source=f"Field inspection by {record.inspector} ({record.source_type})", source_date=record.verified_on,
        verified=True, notes=f"Verified by {record.expert_reviewer} on {record.verified_on}.")


class InspectionStore(Protocol):
    """Where a future inspection workflow keeps its records (not implemented yet)."""

    def for_area(self, area: MonitoredArea) -> list[InspectionRecord]: ...
