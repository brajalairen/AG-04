/** Conversation mode: a running list of questions and answers on top of the existing question flow.
 *
 *  Each message is first read in its conversation by the server (/api/chat/resolve), so a follow-up such as "Why?"
 *  or "What about Thoubal?" becomes the complete question the router already answers. That question is then asked
 *  through the command bar's own `runAnalysis`, exactly as if it had been typed: the routing, the risk engine, the map
 *  highlights and the answer text, with all its figures and warnings, are the existing system's. This store only
 *  keeps the transcript and what the last answer was about. Kept for the browser tab (sessionStorage). */

import { create } from "zustand";
import { api } from "../state/api";
import type { AgriQueryResult, AnalyzeResult, ChatContext } from "../state/types";
import { useAppStore } from "../state/useAppStore";
import { useAgriStore } from "../agri/useAgriStore";

export type ChatRole = "user" | "assistant";
export type ChatKind = "question" | "answer" | "clarification" | "error";

export interface ChatMessage {
  id: string;
  role: ChatRole;
  kind: ChatKind;
  text: string;
  /** For a follow-up: the complete question it was asked as. */
  readAs?: string | null;
  /** Where an answer came from. */
  source?: "risk engine" | "weather" | "satellite analysis";
  placeholder?: boolean;
  sample?: boolean;
  via: "text" | "voice";
}

export const EMPTY_CONTEXT: ChatContext = {
  last_query: null,
  last_intent: null,
  focus_area_id: null,
  area_ids: [],
  language: null,
};

const STORAGE_KEY = "ag04.conversation.v1";
const MAX_MESSAGES = 200;
const BUSY = "The previous question is still being answered. Ask again when it has finished.";
const NO_ANSWER = "No answer came back for this question.";

interface ChatState {
  open: boolean;
  messages: ChatMessage[];
  context: ChatContext;
  pending: boolean;
  /** The risk-engine answer the conversation last showed (the answer card does not repeat it). */
  lastAgri: AgriQueryResult | null;
  setOpen: (open: boolean) => void;
  /** Ask a message in the conversation; resolves to the assistant's reply (null when nothing was sent). */
  send: (text: string, via?: "text" | "voice") => Promise<ChatMessage | null>;
  clear: () => void;
}

let counter = 0;
const id = () => `${Date.now().toString(36)}-${(counter += 1)}`;

function restore(): Pick<ChatState, "messages" | "context"> {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (raw) {
      const saved = JSON.parse(raw) as Pick<ChatState, "messages" | "context">;
      if (Array.isArray(saved.messages) && saved.context) return { messages: saved.messages, context: saved.context };
    }
  } catch {
    // no storage, or a malformed entry: start a new conversation
  }
  return { messages: [], context: EMPTY_CONTEXT };
}

function persist(messages: ChatMessage[], context: ChatContext) {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ messages: messages.slice(-MAX_MESSAGES), context }));
  } catch {
    // storage unavailable: the conversation still works for this page
  }
}

/** What the next follow-up refers to, after a risk-engine answer. */
export function contextAfterAgri(previous: ChatContext, answer: AgriQueryResult, query: string): ChatContext {
  if (answer.intent === "unmatched") return { ...previous, last_query: query };
  const listing = answer.intent === "rank" || answer.intent === "inspect";
  return {
    last_query: query,
    last_intent: answer.common_intent,
    focus_area_id: answer.focus_area_id ?? previous.focus_area_id,
    area_ids: listing ? answer.area_ids : previous.area_ids,
    language: answer.language,
  };
}

/** After a weather or satellite answer: the areas stay in focus, the kind of question changes. */
export function contextAfterAnalysis(previous: ChatContext, result: AnalyzeResult, query: string): ChatContext {
  const intent = result.weather ? "WEATHER_RISK" : result.response.task === "crop_health" ? "CROP_HEALTH" : "IMAGERY";
  return { ...previous, last_query: query, last_intent: intent, language: "english" };
}

export const useChatStore = create<ChatState>((set, get) => ({
  open: false,
  pending: false,
  lastAgri: null,
  ...restore(),

  setOpen: (open) => set({ open }),

  clear: () => {
    set({ messages: [], context: EMPTY_CONTEXT });
    persist([], EMPTY_CONTEXT);
  },

  send: async (raw, via = "text") => {
    const text = raw.trim();
    if (!text || get().pending) return null;
    const add = (message: Omit<ChatMessage, "id" | "via">) => {
      const full: ChatMessage = { ...message, id: id(), via };
      set({ messages: [...get().messages, full] });
      return full;
    };
    const question = add({ role: "user", kind: "question", text });
    if (useAppStore.getState().pending) return add({ role: "assistant", kind: "error", text: BUSY });

    set({ pending: true });
    let reply: ChatMessage;
    try {
      const resolved = await api.chatResolve(text, get().context);
      if (resolved.clarification || !resolved.query) {
        reply = add({ role: "assistant", kind: "clarification", text: resolved.clarification ?? NO_ANSWER });
        return reply;
      }
      const query = resolved.query;
      if (resolved.rewritten) {
        set({ messages: get().messages.map((m) => (m.id === question.id ? { ...m, readAs: query } : m)) });
      }

      const before = { agri: useAgriStore.getState().answer, result: useAppStore.getState().result };
      await useAppStore.getState().runAnalysis(query);
      const agri = useAgriStore.getState().answer;
      const result = useAppStore.getState().result;
      const error = useAppStore.getState().error;

      if (agri && agri !== before.agri) {
        reply = add({
          role: "assistant",
          kind: agri.intent === "unmatched" ? "clarification" : "answer",
          text: agri.answer,
          source: "risk engine",
          placeholder: agri.intent !== "unmatched" && agri.thresholds_status === "PLACEHOLDER",
          sample: agri.intent !== "unmatched" && agri.includes_sample_data,
        });
        set({ context: contextAfterAgri(get().context, agri, query), lastAgri: agri });
      } else if (result && result !== before.result) {
        reply = add({
          role: "assistant",
          kind: "answer",
          text: result.response.answer,
          source: result.weather ? "weather" : "satellite analysis",
        });
        set({ context: contextAfterAnalysis(get().context, result, query) });
      } else {
        reply = add({ role: "assistant", kind: "error", text: error ?? NO_ANSWER });
      }
      return reply;
    } catch (error) {
      reply = add({
        role: "assistant",
        kind: "error",
        text: error instanceof Error && error.message ? error.message : "The question could not be sent to the server.",
      });
      return reply;
    } finally {
      set({ pending: false });
      persist(get().messages, get().context);
    }
  },
}));
