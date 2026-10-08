import { beforeEach, describe, expect, it, vi } from "vitest";
import type { AgriQueryResult, AnalyzeResult, ChatResolveResult } from "../state/types";
import { useAppStore } from "../state/useAppStore";
import { useAgriStore } from "../agri/useAgriStore";
import { EMPTY_CONTEXT, useChatStore } from "./useChatStore";

const chatResolve = vi.fn();
vi.mock("../state/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../state/api")>();
  return { ...actual, api: { ...actual.api, chatResolve: (...args: unknown[]) => chatResolve(...args) } };
});

function resolved(query: string | null, extra: Partial<ChatResolveResult> = {}): ChatResolveResult {
  return { query, rewritten: false, rule: "complete question", clarification: null, area_id: null, ...extra };
}

function agri(extra: Partial<AgriQueryResult> = {}): AgriQueryResult {
  return {
    intent: "rank",
    matched_rule: "ranking cue",
    answer: "Indicators suggest HIGH or CRITICAL risk in 1 of 7 monitored areas:\n#1 Jiribam: HIGH, 71/100 (confidence low)\nPLACEHOLDER thresholds: prototype scores.",
    area_ids: ["jiribam", "churachandpur"],
    focus_area_id: "jiribam",
    computed_at: "2026-10-09T05:00:00+00:00",
    thresholds_status: "PLACEHOLDER",
    includes_sample_data: true,
    disclaimer: "Decision support only.",
    language: "english",
    common_intent: "AREA_RISK_QUERY",
    ...extra,
  };
}

/** The existing question flow, standing in for the server: it records what was asked and leaves an answer. */
const runAnalysis = vi.fn();

beforeEach(() => {
  chatResolve.mockReset();
  runAnalysis.mockReset();
  sessionStorage.clear();
  useChatStore.setState({ messages: [], context: EMPTY_CONTEXT, pending: false, open: true, lastAgri: null });
  useAgriStore.setState({ answer: null });
  useAppStore.setState({ result: null, error: null, pending: false, runAnalysis });
});

describe("a conversation", () => {
  it("asks a question through the existing flow and shows the engine's answer unchanged", async () => {
    chatResolve.mockResolvedValue(resolved("Which areas are at high risk?"));
    const answer = agri();
    runAnalysis.mockImplementation(async () => useAgriStore.setState({ answer }));

    const reply = await useChatStore.getState().send("Which areas are at high risk?");

    expect(runAnalysis).toHaveBeenCalledWith("Which areas are at high risk?");
    expect(reply?.text).toBe(answer.answer); // figures and warnings exactly as the engine wrote them
    expect(reply).toMatchObject({ role: "assistant", kind: "answer", source: "risk engine", placeholder: true, sample: true });
    expect(useChatStore.getState().context).toEqual({
      last_query: "Which areas are at high risk?",
      last_intent: "AREA_RISK_QUERY",
      focus_area_id: "jiribam",
      area_ids: ["jiribam", "churachandpur"],
      language: "english",
    });
    expect(useChatStore.getState().lastAgri).toBe(answer);
  });

  it("sends the previous answer's context with a follow-up and asks the complete question", async () => {
    useChatStore.setState({ context: { ...EMPTY_CONTEXT, last_intent: "AREA_RISK_QUERY", focus_area_id: "jiribam", area_ids: ["jiribam"] } });
    chatResolve.mockResolvedValue(resolved("Why is Jiribam flagged?", { rewritten: true, area_id: "jiribam" }));
    runAnalysis.mockImplementation(async () =>
      useAgriStore.setState({ answer: agri({ intent: "explain", area_ids: ["jiribam"], common_intent: "AREA_SPECIFIC_RISK", answer: "Jiribam: HIGH, 71/100." }) }),
    );

    await useChatStore.getState().send("Why?");

    expect(chatResolve.mock.calls[0]?.[1]).toMatchObject({ focus_area_id: "jiribam", last_intent: "AREA_RISK_QUERY" });
    expect(runAnalysis).toHaveBeenCalledWith("Why is Jiribam flagged?");
    const [question, answer] = useChatStore.getState().messages;
    expect(question).toMatchObject({ text: "Why?", readAs: "Why is Jiribam flagged?" });
    expect(answer?.text).toBe("Jiribam: HIGH, 71/100.");
    // an explanation keeps the last list, so "the second one" still refers to it
    expect(useChatStore.getState().context.area_ids).toEqual(["jiribam"]);
  });

  it("asks back instead of guessing, and asks nothing of the engine", async () => {
    chatResolve.mockResolvedValue(resolved(null, { clarification: "Which area do you mean?" }));
    const reply = await useChatStore.getState().send("Why?");
    expect(reply).toMatchObject({ kind: "clarification", text: "Which area do you mean?" });
    expect(runAnalysis).not.toHaveBeenCalled();
  });

  it("shows a weather or satellite answer and remembers what kind of question it was", async () => {
    chatResolve.mockResolvedValue(resolved("How is the weather?"));
    const result = { response: { answer: "Light rain expected.", task: "weather_forecast" }, weather: {} } as unknown as AnalyzeResult;
    runAnalysis.mockImplementation(async () => useAppStore.setState({ result }));
    const reply = await useChatStore.getState().send("How is the weather?");
    expect(reply).toMatchObject({ text: "Light rain expected.", source: "weather" });
    expect(useChatStore.getState().context.last_intent).toBe("WEATHER_RISK");
  });

  it("reports the existing flow's error message", async () => {
    chatResolve.mockResolvedValue(resolved("Show water bodies"));
    runAnalysis.mockImplementation(async () => useAppStore.setState({ error: "Add an image first." }));
    expect(await useChatStore.getState().send("Show water bodies")).toMatchObject({ kind: "error", text: "Add an image first." });
  });

  it("does not start a question while another is being answered", async () => {
    useAppStore.setState({ pending: true });
    const reply = await useChatStore.getState().send("Which areas are at high risk?");
    expect(reply?.kind).toBe("error");
    expect(chatResolve).not.toHaveBeenCalled();
  });

  it("keeps the conversation for the browser tab", async () => {
    chatResolve.mockResolvedValue(resolved("Which areas are at high risk?"));
    runAnalysis.mockImplementation(async () => useAgriStore.setState({ answer: agri() }));
    await useChatStore.getState().send("Which areas are at high risk?");
    const saved = JSON.parse(sessionStorage.getItem("ag04.conversation.v1") ?? "{}");
    expect(saved.messages).toHaveLength(2);
    expect(saved.context.focus_area_id).toBe("jiribam");
    useChatStore.getState().clear();
    expect(JSON.parse(sessionStorage.getItem("ag04.conversation.v1") ?? "{}").messages).toEqual([]);
  });
});
