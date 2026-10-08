"""Hourly weather for risk rules: about 14 days of recent history and a 7-day forecast (Open-Meteo).

One request returns both, in the location's local time. The "history" is the weather model's own
recent data (analyses and short-range forecasts), not station observations, and every result says
so. Responses are cached on disk; a cached answer is labelled CACHED with its age, and an answer
older than the freshness limit is used only when the provider fails or in offline mode, labelled stale with
the reason. Failures raise
the typed errors of `satquery.specialists.weather`; no value is ever made up.
"""

from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta, timezone

from satquery.agri.cache import JsonCache, cache_key
from satquery.agri.models import DataState, Provenance
from satquery.specialists.weather import (ATTRIBUTION, FORECAST_URL, InvalidWeatherResponse, NoForecastData,
                                          WeatherRateLimited, WeatherTimeout, WeatherUnavailable, _scrub)

HOURLY = ("temperature_2m", "relative_humidity_2m", "dew_point_2m", "precipitation")
PAST_DAYS = 14
FORECAST_DAYS = 7  # includes today
SOURCE = "Open-Meteo forecast API (best_match weather models), hourly"
HISTORY_NOTE = ("Past days are the weather model's own analyses and short-range forecasts for the nearest grid "
                "cell, not station observations.")


@dataclass(frozen=True)
class HourlyWeather:
    requested: tuple[float, float]  # (latitude, longitude) asked for
    latitude: float                 # the model grid cell actually returned
    longitude: float
    elevation_m: float | None
    timezone: str
    utc_offset_seconds: int
    times: tuple[str, ...]          # local ISO hours, e.g. "2026-10-08T14:00"
    values: dict                    # variable -> tuple of floats or None, aligned with `times`
    retrieved_at: str               # ISO UTC
    state: DataState = "LIVE"
    stale: bool = False
    units: dict = field(default_factory=dict)
    stale_reason: str | None = None  # why an old copy is shown: offline mode, or the provider failed

    def local_today(self, now: datetime | None = None) -> date:
        now = now or datetime.now(timezone.utc)
        return (now + timedelta(seconds=self.utc_offset_seconds)).date()

    def by_day(self) -> dict[str, dict[str, list]]:
        """local ISO date -> variable -> that day's hourly values (None where missing)."""
        days: dict[str, dict[str, list]] = {}
        for i, stamp in enumerate(self.times):
            day = days.setdefault(stamp[:10], {name: [] for name in self.values})
            for name, series in self.values.items():
                day[name].append(series[i])
        return days

    def provenance(self) -> Provenance:
        first, last = (self.times[0][:10], self.times[-1][:10]) if self.times else (None, None)
        note = HISTORY_NOTE + f" Grid cell {self.latitude:.3f}, {self.longitude:.3f}; times in {self.timezone}."
        if self.stale:
            note += f" STALE: an older cached copy is shown ({self.stale_reason or 'not refreshed'})."
        return Provenance(source=SOURCE, state=self.state, retrieved_at=self.retrieved_at,
                          covers=f"{first} to {last}" if first else None, licence=ATTRIBUTION, note=note)


def parse_hourly(payload, *, requested: tuple[float, float], retrieved_at: str, state: DataState = "LIVE",
                 stale: bool = False, stale_reason: str | None = None) -> HourlyWeather:
    if not isinstance(payload, dict) or not isinstance(payload.get("hourly"), dict):
        raise InvalidWeatherResponse("The weather provider's response has no hourly data.")
    hourly = payload["hourly"]
    times = hourly.get("time")
    if not isinstance(times, list) or not times:
        raise NoForecastData("The weather provider returned no hours for this location.")
    values = {}
    for name in HOURLY:
        series = hourly.get(name)
        if not isinstance(series, list) or len(series) != len(times):
            raise InvalidWeatherResponse(f"The weather provider's hourly '{name}' is missing or incomplete.")
        values[name] = tuple(float(v) if isinstance(v, (int, float)) else None for v in series)
    if all(v is None for series in values.values() for v in series):
        raise NoForecastData("The weather provider returned only empty values for this location.")
    try:
        offset = int(payload.get("utc_offset_seconds", 0))
        latitude, longitude = float(payload["latitude"]), float(payload["longitude"])
    except (TypeError, ValueError, KeyError) as error:
        raise InvalidWeatherResponse("The weather provider's response has no usable location.") from error
    elevation = payload.get("elevation")
    return HourlyWeather(requested=requested, latitude=latitude, longitude=longitude,
                         elevation_m=float(elevation) if isinstance(elevation, (int, float)) else None,
                         timezone=str(payload.get("timezone") or "GMT"), utc_offset_seconds=offset,
                         times=tuple(str(t) for t in times), values=values, retrieved_at=retrieved_at,
                         state=state, stale=stale, units=dict(payload.get("hourly_units") or {}),
                         stale_reason=stale_reason if stale else None)


