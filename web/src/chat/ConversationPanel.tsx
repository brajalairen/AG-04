/** 💬 Conversation and 🎙️ Voice Chat: a transcript panel on top of the existing question flow.
 *
 *  Answers are the existing system's text, unchanged; a follow-up shows the complete question it was asked as. */

import { useEffect, useRef, useState } from "react";
import { ArrowUp, AudioLines, MessageSquare, Mic, Square, Trash2, X } from "lucide-react";
import { cx, IconButton, Spinner, Surface } from "../ui/primitives";
import { useAppStore } from "../state/useAppStore";
import { PlaceholderNotice, SampleLabel } from "../agri/badges";
import { useAgriStore } from "../agri/useAgriStore";
import { useChatStore, type ChatMessage } from "./useChatStore";
import { useVoiceChat, voiceChatSupported, type VoiceStatus } from "./useVoiceChat";

const EXAMPLES = ["Which areas are at high risk?", "Why?", "What about Thoubal?"];
const STATUS_LABEL: Record<VoiceStatus, string> = {
  idle: "",
  listening: "🎙️ Listening…",
  processing: "Processing…",
  speaking: "🔊 Speaking…",
  interrupting: "🎙️ Listening…",
  error: "",
};
/** Whether a voice session is running (an error or idle state is not). */
const isOn = (status: VoiceStatus) => status !== "idle" && status !== "error";

/** The two mode buttons, beside the theme toggle. */
export function ConversationLaunchers() {
  const open = useChatStore((s) => s.open);
  const setOpen = useChatStore((s) => s.setOpen);
  const status = useVoiceChat((s) => s.status);
  const start = useVoiceChat((s) => s.start);
  const stop = useVoiceChat((s) => s.stop);
  const voiceOn = isOn(status);
  return (
    <Surface className="flex items-center gap-0.5 p-1">
      <IconButton label={open ? "Close conversation" : "Conversation"} side="bottom" active={open}
                  onClick={() => setOpen(!open)}>
        <MessageSquare className="h-[18px] w-[18px]" strokeWidth={1.75} />
      </IconButton>
      <IconButton label={voiceOn ? "Stop Voice Chat" : "Voice Chat (English)"} side="bottom" active={voiceOn}
                  onClick={() => (voiceOn ? stop() : start())}
                  className={cx(voiceOn && "text-danger")}>
        <AudioLines className="h-[18px] w-[18px]" strokeWidth={1.75} />
      </IconButton>
    </Surface>
  );
}

function Bubble({ message }: { message: ChatMessage }) {
  const mine = message.role === "user";
  return (
    <li className={cx("flex flex-col gap-1", mine ? "items-end" : "items-start")}>
      <div
        className={cx(
          "max-w-[92%] rounded-[var(--radius-md)] px-3 py-2 text-[13px] leading-relaxed whitespace-pre-line",
          mine ? "bg-accent text-accent-ink" : "bg-hover text-ink",
          message.kind === "error" && "text-danger",
        )}
      >
        {mine && message.via === "voice" && <Mic className="mr-1 inline h-3 w-3 align-[-1px]" strokeWidth={2} />}
        {message.text}
      </div>
      {message.readAs && <p className="text-[11px] text-faint">Read as: {message.readAs}</p>}
      {!mine && (message.placeholder || message.sample || message.source) && (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-faint">
          {message.source && <span>From the {message.source}</span>}
          {message.sample && <SampleLabel />}
        </div>
      )}
    </li>
  );
}

