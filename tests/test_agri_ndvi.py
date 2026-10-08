"""NDVI now vs the same dates in earlier years (Statistical API), with honest handling of cloud and gaps."""

from datetime import date

import pytest

from agri_helpers import TODAY, FakeStatsProvider, area, rect, stats_response
from satquery.agri.cache import JsonCache
from satquery.agri.config import load_risk_model
from satquery.agri.ndvi import (EVALSCRIPT, NdviClient, parse_statistics, resolution_deg, statistics_payload,
                                windows)
from satquery.providers.errors import RateLimited

CFG = load_risk_model().ndvi


def provider(current=0.70, baseline=(0.72, 0.74, 0.76), **current_kw):
    by_year = {2026: stats_response(current, **current_kw) if not isinstance(current, Exception) else current}
    by_year |= {2025 - i: stats_response(v) if not isinstance(v, Exception) else v for i, v in enumerate(baseline)}
    return FakeStatsProvider(by_year)


def test_windows_are_the_last_30_days_and_the_same_dates_in_the_three_previous_years():
    assert windows(TODAY, CFG) == [("current", date(2026, 9, 8), date(2026, 10, 8)),
                                   ("2025", date(2025, 9, 8), date(2025, 10, 8)),
                                   ("2024", date(2024, 9, 8), date(2024, 10, 8)),
                                   ("2023", date(2023, 9, 8), date(2023, 10, 8))]


def test_a_leap_day_maps_to_28_february_in_other_years():
    found = windows(date(2028, 2, 29), CFG)
    assert found[1] == ("2027", date(2027, 1, 30), date(2027, 2, 28))


def test_the_request_masks_cloud_and_water_per_observation_and_takes_the_median():
    payload = statistics_payload(area(), date(2026, 9, 8), date(2026, 10, 8), 0.0009)
    assert payload["input"]["bounds"]["geometry"] == area().geometry
    assert payload["aggregation"]["timeRange"] == {"from": "2026-09-08T00:00:00Z", "to": "2026-10-08T00:00:00Z"}
    assert payload["aggregation"]["aggregationInterval"]["of"] == "P30D"
    assert 'mosaicking: "ORBIT"' in EVALSCRIPT and "var EXCLUDED = [0, 1, 3, 6, 8, 9, 10, 11];" in EVALSCRIPT
    assert "median" in EVALSCRIPT and "values.length % 2" in EVALSCRIPT  # the %% escape became a real %


def test_resolution_keeps_large_areas_under_the_pixel_budget():
    small = resolution_deg(area(), CFG)
    large = resolution_deg(area(geometry=rect(93.0, 24.0, 94.0, 25.0)), CFG)  # ~11,000 km2
    assert small == CFG.min_resolution_deg
    assert large > small and (1.0 / large) ** 2 <= CFG.max_pixels * 1.01


def test_parse_statistics_reads_the_verified_response_shape():
    parsed = parse_statistics(stats_response(0.73, pixels=6942, nodata=1, median=0.79, p10=0.51, p90=0.87))
    assert parsed == {"mean": 0.73, "median": 0.79, "p10": 0.51, "p90": 0.87, "pixels": 6942, "nodata": 1}


@pytest.mark.parametrize("response", [{"data": [], "status": "OK"}, {"status": "FAILED"},
                                      {"data": [{"error": {"message": "boom"}}], "status": "OK"}])
def test_unusable_responses_are_errors_not_values(response):
    with pytest.raises(ValueError):
        parse_statistics(response)


def test_a_clear_window_is_usable_and_labelled_live(tmp_path):
    client = NdviClient(provider(), JsonCache(tmp_path))
    window = client.window(area(), "current", date(2026, 9, 8), TODAY, 0.0009, CFG)
    assert window.usable and window.state == "LIVE" and window.mean == 0.70 and window.observed_fraction == 1.0


def test_a_cloudy_window_is_unusable_and_says_why():
    client = NdviClient(provider(pixels=1000, nodata=800))
    window = client.window(area(), "current", date(2026, 9, 8), TODAY, 0.0009, CFG)
    assert not window.usable and window.reason == "only 20% of the area had a clear observation (minimum 30%)"
    assert window.mean == 0.70, "the measured value is kept for inspection but not used"


def test_a_provider_error_is_a_reason_not_a_value():
    client = NdviClient(provider(current=RateLimited("Copernicus quota or rate limit reached.")))
    window = client.window(area(), "current", date(2026, 9, 8), TODAY, 0.0009, CFG)
    assert not window.usable and window.mean is None
    assert window.reason == "imagery provider error: Copernicus quota or rate limit reached."


def test_windows_are_cached_and_served_as_cached(tmp_path):
    fake = provider()
    cache = JsonCache(tmp_path)
    NdviClient(fake, cache).anomaly(area(), TODAY, CFG)
    again = NdviClient(fake, cache).anomaly(area(), TODAY, CFG)
    assert len(fake.calls) == 4, "each window fetched once"
    assert {w.state for w in [again.current, *again.baseline]} == {"CACHED"}


def test_offline_without_cache_gives_reasons_not_values(tmp_path):
    anomaly = NdviClient(provider(), JsonCache(tmp_path), offline=True).anomaly(area(), TODAY, CFG)
    assert not anomaly.current.usable and anomaly.current.reason == "offline: no cached NDVI for this window"
    assert anomaly.relative_change is None


def test_the_anomaly_compares_with_the_mean_of_the_baseline_years():
    anomaly = NdviClient(provider(current=0.60, baseline=(0.70, 0.75, 0.80))).anomaly(area(), TODAY, CFG)
    assert anomaly.baseline_mean == pytest.approx(0.75) and anomaly.baseline_years_used == 3
    assert anomaly.relative_change == pytest.approx(-0.2) and anomaly.absolute_change == pytest.approx(-0.15)
    assert anomaly.baseline_range == (0.70, 0.80) and anomaly.within_baseline_range is False


def test_too_few_clear_baseline_years_gives_no_anomaly():
    cloudy = stats_response(0.7, pixels=1000, nodata=900)
    fake = FakeStatsProvider({2026: stats_response(0.6), 2025: stats_response(0.7), 2024: cloudy, 2023: cloudy})
    anomaly = NdviClient(fake).anomaly(area(), TODAY, CFG)
    assert anomaly.baseline_years_used == 1 and anomaly.relative_change is None


def test_an_unusable_current_window_gives_no_anomaly():
    anomaly = NdviClient(provider(pixels=1000, nodata=950)).anomaly(area(), TODAY, CFG)
    assert not anomaly.current.usable and anomaly.relative_change is None and anomaly.baseline_mean is not None


def test_provenance_lists_each_window_with_its_clear_share():
    anomaly = NdviClient(provider()).anomaly(area(), TODAY, CFG)
    provenance = NdviClient.provenance(anomaly)
    assert [p.covers for p in provenance][0] == "2026-09-08 to 2026-10-08 (end exclusive)"
    assert all("Sentinel-2 L2A" in p.source and "Copernicus Sentinel data" in p.licence for p in provenance)
    assert provenance[1].note == "2025 window, 100% of the area observed clear"
