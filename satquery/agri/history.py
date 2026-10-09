"""Assessment history: an append-only record of the assessments the engine actually computed.

Before this module nothing kept past assessments (the frozen snapshot holds only the latest one), so
history starts from the first recorded assessment: nothing is backfilled or reconstructed. Only LIVE
computations are recorded. A frozen snapshot is a copy of an earlier assessment, and an offline run
re-scores old cached inputs, so recording either would invent a point in time.

Each entry keeps what a later calibration needs: when, which level and score, from which kinds of
evidence (REAL / SAMPLE / UNAVAILABLE), under which rule and model versions. `field_outcome` is
reserved for the verified field inspection that may later confirm or rule out the assessment
(`inspections.py`); it is always None until such a workflow exists.

Storage: one JSON object per line in runs/agri/history.jsonl (gitignored runtime data).
"""

import json
import logging
import threading
from pathlib import Path

from pydantic import BaseModel, ValidationError

from satquery.agri.models import RiskAssessment, RiskLevel

log = logging.getLogger(__name__)
HISTORY_VERSION = 1


class PestLevel(BaseModel):
    pest_id: str
    level: RiskLevel
    score: float | None


class HistoryEntry(BaseModel):
    version: int = HISTORY_VERSION
    computed_at: str          # ISO UTC time the assessment was computed
    assessed_at: str          # the assessment's own as-of time
    area_id: str
    area_name: str
    level: RiskLevel
    score: float | None
    score_range: tuple[float, float] | None
    score_without_sample: float | None
    level_without_sample: RiskLevel | None
    confidence: str
    data_completeness: float
    driver_pest: str | None
    pests: list[PestLevel]
    inputs: dict[str, str]    # input -> data state of what was used (LIVE / CACHED / SAMPLE / UNAVAILABLE)
    includes_sample_data: bool
    thresholds_status: str
    calibration: str
    config: dict[str, str]    # rule and model versions in force
    field_outcome: dict | None = None  # reserved: a verified inspection outcome, linked later


def entry_for(assessment: RiskAssessment, computed_at: str, config: dict[str, str]) -> HistoryEntry:
    def state(factor_id: str) -> str:
        factor = next((f for f in assessment.factors if f.id == factor_id), None)
        if factor is None or factor.score is None:
            return "UNAVAILABLE"
        return factor.provenance[0].state if factor.provenance else "UNAVAILABLE"

    return HistoryEntry(
        computed_at=computed_at, assessed_at=assessment.as_of, area_id=assessment.area_id,
        area_name=assessment.area_name, level=assessment.level, score=assessment.score,
        score_range=assessment.score_range, score_without_sample=assessment.score_without_sample,
        level_without_sample=assessment.level_without_sample, confidence=assessment.confidence.level,
        data_completeness=assessment.confidence.data_completeness, driver_pest=assessment.driver_pest,
        pests=[PestLevel(pest_id=p.pest_id, level=p.level, score=p.score) for p in assessment.pest_risks],
        inputs={"weather": state("weather_pest"), "ndvi": state("ndvi_anomaly"),
                "pest_observations": state("report_pressure")},
        includes_sample_data=assessment.includes_sample_data, thresholds_status=assessment.thresholds_status,
        calibration=assessment.calibration, config=config)


class AssessmentHistory:
    """Append-only JSONL store. `path=None` means history is switched off: nothing is recorded and
    reads say so (an empty list from a disabled store is not 'no history')."""

    def __init__(self, path: Path | None):
        self.path = Path(path) if path else None
        self._lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        return self.path is not None

    def record(self, assessments: list[RiskAssessment], computed_at: str, config: dict[str, str]) -> int:
        """Append one entry per assessment; returns how many were written."""
        if not self.enabled or not assessments:
            return 0
        lines = [entry_for(a, computed_at, config).model_dump_json() for a in assessments]
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write("\n".join(lines) + "\n")
        return len(lines)

    def for_area(self, area_id: str, limit: int | None = None) -> list[HistoryEntry]:
        """The area's recorded entries, oldest first (the most recent `limit` when given)."""
        if not self.enabled or not self.path.is_file():
            return []
        entries, skipped = [], 0
        with self._lock, self.path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    raw = json.loads(line)
                    if raw.get("area_id") == area_id:
                        entries.append(HistoryEntry.model_validate(raw))
                except (ValueError, ValidationError):
                    skipped += 1  # a damaged line is skipped, never repaired or guessed
        if skipped:
            log.warning("agri history %s: %d unreadable line(s) skipped", self.path, skipped)
        entries.sort(key=lambda e: e.computed_at)
        return entries[-limit:] if limit else entries
