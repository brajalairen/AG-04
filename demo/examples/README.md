# Demo scenarios

Small example inputs shown as one-click scenarios in the web app (**Help** in the sidebar). The same GeoTIFFs can
also be uploaded by hand to try the upload workflow.

## Format: `examples.json`
```json
[
  {
    "label": "Cross-modal: water and built-up",
    "images": [
      {"path": "bigearthnet_coast_finland/s2_bgrn.tif", "modality": "optical"},
      {"path": "bigearthnet_coast_finland/s1_vv_vh.tif", "modality": "sar"}
    ],
    "query": "Use the optical and SAR images together to identify built-up and water-covered regions."
  }
]
```
`path` is relative to this folder. `acquired` (a `YYYY-MM-DD` date) is optional, but set it for before/after pairs.

## Shipped scenarios (order matches `examples.json` and the app)

| # | Capability | Input | Source |
|---|---|---|---|
| 1 | Single-image question answering | 1 optical | `bigearthnet_coast_finland` |
| 2 | Captioning | 1 optical | `bigearthnet_river_austria` |
| 3 | Grounding | 1 optical | `bigearthnet_coast_finland` |
| 4 | Change analysis | 2 optical, dated | `navi_mumbai_change` |
| 5 | Change question (comparative) | 2 optical, dated | `navi_mumbai_change` |
| 6 | Optical + SAR | optical + SAR, same grid | `bigearthnet_coast_finland` |
| 7 | Single SAR image | 1 SAR | `bigearthnet_coast_finland` |
| 8 | Input rejection | 2 images on different grids | mixes the two sources above |

The BigEarthNet folders pair a Sentinel-2 patch with its Sentinel-1 counterpart (the `s1_name` column of
BigEarthNet.txt). Both pairs share CRS, transform and shape. Each folder's `text.json` holds that patch's
BigEarthNet.txt question/answer rows, and `source.json` records its provenance.

## Attribution
- BigEarthNet v2.0 / BigEarthNet.txt: CDLA-Permissive-1.0; contains modified Copernicus Sentinel data.
- Copernicus Sentinel exports (Navi Mumbai pair): "Contains modified Copernicus Sentinel data [year]".
