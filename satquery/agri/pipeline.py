"""Gather each monitored area's inputs, score it, and rank all areas.

Inputs are fetched independently and a failure in one never stops the others: an unreachable
weather provider makes the weather factor unavailable (named, not estimated) and the remaining
factors still report. Scoring itself (`risk.py`) is a pure function of the gathered inputs.

Field observations come from a real dataset when SATQUERY_AGRI_OBSERVATIONS names one
(`observations.py`); otherwise from the SAMPLE generator, labelled as such.
"""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone

from satquery.agri import risk, rules as pest_rules
from satquery.agri.areas import representative_point
from satquery.agri.cache import JsonCache
from satquery.agri.config import (ObservationRulesConfig, PestRulesConfig, RiskModelConfig, load_observation_rules,
                                  load_pest_rules, load_risk_model)
from satquery.agri.context import ReverseGeocoder, district_context
from satquery.agri.models import MonitoredArea, RiskAssessment
from satquery.agri.ndvi import NdviClient
from satquery.agri.observations import PestObservationProvider, load_default_source
from satquery.agri.reports import SampleReportSource
from satquery.agri.weather import HourlyWeatherClient
from satquery.providers.errors import RetrievalError
from satquery.specialists.weather import WeatherError


@dataclass
class Sources:
    weather: HourlyWeatherClient | None
    ndvi: NdviClient | None
    reports: PestObservationProvider | None  # field observations, SAMPLE or real
    geocoder: ReverseGeocoder | None = None


def default_sources(settings, *, offline: bool = False, ndvi: bool = True, geocode: bool = False) -> Sources:
    """Live sources with a disk cache under `runs/agri-cache`. NDVI needs Copernicus credentials;
    without them the NDVI factor is reported unavailable rather than estimated. Field observations
    are the real dataset in SATQUERY_AGRI_OBSERVATIONS when set, else the SAMPLE generator."""
    cache = JsonCache(settings.runs_dir / "agri-cache")
    provider = None
    if ndvi and settings.copernicus_client_id and settings.copernicus_client_secret:
        from satquery.providers.copernicus import CopernicusSentinelProvider

        provider = CopernicusSentinelProvider(settings.copernicus_client_id, settings.copernicus_client_secret)
    return Sources(weather=HourlyWeatherClient(cache, offline=offline),
                   ndvi=NdviClient(provider, cache, offline=offline) if ndvi else None,
                   reports=load_default_source() or SampleReportSource(),
                   geocoder=ReverseGeocoder(cache, offline=offline) if geocode else None)


def assess_area(area: MonitoredArea, sources: Sources, rules: PestRulesConfig, model: RiskModelConfig, *,
                now: datetime, observation_rules: ObservationRulesConfig | None = None) -> RiskAssessment:
    longitude, latitude = representative_point(area)
    weather, weather_error = None, None
    if sources.weather is None:
        weather_error = "no weather source is configured"
    else:
        try:
            weather = sources.weather.fetch(latitude, longitude)
        except WeatherError as error:
            weather_error = error.message
    today = weather.local_today(now) if weather else now.date()
    pests = [pest_rules.evaluate(rule, weather, today, rules.min_hours_per_day) for rule in rules.pests] if weather else []

    anomaly, ndvi_error = None, None
    if sources.ndvi is None:
        ndvi_error = "NDVI is switched off for this run"
    elif sources.ndvi.provider is None and not sources.ndvi.offline:
        ndvi_error = "Copernicus credentials are not configured"
    else:
        try:
            anomaly = sources.ndvi.anomaly(area, today, model.ndvi)
        except RetrievalError as error:
            ndvi_error = error.message

    evidence = None
    if sources.reports is not None:
        evidence = sources.reports.observations(area, today, model.reports.lookback_days, observation_rules)

    names = {rule.id: rule.name for rule in observation_rules.pests} if observation_rules else {}
    return risk.assess_area(area, rules=rules, model=model, as_of=now.isoformat(timespec="seconds"), today=today,
                            pests=pests, weather=weather, weather_error=weather_error,
                            ndvi=risk.ndvi_factor(anomaly, ndvi_error, model), evidence=evidence, names=names,
                            district_context=district_context(area, sources.geocoder))


def assess_areas(areas: list[MonitoredArea], sources: Sources, *, rules: PestRulesConfig | None = None,
                 model: RiskModelConfig | None = None, now: datetime | None = None,
                 observation_rules: ObservationRulesConfig | None = None, workers: int = 4) -> list[RiskAssessment]:
    """Every area scored and ranked, most urgent first."""
    rules, model = rules or load_pest_rules(), model or load_risk_model()
    observation_rules = observation_rules or load_observation_rules()
    now = now or datetime.now(timezone.utc)
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        assessed = list(pool.map(lambda area: assess_area(area, sources, rules, model, now=now,
                                                          observation_rules=observation_rules), areas))
    return risk.rank(assessed)
