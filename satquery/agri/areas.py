"""Monitored areas: where they come from, and the little geometry the risk engine needs.

Any GeoJSON polygon can be monitored, so the engine is not tied to a fixed list of districts. Every
area must say where its outline comes from (`boundary_source`): a verified district file names its
dataset, and a demo rectangle says it is not an administrative boundary. Outlines are never
invented. Geometry is planar in longitude/latitude with a latitude correction, which is adequate at
district scale; shapely is deliberately not a dependency (see `satquery.geo`).
"""

import json
import math
from pathlib import Path

from satquery import geo
from satquery.agri.config import ASSETS
from satquery.agri.models import MonitoredArea

KM_PER_DEGREE_LAT = 110.57
KM_PER_DEGREE_LON_EQUATOR = 111.32


class AreaFileError(ValueError):
    """The areas file cannot be used; the message says which feature and why."""


def load_areas(path: str | Path) -> list[MonitoredArea]:
    """Monitored areas from a GeoJSON FeatureCollection.

    Each feature needs properties `id`, `name` and `boundary_source`; `kind` defaults to "district",
    `district`, `state` and `note` are optional. Refused as a whole when any feature is invalid, so a
    half-loaded district set can never be ranked as if it were complete.
    """
    collection = json.loads(Path(path).read_text(encoding="utf-8"))
    if collection.get("type") != "FeatureCollection":
        raise AreaFileError(f"{Path(path).name}: not a GeoJSON FeatureCollection")
    areas, seen = [], set()
    for index, feature in enumerate(collection.get("features") or []):
        props = feature.get("properties") or {}
        where = f"{Path(path).name}, feature {index} ({props.get('name') or props.get('id') or 'unnamed'})"
        for required in ("id", "name", "boundary_source"):
            if not props.get(required):
                raise AreaFileError(f"{where}: property '{required}' is missing")
        problem = geo.geometry_problem(feature.get("geometry") or {})
        if problem:
            raise AreaFileError(f"{where}: {problem}")
        if props["id"] in seen:
            raise AreaFileError(f"{where}: duplicate id '{props['id']}'")
        seen.add(props["id"])
        areas.append(MonitoredArea(id=str(props["id"]), name=str(props["name"]), kind=props.get("kind", "district"),
                                   geometry=feature["geometry"], boundary_source=str(props["boundary_source"]),
                                   district=props.get("district"), state=props.get("state"), note=props.get("note")))
    if not areas:
        raise AreaFileError(f"{Path(path).name}: no features")
    return areas


def demo_areas() -> list[MonitoredArea]:
    """The team's demo monitoring rectangles over Manipur valley farmland (not administrative boundaries)."""
    return load_areas(ASSETS / "demo_areas.geojson")


def _rings(geometry: dict) -> list[list[list[tuple[float, float]]]]:
    polygons = [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
    return [[[(float(p[0]), float(p[1])) for p in ring] for ring in polygon] for polygon in polygons]


def _ring_area_deg2(ring: list[tuple[float, float]]) -> float:
    return 0.5 * sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1]))


def area_km2(geometry: dict) -> float:
    """Approximate area in km2: shoelace in degrees, scaled at the polygon's mean latitude; holes subtracted."""
    total = 0.0
    for polygon in _rings(geometry):
        latitude = sum(y for _, y in polygon[0]) / len(polygon[0])
        scale = KM_PER_DEGREE_LAT * KM_PER_DEGREE_LON_EQUATOR * math.cos(math.radians(latitude))
        outer = abs(_ring_area_deg2(polygon[0]))
        holes = sum(abs(_ring_area_deg2(ring)) for ring in polygon[1:])
        total += (outer - holes) * scale
    return total


def _in_ring(lon: float, lat: float, ring: list[tuple[float, float]]) -> bool:
    inside = False
    for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1]):
        if (y0 > lat) != (y1 > lat) and lon < x0 + (lat - y0) * (x1 - x0) / (y1 - y0):
            inside = not inside
    return inside


def contains(geometry: dict, lon: float, lat: float) -> bool:
    """Is the point inside the area (inside an outer ring and outside its holes)?"""
    return any(_in_ring(lon, lat, polygon[0]) and not any(_in_ring(lon, lat, hole) for hole in polygon[1:])
               for polygon in _rings(geometry))


def representative_point(area: MonitoredArea) -> tuple[float, float]:
    """(longitude, latitude) of a point inside the area (see `satquery.geo.representative_point`)."""
    return geo.representative_point(area.geometry)


def extent_km(area: MonitoredArea) -> tuple[float, float]:
    return geo.area_extent_km(area.geometry)
