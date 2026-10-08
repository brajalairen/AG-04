/** Presentation only: colours, labels and formatting for the AG-04 dashboard.
 *
 *  Nothing here computes risk. Ranks, levels, scores, points, confidence and completeness all come
 *  from the server's risk engine; these helpers only decide how they look. */

import type { ExpressionSpecification } from "maplibre-gl";
import type { AreaSummary, DataState, DistrictSummary, FactorId, RiskLevel } from "../state/types";

/** Risk levels are states, so they use the fixed status palette (dataviz reference: good, warning,
 *  serious, critical), identical in light and dark. A level is never shown by colour alone: every
 *  place that colours one also prints its label. */
export const LEVEL_COLOR: Record<RiskLevel, string> = {
  CRITICAL: "#d03b3b",
  HIGH: "#ec835a",
  MODERATE: "#fab219",
  LOW: "#0ca30c",
  INSUFFICIENT_DATA: "#898781",
};

export const LEVEL_LABEL: Record<RiskLevel, string> = {
  CRITICAL: "Critical",
  HIGH: "High",
  MODERATE: "Moderate",
  LOW: "Low",
  INSUFFICIENT_DATA: "Not enough data",
};

/** Most urgent first, the engine's own order. */
export const LEVELS: RiskLevel[] = ["CRITICAL", "HIGH", "MODERATE", "LOW", "INSUFFICIENT_DATA"];

export const FACTOR_LABEL: Record<FactorId, string> = {
  weather_pest: "Weather",
  ndvi_anomaly: "NDVI vs baseline",
  report_pressure: "Pest reports (SAMPLE)",
};

/** Factor identity in the score breakdown: the first three categorical slots, validated all-pairs
 *  in both modes; CSS variables carry the light and dark steps (index.css). */
export const FACTOR_COLOR_VAR: Record<FactorId, string> = {
  weather_pest: "var(--factor-weather)",
  ndvi_anomaly: "var(--factor-ndvi)",
  report_pressure: "var(--factor-reports)",
};

export const FACTORS: FactorId[] = ["weather_pest", "ndvi_anomaly", "report_pressure"];

export type LevelFilter = "all" | "high" | "moderate" | "low";

export const FILTER_OPTIONS: { value: LevelFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "high", label: "High" },
  { value: "moderate", label: "Moderate" },
  { value: "low", label: "Low" },
];

/** "High" includes Critical: both call for attention first. */
const FILTER_LEVELS: Record<LevelFilter, RiskLevel[] | null> = {
  all: null,
  high: ["CRITICAL", "HIGH"],
  moderate: ["MODERATE"],
  low: ["LOW"],
};

/** The districts a filter shows, in the server's priority order (never re-sorted here). A district's
 *  level is its highest-priority zone's, as the server reports it; districts without coverage have
 *  none and appear only under "All". */
export function filterDistricts(districts: DistrictSummary[], filter: LevelFilter): DistrictSummary[] {
  const levels = FILTER_LEVELS[filter];
  return levels ? districts.filter((d) => d.level !== null && levels.includes(d.level)) : districts;
}

export function formatScore(score: number | null): string {
  return score === null ? "–" : String(Math.round(score));
}

export function formatPercent(fraction: number | null | undefined, digits = 0): string {
  return fraction === null || fraction === undefined ? "–" : `${(fraction * 100).toFixed(digits)}%`;
}

export function formatNumber(value: number | null | undefined, digits = 2): string {
  return value === null || value === undefined ? "–" : value.toFixed(digits);
}

/** Times are shown in Manipur's own time zone, labelled, whatever the viewer's clock says. */
export function formatTime(iso: string | null | undefined): string {
  if (!iso) return "–";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  const text = new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "Asia/Kolkata",
  }).format(date);
  return `${text} IST`;
}

export function pestName(id: string): string {
  return id.replace(/_/g, " ");
}

export const STATE_LABEL: Record<DataState, string> = {
  LIVE: "Live",
  CACHED: "Cached",
  SNAPSHOT: "Snapshot",
  SAMPLE: "SAMPLE",
  UNAVAILABLE: "Unavailable",
};

/** The map's features: geometry from the server plus the display state of each area. */
export function areaFeatures(
  areas: AreaSummary[],
  view: { selectedId: string | null; hoveredId: string | null; highlightIds: string[] },
): GeoJSON.FeatureCollection<GeoJSON.Geometry> {
  return {
    type: "FeatureCollection",
    features: areas.map((area) => ({
      type: "Feature",
      geometry: area.geometry,
      properties: {
        id: area.id,
        level: area.level,
        official: area.official_boundary,
        selected: area.id === view.selectedId,
        hovered: area.id === view.hoveredId,
        highlighted: view.highlightIds.includes(area.id),
      },
    })),
  };
}

/** Fill colour by level: a MapLibre `match` on the engine's level. */
export function levelColorExpression(): ExpressionSpecification {
  const pairs = LEVELS.flatMap((level) => [level, LEVEL_COLOR[level]]);
  return ["match", ["get", "level"], ...pairs, LEVEL_COLOR.INSUFFICIENT_DATA] as unknown as ExpressionSpecification;
}

/** The breakdown bar: each factor's points (from the engine) as a share of 100. */
export function scoreSegments(points: Record<FactorId, number | null>): { id: FactorId; points: number }[] {
  return FACTORS.flatMap((id) => {
    const value = points[id];
    return value !== null && value !== undefined && value > 0 ? [{ id, points: value }] : [];
  });
}

/** Verified district outlines only (context, never coloured by risk); none when not loaded. */
export function districtFeatures(districts: DistrictSummary[], focused: string | null): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: districts.flatMap((d) =>
      d.geometry ? [{ type: "Feature" as const, geometry: d.geometry, properties: { name: d.name, focused: d.name === focused } }] : [],
    ),
  };
}