export function ConversationPanel() {
  const open = useChatStore((s) => s.open);
  const setOpen = useChatStore((s) => s.setOpen);
  const messages = useChatStore((s) => s.messages);
  const pending = useChatStore((s) => s.pending);
  const send = useChatStore((s) => s.send);
  const clear = useChatStore((s) => s.clear);
  const appBusy = useAppStore((s) => s.pending);
  // Beside an open sidebar panel, not over it (the sidebar ends at 412px, as for the answer card).
  const sidebarPanelOpen = useAppStore((s) => s.sidebarOpen && s.section !== null);
  const status = useVoiceChat((s) => s.status);
  const hearing = useVoiceChat((s) => s.hearing);
  const notice = useVoiceChat((s) => s.notice);
  const startVoice = useVoiceChat((s) => s.start);
  const stopVoice = useVoiceChat((s) => s.stop);
  const [draft, setDraft] = useState("");
  const list = useRef<HTMLOListElement>(null);
  const voiceOn = isOn(status);
  const busy = pending || appBusy || voiceOn;
  const placeholderShown = messages.some((m) => m.placeholder);
  const thresholdsNote = useAgriStore((s) => s.overview?.thresholds_note ?? null);

  useEffect(() => {
    list.current?.scrollTo({ top: list.current.scrollHeight });
  }, [messages.length, hearing, open]);

  if (!open) return null;

  const submit = (text = draft) => {
    if (!text.trim() || busy) return;
    setDraft("");
    void send(text);
  };

  return (
    <div
      className={cx(
        "pointer-events-none absolute top-16 bottom-28 z-30 flex max-sm:inset-x-4 max-sm:left-4",
        sidebarPanelOpen ? "left-[412px]" : "left-20",
      )}
    >
      <Surface
        raised
        role="region"
        aria-label="Conversation"
        className="pointer-events-auto flex w-[400px] max-w-full flex-col overflow-hidden"
      >
        <header className="flex shrink-0 items-center gap-2 border-b border-line px-3 py-2">
          <MessageSquare className="h-4 w-4 text-muted" strokeWidth={1.75} />
          <h2 className="flex-1 text-[13px] font-semibold text-ink">Conversation</h2>
          {voiceOn && (
            <span className="rounded-full bg-accent-soft px-2 py-0.5 text-[11px] font-medium text-accent" aria-live="polite">
              {STATUS_LABEL[status]}
            </span>
          )}
          <IconButton label="Clear conversation" side="bottom" onClick={clear} disabled={busy || !messages.length}
                      className="h-7 w-7">
            <Trash2 className="h-4 w-4" strokeWidth={1.75} />
          </IconButton>
          <IconButton label="Close conversation" side="bottom" onClick={() => setOpen(false)} className="h-7 w-7">
            <X className="h-4 w-4" strokeWidth={2} />
          </IconButton>
        </header>

        <ol ref={list} className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto px-3 py-3" aria-live="polite">
          {!messages.length && (
            <li className="text-[12px] leading-relaxed text-muted">
              Ask about crop & pest risk and follow up naturally, for example:
              <span className="mt-2 flex flex-wrap gap-1.5">
                {EXAMPLES.map((example) => (
                  <button key={example} type="button" onClick={() => submit(example)} disabled={busy}
                          className="rounded-full border border-line px-2.5 py-1 text-[12px] text-ink hover:bg-hover disabled:opacity-50">
                    {example}
                  </button>
                ))}
              </span>
            </li>
          )}
          {messages.map((message) => (
            <Bubble key={message.id} message={message} />
          ))}
          {hearing && <li className="self-end text-[12px] text-muted italic">{hearing}</li>}
          {pending && (
            <li className="flex items-center gap-2 text-[12px] text-muted">
              <Spinner /> Working on it…
            </li>
          )}
        </ol>

        {placeholderShown && (
          <div className="shrink-0 border-t border-line px-3 py-2">
            <PlaceholderNotice note={thresholdsNote} compact />
          </div>
        )}
        {notice && <p className="shrink-0 border-t border-line px-3 py-2 text-[12px] text-warn">{notice}</p>}

        <div className="flex shrink-0 items-end gap-1 border-t border-line p-1.5">
          <textarea
            rows={1}
            value={draft}
            disabled={busy}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                submit();
              }
            }}
            placeholder={voiceOn ? "Voice Chat is on: just speak" : "Ask a question or a follow-up…"}
            aria-label="Conversation message"
            className="max-h-[96px] flex-1 resize-none self-center bg-transparent px-2 py-2 text-[13px] leading-snug text-ink placeholder:text-faint focus:outline-none disabled:opacity-60"
          />
          {voiceChatSupported() && (
            <IconButton label={voiceOn ? "Stop Voice Chat" : "Voice Chat (English)"} side="top" active={voiceOn}
                        onClick={() => (voiceOn ? stopVoice() : startVoice())}
                        className={cx(voiceOn && "text-danger")}>
              {voiceOn ? <Square className="h-4 w-4" strokeWidth={2} /> : <AudioLines className="h-[18px] w-[18px]" strokeWidth={1.75} />}
            </IconButton>
          )}
          <IconButton label="Send" side="top" disabled={!draft.trim() || busy} onClick={() => submit()}
                      className={cx(draft.trim() && !busy && "bg-accent text-accent-ink hover:brightness-110")}>
            {pending ? <Spinner /> : <ArrowUp className="h-[18px] w-[18px]" strokeWidth={2.25} />}
          </IconButton>
        </div>
      </Surface>
    </div>
  );
}
