/** "What should I inspect first?": districts in the risk engine's priority order, then the monitored
 *  agricultural zones inside one district. Opens by default.
 *
 *  Every figure is the server's. A district is administrative context and is never scored: its level and
 *  score are those of its highest-priority monitored zone, as the API reports them. A district without
 *  a monitored zone has no level at all: monitoring coverage is not available there, which is not "no risk". */

import { ArrowLeft, MapPinned, RotateCw } from "lucide-react";
import { EmptyState } from "../sidebar/Sidebar";
import type { AgriOverview, AreaSummary, DistrictSummary } from "../state/types";
import { Button, cx, Segmented, Spinner } from "../ui/primitives";
import { CompletenessBar, DemoTag, LevelBadge, StateChip } from "./badges";
import { filterDistricts, FILTER_OPTIONS, formatScore, formatTime, LEVEL_COLOR, LEVEL_LABEL, LEVELS } from "./format";
import { useAgriStore } from "./useAgriStore";

export function PriorityPanel() {
  const overview = useAgriStore((s) => s.overview);
  const status = useAgriStore((s) => s.status);
  const error = useAgriStore((s) => s.error);
  const districtName = useAgriStore((s) => s.districtName);
  const load = useAgriStore((s) => s.load);

  if (status === "loading" && !overview) {
    return (
      <div className="flex flex-col items-center gap-3 px-6 py-10 text-center">
        <Spinner />
        <p className="text-[12px] leading-relaxed text-muted">
          Assessing the monitored zones. A first run fetches weather and satellite statistics and can take about a
          minute; after that the dashboard is served from the warm cache.
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
  if (!overview.areas.length) return <EmptyState icon={MapPinned}>No monitored zones are configured.</EmptyState>;

  const district = districtName ? overview.districts.find((d) => d.name === districtName) : null;
  return district ? <DistrictView overview={overview} district={district} /> : <DistrictList overview={overview} />;
}

function DataLine({ overview }: { overview: AgriOverview }) {
  return (
    <div className="flex flex-col gap-1.5">
      <p className="flex flex-wrap items-center gap-1.5 text-[11px] text-muted">
        <span>As of {formatTime(overview.as_of)}</span>
        {overview.data_states.map((state) => (
          <StateChip key={state} state={state} />
        ))}
      </p>
      {overview.mode === "snapshot" && (
        <p role="note" className="rounded-[var(--radius-sm)] border border-accent/40 bg-accent-soft px-3 py-2 text-[11px] leading-relaxed text-ink">
          <strong className="font-semibold">Frozen SNAPSHOT of {formatTime(overview.snapshot_saved_at)}</strong>, not live
          data. {overview.fallback_reason}
        </p>
      )}
    </div>
  );
}

/** One compact line of what makes this a prototype: never silent, never loud. Each clause is read
 *  from the same server fields the fuller per-zone notices use, so if pest thresholds or pest data
 *  are ever VERIFIED/real, the clause naming them drops on its own rather than staying stale. */
function PrototypeNotice({ overview }: { overview: AgriOverview }) {
  const unvalidated = overview.pest_thresholds_status !== "VERIFIED";
  const clauses = [
    "Prototype assessment",
    overview.includes_sample_data ? "Synthetic pest reports" : null,
    unvalidated ? "Unvalidated thresholds" : null,
  ].filter(Boolean);
  return (
    <p
      title="Decision support only: scores are not validated agricultural findings and do not confirm any outbreak."
      className="text-[11px] tracking-wide text-faint uppercase"
    >
      {clauses.join(" · ")}
    </p>
  );
}

function DistrictList({ overview }: { overview: AgriOverview }) {
  const filter = useAgriStore((s) => s.filter);
  const setFilter = useAgriStore((s) => s.setFilter);
  const setDistrict = useAgriStore((s) => s.setDistrict);
  const highlightIds = useAgriStore((s) => s.highlightIds);
  const covered = overview.districts.filter((d) => d.coverage === "monitored");
  const uncovered = overview.districts.filter((d) => d.coverage !== "monitored");
  const shown = filterDistricts(covered, filter);

  return (
    <div className="flex flex-col gap-3 p-4">
      <div>
        <p className="text-[13px] font-semibold text-ink">
          {overview.zone_count} monitored zone{overview.zone_count === 1 ? "" : "s"} in {covered.length} district
          {covered.length === 1 ? "" : "s"}
        </p>
        <p className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-[12px] text-muted" aria-label="Monitored zones by risk level">
          {LEVELS.filter((level) => overview.counts[level] || level === "HIGH" || level === "MODERATE" || level === "LOW").map(
            (level) => (
              <span key={level} className="inline-flex items-center gap-1.5">
                <span aria-hidden="true" className="h-2 w-2 rounded-full" style={{ background: LEVEL_COLOR[level] }} />
                <strong className="font-semibold text-ink tabular-nums">{overview.counts[level] ?? 0}</strong>
                {level === "INSUFFICIENT_DATA" ? "no data" : LEVEL_LABEL[level].toLowerCase()}
              </span>
            ),
          )}
        </p>
      </div>

      <DataLine overview={overview} />
      <PrototypeNotice overview={overview} />

      <Segmented value={filter} options={FILTER_OPTIONS} onChange={setFilter} />

      {shown.length === 0 ? (
        <p className="py-4 text-center text-[12px] text-muted">No district has a monitored zone at this level.</p>
      ) : (
        <ol className="-mx-1 flex flex-col" aria-label="Districts by priority">
          {shown.map((d) => (
            <li key={d.name}>
              <button
                type="button"
                onClick={() => setDistrict(d.name)}
                className={cx(
                  "flex w-full items-center gap-3 rounded-[var(--radius-sm)] px-2 py-2.5 text-left transition-colors hover:bg-hover",
                  d.zone_ids.some((id) => highlightIds.includes(id)) && "ring-1 ring-accent/40",
                )}
              >
                <span className="w-5 shrink-0 text-right text-[13px] font-semibold text-muted tabular-nums">
                  {d.rank ?? "–"}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-2">
                    <span className="truncate text-[14px] font-semibold text-ink">{d.name}</span>
                    {d.level && <LevelBadge level={d.level} />}
                  </span>
                  <span className="mt-0.5 block text-[11px] text-muted">
                    {d.confidence && <>Confidence {d.confidence} · </>}
                    {d.zone_count} monitored zone{d.zone_count === 1 ? "" : "s"}
                  </span>
                </span>
                <span className="shrink-0 text-right">
                  <span className="block text-[18px] leading-none font-semibold text-ink tabular-nums">
                    {formatScore(d.score)}
                  </span>
                  <span className="text-[10px] text-faint">/100</span>
                </span>
              </button>
            </li>
          ))}
        </ol>
      )}

      {filter === "all" && uncovered.length > 0 && (
        <div className="border-t border-line pt-3">
          <p className="text-[11px] font-semibold tracking-wide text-muted uppercase">
            Monitoring coverage not yet available ({uncovered.length})
          </p>
          <p className="mt-1 text-[11px] leading-relaxed text-faint">
            No agricultural zone is monitored in these districts yet. This is not the same as no risk.
          </p>
          <p className="mt-1.5 flex flex-wrap gap-1">
            {uncovered.map((d) => (
              <button
                key={d.name}
                type="button"
                onClick={() => setDistrict(d.name)}
                className="rounded-full border border-line px-2 py-0.5 text-[11px] text-muted transition-colors hover:bg-hover hover:text-ink"
              >
                {d.name}
              </button>
            ))}
          </p>
        </div>
      )}

      <Footer overview={overview} />
    </div>
  );
}

function DistrictView({ overview, district: d }: { overview: AgriOverview; district: DistrictSummary }) {
  const setDistrict = useAgriStore((s) => s.setDistrict);
  const select = useAgriStore((s) => s.select);
  const hover = useAgriStore((s) => s.hover);
  const selectedId = useAgriStore((s) => s.selectedId);
  // The server's engine order, restricted to this district's zones.
  const zones: AreaSummary[] = overview.areas.filter((a) => d.zone_ids.includes(a.id));
  const topCount = d.level ? d.level_counts[d.level] : 0;

  return (
    <div className="flex flex-col gap-3 p-4">
      <button
        type="button"
        onClick={() => setDistrict(null)}
        className="inline-flex items-center gap-1 self-start text-[12px] text-muted hover:text-ink"
      >
        <ArrowLeft className="h-3.5 w-3.5" strokeWidth={2} /> All districts
      </button>

      <div>
        <h3 className="text-[16px] font-semibold tracking-wide text-ink uppercase">{d.name}</h3>
        {d.coverage === "monitored" ? (
          <div className="mt-2 flex flex-col gap-1.5 text-[12px] text-muted">
            <p className="flex items-center gap-2">
              Priority {d.level && <LevelBadge level={d.level} />}
              {d.rank && <span>#{d.rank} of {overview.districts.filter((x) => x.rank !== null).length} districts</span>}
            </p>
            <p>
              Coverage: <strong className="font-semibold text-ink">{d.zone_count}</strong> monitored zone
              {d.zone_count === 1 ? "" : "s"}
              {d.level && (
                <>
                  {" "}
                  · {topCount} of {d.zone_count} {LEVEL_LABEL[d.level].toLowerCase()}
                </>
              )}
            </p>
            <p className="text-[11px] leading-relaxed text-faint">
              A district alert means a monitored agricultural zone in it needs attention. It does not mean the whole
              district is affected.
            </p>
          </div>
        ) : (
          <p className="mt-2 rounded-[var(--radius-sm)] border border-line bg-sunken px-3 py-2 text-[12px] leading-relaxed text-ink">
            Monitoring coverage not yet available. No agricultural zone is monitored in this district yet; this is not
            the same as no risk.
          </p>
        )}
        <p className="mt-2 text-[11px] leading-relaxed text-faint">
          {d.has_boundary
            ? `District boundary: ${d.boundary_source}.`
            : "District boundary not loaded yet (pending verified data)" +
              (d.coverage === "monitored" ? "; the map frames this district's monitored zones." : ".")}
        </p>
      </div>

      {zones.length > 0 && (
        <div>
          <p className="mb-1 text-[11px] font-semibold tracking-wide text-muted uppercase">Monitored zones</p>
          <ol className="-mx-1 flex flex-col">
            {zones.map((zone) => (
              <li key={zone.id}>
                <button
                  type="button"
                  onClick={() => select(zone.id)}
                  onMouseEnter={() => hover(zone.id)}
                  onMouseLeave={() => hover(null)}
                  aria-current={selectedId === zone.id ? "true" : undefined}
                  className={cx(
                    "flex w-full items-start gap-2.5 rounded-[var(--radius-sm)] px-2 py-2 text-left transition-colors hover:bg-hover",
                    selectedId === zone.id && "bg-accent-soft",
                  )}
                >
                  <span className="min-w-0 flex-1">
                    <span className="block text-[12px] leading-snug font-medium text-ink">{zone.name}</span>
                    <span className="mt-1 flex flex-wrap items-center gap-1.5 text-[11px] text-muted">
                      <LevelBadge level={zone.level} />
                      {zone.kind === "demo" && <DemoTag />}
                      <span>conf. {zone.confidence}</span>
                      <CompletenessBar fraction={zone.data_completeness} />
                    </span>
                  </span>
                  <span className="shrink-0 text-right">
                    <span className="block text-[16px] leading-none font-semibold text-ink tabular-nums">
                      {formatScore(zone.score)}
                    </span>
                    <span className="text-[10px] text-faint">/100</span>
                  </span>
                </button>
              </li>
            ))}
          </ol>
          <p className="mt-1 text-[11px] text-faint">Select a zone to see why it is flagged.</p>
        </div>
      )}

      <Footer overview={overview} />
    </div>
  );
}

function Footer({ overview }: { overview: AgriOverview }) {
  const status = useAgriStore((s) => s.status);
  const error = useAgriStore((s) => s.error);
  const load = useAgriStore((s) => s.load);
  return (
    <div className="flex flex-col gap-1.5 border-t border-line pt-3">
      <p className="text-[11px] leading-relaxed text-faint">{overview.area_note}</p>
      <p className="text-[11px] leading-relaxed text-faint">{overview.district_note}</p>
      <p className="text-[11px] leading-relaxed text-faint">{overview.disclaimer}</p>
      <div>
        <Button variant="quiet" size="sm" onClick={() => void load()} disabled={status === "loading"}>
          <RotateCw className={cx("h-3.5 w-3.5", status === "loading" && "animate-spin")} strokeWidth={2} />
          {status === "loading" ? "Reloading…" : "Reload"}
        </Button>
        {status === "error" && <p className="mt-1 text-[11px] text-danger">{error}</p>}
      </div>
    </div>
  );
}
