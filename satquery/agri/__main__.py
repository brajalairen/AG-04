"""Command line for the AG-04 risk engine (verification and inspection; the dashboard comes later).

  python -m satquery.agri assess                 rank the demo areas with live data (cached under runs/)
  python -m satquery.agri assess --offline       cached data only, no network
  python -m satquery.agri assess --areas X.geojson --json out.json
  python -m satquery.agri thresholds             show whether thresholds are PLACEHOLDER or VERIFIED
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
    args = parser.parse_args(argv)

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


if __name__ == "__main__":
    sys.exit(main())
