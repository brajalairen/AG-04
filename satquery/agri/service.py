"""The dashboard's view of the risk engine: one assessment of every monitored area, reused for a while.

The API never scores anything itself. It asks this service, which runs the unchanged pipeline
(`pipeline.assess_areas`) at most once at a time and keeps the result for `agri_refresh_s`. The
inputs underneath are cached on disk by their own clients (weather 3 h, NDVI by window), so a
recompute is cheap once warm, and offline mode serves those caches only, labelled CACHED.

Demo reliability (Phase 4):
- `warm_in_background()` computes the first assessment when the server starts, so the first page
  does not wait for it.
- `save_snapshot()` freezes a known-good assessment to a file. It is served instead of live data when
  `agri_mode` is "snapshot", or automatically when the live assessment is missing inputs the snapshot
  has (lower data completeness), for example when the venue network is down. Snapshot data is always
  labelled SNAPSHOT with its time and the reason it is shown; it is never presented as live.

History: every live assessment that is served is appended to runs/agri/history.jsonl
(`history.py`); snapshots and offline re-scores are not, so the record holds only real points in time.
"""

import json
import logging
import threading
import time
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path

from satquery.agri.areas import demo_areas, load_areas
from satquery.agri.config import PestRulesConfig, RiskModelConfig, load_observation_rules, load_pest_rules, \
    load_risk_model
from satquery.agri.history import AssessmentHistory
from satquery.agri.models import MonitoredArea, RiskAssessment
from satquery.agri.pipeline import Sources, assess_areas, default_sources
from satquery.settings import Settings, load_settings

log = logging.getLogger(__name__)
SNAPSHOT_VERSION = 1
FALLBACK_MARGIN = 0.05  # live completeness this far below the snapshot's counts as "missing inputs"


@dataclass(frozen=True)
class Snapshot:
    areas: dict[str, MonitoredArea]
    assessments: list[RiskAssessment]  # ranked, most urgent first
    rules: PestRulesConfig
    model: RiskModelConfig
    computed_at: str  # ISO UTC
    offline: bool
    mode: str = "live"  # "live", or "snapshot" when a frozen snapshot is served
    snapshot_saved_at: str | None = None
    fallback_reason: str | None = None
    notes: list[str] = field(default_factory=list)

    def assessment(self, area_id: str) -> RiskAssessment | None:
        return next((a for a in self.assessments if a.area_id == area_id), None)


class AgriUnavailable(Exception):
    """The assessment could not be produced at all (for example an invalid areas file)."""


def mean_completeness(assessments: list[RiskAssessment]) -> float:
    return sum(a.confidence.data_completeness for a in assessments) / len(assessments) if assessments else 0.0


def write_snapshot(snapshot: Snapshot, path: Path) -> Path:
    """Freeze an assessment to `path` (atomic replace). Returns the path."""
    record = {"version": SNAPSHOT_VERSION, "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "computed_at": snapshot.computed_at, "offline": snapshot.offline,
              "areas": [a.model_dump() for a in snapshot.areas.values()],
              "assessments": [a.model_dump() for a in snapshot.assessments]}
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(".partial")
    partial.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    partial.replace(path)
    return path


def read_snapshot(path: Path, rules: PestRulesConfig, model: RiskModelConfig, reason: str | None) -> Snapshot:
    """A frozen snapshot, relabelled: every LIVE or CACHED source becomes SNAPSHOT (its original state
    and time are kept in the note), so nothing from the file can be shown as live. SAMPLE stays SAMPLE."""
    record = json.loads(path.read_text(encoding="utf-8"))
    if record.get("version") != SNAPSHOT_VERSION:
        raise ValueError(f"unsupported snapshot version {record.get('version')}")
    saved_at = record["saved_at"]
    areas = {a["id"]: MonitoredArea.model_validate(a) for a in record["areas"]}

    def relabel(provenance: list) -> list:
        out = []
        for p in provenance:
            if p.state in ("LIVE", "CACHED"):
                note = f"Frozen snapshot of {saved_at} (originally {p.state})." + (f" {p.note}" if p.note else "")
                p = p.model_copy(update={"state": "SNAPSHOT", "note": note})
            out.append(p)
        return out

    assessments = []
    for raw in record["assessments"]:
        a = RiskAssessment.model_validate(raw)
        factors = [f.model_copy(update={"provenance": relabel(f.provenance)}) for f in a.factors]
        assessments.append(a.model_copy(update={"factors": factors, "provenance": relabel(a.provenance)}))
    return Snapshot(areas=areas, assessments=assessments, rules=rules, model=model,
                    computed_at=record["computed_at"], offline=bool(record.get("offline")), mode="snapshot",
                    snapshot_saved_at=saved_at, fallback_reason=reason)


