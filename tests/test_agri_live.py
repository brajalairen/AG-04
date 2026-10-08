"""Live checks of the AG-04 data sources. Deselected by default; run with `pytest -m live` (uses quota)."""

from datetime import datetime, timezone

import pytest

from satquery.agri.areas import demo_areas
from satquery.agri.config import load_risk_model
from satquery.agri.ndvi import NdviClient
from satquery.agri.weather import HourlyWeatherClient
from satquery.settings import load_settings

pytestmark = pytest.mark.live


def test_open_meteo_returns_14_past_and_7_forecast_days_of_hourly_data():
    found = HourlyWeatherClient().fetch(24.485, 93.99)
    days = found.by_day()
    assert len(days) == 21 and all(len(day["relative_humidity_2m"]) == 24 for day in days.values())
    assert found.timezone == "Asia/Kolkata" and found.state == "LIVE"


def test_the_statistical_api_gives_a_current_ndvi_and_a_baseline_for_a_demo_area():
    settings = load_settings()
    if not settings.copernicus_client_id:
        pytest.skip("Copernicus credentials are not configured")
    from satquery.providers.copernicus import CopernicusSentinelProvider

    provider = CopernicusSentinelProvider(settings.copernicus_client_id, settings.copernicus_client_secret)
    area = demo_areas()[0]
    anomaly = NdviClient(provider).anomaly(area, datetime.now(timezone.utc).date(), load_risk_model().ndvi)
    assert anomaly.current.pixels > 1000 and anomaly.current.state == "LIVE"
    assert all(-0.2 <= w.mean <= 1.0 for w in [anomaly.current, *anomaly.baseline] if w.mean is not None)
