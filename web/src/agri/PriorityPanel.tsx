/** The early-warning list: every monitored area in the risk engine's rank order.
 *  Opens by default; clicking a row opens that area's "Why is this area at risk?" drawer. */

import { MapPinned, RotateCw } from "lucide-react";
import { EmptyState } from "../sidebar/Sidebar";
import { Button, cx, Segmented, Spinner } from "../ui/primitives";
import { CompletenessBar, DemoTag, LevelBadge, PlaceholderNotice, SampleLabel, StateChip } from "./badges";
import { filterAreas, FILTER_OPTIONS, formatScore, formatTime, LEVEL_COLOR, LEVEL_LABEL, LEVELS } from "./format";
import { useAgriStore } from "./useAgriStore";

export function PriorityPanel() {
  const { overview, status, error, filter, selectedId, highlightIds } = useAgriStore();
  const load = useAgriStore((s) => s.load);
  const setFilter = useAgriStore((s) => s.setFilter);
  const select = useAgriStore((s) => s.select);
  const hover = useAgriStore((s) => s.hover);

  if (status === "loading" && !overview) {
    return (
      <div className="flex flex-col items-center gap-3 px-6 py-10 text-center">
        <Spinner />
        <p className="text-[12px] leading-relaxed text-muted">
          Assessing the monitored areas. The first run fetches weather and satellite statistics and can take
          about a minute; later runs come from the cache.
        </p>
      </div>
    );
  }
  if (status === "error" && !overview) {
    return (
      <div className="flex flex-col items-center gap-3 px-6 py-10 text-center">
        <p className="text-[12px] leading-relaxed text-danger">{error}</p>
        <Button variant="outline" size="sm" onClick={() => void load()}>
          <RotateCw className="h-3.5 w-3.5" strokeWidth={2} /> Try again
        </Button>
      </div>
    );
  }
  if (!overview) return null;
  if (!overview.areas.length) {
    return <EmptyState icon={MapPinned}>No monitored areas are configured.</EmptyState>;
  }

  const shown = filterAreas(overview.areas, filter);
  return (
    <div className="flex flex-col gap-3 p-4">
      <div className="flex flex-wrap items-center gap-1.5 text-[11px] text-muted">
        <span>
          {overview.region} · as of {formatTime(overview.as_of)}
          {overview.offline && " · offline (cached data)"}
        </span>
        {overview.data_states.map((state) => (
          <StateChip key={state} state={state} />
        ))}
      </div>

      <PlaceholderNotice note={overview.thresholds_note} compact />
      {overview.includes_sample_data && (
        <p className="flex flex-wrap items-center gap-1.5 text-[11px] leading-relaxed text-muted">
          <SampleLabel text={overview.sample_label} /> Pest-report figures are synthetic.
        </p>
      )}

      <div className="grid grid-cols-5 gap-1" aria-label="Areas by risk level">
        {LEVELS.map((level) => (
          <div key={level} className="flex flex-col items-center rounded-[6px] border border-line px-1 py-1.5">
            <span className="text-[15px] font-semibold text-ink tabular-nums">{overview.counts[level] ?? 0}</span>
            <span className="flex items-center gap-1 text-[10px] text-muted">
              <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full" style={{ background: LEVEL_COLOR[level] }} />
              {level === "INSUFFICIENT_DATA" ? "No data" : LEVEL_LABEL[level]}
            </span>
          </div>
        ))}
      </div>

      <Segmented value={filter} options={FILTER_OPTIONS} onChange={setFilter} />

      {shown.length === 0 ? (
        <p className="py-6 text-center text-[12px] text-muted">No area at this level.</p>
      ) : (
        <ol className="-mx-1 flex flex-col">
          {shown.map((area) => (
            <li key={area.id}>
              <button
                type="button"
                onClick={() => select(area.id)}
                onMouseEnter={() => hover(area.id)}
                onMouseLeave={() => hover(null)}
                aria-current={selectedId === area.id ? "true" : undefined}
                className={cx(
                  "flex w-full items-start gap-2.5 rounded-[var(--radius-sm)] px-2 py-2 text-left transition-colors hover:bg-hover",
                  selectedId === area.id && "bg-accent-soft",
                  highlightIds.includes(area.id) && selectedId !== area.id && "ring-1 ring-accent/40",
                )}
              >
                <span className="w-6 shrink-0 pt-0.5 text-right text-[12px] font-semibold text-muted tabular-nums">
                  {area.rank ? `#${area.rank}` : "–"}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block text-[12px] leading-snug font-medium text-ink">{area.name}</span>
                  <span className="mt-1 flex flex-wrap items-center gap-1.5 text-[11px] text-muted">
                    <LevelBadge level={area.level} />
                    {area.kind === "demo" && <DemoTag />}
                    <span>conf. {area.confidence}</span>
                    <CompletenessBar fraction={area.data_completeness} />
                  </span>
                </span>
                <span className="shrink-0 text-right">
                  <span className="block text-[16px] leading-none font-semibold text-ink tabular-nums">
                    {formatScore(area.score)}
                  </span>
                  <span className="text-[10px] text-faint">/100</span>
                </span>
              </button>
            </li>
          ))}
        </ol>
      )}

      <p className="text-[11px] leading-relaxed text-faint">{overview.area_note}</p>
      <p className="text-[11px] leading-relaxed text-faint">{overview.disclaimer}</p>
      <div>
        <Button variant="quiet" size="sm" onClick={() => void load()} disabled={status === "loading"}>
          <RotateCw className={cx("h-3.5 w-3.5", status === "loading" && "animate-spin")} strokeWidth={2} />
          {status === "loading" ? "Refreshing…" : "Refresh"}
        </Button>
        {status === "error" && <p className="mt-1 text-[11px] text-danger">{error}</p>}
      </div>
    </div>
  );
}
