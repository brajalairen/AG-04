import { describe, expect, it } from "vitest";
import {
  areaFeatures,
  filterAreas,
  formatScore,
  formatTime,
  LEVEL_COLOR,
  LEVEL_LABEL,
  LEVELS,
  levelColorExpression,
  scoreSegments,
} from "./format";
import { summary } from "./testFixtures";


describe("risk levels", () => {
  it("every level has a colour and a printed label, in the engine's urgency order", () => {
    expect(LEVELS).toEqual(["CRITICAL", "HIGH", "MODERATE", "LOW", "INSUFFICIENT_DATA"]);
    for (const level of LEVELS) {
      expect(LEVEL_COLOR[level]).toMatch(/^#[0-9a-f]{6}$/);
      expect(LEVEL_LABEL[level].length).toBeGreaterThan(0);
    }
  });

  it("colours the map by the level the engine gave, with a fallback for anything else", () => {
    const expression = levelColorExpression() as unknown[];
    expect(expression.slice(0, 2)).toEqual(["match", ["get", "level"]]);
    expect(expression).toContain("HIGH");
    expect(expression.at(-1)).toBe(LEVEL_COLOR.INSUFFICIENT_DATA);
  });
});

describe("the priority list filter", () => {
  const areas = [
    summary("a", { level: "CRITICAL" }),
    summary("b", { level: "HIGH" }),
    summary("c", { level: "MODERATE" }),
    summary("d", { level: "INSUFFICIENT_DATA", rank: null, score: null }),
  ];

  it("keeps the server's rank order and never re-sorts", () => {
    expect(filterAreas(areas, "all").map((a) => a.id)).toEqual(["a", "b", "c", "d"]);
    expect(filterAreas([...areas].reverse(), "all").map((a) => a.id)).toEqual(["d", "c", "b", "a"]);
  });

  it("groups High and Critical, and keeps areas without an estimate findable", () => {
    expect(filterAreas(areas, "severe").map((a) => a.id)).toEqual(["a", "b"]);
    expect(filterAreas(areas, "nodata").map((a) => a.id)).toEqual(["d"]);
    expect(filterAreas(areas, "low")).toEqual([]);
  });
});

describe("presentation of the engine's numbers", () => {
  it("shows a missing score as a dash, never as zero", () => {
    expect(formatScore(null)).toBe("–");
    expect(formatScore(66.7)).toBe("67");
  });

  it("draws the breakdown from the engine's own points, skipping unavailable factors", () => {
    expect(scoreSegments({ weather_pest: 50, ndvi_anomaly: null, report_pressure: 13.3 })).toEqual([
      { id: "weather_pest", points: 50 },
      { id: "report_pressure", points: 13.3 },
    ]);
    expect(scoreSegments({ weather_pest: 0, ndvi_anomaly: 0, report_pressure: 0 })).toEqual([]);
  });

  it("states times in Manipur's time zone", () => {
    expect(formatTime("2026-10-08T05:00:26+00:00")).toBe("08 Oct, 10:30 IST");
    expect(formatTime(null)).toBe("–");
  });

  it("marks demo areas and the selected, hovered and highlighted ones for the map", () => {
    const features = areaFeatures([summary("a"), summary("b", { official_boundary: true, kind: "district" })], {
      selectedId: "a",
      hoveredId: "b",
      highlightIds: ["b"],
    }).features;
    expect(features.map((f) => f.properties)).toEqual([
      { id: "a", level: "HIGH", official: false, selected: true, hovered: false, highlighted: false },
      { id: "b", level: "HIGH", official: true, selected: false, hovered: true, highlighted: true },
    ]);
  });
});
