# Member B: Geography

**Primary deliverable:** `manipur_districts.geojson`, the current Manipur district boundaries from a named, citable dataset. No API is needed: the AG-04 engine already scores any polygon, and the dashboard draws official districts with solid outlines (demo rectangles stay dashed).

**Never draw, trace or "fix" boundaries by hand.** If no trustworthy current dataset exists, say so in `SOURCES.md` and we keep the demo rectangles. If only an older structure is available (for example the 9 pre-2016 districts), deliver it clearly labelled. The dashboard will disclose it.

## `manipur_districts.geojson`

- GeoJSON `FeatureCollection` in **WGS84 longitude/latitude** (CRS84/EPSG:4326). Each feature is a `Polygon` or `MultiPolygon`.
- Each feature's `properties`:

| Property | Required | Example | Meaning |
|---|---|---|---|
| `id` | yes | `mn-bishnupur` | unique, lowercase, stable |
| `name` | yes | `Bishnupur` | the district name as used officially |
| `kind` | yes | `district` | marks an official boundary (solid outline) |
| `boundary_source` | yes | `<dataset name, version/date>` | where the outline comes from (shown in the app) |
| `district` | yes | `Bishnupur` | the same as `name` |
| `state` | yes | `Manipur` | |
| `note` | no | `Simplified to 50 m` | processing or limitations |

- Keep the file small enough to serve to a browser: simplify only with a documented tolerance, and say so in `geo_validation.md`.

**Reference list, for cross-checking only.** These are the 16 districts as the integration lead understands them. Confirm against an official source (for example the Government of Manipur or the Local Government Directory). Do not treat this list as authoritative:

Bishnupur, Chandel, Churachandpur, Imphal East, Imphal West, Jiribam, Kakching, Kamjong, Kangpokpi, Noney, Pherzawl, Senapati, Tamenglong, Tengnoupal, Thoubal, Ukhrul.

## `SOURCES.md`

Source and publisher, URL, dataset name and version, access date, licence and attribution text, administrative level, every processing step, and known limitations.

## `geo_validation.md`

Record what you checked and the results:
- the district count and names (against the official list)
- no duplicate names or ids
- valid geometry (closed rings, no self-intersections)
- CRS
- the bounding box inside Manipur
- for simplified data, how much area changed

Run `python team/check_deliverables.py`. It loads your file with the application's own area loader and checks ids, names, kind, CRS bounds and count.

To preview it in the engine (read-only; nothing is changed):

```bash
python -m satquery.agri assess --areas team/member-b-geo/manipur_districts.geojson --no-ndvi
```

**Do not modify** `satquery/`, `web/` or any other member's folder.