class HourlyWeatherClient:
    """Fetches and caches hourly history + forecast for a point. `offline=True` serves the cache only."""

    def __init__(self, cache: JsonCache | None = None, *, timeout: float = 20.0, max_age_s: float = 3 * 3600,
                 offline: bool = False):
        self.cache = cache
        self.timeout = timeout
        self.max_age_s = max_age_s
        self.offline = offline

    def fetch(self, latitude: float, longitude: float) -> HourlyWeather:
        requested = (round(latitude, 3), round(longitude, 3))
        key = cache_key("hourly", requested, PAST_DAYS, FORECAST_DAYS, HOURLY)
        hit = self.cache.get("weather", key) if self.cache else None
        if hit and (self.offline or hit.age_s < self.max_age_s):
            return parse_hourly(hit.value, requested=requested, retrieved_at=hit.retrieved_at, state="CACHED",
                                stale=hit.age_s >= self.max_age_s,
                                stale_reason="offline mode: cached data only, not refreshed")
        if self.offline:
            raise WeatherUnavailable("Offline mode: no cached weather for this location.")
        try:
            payload = self._get(*requested)
            parsed = parse_hourly(payload, requested=requested,
                                  retrieved_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
        except (WeatherUnavailable, WeatherTimeout, WeatherRateLimited, InvalidWeatherResponse, NoForecastData):
            if hit:  # an older copy, labelled stale, rather than nothing or something invented
                return parse_hourly(hit.value, requested=requested, retrieved_at=hit.retrieved_at, state="CACHED",
                                    stale=True, stale_reason="the provider could not be reached")
            raise
        if self.cache:  # cached only once it has parsed, so a broken response is never kept
            entry = self.cache.put("weather", key, payload)
            parsed = replace(parsed, retrieved_at=entry.retrieved_at)  # one fetch time, live or cached
        return parsed

    def _get(self, latitude: float, longitude: float) -> dict:
        import httpx

        params = {"latitude": latitude, "longitude": longitude, "timezone": "auto", "past_days": PAST_DAYS,
                  "forecast_days": FORECAST_DAYS, "hourly": ",".join(HOURLY)}
        try:
            with httpx.Client(timeout=self.timeout, headers={"User-Agent": "SatQuery AG-04 prototype"}) as client:
                response = client.get(FORECAST_URL, params=params)
        except httpx.TimeoutException as error:
            raise WeatherTimeout("The weather provider did not respond in time.") from error
        except httpx.HTTPError as error:
            raise WeatherUnavailable("The weather provider could not be reached.") from error
        if response.status_code == 429:
            raise WeatherRateLimited("The weather provider is limiting requests right now.")
        if response.status_code >= 400:
            raise WeatherUnavailable(f"The weather provider could not answer (HTTP {response.status_code}).",
                                     detail=_scrub(response.text) or None)
        try:
            return response.json()
        except ValueError as error:
            raise InvalidWeatherResponse("The weather provider's response is not valid JSON.") from error


def summarise(weather: HourlyWeather, today: date) -> dict:
    """Plain figures for an area's drawer: the last 7 days and the next 7 (None where data is missing)."""
    days = weather.by_day()

    def span(start: date, count: int) -> list[dict]:
        return [days[d] for d in ((start + timedelta(days=i)).isoformat() for i in range(count)) if d in days]

    def figures(chunk: list[dict]) -> dict:
        def values(name):
            return [v for day in chunk for v in day[name] if v is not None]

        temp, rh, rain = values("temperature_2m"), values("relative_humidity_2m"), values("precipitation")
        return {"days": len(chunk),
                "mean_temperature_c": round(sum(temp) / len(temp), 1) if temp else None,
                "min_temperature_c": round(min(temp), 1) if temp else None,
                "max_temperature_c": round(max(temp), 1) if temp else None,
                "mean_relative_humidity_pct": round(sum(rh) / len(rh), 1) if rh else None,
                "hours_rh_at_or_above_90": sum(1 for v in values("relative_humidity_2m") if v >= 90),
                "precipitation_mm": round(sum(rain), 1) if rain else None}

    return {"past_7_days": figures(span(today - timedelta(days=7), 7)),
            "next_7_days": figures(span(today, 7))}
