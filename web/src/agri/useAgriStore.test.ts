import { beforeEach, describe, expect, it, vi } from "vitest";
import type { AgriAreaDetail, AgriOverview, AgriQueryResult } from "../state/types";
import { ApiError } from "../state/api";
import { useAgriStore } from "./useAgriStore";
import { summary } from "./testFixtures";

const agriOverview = vi.fn();
const agriArea = vi.fn();
const agriQuery = vi.fn();
vi.mock("../state/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../state/api")>();
  return {
    ...actual,
    api: {
      ...actual.api,
      agriOverview: (...args: unknown[]) => agriOverview(...args),
      agriArea: (...args: unknown[]) => agriArea(...args),
      agriQuery: (...args: unknown[]) => agriQuery(...args),
    },
  };
});

function overview(): AgriOverview {
  return {
    computed_at: "2026-10-08T05:00:26+00:00",
    as_of: "2026-10-08T05:00:26+00:00",
    region: "Manipur",
    view_bounds: [93, 24, 94, 25],
    thresholds_status: "PLACEHOLDER",
    thresholds_note: "Thresholds are PLACEHOLDERS for development.",
    includes_sample_data: true,
    sample_label: "SAMPLE DATA — Prototype Simulation",
    disclaimer: "Decision support only.",
    area_note: "7 demo monitoring rectangle(s)",
    official_boundaries: false,
    offline: false,
    data_states: ["LIVE", "SAMPLE"],
    counts: { CRITICAL: 0, HIGH: 1, MODERATE: 1, LOW: 0, INSUFFICIENT_DATA: 0 },
    examples: [],
    areas: [summary("a"), summary("b", { rank: 2, level: "MODERATE" })],
  };
}

function answer(extra: Partial<AgriQueryResult> = {}): AgriQueryResult {
  return {
    intent: "rank",
    matched_rule: "ranking cue",
    answer: "Indicators suggest HIGH or CRITICAL risk in 1 of 2 monitored areas",
    area_ids: ["a"],
    focus_area_id: "a",
    computed_at: "2026-10-08T05:00:26+00:00",
    thresholds_status: "PLACEHOLDER",
    includes_sample_data: true,
    disclaimer: "Decision support only.",
    language: "english",
    common_intent: "AREA_RISK_QUERY",
    ...extra,
  };
}

const flush = () => new Promise((resolve) => setTimeout(resolve, 0));

beforeEach(() => {
  agriOverview.mockReset();
  agriArea.mockReset();
  agriQuery.mockReset();
  useAgriStore.setState({
    overview: null, status: "idle", error: null, filter: "all", selectedId: null, hoveredId: null,
    highlightIds: [], detail: null, detailStatus: "idle", detailError: null, answer: null,
  });
});

describe("loading the assessment", () => {
  it("holds exactly what the server returned", async () => {
    const data = overview();
    agriOverview.mockResolvedValue(data);
    await useAgriStore.getState().load();
    expect(useAgriStore.getState().status).toBe("ready");
    expect(useAgriStore.getState().overview).toBe(data);
  });

  it("keeps the server's reason when the assessment is unavailable", async () => {
    agriOverview.mockRejectedValue(new ApiError("The monitored areas could not be loaded: no features", 503));
    await useAgriStore.getState().load();
    expect(useAgriStore.getState().status).toBe("error");
    expect(useAgriStore.getState().error).toBe("The monitored areas could not be loaded: no features");
  });
});

describe("the area drawer", () => {
  it("opens on select and loads that area's assessment", async () => {
    agriArea.mockResolvedValue({ area: summary("a") } as AgriAreaDetail);
    useAgriStore.getState().select("a");
    expect(useAgriStore.getState().detailStatus).toBe("loading");
    await flush();
    expect(agriArea).toHaveBeenCalledWith("a");
    expect(useAgriStore.getState().detailStatus).toBe("ready");
  });

  it("never lets a slow earlier answer overwrite the area now selected", async () => {
    let resolveFirst!: (value: AgriAreaDetail) => void;
    agriArea.mockImplementationOnce(() => new Promise((resolve) => (resolveFirst = resolve)));
    agriArea.mockResolvedValueOnce({ area: summary("b") } as AgriAreaDetail);
    useAgriStore.getState().select("a");
    useAgriStore.getState().select("b");
    await flush();
    resolveFirst({ area: summary("a") } as AgriAreaDetail);
    await flush();
    expect(useAgriStore.getState().detail?.area.id).toBe("b");
  });

  it("closes cleanly", () => {
    useAgriStore.setState({ selectedId: "a", detailStatus: "ready" });
    useAgriStore.getState().select(null);
    expect(useAgriStore.getState()).toMatchObject({ selectedId: null, detail: null, detailStatus: "idle" });
  });

  it("shows the server's reason when the area cannot be loaded", async () => {
    agriArea.mockRejectedValue(new ApiError("No monitored area has the id 'x'.", 404));
    useAgriStore.getState().select("x");
    await flush();
    expect(useAgriStore.getState().detailError).toBe("No monitored area has the id 'x'.");
  });
});

describe("agricultural questions", () => {
  it("a ranking outlines its areas without opening a drawer", async () => {
    useAgriStore.setState({ status: "ready", overview: overview() });
    agriQuery.mockResolvedValue(answer());
    await useAgriStore.getState().ask("Which areas are high risk?");
    expect(useAgriStore.getState().highlightIds).toEqual(["a"]);
    expect(useAgriStore.getState().selectedId).toBeNull();
  });

  it("an explanation opens the drawer of the area it explains", async () => {
    useAgriStore.setState({ status: "ready", overview: overview() });
    agriQuery.mockResolvedValue(answer({ intent: "explain", focus_area_id: "b", area_ids: ["b"] }));
    agriArea.mockResolvedValue({ area: summary("b") } as AgriAreaDetail);
    await useAgriStore.getState().ask("Why is B flagged?");
    expect(useAgriStore.getState().selectedId).toBe("b");
  });

  it("sends the selected area so 'this area' can be resolved", async () => {
    useAgriStore.setState({ status: "ready", overview: overview(), selectedId: "a" });
    agriQuery.mockResolvedValue(answer());
    await useAgriStore.getState().ask("Why is this area at risk?");
    expect(agriQuery).toHaveBeenCalledWith("Why is this area at risk?", "a", undefined);
  });

  it("clears the answer and its outlines", () => {
    useAgriStore.setState({ answer: answer(), highlightIds: ["a"] });
    useAgriStore.getState().clearAnswer();
    expect(useAgriStore.getState()).toMatchObject({ answer: null, highlightIds: [] });
  });
});
