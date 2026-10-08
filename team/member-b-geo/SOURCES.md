# Member B: sources for the Manipur district boundaries

## Status: local only, not in this repository

The district file `data/geo/manipur_districts.geojson` is derived from Survey of India data. Survey of India requires written permission to reproduce its material (see [Terms](#terms-and-attribution)), and that permission has not been received. The file therefore lives only under `data/`, which `.gitignore` excludes. It must not be committed, pushed, attached or shared until permission is granted.

To show the outlines on a machine that has the file, set `SATQUERY_AGRI_DISTRICTS` to its full path before starting the server. Without it, the dashboard shows no outlines and says so.

The outlines are map context only. AG-04 scores monitoring zones, never districts.

## Dataset

| | |
|---|---|
| Publisher and owner | Survey of India, Government of India (Director, NGDR & UGID; ngdc.soi@gov.in) |
| Title | District boundaries of India |
| Series | Administrative Boundary Data Base (ABDB) |
| Identifier | `SOI/ABDB/VECTOR/50000/2025/DISTRICT/INDIA` |
| Edition date | 2025 |
| Metadata date | 2026-05-06 (date type "publication"), from SoI's ISO 19115-1 metadata sheet `DISTRICT BOUNDARY.xlsx` |
| Administrative level | District |

As stated in the SoI metadata:
- Coverage: "Entire India".
- Equivalent scale 1:50,000; "Horizontal RMSE ±12.5 m".
- Temporal extent: 2022–2025.
- Lineage: "primarily derived from Survey of India 1:50,000 scale Digital Topographical Data (DTDB)".
- Source coordinate reference system: "LCC- WGS84; EPSG7755" (WGS 84 / India NSF LCC).

## Where it was downloaded

Downloaded by Member B on 2026-10-08 from the main Survey of India website, not from the Online Maps Portal. There is therefore no portal product code.

| | Data | Metadata |
|---|---|---|
| Page | [Administrative Boundary Data Base (ABDB)](https://surveyofindia.gov.in/pages/administrative-boundary-data-base-abdb-), link "State/District/Sub District Boundary Data-Base of India" | same page, link "Meta Data" |
| File URL | https://surveyofindia.gov.in/documents/State_District_Subdistrict_PAN%20INDIA.rar | https://surveyofindia.gov.in/documents/Metadata_ABDB.zip |
| Downloaded | 2026-10-08, 16:05–16:09 IST | 2026-10-08, 21:37 IST |
| Size | 202,524,438 bytes (same as the server copy) | 38,879 bytes |
| Server Last-Modified | 2026-05-12 08:51 GMT | 2026-05-29 04:41 GMT |
| SHA-256 | `b8325e5d9dd0f04a6663d775363fe38cd2f23bd9dbae3fb7118b4e6e0ce0bcb7` | `1a14716b73f00fc8391f2708a7975c2f2c1ad4a4e91aafb6dce6546a039e9514` (identical to the server copy on 2026-10-08) |

The origin is recorded by Windows on the downloaded archives (`Zone.Identifier`: `HostUrl` as above), and every extracted file points back to its archive.

Files used from the archive (folder `District_Subdistrict_PAN INDIA`):

| File | SHA-256 |
|---|---|
| `District Boundary.shp` | `05efac0a02c113f25cd55df3f01a4aee7201bfc9b299f73bb3e273b9aa7e3740` |
| `District Boundary.shx` | `691482470b29fe9d5c6d5a7753e90823a1fbe162c603c6260fbd28b5e0a23aea` |
| `District Boundary.dbf` | `0bcc1d46dcbc403f29c47c8c47db2fe4b71e802cd3c8038fc4663765fc2c4236` |
| `District Boundary.prj` | `4e0115a1711327038fc52f74a11a80ee1c399c8d84e8f0e5f54bf00b9fd20f16` |
| `District Boundary.cpg` | `3ad3031f5503a4404af825262ee8232cc04d4ea6683d42c5dd0a2f2a27ac9824` |
| `DISTRICT BOUNDARY.xlsx` (metadata) | `6b05a2497fa8e6dd196c8534f75f8d8dcd76307b0132807e939adb886b72b21d` |

The SoI `State Boundary` layer from the same archive was used only to check for gaps (see `geo_validation.md`).

## Processing

Run on 2026-10-08 with [mapshaper](https://github.com/mbloch/mapshaper) 0.7.80 and Python. The raw data and all intermediate files stay outside the repository.

1. **Manipur only.** Kept the 16 features with `STATE_UT == 'MANIPUR'` (of 808), still in EPSG:7755.
   `mapshaper -i "District Boundary.shp" encoding=utf8 -filter "STATE_UT == 'MANIPUR'" -o manipur_lcc.shp`
2. **Simplify, then reproject.** Applied Ramer–Douglas–Peucker simplification with a 10 m threshold in EPSG:7755 metres. The borders are shared, so neighbouring districts stay gap-free. Then reprojected to WGS84 longitude/latitude (EPSG:4326, RFC 7946 GeoJSON) with 6 decimal places.
   `mapshaper -i manipur_lcc.shp encoding=utf8 -simplify dp interval=10m keep-shapes stats -proj wgs84 -o manipur_wgs84_10m.geojson precision=0.000001`
   Result: 36,750 of 54,876 vertices removed (67%), maximum displacement 9.999 m, no collapsed rings, no intersections. The threshold is below the stated ±12.5 m accuracy.
3. **AG-04 schema.** Renamed the districts to their LGD names, added the LGD codes, and kept SoI's own name and code as raw traceability fields (`soi_district_name`, `soi_dist_lgd`). Each feature has `id` (`mn-<name>`), `name`, `district`, `kind: "district"`, `state: "Manipur"`, `boundary_source`, `lgd_district_code`, `lgd_state_code: "14"`, `soi_district_name`, `soi_dist_lgd`, and `note` where a name differs.
4. **Validation.** Recorded in `geo_validation.md`.

Output: 16 features, 30,781 vertices, 677 KB, SHA-256 `9424a9ec8015e074d3786c19b1ce0063d1714dbae268f1ff31475401c6ea13fd`.

## Names and codes

Names and codes follow the Local Government Directory (LGD), using its `districtList` web service for state code 14, queried on 2026-10-08. They are identical to the 16 names in `satquery/agri/assets/manipur_district_names.json`.

| LGD name | LGD code | SoI `DISTRICT` | SoI `DIST_LGD` |
|---|---|---|---|
| Bishnupur | 252 | BISHNUPUR | 275 |
| Chandel | 253 | CHANDEL | 280 |
| Churachandpur | 254 | CHURACHANDPUR | 274 |
| Imphal East | 255 | IMPHAL EAST | 278 |
| Imphal West | 256 | IMPHAL WEST | 277 |
| Jiribam | 713 | JIRIBAM | 658 |
| Kakching | 711 | KAKCHING | 651 |
| **Kamjong** | **717** | **KAMJANG** | **670** |
| Kangpokpi | 712 | KANGPOKPI | 679 |
| Noney | 714 | NONEY | 659 |
| Pherzawl | 715 | PHERZAWL | 718 |
| Senapati | 257 | SENAPATI | 272 |
| Tamenglong | 258 | TAMENGLONG | 273 |
| Tengnoupal | 716 | TENGNOUPAL | 667 |
| Thoubal | 259 | THOUBAL | 276 |
| Ukhrul | 260 | UKHRUL | 279 |

**Kamjong.** Survey of India writes this district as `KAMJANG` with `DIST_LGD` 670. The district's official name is Kamjong:
- LGD lists district code **717** as "Kamjong".
- The district administration's website ([kamjong.nic.in](https://kamjong.nic.in/about-district/)) calls it "KAMJONG DISTRICT", created by Government of Manipur notification No.16/20/2016-R dated 06-12-2016.

The SoI polygon is the only one in that location, east of Ukhrul, its parent district. AG-04 shows **Kamjong** in `id`, `name` and `district`. `KAMJANG` and `670` appear only in the raw traceability fields and the feature's `note`.

**SoI's `DIST_LGD` is not the LGD code.** For the nine districts that existed in 2011 it equals the Census 2011 district code, which LGD records separately as `census2011Code`. For the seven districts created in 2016 it matches neither code. AG-04 never uses it as an LGD code.

## Terms and attribution

- **No open licence** applies to this dataset.
- **SoI website Copyright Policy** ([surveyofindia.gov.in/pages/copyright-policy](https://surveyofindia.gov.in/pages/copyright-policy), read 2026-10-08): "Material featured on the Survey of India website is prohibited for reproduction in whole or part without written permission of Survey of India in any format or media. … Wherever the material is published or shared, the source must be clearly and prominently acknowledged as: 'Source: Survey of India, Government of India.'"
- **SoI metadata:** access and use constraints "copyright"; "Geospatial Guidelines 2021 to be followed. Any violation of the Guidelines will be dealt under the applicable laws."
- **Geospatial Data Guidelines** (15 Feb 2021), para xiii, [as published by SoI](https://onlinemaps.surveyofindia.gov.in/GeospatialGuidelines.aspx): SoI digital boundary data "shall be made easily downloadable for free and their digital display and printing shall be permissible."
- **Written permission from SoI for reproduction or redistribution: not received.** Until it is, the derived file stays local (see Status).

Attribution, wherever the outlines are shown: **Source: Survey of India, Government of India.**

## Limitations

- SoI states no "as of" date for these boundaries and does not state that they are current.
- SoI's metadata lists the states and union territories whose boundaries were harmonised with ORGI in 2024 and 2025. Manipur is not among them.
- The outlines are simplified (10 m) and are not an authoritative legal boundary.
- They are used only as map context.
