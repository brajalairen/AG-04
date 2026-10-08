/** Small, consistent labels for the AG-04 dashboard. Every risk level, data state and sample or
 *  placeholder notice is printed in words beside any colour, so nothing depends on colour alone. */

import { AlertTriangle, FlaskConical } from "lucide-react";
import type { AgriOverview, DataState, RiskLevel } from "../state/types";
import { cx } from "../ui/primitives";
import { LEVEL_COLOR, LEVEL_LABEL, STATE_LABEL } from "./format";

export function LevelBadge({ level, className }: { level: RiskLevel; className?: string }) {
  return (
    <span
      className={cx(
        "inline-flex shrink-0 items-center gap-1.5 rounded-full border border-line px-2 py-0.5 text-[11px] font-semibold text-ink",
        className,
      )}
    >
      <span aria-hidden="true" className="h-2 w-2 rounded-full" style={{ background: LEVEL_COLOR[level] }} />
      {LEVEL_LABEL[level]}
    </span>
  );
}

const STATE_TONE: Record<DataState, string> = {
  LIVE: "border-ok/40 text-ok",
  CACHED: "border-line-strong text-muted",
  SNAPSHOT: "border-accent/50 text-accent",
  SAMPLE: "border-warn/50 text-warn",
  UNAVAILABLE: "border-line text-faint",
};

export function StateChip({ state, title }: { state: DataState; title?: string }) {
  return (
    <span
      title={title}
      className={cx(
        "inline-flex shrink-0 items-center rounded-[4px] border px-1.5 py-px text-[10px] font-semibold tracking-wide uppercase",
        STATE_TONE[state],
      )}
    >
      {STATE_LABEL[state]}
    </span>
  );
}

/** The sample-data label, verbatim wherever synthetic pest reports appear. */
export function SampleLabel({ text = "SAMPLE DATA — Prototype Simulation" }: { text?: string }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-[4px] border border-warn/50 bg-warn/10 px-1.5 py-px text-[10px] font-semibold tracking-wide text-warn uppercase">
      <FlaskConical className="h-3 w-3" strokeWidth={2} aria-hidden="true" />
      {text}
    </span>
  );
}

export function DemoTag() {
  return (
    <span
      title="Demo monitoring rectangle: not an administrative boundary"
      className="inline-flex shrink-0 items-center rounded-[4px] border border-dashed border-line-strong px-1.5 py-px text-[10px] font-semibold tracking-wide text-muted uppercase"
    >
      Demo area
    </span>
  );
}

/** While thresholds are placeholders, scores must never read as validated findings. */
export function PlaceholderNotice({ note, compact }: { note: string | null; compact?: boolean }) {
  if (!note) return null;
  return (
    <div
      role="note"
      className="flex gap-2 rounded-[var(--radius-sm)] border border-warn/50 bg-warn/10 px-3 py-2 text-[11px] leading-relaxed text-ink"
    >
      <AlertTriangle className="mt-px h-3.5 w-3.5 shrink-0 text-warn" strokeWidth={2} aria-hidden="true" />
      <p>
        <strong className="font-semibold">PLACEHOLDER thresholds.</strong>{" "}
        {compact
          ? "Prototype scores, not validated findings or confirmed outbreaks."
          : "These scores test the method. They are not validated agricultural findings and do not confirm any outbreak."}
      </p>
    </div>
  );
}

export function CompletenessBar({ fraction }: { fraction: number }) {
  return (
    <span className="inline-flex items-center gap-1.5" title="Data completeness: share of the model's inputs available">
      <span className="relative h-1.5 w-10 overflow-hidden rounded-full bg-sunken" aria-hidden="true">
        <span className="absolute inset-y-0 left-0 rounded-full bg-muted" style={{ width: `${Math.round(fraction * 100)}%` }} />
      </span>
      <span className="text-[11px] text-muted tabular-nums">{Math.round(fraction * 100)}%</span>
    </span>
  );
}

/** Threshold status for the dashboard: pest thresholds and risk weighting are stated separately, so
 *  verified pest rules can never make the team's weighting look scientifically validated. */
export function ThresholdsNotice({ overview }: { overview: AgriOverview }) {
  const pestVerified = overview.pest_thresholds_status === "VERIFIED";
  const weightsVerified = overview.risk_weights_status === "VERIFIED";
  if (!pestVerified) return <PlaceholderNotice note={overview.thresholds_note ?? "placeholder"} compact />;
  return (
    <p role="note" className="rounded-[var(--radius-sm)] border border-line px-3 py-2 text-[11px] leading-relaxed text-ink">
      <strong className="font-semibold">Pest thresholds: VERIFIED</strong> (sources in each pest rule).{" "}
      <strong className="font-semibold">Risk weighting: {weightsVerified ? "VERIFIED" : "prototype design"}</strong>.
      Decision support, not a validated prediction.
    </p>
  );
}
