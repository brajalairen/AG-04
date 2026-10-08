"""Monitored areas: any polygon, an outline source always named, geometry helpers without shapely."""

import json

import pytest

from agri_helpers import rect
from satquery.agri.areas import AreaFileError, area_km2, contains, demo_areas, load_areas


def write(tmp_path, features):
    path = tmp_path / "areas.geojson"
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}), encoding="utf-8")
    return path


def feature(**props):
    return {"type": "Feature", "geometry": props.pop("geometry", rect(93.9, 24.5, 94.0, 24.6)),
            "properties": {"id": "d1", "name": "District 1", "boundary_source": "Test dataset v1"} | props}


def test_demo_areas_are_labelled_as_rectangles_not_administrative_boundaries():
    areas = demo_areas()
    assert len(areas) == 7 and len({a.id for a in areas}) == 7
    for found in areas:
        assert found.kind == "demo" and found.state == "Manipur" and found.district
        assert "not an administrative boundary" in found.boundary_source
        assert "OpenStreetMap" in found.note


def test_an_area_file_loads_any_polygon_as_a_district_by_default(tmp_path):
    loaded = load_areas(write(tmp_path, [feature(district="Bishnupur")]))
    assert loaded[0].kind == "district" and loaded[0].district == "Bishnupur"
    assert loaded[0].boundary_source == "Test dataset v1"


@pytest.mark.parametrize("bad, message", [
    ({"boundary_source": ""}, "'boundary_source' is missing"),
    ({"id": None}, "'id' is missing"),
    ({"geometry": {"type": "Point", "coordinates": [93.9, 24.5]}}, "Polygon or MultiPolygon"),
])
def test_an_area_without_a_named_outline_source_or_valid_shape_is_refused(tmp_path, bad, message):
    with pytest.raises(AreaFileError, match=message):
        load_areas(write(tmp_path, [feature(**bad)]))


def test_a_half_valid_file_is_refused_as_a_whole(tmp_path):
    with pytest.raises(AreaFileError, match="duplicate id"):
        load_areas(write(tmp_path, [feature(), feature()]))


def test_area_and_containment_respect_holes_and_multipolygons():
    square = rect(93.0, 24.0, 93.1, 24.1)  # about 10.2 x 11.1 km
    assert area_km2(square) == pytest.approx(112.4, rel=0.01)
    holed = {"type": "Polygon", "coordinates": square["coordinates"] + rect(93.04, 24.04, 93.06, 24.06)["coordinates"]}
    assert area_km2(holed) == pytest.approx(area_km2(square) * (1 - 0.04), rel=0.001)
    assert contains(holed, 93.01, 24.01) and not contains(holed, 93.05, 24.05)
    multi = {"type": "MultiPolygon", "coordinates": [square["coordinates"], rect(94, 25, 94.1, 25.1)["coordinates"]]}
    assert contains(multi, 94.05, 25.05) and not contains(multi, 93.5, 24.5)
