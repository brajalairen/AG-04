"""Command line for the AG-04 risk engine (verification and inspection; the dashboard comes later).

  python -m satquery.agri assess                 rank the demo areas with live data (cached under runs/)
  python -m satquery.agri assess --offline       cached data only, no network
  python -m satquery.agri assess --areas X.geojson --json out.json
  python -m satquery.agri thresholds             show whether thresholds are PLACEHOLDER or VERIFIED
  python -m satquery.agri warm --save-snapshot --crop-health
                                                 before a demo: fetch today's data live, freeze it as the
                                                 fallback snapshot, and warm the crop-health imagery cache
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from satquery.agri.areas import demo_areas, load_areas
from satquery.agri.config import load_pest_rules, load_risk_model, thresholds_status
from satquery.agri.pipeline import assess_areas, default_sources
from satquery.settings import load_settings


def _table(assessments) -> str:
    rows = [f"{'#':>3}  {'Area':48} {'Level':17} {'Score':>5}  {'Conf':6} {'Data':>4}  Factors (points)"]
    for a in assessments:
        factors = ", ".join(f"{f.id.split('_')[0]} {f.points:g}" if f.points is not None else f"{f.id.split('_')[0]} n/a"
                            for f in a.factors)
        rows.append(f"{a.rank or '-':>3}  {a.area_name[:48]:48} {a.level:17} "
                    f"{(f'{a.score:.0f}' if a.score is not None else '-'):>5}  {a.confidence.level:6} "
                    f"{a.confidence.data_completeness:>4.0%}  {factors}")
    return "\n".join(rows)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m satquery.agri", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("assess", help="assess and rank monitored areas")
    run.add_argument("--areas", default="demo", help="'demo' or a GeoJSON FeatureCollection of monitored areas")
    run.add_argument("--offline", action="store_true", help="use cached data only (no network)")
    run.add_argument("--no-ndvi", action="store_true", help="skip NDVI (no Copernicus requests)")
    run.add_argument("--geocode", action="store_true", help="look up district context with OpenStreetMap")
    run.add_argument("--json", type=Path, help="write the full assessments here (default: runs/agri/...)")
    sub.add_parser("thresholds", help="show threshold status and sources")
    warm = sub.add_parser("warm", help="fetch today's data live for the dashboard (run before a demo)")
    warm.add_argument("--save-snapshot", action="store_true",
                      help="freeze the live assessment as the fallback snapshot (runs/agri/snapshot.json)")
    warm.add_argument("--crop-health", action="store_true",
                      help="also fetch today's Sentinel-2 scene for each rectangular zone (crop-health demo)")
    args = parser.parse_args(argv)
    if args.command == "warm":
        return _warm(args)

    rules, model = load_pest_rules(), load_risk_model()
    if args.command == "thresholds":
        print(f"Overall: {thresholds_status(rules, model)}")
        print(f"risk_model.json v{model.version}: {model.status}")
        for pest in rules.pests:
            print(f"  {pest.id}: {pest.status}; sources: {len(pest.sources)}; conditions: "
                  + "; ".join(c.label for c in pest.conditions))
        return 0

    settings = load_settings()
    areas = demo_areas() if args.areas == "demo" else load_areas(args.areas)
    sources = default_sources(settings, offline=args.offline, ndvi=not args.no_ndvi, geocode=args.geocode)
    assessments = assess_areas(areas, sources, rules=rules, model=model)
    print(_table(assessments))
    print(f"\nThresholds: {assessments[0].thresholds_status}. "
          + ("Includes SAMPLE DATA (synthetic pest reports). " if any(a.includes_sample_data for a in assessments) else "")
          + assessments[0].disclaimer)
    out = args.json or settings.runs_dir / "agri" / f"assessment-{datetime.now():%Y%m%d-%H%M%S}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps([a.model_dump() for a in assessments], indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"Full assessments: {out}")
    return 0


def _warm(args) -> int:
    """Live assessment through the dashboard's own service (so its caches are the ones served)."""
    from dataclasses import replace

    from satquery.agri.service import AgriUnavailable, AssessmentService

    settings = replace(load_settings(), agri_mode="live", agri_refresh_s=0.0, agri_offline=False)
    service = AssessmentService(settings)
    snapshot = service.snapshot()
    print(_table(snapshot.assessments))
    print(f"\nComputed {snapshot.computed_at} ({snapshot.mode}).")
    status = 0
    if snapshot.mode == "snapshot":
        print(f"WARNING: live data was incomplete, so the existing snapshot was kept: {snapshot.fallback_reason}")
        status = 1
    elif args.save_snapshot:
        try:
            print(f"Snapshot frozen: {service.save_snapshot()}")
        except AgriUnavailable as error:
            print(f"Snapshot NOT saved: {error}")
            status = 1
    if args.crop_health:
        from fastapi.testclient import TestClient

        from satquery import geo
        from satquery.server import create_app

        client = TestClient(create_app(agri_service=service))  # in-process; no server needed
        for area in snapshot.areas.values():
            if not geo.is_bounding_box(area.geometry):
                print(f"  crop health {area.name}: skipped (not a rectangle)")
                continue
            response = client.post("/api/fetch-imagery", json={"query": "How healthy is the crop here?",
                                                                 "aoi_bbox": list(geo.geometry_bounds(area.geometry))})
            body = response.json()
            outcome = (f"scene {body['metadata']['acquired']}" if response.status_code == 200
                       else f"{body.get('code')}: {str(body.get('message'))[:90]}")
            print(f"  crop health {area.name}: HTTP {response.status_code}, {outcome}")
    return status


if __name__ == "__main__":
    sys.exit(main())
