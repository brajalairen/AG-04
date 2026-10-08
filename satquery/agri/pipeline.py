"""Gather each monitored area's inputs, score it, and rank all areas.

Inputs are fetched independently and a failure in one never stops the others: an unreachable
weather provider makes the weather factor unavailable (named, not estimated) and the remaining
factors still report. Scoring itself (`risk.py`) is a pure function of the gathered inputs.
"""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone

from satquery.agri import risk, rules as pest_rules
from satquery.agri.areas import representative_point
from satquery.agri.cache import JsonCache
from satquery.agri.config import PestRulesConfig, RiskModelConfig, load_pest_rules, load_risk_model
from satquery.agri.context import ReverseGeocoder, district_context
from satquery.agri.models import MonitoredArea, RiskAssessment
from satquery.agri.ndvi import NdviClient
from satquery.agri.reports import SampleReportSource
from satquery.agri.weather import HourlyWeatherClient
from satquery.providers.errors import RetrievalError
from satquery.specialists.weather import WeatherError


@dataclass
class Sources:
    weather: HourlyWeatherClient | None
    ndvi: NdviClient | None
    reports: SampleReportSource | None
    geocoder: ReverseGeocoder | None = None


def default_sources(settings, *, offline: bool = False, ndvi: bool = True, geocode: bool = False) -> Sources:
    """Live sources with a disk cache under `runs/agri-cache`. NDVI needs Copernicus credentials;
    without them the NDVI factor is reported unavailable rather than estimated."""
    cache = JsonCache(settings.runs_dir / "agri-cache")
    provider = None
    if ndvi and settings.copernicus_client_id and settings.copernicus_client_secret:
        from satquery.providers.copernicus import CopernicusSentinelProvider

        provider = CopernicusSentinelProvider(settings.copernicus_client_id, settings.copernicus_client_secret)
    return Sources(weather=HourlyWeatherClient(cache, offline=offline),
                   ndvi=NdviClient(provider, cache, offline=offline) if ndvi else None,
                   reports=SampleReportSource(),
                   geocoder=ReverseGeocoder(cache, offline=offline) if geocode else None)


def assess_area(area: MonitoredArea, sources: Sources, rules: PestRulesConfig, model: RiskModelConfig, *,
                now: datetime) -> RiskAssessment:
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

    reports, report_provenance = None, None
    if sources.reports is not None:
        reports, report_provenance = sources.reports.for_area(area, today, model.reports.lookback_days)

    factors = [risk.weather_factor(pests, weather, weather_error, model, area, today),
               risk.ndvi_factor(anomaly, ndvi_error, model),
               risk.report_factor(reports, report_provenance, model, today)]
    return risk.combine(area, factors, pests, rules, model, as_of=now.isoformat(timespec="seconds"),
                        district_context=district_context(area, sources.geocoder))


def assess_areas(areas: list[MonitoredArea], sources: Sources, *, rules: PestRulesConfig | None = None,
                 model: RiskModelConfig | None = None, now: datetime | None = None,
                 workers: int = 4) -> list[RiskAssessment]:
    """Every area scored and ranked, most urgent first."""
    rules, model = rules or load_pest_rules(), model or load_risk_model()
    now = now or datetime.now(timezone.utc)
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        assessed = list(pool.map(lambda area: assess_area(area, sources, rules, model, now=now), areas))
    return risk.rank(assessed)
