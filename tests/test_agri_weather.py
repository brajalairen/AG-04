"""Hourly weather history + forecast: request, parsing, caching, honest stale and offline behaviour."""

from datetime import datetime, timezone

import pytest

from agri_helpers import TODAY, hourly_payload, weather
from satquery.agri.cache import JsonCache
from satquery.agri.weather import HourlyWeatherClient, parse_hourly, summarise
from satquery.specialists.weather import InvalidWeatherResponse, NoForecastData, WeatherUnavailable


class Clock:
    def __init__(self):
        self.now = 1_000_000.0

    def __call__(self):
        return self.now


def test_the_request_asks_for_14_past_days_7_forecast_days_and_the_four_variables(monkeypatch):
    seen = {}

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return hourly_payload()

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url, params):
            seen.update(url=url, params=params)
            return FakeResponse()

    monkeypatch.setattr("httpx.Client", FakeClient)
    result = HourlyWeatherClient().fetch(24.4851, 93.9912)
    assert seen["url"] == "https://api.open-meteo.com/v1/forecast"
    assert seen["params"] == {"latitude": 24.485, "longitude": 93.991, "timezone": "auto", "past_days": 14,
                                   "forecast_days": 7,
                                   "hourly": "temperature_2m,relative_humidity_2m,dew_point_2m,precipitation"}
    assert result.state == "LIVE" and len(result.times) == 21 * 24


def test_parsing_groups_hours_by_local_day_and_keeps_the_grid_cell():
    parsed = weather()
    days = parsed.by_day()
    assert len(days) == 21 and all(len(day["temperature_2m"]) == 24 for day in days.values())
    assert (parsed.latitude, parsed.longitude, parsed.timezone) == (24.49912, 93.94231, "Asia/Kolkata")
    # 19:00 UTC on 7 October is already 8 October in Manipur (UTC+5:30)
    assert parsed.local_today(datetime(2026, 10, 7, 19, 0, tzinfo=timezone.utc)) == TODAY


def test_provenance_says_the_history_is_model_data_not_station_observations():
    provenance = weather().provenance()
    assert provenance.state == "LIVE" and "Open-Meteo" in provenance.source
    assert "not station observations" in provenance.note and "CC BY 4.0" in provenance.licence
    assert provenance.covers == "2026-09-24 to 2026-10-14"


@pytest.mark.parametrize("payload, error", [
    ({}, InvalidWeatherResponse),
    ({"hourly": {"time": []}}, NoForecastData),
    ({"hourly": {"time": ["2026-10-08T00:00"], "temperature_2m": [20]}}, InvalidWeatherResponse),
])
def test_broken_responses_raise_typed_errors(payload, error):
    with pytest.raises(error):
        parse_hourly(payload, requested=(0, 0), retrieved_at="x")


def test_all_empty_values_are_no_data_not_zeros():
    payload = hourly_payload(count=1)
    for name in ("temperature_2m", "relative_humidity_2m", "dew_point_2m", "precipitation"):
        payload["hourly"][name] = [None] * 24
    with pytest.raises(NoForecastData):
        parse_hourly(payload, requested=(0, 0), retrieved_at="x")


def test_a_fresh_cache_answers_as_cached(tmp_path, monkeypatch):
    clock = Clock()
    client = HourlyWeatherClient(JsonCache(tmp_path, clock=clock))
    calls = []
    monkeypatch.setattr(client, "_get", lambda lat, lon: calls.append((lat, lon)) or hourly_payload())
    first, second = client.fetch(24.485, 93.99), client.fetch(24.485, 93.99)
    assert (first.state, second.state, len(calls)) == ("LIVE", "CACHED", 1)
    assert second.retrieved_at == first.retrieved_at and not second.stale


def test_an_expired_cache_is_refreshed_and_used_only_as_a_labelled_stale_fallback(tmp_path, monkeypatch):
    clock = Clock()
    client = HourlyWeatherClient(JsonCache(tmp_path, clock=clock), max_age_s=3600)
    monkeypatch.setattr(client, "_get", lambda lat, lon: hourly_payload())
    client.fetch(24.485, 93.99)
    clock.now += 7200

    def down(lat, lon):
        raise WeatherUnavailable("The weather provider could not be reached.")

    monkeypatch.setattr(client, "_get", down)
    stale = client.fetch(24.485, 93.99)
    assert stale.state == "CACHED" and stale.stale
    assert "STALE" in stale.provenance().note


def test_no_cache_and_no_provider_raises_instead_of_inventing(tmp_path, monkeypatch):
    client = HourlyWeatherClient(JsonCache(tmp_path))

    def down(lat, lon):
        raise WeatherUnavailable("The weather provider could not be reached.")

    monkeypatch.setattr(client, "_get", down)
    with pytest.raises(WeatherUnavailable):
        client.fetch(24.485, 93.99)


def test_offline_mode_serves_only_the_cache(tmp_path, monkeypatch):
    cache = JsonCache(tmp_path)
    with pytest.raises(WeatherUnavailable, match="Offline mode"):
        HourlyWeatherClient(cache, offline=True).fetch(24.485, 93.99)
    online = HourlyWeatherClient(cache)
    monkeypatch.setattr(online, "_get", lambda lat, lon: hourly_payload())
    online.fetch(24.485, 93.99)
    assert HourlyWeatherClient(cache, offline=True).fetch(24.485, 93.99).state == "CACHED"


def test_summary_figures_for_the_last_and_next_seven_days():
    figures = summarise(weather(), TODAY)
    past = figures["past_7_days"]
    assert past["days"] == 7 and past["mean_temperature_c"] == 23.0 and past["mean_relative_humidity_pct"] == 60.0
    assert past["hours_rh_at_or_above_90"] == 0 and past["precipitation_mm"] == 0.0
    assert figures["next_7_days"]["days"] == 7
