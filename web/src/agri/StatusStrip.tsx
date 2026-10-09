/** Always visible at the top of the map: what this dashboard is, the state of its data (live or a
 *  frozen snapshot), the threshold status and SAMPLE notice, and the map legend. Top-centre, so it
 *  never covers eastern Manipur at projector sizes. */

import { Surface } from "../ui/primitives";
import { formatTime, LEVEL_COLOR, LEVEL_LABEL, LEVELS } from "./format";
import { useAgriStore } from "./useAgriStore";

export function StatusStrip() {
  const overview = useAgriStore((s) => s.overview);
  const pestPlaceholder = overview ? overview.pest_thresholds_status === "PLACEHOLDER" : true;
  const weightsPlaceholder = overview ? overview.risk_weights_status === "PLACEHOLDER" : true;
  const sample = overview?.includes_sample_data ?? true;
  const notices = [
    pestPlaceholder ? "PLACEHOLDER thresholds" : weightsPlaceholder ? "Pest thresholds verified · prototype weighting" : null,
    sample ? "SAMPLE pest reports" : null,
  ].filter(Boolean);

  return (
    <div className="pointer-events-none absolute inset-x-0 top-4 z-20 flex justify-center px-4 max-md:hidden">
      <Surface className="pointer-events-auto flex flex-col items-center gap-1 px-3 py-1.5">
        <p className="flex items-center gap-2 text-[12px]">
          <span className="font-semibold text-ink">Crop &amp; Pest Risk Monitoring · {overview?.region ?? "Manipur"}</span>
          {overview?.mode === "snapshot" && (
            <span
              title={overview.fallback_reason ?? undefined}
              className="rounded-[4px] border border-accent/50 px-1.5 text-[11px] font-semibold text-accent"
            >
              SNAPSHOT · {formatTime(overview.snapshot_saved_at)}
            </span>
          )}
          {notices.length > 0 && (
            <span
              title={notices.join(" · ")}
              className="rounded-full border border-line px-2 py-0.5 text-[10px] font-semibold tracking-wide text-muted uppercase"
            >
              Prototype data
            </span>
          )}
        </p>
        {overview && overview.areas.length > 0 && (
          <p className="flex flex-wrap items-center justify-center gap-x-3 gap-y-0.5 text-[11px] text-muted" aria-label="Map legend">
            <span className="font-medium text-ink">Zone risk:</span>
            {LEVELS.map((level) => (
              <span key={level} className="inline-flex items-center gap-1">
                <span aria-hidden="true" className="h-2.5 w-3.5 rounded-[2px] border border-line" style={{ background: LEVEL_COLOR[level] }} />
                {LEVEL_LABEL[level]}
              </span>
            ))}
            <span className="inline-flex items-center gap-1">
              <span aria-hidden="true" className="h-0 w-3.5 border-t-2 border-dashed border-ink" />
              demo zone
            </span>
            <span className="inline-flex items-center gap-1">
              <span className="rounded-full border border-line px-1 text-[10px] font-semibold text-ink">#1</span>
              priority
            </span>
          </p>
        )}
      </Surface>
    </div>
  );
}