class AssessmentService:
    def __init__(self, settings: Settings | None = None, *, sources: Sources | None = None,
                 areas: list[MonitoredArea] | None = None, clock=time.monotonic,
                 history: AssessmentHistory | None = None):
        self._settings = settings
        self._sources = sources
        self._areas = areas
        self._clock = clock
        self._lock = threading.Lock()
        self._snapshot: Snapshot | None = None
        self._computed = 0.0
        self._history = history

    def _settings_now(self) -> Settings:
        return self._settings or load_settings()

    def history(self) -> AssessmentHistory:
        """The assessment history store (disabled when SATQUERY_AGRI_HISTORY is off)."""
        if self._history is None:
            settings = self._settings_now()
            self._history = AssessmentHistory(settings.runs_dir / "agri" / "history.jsonl"
                                              if settings.agri_history else None)
        return self._history

    def _record(self, live: Snapshot) -> None:
        """Append a served live assessment to the history; a failure is logged, never fatal."""
        try:
            config = {"pest_rules": f"{live.rules.version} ({live.rules.status})",
                      "risk_model": f"{live.model.version} ({live.model.status}, {live.model.calibration.status})"}
            try:
                observation_rules = load_observation_rules()
                config["observation_rules"] = f"{observation_rules.version} ({observation_rules.status})"
            except (OSError, ValueError):
                config["observation_rules"] = "unavailable"
            self.history().record(live.assessments, live.computed_at, config)
        except OSError as error:
            log.warning("agri history not recorded: %s", error)

    def snapshot_path(self) -> Path:
        settings = self._settings_now()
        return Path(settings.agri_snapshot) if settings.agri_snapshot else settings.runs_dir / "agri" / "snapshot.json"

    def areas(self) -> list[MonitoredArea]:
        """The monitored areas, without assessing them (for routing a question by its wording)."""
        if self._snapshot:
            return list(self._snapshot.areas.values())
        if self._areas:
            return self._areas
        settings = self._settings_now()
        try:
            return demo_areas() if settings.agri_areas == "demo" else load_areas(settings.agri_areas)
        except (OSError, ValueError):
            return []

    def _load_config(self, settings: Settings):
        try:
            areas = self._areas or (demo_areas() if settings.agri_areas == "demo" else load_areas(settings.agri_areas))
            return areas, load_pest_rules(), load_risk_model()
        except (OSError, ValueError) as error:
            raise AgriUnavailable(f"The monitored areas or thresholds could not be loaded: {error}") from error

    def _frozen(self, rules, model, reason: str) -> Snapshot | None:
        path = self.snapshot_path()
        if not path.is_file():
            return None
        try:
            return read_snapshot(path, rules, model, reason)
        except (OSError, ValueError, KeyError) as error:
            log.warning("agri snapshot %s unusable: %s", path, error)
            return None

    def _compute(self, settings: Settings) -> Snapshot:
        areas, rules, model = self._load_config(settings)
        if settings.agri_mode == "snapshot":
            frozen = self._frozen(rules, model, "Snapshot mode is switched on (SATQUERY_AGRI_MODE=snapshot).")
            if frozen is None:
                raise AgriUnavailable(f"Snapshot mode is on, but no usable snapshot exists at {self.snapshot_path()}.")
            return frozen
        sources = self._sources or default_sources(settings, offline=settings.agri_offline)
        try:
            assessments = assess_areas(areas, sources, rules=rules, model=model)
        except Exception as error:  # never leave the dashboard empty when a frozen snapshot exists
            frozen = self._frozen(rules, model, f"The live assessment failed ({type(error).__name__}).")
            if frozen is None:
                raise
            return frozen
        live = Snapshot(areas={a.id: a for a in areas}, assessments=assessments, rules=rules, model=model,
                        offline=settings.agri_offline,
                        computed_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
        # Prefer live data; fall back only when live is missing inputs the snapshot had.
        frozen = self._frozen(rules, model, "")
        if frozen is not None:
            live_c, frozen_c = mean_completeness(assessments), mean_completeness(frozen.assessments)
            if live_c + FALLBACK_MARGIN < frozen_c:
                return replace(frozen, fallback_reason=(
                    f"Live data is incomplete (mean data completeness {live_c:.0%}, snapshot {frozen_c:.0%}), "
                    "for example a provider could not be reached; showing the frozen snapshot."))
        if not settings.agri_offline:  # an offline run re-scores old cached inputs: not a new point in time
            self._record(live)
        return live

    def snapshot(self) -> Snapshot:
        """The current assessment, computed now if there is none or it is older than the refresh period."""
        settings = self._settings_now()
        with self._lock:  # concurrent first requests wait for one computation instead of starting several
            if self._snapshot and self._clock() - self._computed < settings.agri_refresh_s:
                return self._snapshot
            self._snapshot = self._compute(settings)
            self._computed = self._clock()
            return self._snapshot

    def save_snapshot(self, path: Path | None = None) -> Path:
        """Freeze the current assessment (live) to the snapshot file. Refuses to re-freeze a snapshot."""
        current = self._snapshot or self.snapshot()  # freeze what was just computed, not a fresh run
        if current.mode == "snapshot":
            raise AgriUnavailable("The current assessment is itself a snapshot; refusing to re-freeze it.")
        return write_snapshot(current, path or self.snapshot_path())

    def warm_in_background(self) -> threading.Thread:
        """Compute the first assessment off the request path (server start). Errors are logged, not raised."""
        def run():
            try:
                self.snapshot()
                log.info("agri assessment warmed")
            except Exception as error:
                log.warning("agri warm-up failed: %s", error)

        thread = threading.Thread(target=run, name="agri-warm-up", daemon=True)
        thread.start()
        return thread
