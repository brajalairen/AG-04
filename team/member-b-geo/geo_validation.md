# Member B: validation of the Manipur district boundaries

Checked on 2026-10-08. The file checked is `data/geo/manipur_districts.geojson`, SHA-256 `9424a9ec8015e074d3786c19b1ce0063d1714dbae268f1ff31475401c6ea13fd`. It is local only, outside Git; see `SOURCES.md` for why.

**Result: every check passed.**

## Conversion

| Step | Result |
|---|---|
| Filter `STATE_UT == 'MANIPUR'` | 16 of 808 features |
| Source CRS | EPSG:7755, read from the `.prj` (`+proj=lcc +lat_0=24 +lon_0=80 +lat_1=12.472944 +lat_2=35.172806 +x_0=4000000 +y_0=4000000 +datum=WGS84`) |
| Simplification | Ramer–Douglas–Peucker, 10 m in EPSG:7755, on the shared borders. 36,750 of 54,876 vertices removed (67%); mean displacement 4.7 m, maximum 9.999 m; 0 collapsed rings; no intersections |
| Output | WGS84 longitude/latitude (EPSG:4326, RFC 7946), 6 decimal places, 16 features, 30,781 vertices, 677 KB |
| Bounds | 92.97049, 23.83285 to 94.74489, 25.69195 (the same before and after simplification) |

## Geometry, names and codes

These checks used shapely 2 in a throwaway environment, not a repository dependency.

| Check | Result |
|---|---|
| GeoJSON `FeatureCollection` without a `crs` member (RFC 7946, so WGS84) | pass |
| District count | 16 |
| `id`, `name`, `lgd_district_code` present and unique | pass |
| `kind: "district"`, `state: "Manipur"`, `lgd_state_code: "14"`, `district` equal to `name`, `boundary_source` set | pass |
| Each geometry valid, not empty, area above zero, outer rings counter-clockwise, inside the Manipur sanity box | 16 of 16 pass |
| Total overlap between districts | 0.0000 km² |
| Gaps inside the union of districts | none (0 interior rings) |
| Union compared with SoI's own Manipur state outline | 0.0087% difference |
| Area change from simplification | worst 0.0024% (Imphal East) |
| Total area | about 22,288 km² |
| Names and codes compared with LGD (`districtList`, state 14, queried 2026-10-08) | identical, 16 of 16 |
| Kamjong | `name`/`district` "Kamjong", LGD 717; SoI `KAMJANG` and `670` only in `soi_district_name`/`soi_dist_lgd` (and the feature's `note`) |
| LGD itself lists Kamjong as 717 | pass |
| "Kamjang" in any `id`, `name` or `district` | none |

## Compatibility with AG-04

These checks used the application's own code, with the frozen snapshot of 2026-10-08 17:17 UTC.

| Check | Result |
|---|---|
| `satquery.agri.areas.load_areas` accepts the file | 16 features, all `kind: "district"` |
| `districts.load_boundaries` keys equal `manipur_district_names.json` | 16 of 16 |
| `team/check_deliverables.py` (Member B check, run on `data/geo/`) | OK: 16 districts, about 22,288 km² |
| `/api/agri/overview` with the outlines loaded | 16 districts, all with an outline and a `boundary_source`; `official_boundaries: true` |
| The SoI spelling in what the dashboard receives | `KAMJANG` and `soi_dist_lgd` never appear in `/api/agri/overview` |
| Payload of `/api/agri/overview` | 16 KB without outlines, 750 KB with |

## Districts are never scored

- The scored areas come from `SATQUERY_AGRI_AREAS`, which is `demo`: 7 zones, none of `kind: "district"`. The outlines come only from `SATQUERY_AGRI_DISTRICTS`.
- With and without the outlines, the zone ids, ranks, levels and scores are identical. Only the 7 demo zones are scored.

## Demo zones compared with the district each one names

Sampled on a 40 × 40 grid in each zone.

| Zone | Inside its district |
|---|---|
| `demo-jiribam-sonapur` | 100% Jiribam |
| `demo-imphal-east-sawombung` | 100% Imphal East |
| `demo-churachandpur-bungmual` | 100% Churachandpur |
| `demo-imphal-west-lamsang` | 87% Imphal West |
| `demo-bishnupur-nambol` | 68% Bishnupur |
| `demo-kakching-khangshim` | 66% Kakching |
| `demo-thoubal-chaobok` | 66% Thoubal |

Every zone lies wholly inside Manipur. The earlier `demo-jiribam-kamaranga` zone was only 33% inside Jiribam; 67% of it lay in Cachar, Assam. It was replaced on 2026-10-08. Three zones still straddle district lines, which the map shows once the outlines are loaded.

## Dashboard

Checked in headless Chrome against a local server with the outlines loaded:
- The Jiribam drill-down shows "Jiribam farmland near Sonapur", inside the Jiribam outline and east of its western (Jiri river, Assam) border.
- The page cites the SoI outline.
- Crop health returned a Sentinel-2 result: NDVI 0.76, 0% cloud.
- There were no page errors and no failed requests.

## How to re-run

The scripts are kept outside the repository with the raw data, in `Seva/work`. The commands are in `SOURCES.md` (Processing). Validation:

```bash
uv run --no-project --with "shapely>=2.0" python validate_geometry.py data/geo/manipur_districts.geojson \
    manipur_wgs84_full.geojson manipur_state_wgs84.geojson lgd_manipur_2026-10-08.json
.venv/Scripts/python.exe validate_app.py data/geo/manipur_districts.geojson
```
