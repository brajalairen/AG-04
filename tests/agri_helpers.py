"""Shared builders for the AG-04 tests: synthetic weather, fake Statistical API, areas, configs.

Nothing here touches the network: weather payloads are built hour by hour, and the NDVI provider
returns statistics chosen by each test.
"""

import json
from datetime import date, timedelta

from satquery.agri.config import ASSETS, PestRulesConfig, RiskModelConfig
from satquery.agri.models import MonitoredArea
from satquery.agri.weather import parse_hourly

TODAY = date(2026, 10, 8)
VERIFIED_SOURCE = {"title": "Test source", "url": "https://example.org/verified", "verified_by": "Test agronomist",
                   "verified_on": "2026-10-08"}


def rect(west, south, east, north) -> dict:
    return {"type": "Polygon", "coordinates": [[[west, south], [east, south], [east, north], [west, north],
                                                [west, south]]]}


def area(area_id="a1", name="Test area", geometry=None, **extra) -> MonitoredArea:
    return MonitoredArea(id=area_id, name=name, kind=extra.pop("kind", "demo"),
                         geometry=geometry or rect(93.95, 24.45, 94.03, 24.52),
                         boundary_source=extra.pop("boundary_source", "test rectangle"), **extra)


def humid_day(rh_high_hours=12, temp=23.0):
    """A blast-favourable day under the placeholder rule: RH 95% for `rh_high_hours`, 75% otherwise."""
    return {"temperature_2m": [temp] * 24, "relative_humidity_2m": [95.0] * rh_high_hours + [75.0] * (24 - rh_high_hours),
            "dew_point_2m": [temp - 2] * 24, "precipitation": [0.2] * 24}


def dry_day(temp=23.0, rh=60.0):
    return {"temperature_2m": [temp] * 24, "relative_humidity_2m": [rh] * 24, "dew_point_2m": [temp - 8] * 24,
            "precipitation": [0.0] * 24}


def hourly_payload(days: dict[date, dict] | None = None, *, start=TODAY - timedelta(days=14), count=21,
                   default=None, offset=19800, latitude=24.49912, longitude=93.94231) -> dict:
    """An Open-Meteo-shaped hourly payload; `days` overrides chosen local dates (missing hours as None)."""
    default = default or dry_day()
    times, values = [], {name: [] for name in ("temperature_2m", "relative_humidity_2m", "dew_point_2m",
                                               "precipitation")}
    for n in range(count):
        day = start + timedelta(days=n)
        spec = (days or {}).get(day, default)
        for hour in range(24):
            times.append(f"{day.isoformat()}T{hour:02d}:00")
            for name in values:
                series = spec[name]
                values[name].append(series[hour] if hour < len(series) else None)
    return {"latitude": latitude, "longitude": longitude, "elevation": 781.0, "utc_offset_seconds": offset,
            "timezone": "Asia/Kolkata", "hourly_units": {"temperature_2m": "°C"}, "hourly": {"time": times, **values}}


def weather(days: dict[date, dict] | None = None, **kwargs):
    return parse_hourly(hourly_payload(days, **kwargs), requested=(24.485, 93.99),
                        retrieved_at="2026-10-08T00:00:00+00:00")


def stats_response(mean, *, pixels=1000, nodata=0, median=None, p10=None, p90=None) -> dict:
    stats = {"min": 0.0, "max": 0.9, "mean": mean, "stDev": 0.1, "sampleCount": pixels, "noDataCount": nodata,
             "percentiles": {"10.0": p10 if p10 is not None else (mean or 0) - 0.2,
                             "50.0": median if median is not None else mean,
                             "90.0": p90 if p90 is not None else (mean or 0) + 0.1}}
    return {"data": [{"interval": {"from": "x", "to": "y"}, "outputs": {"ndvi": {"bands": {"B0": {"stats": stats}}}}}],
            "status": "OK"}


class FakeStatsProvider:
    """`statistics(payload)` answers by the window's start year: {year: response or exception}."""

    def __init__(self, by_year: dict):
        self.by_year = by_year
        self.calls = []

    def statistics(self, payload):
        self.calls.append(payload)
        year = int(payload["aggregation"]["timeRange"]["from"][:4])
        answer = self.by_year[year]
        if isinstance(answer, Exception):
            raise answer
        return answer


def pest_rules_dict() -> dict:
    return json.loads((ASSETS / "pest_rules.json").read_text(encoding="utf-8"))


def risk_model_dict() -> dict:
    return json.loads((ASSETS / "risk_model.json").read_text(encoding="utf-8"))


def verified_rules() -> PestRulesConfig:
    data = pest_rules_dict()
    data["status"] = "VERIFIED"
    for pest in data["pests"]:
        pest["status"], pest["sources"] = "VERIFIED", [VERIFIED_SOURCE]
    return PestRulesConfig.model_validate(data)


def verified_model(**overrides) -> RiskModelConfig:
    data = risk_model_dict() | {"status": "VERIFIED", "sources": [VERIFIED_SOURCE]} | overrides
    return RiskModelConfig.model_validate(data)
