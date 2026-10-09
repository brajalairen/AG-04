"""Escalation readiness: the facts a WATCH / PRIORITIZE / inspection policy will need, without a policy.

No verified escalation policy exists, so none is applied. "HIGH once means send officials" is not a
rule this system makes up. What is exposed is the evidence such a policy would weigh:

- persistence: how many consecutive recorded assessments were elevated (from real history only;
  None when history is switched off, never estimated)
- independent real indicators: REAL (non-SAMPLE) factors at or above the configured indicator cut
  (`critical_corroboration.factor_score_at_least` in risk_model.json, itself a PLACEHOLDER)
- evidence types, verified / unverified / SAMPLE observation counts, data completeness, freshness

The one stage assigned is a fact, not a threshold: VERIFIED_OBSERVATION when an expert-verified
field observation of a pest exists for the area. Every other stage stays unassigned until Member A
and the Department provide a verified policy through `EscalationPolicy`.
"""

from typing import Literal, Protocol

from pydantic import BaseModel

from satquery.agri.config import RiskModelConfig
from satquery.agri.history import AssessmentHistory
from satquery.agri.models import RiskAssessment

EscalationStage = Literal["WATCH", "PRIORITIZE", "FIELD_INSPECTION_RECOMMENDED", "VERIFIED_OBSERVATION"]
STAGE_MEANING = {
    "WATCH": "keep under watch (policy not configured)",
    "PRIORITIZE": "prioritise for follow-up (policy not configured)",
    "FIELD_INSPECTION_RECOMMENDED": "a field inspection is recommended (policy not configured)",
    "VERIFIED_OBSERVATION": "an expert-verified field observation of a pest or disease exists for this area",
}
ELEVATED = ("HIGH", "CRITICAL")
Origin = Literal["REAL", "SAMPLE", "UNAVAILABLE"]


class Persistence(BaseModel):
    history_enabled: bool
    recorded_assessments: int | None     # None: history switched off
    elevated_streak: int | None          # consecutive most recent recorded assessments at HIGH or CRITICAL
    elevated_since: str | None           # computed_at of the first assessment in that streak
    first_recorded_at: str | None


class EscalationFacts(BaseModel):
    elevated_now: bool
    level: str
    persistence: Persistence
    independent_real_indicators: list[str]  # factor ids
    indicator_cut: float
    indicator_cut_status: str                # status of the risk model the cut comes from
    evidence_types: dict[str, Origin]        # weather / ndvi / pest_observations
    verified_observations: int
    unverified_real_observations: int
    sample_observations: int
    data_completeness: float
    freshness: str


class AttentionStatus(BaseModel):
    stage: EscalationStage | None
    policy: Literal["NOT_CONFIGURED", "CONFIGURED"]
    policy_note: str
    facts: EscalationFacts


class EscalationPolicy(Protocol):
    """A verified escalation policy (future). Returns a stage, or None to assign none."""

    name: str

    def stage(self, facts: EscalationFacts) -> EscalationStage | None: ...


NO_POLICY_NOTE = ("No verified escalation policy is configured, so WATCH, PRIORITIZE and FIELD_INSPECTION_RECOMMENDED "
                  "are not assigned. The facts below are what such a policy would use.")


def _origin(assessment: RiskAssessment, factor_id: str) -> Origin:
    factor = next((f for f in assessment.factors if f.id == factor_id), None)
    if factor is None or factor.score is None:
        return "UNAVAILABLE"
    return "SAMPLE" if factor.sample_data else "REAL"


def observation_counts(assessment: RiskAssessment) -> tuple[int, int, int]:
    """(verified REAL, unverified REAL, SAMPLE) observations in the window, across all pests."""
    seen = {}
    for pest in assessment.pest_risks:
        for factor in pest.factors:
            if factor.id == "report_pressure":
                for record in factor.details.get("reports", []):
                    seen[record["id"]] = record
    verified = sum(1 for r in seen.values() if r.get("status") == "REAL" and r.get("verified"))
    unverified = sum(1 for r in seen.values() if r.get("status") == "REAL" and not r.get("verified"))
    sample = sum(1 for r in seen.values() if r.get("status") != "REAL")
    return verified, unverified, sample


def persistence(history: AssessmentHistory | None, area_id: str) -> Persistence:
    if history is None or not history.enabled:
        return Persistence(history_enabled=False, recorded_assessments=None, elevated_streak=None,
                           elevated_since=None, first_recorded_at=None)
    entries = history.for_area(area_id)
    streak, since = 0, None
    for entry in reversed(entries):
        if entry.level not in ELEVATED:
            break
        streak, since = streak + 1, entry.computed_at
    return Persistence(history_enabled=True, recorded_assessments=len(entries), elevated_streak=streak,
                       elevated_since=since, first_recorded_at=entries[0].computed_at if entries else None)


def facts(assessment: RiskAssessment, model: RiskModelConfig, history: AssessmentHistory | None,
          freshness: str) -> EscalationFacts:
    cut = model.critical_corroboration.factor_score_at_least
    indicators = [f.id for f in assessment.factors
                  if f.score is not None and not f.sample_data and f.score >= cut]
    verified, unverified, sample = observation_counts(assessment)
    return EscalationFacts(
        elevated_now=assessment.level in ELEVATED, level=assessment.level,
        persistence=persistence(history, assessment.area_id), independent_real_indicators=indicators,
        indicator_cut=cut, indicator_cut_status=model.status,
        evidence_types={"weather": _origin(assessment, "weather_pest"), "ndvi": _origin(assessment, "ndvi_anomaly"),
                        "pest_observations": _origin(assessment, "report_pressure")},
        verified_observations=verified, unverified_real_observations=unverified, sample_observations=sample,
        data_completeness=assessment.confidence.data_completeness, freshness=freshness)


def attention(assessment: RiskAssessment, model: RiskModelConfig, history: AssessmentHistory | None,
              freshness: str, policy: EscalationPolicy | None = None) -> AttentionStatus:
    found = facts(assessment, model, history, freshness)
    if policy is not None:
        return AttentionStatus(stage=policy.stage(found), policy="CONFIGURED",
                               policy_note=f"Stage from the configured policy '{policy.name}'.", facts=found)
    stage = "VERIFIED_OBSERVATION" if found.verified_observations else None
    return AttentionStatus(stage=stage, policy="NOT_CONFIGURED", policy_note=NO_POLICY_NOTE, facts=found)
