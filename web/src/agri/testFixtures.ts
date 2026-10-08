/** Test fixtures shared by the AG-04 dashboard tests (a plain module, so no test runs twice). */

import type { AreaSummary, DistrictSummary } from "../state/types";

export function summary(id: string, extra: Partial<AreaSummary> = {}): AreaSummary {
  return {
    id,
    name: `Area ${id}`,
    kind: "demo",
    official_boundary: false,
    boundary_source: "demo rectangle drawn by the team (not an administrative boundary)",
    district: "Bishnupur",
    state: "Manipur",
    geometry: { type: "Polygon", coordinates: [[[93, 24], [94, 24], [94, 25], [93, 25], [93, 24]]] },
    label_point: [93.5, 24.5],
    bounds: [93, 24, 94, 25],
    rank: 1,
    rank_of: 3,
    level: "HIGH",
    score: 66.7,
    headline: "Indicators suggest HIGH risk (67/100) for Area.",
    confidence: "low",
    data_completeness: 1,
    top_factors: ["weather_pest"],
    factor_points: { weather_pest: 50, ndvi_anomaly: 3.4, report_pressure: 13.3 },
    factor_status: { weather_pest: "ok", ndvi_anomaly: "ok", report_pressure: "ok" },
    includes_sample_data: true,
    thresholds_status: "PLACEHOLDER",
    ...extra,
  };
}

export function district(name: string, extra: Partial<DistrictSummary> = {}): DistrictSummary {
  return {
    name,
    listed: true,
    rank: 1,
    coverage: "monitored",
    zone_count: 1,
    zone_ids: [`zone-${name}`],
    level_counts: { CRITICAL: 0, HIGH: 1, MODERATE: 0, LOW: 0, INSUFFICIENT_DATA: 0 },
    top_zone_id: `zone-${name}`,
    level: "HIGH",
    score: 66.7,
    confidence: "low",
    best_zone_rank: 1,
    has_boundary: false,
    boundary_source: null,
    geometry: null,
    bounds: [93, 24, 94, 25],
    ...extra,
  };
}
