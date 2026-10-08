/** AG-04 dashboard state: what the risk engine said (fetched from /api/agri/*) and what the user is
 *  looking at. It holds server results only; it never computes a risk figure itself. */

import { create } from "zustand";
import { api, ApiError } from "../state/api";
import type { AgriAreaDetail, AgriOverview, AgriQueryResult } from "../state/types";
import type { LevelFilter } from "./format";

type Status = "idle" | "loading" | "ready" | "error";

/** What the map draws. Presentation only: hiding a layer never changes any figure. */
export interface MapLayers {
  zones: boolean;      // monitored agricultural zones, filled by their engine level
  ranks: boolean;      // priority rank markers
  districts: boolean;  // verified district outlines (context), when loaded
}

interface AgriState {
  overview: AgriOverview | null;
  status: Status;
  error: string | null;

  filter: LevelFilter;
  /** The district open in the priority panel's drill-down (null: the district list). */
  districtName: string | null;
  layers: MapLayers;
  /** The area whose "Why is this area at risk?" drawer is open. */
  selectedId: string | null;
  hoveredId: string | null;
  /** Areas an agricultural answer referred to, outlined on the map. */
  highlightIds: string[];

  detail: AgriAreaDetail | null;
  detailStatus: Status;
  detailError: string | null;

  answer: AgriQueryResult | null;

  load: () => Promise<void>;
  setFilter: (filter: LevelFilter) => void;
  setDistrict: (name: string | null) => void;
  toggleLayer: (layer: keyof MapLayers) => void;
  select: (id: string | null) => void;
  hover: (id: string | null) => void;
  ask: (query: string, signal?: AbortSignal) => Promise<AgriQueryResult>;
  clearAnswer: () => void;
}

function message(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback;
}

let detailRequest = 0;

export const useAgriStore = create<AgriState>((set, get) => ({
  overview: null,
  status: "idle",
  error: null,
  filter: "all",
  districtName: null,
  layers: { zones: true, ranks: true, districts: true },
  selectedId: null,
  hoveredId: null,
  highlightIds: [],
  detail: null,
  detailStatus: "idle",
  detailError: null,
  answer: null,

  load: async () => {
    if (get().status === "loading") return;
    set({ status: "loading", error: null });
    try {
      const overview = await api.agriOverview();
      set({ overview, status: "ready" });
    } catch (error) {
      set({ status: "error", error: message(error, "The risk assessment could not be loaded.") });
    }
  },

  setFilter: (filter) => set({ filter }),

  setDistrict: (districtName) => set({ districtName }),

  toggleLayer: (layer) => set((state) => ({ layers: { ...state.layers, [layer]: !state.layers[layer] } })),

  select: (id) => {
    if (id === null) {
      set({ selectedId: null, detail: null, detailStatus: "idle", detailError: null });
      return;
    }
    // Only the latest request may fill the drawer: a slow earlier answer never overwrites it.
    const ticket = ++detailRequest;
    set({ selectedId: id, detail: null, detailStatus: "loading", detailError: null });
    api
      .agriArea(id)
      .then((detail) => {
        if (ticket === detailRequest) set({ detail, detailStatus: "ready" });
      })
      .catch((error) => {
        if (ticket === detailRequest) {
          set({ detailStatus: "error", detailError: message(error, "This area's assessment could not be loaded.") });
        }
      });
  },

  hover: (id) => {
    if (get().hoveredId !== id) set({ hoveredId: id });
  },

  ask: async (query, signal) => {
    const answer = await api.agriQuery(query, get().selectedId, signal);
    set({ answer, highlightIds: answer.area_ids });
    // An explanation opens that area's drawer; a ranking or inspection list only outlines its areas.
    if (answer.intent === "explain" && answer.focus_area_id) get().select(answer.focus_area_id);
    if (get().status !== "ready") void get().load();
    return answer;
  },

  clearAnswer: () => set({ answer: null, highlightIds: [] }),
}));
