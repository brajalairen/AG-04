/** The answer to an agricultural question from the command bar, just above it. The text is the
 *  server's (built from the risk engine's assessments); the matched rule is shown for transparency. */

import { X } from "lucide-react";
import { cx, IconButton, Surface } from "../ui/primitives";
import { useAppStore } from "../state/useAppStore";
import { PlaceholderNotice, SampleLabel } from "./badges";
import { formatTime } from "./format";
import { useAgriStore } from "./useAgriStore";
import { useChatStore } from "../chat/useChatStore";

const INTENT_LABEL = {
  rank: "Risk ranking",
  inspect: "Suggested inspection order",
  explain: "Why this area is flagged",
  unmatched: "Crop & pest risk",
} as const;

export function AgriAnswerCard() {
  const answer = useAgriStore((s) => s.answer);
  const clearAnswer = useAgriStore((s) => s.clearAnswer);
  const thresholdsNote = useAgriStore((s) => s.overview?.thresholds_note ?? null);
  const panelOpen = useAppStore((s) => s.sidebarOpen && s.section !== null);
  // An answer the open conversation already shows is not repeated; command-bar answers still appear here.
  const inConversation = useChatStore((s) => s.open && s.lastAgri !== null && s.lastAgri === answer);
  if (!answer || inConversation) return null;
  return (
    <div
      className={cx(
        "pointer-events-none absolute inset-x-0 bottom-[8.5rem] z-30 flex justify-center px-4",
        panelOpen && "sm:pl-[412px]",
      )}
    >
      <Surface
        raised
        role="region"
        aria-label="Agricultural answer"
        className="pointer-events-auto flex max-h-[42vh] w-[640px] max-w-full flex-col overflow-hidden"
      >
        <header className="flex shrink-0 items-center justify-between gap-2 border-b border-line px-4 py-2.5">
          <h2 className="text-[13px] font-semibold text-ink">{INTENT_LABEL[answer.intent]}</h2>
          <IconButton label="Dismiss answer" side="left" onClick={clearAnswer} className="-mr-1.5 h-7 w-7">
            <X className="h-4 w-4" strokeWidth={2} />
          </IconButton>
        </header>
        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3">
          <p className="text-[13px] leading-relaxed whitespace-pre-line text-ink">{answer.answer}</p>
          {answer.intent !== "unmatched" && answer.thresholds_status === "PLACEHOLDER" && (
            <div className="mt-3">
              <PlaceholderNotice note={thresholdsNote ?? "placeholder"} compact />
            </div>
          )}
          <p className="mt-2.5 flex flex-wrap items-center gap-2 text-[10px] text-faint">
            {answer.includes_sample_data && answer.intent !== "unmatched" && <SampleLabel />}
            <span>Rule: {answer.matched_rule}</span>
            <span>Assessment of {formatTime(answer.computed_at)}</span>
          </p>
        </div>
      </Surface>
    </div>
  );
}
