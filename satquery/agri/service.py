"""The dashboard's view of the risk engine: one assessment of every monitored area, reused for a while.

The API never scores anything itself. It asks this service, which runs the unchanged pipeline
(`pipeline.assess_areas`) at most once at a time and keeps the result for `agri_refresh_s`. The
inputs underneath are cached on disk by their own clients (weather 3 h, NDVI by window), so a
recompute is cheap once warm, and offline mode serves those caches only, labelled CACHED.
"""

import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from satquery.agri.areas import demo_areas, load_areas
from satquery.agri.config import PestRulesConfig, RiskModelConfig, load_pest_rules, load_risk_model
from satquery.agri.models import MonitoredArea, RiskAssessment
from satquery.agri.pipeline import Sources, assess_areas, default_sources
from satquery.settings import Settings, load_settings


@dataclass(frozen=True)
class Snapshot:
    areas: dict[str, MonitoredArea]
    assessments: list[RiskAssessment]  # ranked, most urgent first
    rules: PestRulesConfig
    model: RiskModelConfig
    computed_at: str  # ISO UTC
    offline: bool

    def assessment(self, area_id: str) -> RiskAssessment | None:
        return next((a for a in self.assessments if a.area_id == area_id), None)


class AgriUnavailable(Exception):
    """The assessment could not be produced at all (for example an invalid areas file)."""


class AssessmentService:
    def __init__(self, settings: Settings | None = None, *, sources: Sources | None = None,
                 areas: list[MonitoredArea] | None = None, clock=time.monotonic):
        self._settings = settings
        self._sources = sources
        self._areas = areas
        self._clock = clock
        self._lock = threading.Lock()
        self._snapshot: Snapshot | None = None
        self._computed = 0.0

    def _settings_now(self) -> Settings:
        return self._settings or load_settings()

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

    def snapshot(self) -> Snapshot:
        """The current assessment, computed now if there is none or it is older than the refresh period."""
        settings = self._settings_now()
        with self._lock:  # concurrent first requests wait for one computation instead of starting several
            if self._snapshot and self._clock() - self._computed < settings.agri_refresh_s:
                return self._snapshot
            try:
                areas = self._areas or (demo_areas() if settings.agri_areas == "demo" else load_areas(settings.agri_areas))
                rules, model = load_pest_rules(), load_risk_model()
            except (OSError, ValueError) as error:
                raise AgriUnavailable(f"The monitored areas or thresholds could not be loaded: {error}") from error
            sources = self._sources or default_sources(settings, offline=settings.agri_offline)
            assessments = assess_areas(areas, sources, rules=rules, model=model)
            self._snapshot = Snapshot(areas={a.id: a for a in areas}, assessments=assessments, rules=rules,
                                      model=model, offline=settings.agri_offline,
                                      computed_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
            self._computed = self._clock()
            return self._snapshot
