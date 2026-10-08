/** The risk map: each monitored area filled by the level the risk engine gave it.
 *
 *  Demo rectangles are outlined dashed and official district outlines solid, so a demo area is never
 *  mistaken for an administrative boundary. Rank numbers sit on each area; hover shows its level and
 *  score, a click opens its drawer. Follows MapView's pattern: everything is re-added whenever a new
 *  style has loaded (a basemap switch drops runtime sources). */

import { useEffect, useRef, useState } from "react";
import { Marker, type ExpressionSpecification, type GeoJSONSource, type MapLayerMouseEvent } from "maplibre-gl";
import { useMap, useMapReady } from "../map/MapView";
import { DemoTag, LevelBadge } from "./badges";
import { areaFeatures, formatScore, levelColorExpression } from "./format";
import { useAgriStore } from "./useAgriStore";
import { useAppStore } from "../state/useAppStore";

const SOURCE = "agri-areas";
const FILL = "agri-fill";
const LINE_OFFICIAL = "agri-line-official";
const LINE_DEMO = "agri-line-demo";
/** Room for the floating panels when the map frames the areas: sidebar left, legend right, command bar below. */
const PADDING = { top: 80, bottom: 150, left: 400, right: 260 };

export function RiskLayer() {
  const map = useMap();
  const styleReady = useMapReady();
  const overview = useAgriStore((s) => s.overview);
  const selectedId = useAgriStore((s) => s.selectedId);
  const hoveredId = useAgriStore((s) => s.hoveredId);
  const highlightIds = useAgriStore((s) => s.highlightIds);
  const select = useAgriStore((s) => s.select);
  const hover = useAgriStore((s) => s.hover);
  const [tip, setTip] = useState<{ x: number; y: number } | null>(null);
  // Outlines must stand out from the basemap: light over dark themes and satellite imagery.
  const darkBase = useAppStore((s) => s.theme === "dark" || s.basemap !== "standard");
  const outline = darkBase ? "#f3f4f6" : "#3b3b3b";
  const framed = useRef(false);

  // --- the areas, re-added after every style load
  useEffect(() => {
    if (!map || !styleReady || !overview) return;
    const data = areaFeatures(overview.areas, { selectedId, hoveredId, highlightIds });
    const color = ["case", ["any", ["get", "selected"], ["get", "highlighted"]], "#2563eb", outline] as ExpressionSpecification;
    const source = map.getSource(SOURCE) as GeoJSONSource | undefined;
    if (source) {
      source.setData(data);
      map.setPaintProperty(LINE_OFFICIAL, "line-color", color);
      map.setPaintProperty(LINE_DEMO, "line-color", color);
      return;
    }
    map.addSource(SOURCE, { type: "geojson", data });
    map.addLayer({
      id: FILL,
      type: "fill",
      source: SOURCE,
      paint: {
        "fill-color": levelColorExpression(),
        "fill-opacity": ["case", ["any", ["get", "selected"], ["get", "hovered"]], 0.65, 0.48],
      },
    });
    const width = ["case", ["get", "selected"], 3.5, ["any", ["get", "hovered"], ["get", "highlighted"]], 2.5, 1.5];
    map.addLayer({
      id: LINE_OFFICIAL,
      type: "line",
      source: SOURCE,
      filter: ["==", ["get", "official"], true],
      paint: { "line-color": color, "line-width": width as ExpressionSpecification },
    });
    map.addLayer({
      id: LINE_DEMO,
      type: "line",
      source: SOURCE,
      filter: ["==", ["get", "official"], false],
      paint: { "line-color": color, "line-width": width as ExpressionSpecification, "line-dasharray": [3, 2] },
    });
  }, [map, styleReady, overview, selectedId, hoveredId, highlightIds, outline]);

  // --- frame Manipur's monitored areas once, when they first arrive
  useEffect(() => {
    if (!map || !overview?.view_bounds || framed.current) return;
    framed.current = true;
    const [west, south, east, north] = overview.view_bounds;
    map.fitBounds([[west, south], [east, north]], { padding: PADDING, duration: 800, maxZoom: 10 });
  }, [map, overview]);

  // --- bring the selected area into view beside the drawer
  useEffect(() => {
    if (!map || !overview || !selectedId) return;
    const area = overview.areas.find((a) => a.id === selectedId);
    if (!area) return;
    const [west, south, east, north] = area.bounds;
    map.fitBounds([[west, south], [east, north]], {
      padding: { ...PADDING, right: 480 },
      duration: 700,
      maxZoom: 11,
    });
  }, [map, overview, selectedId]);

  // --- hover and click
  useEffect(() => {
    if (!map) return;
    const move = (event: MapLayerMouseEvent) => {
      const id = event.features?.[0]?.properties?.id as string | undefined;
      map.getCanvas().style.cursor = id ? "pointer" : "";
      hover(id ?? null);
      setTip(id ? { x: event.point.x, y: event.point.y } : null);
    };
    const leave = () => {
      map.getCanvas().style.cursor = "";
      hover(null);
      setTip(null);
    };
    const click = (event: MapLayerMouseEvent) => {
      const id = event.features?.[0]?.properties?.id as string | undefined;
      if (id) select(id);
    };
    map.on("mousemove", FILL, move);
    map.on("mouseleave", FILL, leave);
    map.on("click", FILL, click);
    return () => {
      map.off("mousemove", FILL, move);
      map.off("mouseleave", FILL, leave);
      map.off("click", FILL, click);
    };
  }, [map, hover, select]);

  // --- rank numbers: DOM markers, so they survive a basemap switch and need no map fonts
  useEffect(() => {
    if (!map || !overview) return;
    const markers = overview.areas
      .filter((area) => area.rank !== null)
      .map((area) => {
        const element = document.createElement("button");
        element.type = "button";
        element.className =
          "rounded-full border border-line bg-surface px-1.5 py-px text-[11px] font-semibold text-ink shadow-[var(--shadow-sm)] tabular-nums";
        element.textContent = `#${area.rank}`;
        element.setAttribute("aria-label", `Priority ${area.rank}: ${area.name}`);
        element.addEventListener("click", (event) => {
          event.stopPropagation();
          select(area.id);
        });
        return new Marker({ element }).setLngLat(area.label_point).addTo(map);
      });
    return () => markers.forEach((marker) => marker.remove());
  }, [map, overview, select]);

  const hovered = overview?.areas.find((a) => a.id === hoveredId);
  if (!tip || !hovered) return null;
  return (
    <div
      className="pointer-events-none absolute z-20 max-w-[260px] rounded-[var(--radius-sm)] border border-line bg-surface px-3 py-2 shadow-[var(--shadow-md)]"
      style={{ left: tip.x + 14, top: tip.y + 14 }}
    >
      <p className="text-[12px] leading-snug font-medium text-ink">{hovered.name}</p>
      <p className="mt-1 flex flex-wrap items-center gap-1.5 text-[11px] text-muted">
        <LevelBadge level={hovered.level} />
        <span className="tabular-nums">{formatScore(hovered.score)}/100</span>
        {hovered.rank && <span>#{hovered.rank}</span>}
        {hovered.kind === "demo" && <DemoTag />}
      </p>
      <p className="mt-1 text-[10px] text-faint">Click for why</p>
    </div>
  );
}
