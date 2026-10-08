"""Which district an area lies in: from the area's own properties, else OpenStreetMap reverse geocoding.

For any drawn area (not only predefined districts) the district of its representative point is
looked up with Nominatim, so later steps (jurisdiction, whom to contact) have a place to start. It
is context, labelled with its source (OpenStreetMap, ODbL), not an administrative determination:
an area can straddle a district border. Lookups are cached and rate-limited to Nominatim's usage
policy (at most one request per second, an identifying User-Agent).
"""

import threading
import time

from satquery.agri.areas import representative_point
from satquery.agri.cache import JsonCache, cache_key
from satquery.agri.models import MonitoredArea

NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
SOURCE = "OpenStreetMap Nominatim reverse geocoding"
LICENCE = "© OpenStreetMap contributors, ODbL"
USER_AGENT = "SatQuery-AG04-prototype (AI4SEVA hackathon 2026)"


class ReverseGeocoder:
    def __init__(self, cache: JsonCache | None = None, *, offline: bool = False, timeout: float = 15.0):
        self.cache = cache
        self.offline = offline
        self.timeout = timeout
        self._lock = threading.Lock()
        self._last = 0.0

    def lookup(self, latitude: float, longitude: float) -> dict | None:
        key = cache_key("reverse", round(latitude, 4), round(longitude, 4))
        hit = self.cache.get("geocode", key) if self.cache else None
        if hit:
            return hit.value | {"state_of_data": "CACHED", "retrieved_at": hit.retrieved_at}
        if self.offline:
            return None
        try:
            address = self._get(latitude, longitude)
        except Exception:  # context is optional: an unreachable geocoder never blocks an assessment
            return None
        found = {"district": address.get("state_district") or address.get("county"), "state": address.get("state"),
                 "country": address.get("country"), "source": SOURCE, "licence": LICENCE}
        if self.cache:
            entry = self.cache.put("geocode", key, found)
            return found | {"state_of_data": "LIVE", "retrieved_at": entry.retrieved_at}
        return found | {"state_of_data": "LIVE"}

    def _get(self, latitude: float, longitude: float) -> dict:
        import httpx

        with self._lock:  # Nominatim's policy: at most one request per second
            wait = 1.1 - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            with httpx.Client(timeout=self.timeout, headers={"User-Agent": USER_AGENT}) as client:
                response = client.get(NOMINATIM_URL, params={"lat": latitude, "lon": longitude, "format": "jsonv2",
                                                             "zoom": 10, "accept-language": "en"})
        response.raise_for_status()
        return response.json().get("address") or {}


def district_context(area: MonitoredArea, geocoder: ReverseGeocoder | None) -> dict | None:
    if area.district:
        return {"district": area.district, "state": area.state, "source": f"area properties ({area.boundary_source})",
                "note": area.note}
    if geocoder is None:
        return None
    longitude, latitude = representative_point(area)
    found = geocoder.lookup(latitude, longitude)
    return found | {"note": "District of the area's representative point; an area can straddle a border."} \
        if found else None
