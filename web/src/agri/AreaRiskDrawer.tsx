/** "Why is this area at risk?": one area's full assessment, exactly as the risk engine produced it.
 *  Every number is read from the API; the drawer only lays it out, with each limitation in view. */

import type { ReactNode } from "react";
import { RotateCw, Satellite, X } from "lucide-react";
import type {
  AgriAreaDetail,
  DayCheck,
  FactorResult,
  NdviAnomaly,
  PestEvaluation,
  PestReport,
  WeatherFigures,
} from "../state/types";
import { Button, cx, IconButton, Spinner, Surface } from "../ui/primitives";
import { CompletenessBar, DemoTag, LevelBadge, PlaceholderNotice, SampleLabel, StateChip } from "./badges";
import {
  FACTOR_COLOR_VAR,
  FACTOR_LABEL,
  FACTORS,
  formatNumber,
  formatPercent,
  formatScore,
  formatTime,
  LEVEL_COLOR,
  pestName,
  scoreSegments,
} from "./format";
import { useAgriStore } from "./useAgriStore";
import { useAppStore } from "../state/useAppStore";

export function AreaRiskDrawer() {
  const selectedId = useAgriStore((s) => s.selectedId);
  const detail = useAgriStore((s) => s.detail);
  const status = useAgriStore((s) => s.detailStatus);
  const error = useAgriStore((s) => s.detailError);
  const select = useAgriStore((s) => s.select);
  const name = useAgriStore((s) => s.overview?.areas.find((a) => a.id === s.selectedId)?.name);
  if (!selectedId) return null;

  return (
    <div className="pointer-events-none absolute inset-0 z-40 flex justify-end">
      <Surface
        raised
        role="dialog"
        aria-label="Why is this area at risk?"
        className="pointer-events-auto m-4 flex w-[440px] max-w-[calc(100vw-2rem)] flex-col overflow-hidden"
      >
        <header className="flex shrink-0 items-start justify-between gap-2 border-b border-line px-4 py-3">
          <div className="min-w-0">
            <h2 className="text-[14px] font-semibold text-ink">Why is this area at risk?</h2>
            <p className="truncate text-[12px] text-muted">{detail?.area.name ?? name ?? selectedId}</p>
          </div>
          <IconButton label="Close" side="left" onClick={() => select(null)} className="-mr-1.5 h-7 w-7">
            <X className="h-4 w-4" strokeWidth={2} />
          </IconButton>
        </header>
        <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
          {status === "loading" && (
            <div className="flex flex-col items-center gap-3 px-6 py-12 text-center">
              <Spinner />
              <p className="text-[12px] text-muted">Loading the assessment</p>
            </div>
          )}
          {status === "error" && (
            <div className="flex flex-col items-center gap-3 px-6 py-12 text-center">
              <p className="text-[12px] text-danger">{error}</p>
              <Button variant="outline" size="sm" onClick={() => select(selectedId)}>
                <RotateCw className="h-3.5 w-3.5" strokeWidth={2} /> Try again
              </Button>
            </div>
          )}
          {status === "ready" && detail && <Content detail={detail} />}
        </div>
      </Surface>
    </div>
  );
}

function Content({ detail }: { detail: AgriAreaDetail }) {
  const { area, assessment: a } = detail;
  const factor = (id: string) => a.factors.find((f) => f.id === id);
  const weather = factor("weather_pest");
  const ndvi = factor("ndvi_anomaly");
  const reports = factor("report_pressure");
  return (
    <>
      <Block>
        <div className="flex items-start justify-between gap-3">
          <div className="flex flex-col gap-1.5">
            <LevelBadge level={a.level} className="self-start text-[12px]" />
            <p className="text-[12px] text-muted">
              {a.rank ? `Priority #${a.rank} of ${a.rank_of} assessed areas` : "Not ranked: not enough data"}
            </p>
          </div>
          <p className="text-right">
            <span className="text-[30px] leading-none font-semibold text-ink tabular-nums">{formatScore(a.score)}</span>
            <span className="text-[12px] text-faint">/100</span>
          </p>
        </div>
        <p className="mt-2.5 text-[13px] leading-relaxed text-ink">{a.headline}</p>
        <CropHealthAction bounds={area.bounds} />
        <div className="mt-2.5 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[11px] text-muted">
          <span>
            Confidence <strong className="font-semibold text-ink">{a.confidence.level}</strong>
          </span>
          <span className="inline-flex items-center gap-1.5">
            Data completeness <CompletenessBar fraction={a.confidence.data_completeness} />
          </span>
          <span>As of {formatTime(a.as_of)}</span>
        </div>
        <div className="mt-3">
          <PlaceholderNotice note={detail.thresholds_note} />
        </div>
      </Block>

      <Block title="Score breakdown">
        <ScoreBar factors={a.factors} score={a.score} />
        <ul className="mt-3 flex flex-col gap-2.5">
          {FACTORS.map((id) => {
            const f = factor(id);
            return f ? <FactorRow key={id} factor={f} /> : null;
          })}
        </ul>
      </Block>

      <Block title="Why">
        <ul className="flex list-disc flex-col gap-1.5 pl-4 text-[12px] leading-relaxed text-ink marker:text-faint">
          {a.reasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      </Block>

      <Block title="Vegetation (NDVI) vs the same dates in earlier years">
        <NdviSection anomaly={ndvi?.details.anomaly} factor={ndvi} />
      </Block>

      <Block title="Weather">
        <WeatherSection factor={weather} />
      </Block>

      <Block title="Pest-favourable weather, day by day">
        {a.pests.length ? (
          <div className="flex flex-col gap-4">
            {a.pests.map((pest) => (
              <PestRow key={pest.pest_id} pest={pest} />
            ))}
            <DayLegend />
          </div>
        ) : (
          <Unavailable>No pest indicators: {weather?.unavailable_reason ?? "weather unavailable"}.</Unavailable>
        )}
      </Block>

      <Block title="Recent pest reports">
        <ReportsSection factor={reports} label={detail.sample_label} />
      </Block>

      <Block title="Data sources">
        <ul className="flex flex-col gap-2.5">
          {a.provenance.map((p, i) => (
            <li key={`${p.source}-${p.covers}-${i}`} className="text-[11px] leading-relaxed">
              <p className="flex items-start gap-1.5">
                <StateChip state={p.state} />
                <span className="font-medium text-ink">{p.source}</span>
              </p>
              <p className="text-muted">
                {p.covers && <>Covers {p.covers}. </>}
                {p.retrieved_at && <>Fetched {formatTime(p.retrieved_at)}. </>}
                {p.note}
              </p>
              {p.licence && <p className="text-faint">{p.licence}</p>}
            </li>
          ))}
        </ul>
      </Block>

      <Block title="Area">
        <p className="flex flex-wrap items-center gap-1.5 text-[12px] text-ink">
          {area.kind === "demo" && <DemoTag />}
          {detail.boundary_note}
        </p>
        {a.district_context?.district && (
          <p className="mt-1.5 text-[11px] text-muted">
            District: {a.district_context.district}
            {a.district_context.state ? `, ${a.district_context.state}` : ""}.{" "}
            {a.district_context.note ?? `Source: ${a.district_context.source}.`}
          </p>
        )}
      </Block>

      <Block>
        <p className="text-[11px] leading-relaxed text-muted">{a.disclaimer}</p>
        <p className="mt-1.5 text-[11px] leading-relaxed text-faint">{a.confidence.method}</p>
      </Block>
    </>
  );
}

/** Supporting satellite evidence for the zone: the existing Phase 1 crop-health flow (Sentinel-2 NDVI,
 *  cloud-masked), run on the zone's rectangle. Its result is separate from the risk score above. */
function CropHealthAction({ bounds }: { bounds: [number, number, number, number] }) {
  const select = useAgriStore((s) => s.select);
  const pending = useAppStore((s) => s.pending);
  const run = () => {
    const [west, south, east, north] = bounds;
    const feature: GeoJSON.Feature = {
      type: "Feature",
      properties: {},
      geometry: { type: "Polygon", coordinates: [[[west, south], [east, south], [east, north], [west, north], [west, south]]] },
    };
    useAppStore.getState().setAoi({ feature, bounds });
    select(null); // the drawer makes room for the crop-health result card
    void useAppStore.getState().runAnalysis("How healthy is the crop here?");
  };
  return (
    <div className="mt-3 flex flex-col gap-1">
      <Button variant="outline" size="sm" onClick={run} disabled={pending} className="self-start">
        <Satellite className="h-3.5 w-3.5" strokeWidth={2} /> Check crop health here · Sentinel-2
      </Button>
      <p className="text-[11px] leading-relaxed text-faint">
        Satellite evidence (NDVI from Sentinel-2, cloud-masked) for this zone's rectangle. It is separate from the
        risk score.
      </p>
    </div>
  );
}

function Block({ title, children }: { title?: string; children: ReactNode }) {
  return (
    <section className="border-b border-line px-4 py-3.5 last:border-b-0">
      {title && <h3 className="mb-2.5 text-[11px] font-semibold tracking-wide text-muted uppercase">{title}</h3>}
      {children}
    </section>
  );
}

function Unavailable({ children }: { children: ReactNode }) {
  return <p className="text-[12px] leading-relaxed text-muted">{children}</p>;
}

/** The score as the sum of its factor points (computed by the engine), on a 0-100 track. */
function ScoreBar({ factors, score }: { factors: FactorResult[]; score: number | null }) {
  const points = Object.fromEntries(factors.map((f) => [f.id, f.points])) as Record<FactorResult["id"], number | null>;
  const segments = scoreSegments(points);
  return (
    <div>
      <div
        className="flex h-3 w-full gap-[2px] overflow-hidden rounded-[4px] bg-sunken"
        role="img"
        aria-label={`Score ${formatScore(score)} of 100: ${segments.map((s) => `${FACTOR_LABEL[s.id]} ${s.points}`).join(", ")}`}
      >
        {segments.map((s) => (
          <span
            key={s.id}
            title={`${FACTOR_LABEL[s.id]}: ${s.points} points`}
            className="h-full first:rounded-l-[4px] last:rounded-r-[4px]"
            style={{ width: `${s.points}%`, background: FACTOR_COLOR_VAR[s.id] }}
          />
        ))}
      </div>
      <div className="mt-1 flex justify-between text-[10px] text-faint tabular-nums">
        <span>0</span>
        <span>100</span>
      </div>
    </div>
  );
}

function FactorRow({ factor: f }: { factor: FactorResult }) {
  return (
    <li className="text-[12px] leading-relaxed">
      <p className="flex items-center gap-2">
        <span aria-hidden="true" className="h-2.5 w-2.5 shrink-0 rounded-[3px]" style={{ background: FACTOR_COLOR_VAR[f.id] }} />
        <span className="font-medium text-ink">{FACTOR_LABEL[f.id]}</span>
        <span className="ml-auto text-ink tabular-nums">
          {f.points === null ? "not scored" : `${f.points} pts`}
        </span>
      </p>
      <p className="pl-[18px] text-[11px] text-muted">
        {f.status === "unavailable" ? (
          <>Unavailable: {f.unavailable_reason}. Left out of the score, not estimated.</>
        ) : (
          <>
            {f.summary}. Weight {f.weight}
            {f.status === "partial" && <>; partly available ({formatPercent(f.availability)})</>}.
          </>
        )}
      </p>
      {f.sample_data && (
        <p className="mt-1 pl-[18px]">
          <SampleLabel />
        </p>
      )}
    </li>
  );
}

function NdviSection({ anomaly, factor }: { anomaly?: NdviAnomaly; factor?: FactorResult }) {
  if (!anomaly) return <Unavailable>Unavailable: {factor?.unavailable_reason ?? "no NDVI data"}.</Unavailable>;
  const windows = [anomaly.current, ...anomaly.baseline];
  return (
    <div className="flex flex-col gap-2">
      <ul className="flex flex-col gap-1.5" aria-label="Mean NDVI per window">
        {windows.map((w) => (
          <li key={w.label} className="grid grid-cols-[72px_1fr_40px] items-center gap-2 text-[11px]">
            <span className={cx(w.label === "current" ? "font-semibold text-ink" : "text-muted")}>
              {w.label === "current" ? "Last 30 days" : w.label}
            </span>
            <span className="relative h-2.5 rounded-[3px] bg-sunken">
              {w.usable && w.mean !== null && (
                <span
                  className="absolute inset-y-0 left-0 rounded-[3px]"
                  style={{
                    width: `${Math.max(0, Math.min(1, w.mean)) * 100}%`,
                    background: w.label === "current" ? FACTOR_COLOR_VAR.ndvi_anomaly : "rgb(var(--text-faint))",
                  }}
                />
              )}
            </span>
            <span className="text-right text-ink tabular-nums">{w.usable ? formatNumber(w.mean) : "n/a"}</span>
            {!w.usable && <span className="col-span-3 -mt-1 text-[10px] text-muted">{w.reason}</span>}
          </li>
        ))}
      </ul>
      <p className="text-[11px] leading-relaxed text-muted">
        {anomaly.relative_change !== null ? (
          <>
            Change vs the {formatNumber(anomaly.baseline_mean)} baseline:{" "}
            <strong className="font-semibold text-ink">
              {anomaly.relative_change > 0 ? "+" : ""}
              {formatPercent(anomaly.relative_change, 1)}
            </strong>
            {anomaly.within_baseline_range !== null &&
              (anomaly.within_baseline_range ? ", within" : ", outside") + " the range of earlier years"}
            . {formatPercent(anomaly.current.observed_fraction)} of the area was observed clear.
          </>
        ) : (
          <>No comparison: {factor?.unavailable_reason}.</>
        )}
      </p>
      <p className="text-[10px] leading-relaxed text-faint">{anomaly.method}</p>
    </div>
  );
}

function WeatherSection({ factor }: { factor?: FactorResult }) {
  const summary = factor?.details.weather_summary;
  if (!summary) return <Unavailable>Unavailable: {factor?.unavailable_reason ?? "no weather data"}.</Unavailable>;
  const rows: [string, (w: WeatherFigures) => string][] = [
    ["Mean temperature", (w) => (w.mean_temperature_c === null ? "–" : `${w.mean_temperature_c} °C`)],
    ["Min – max", (w) => (w.min_temperature_c === null ? "–" : `${w.min_temperature_c} – ${w.max_temperature_c} °C`)],
    ["Mean humidity", (w) => (w.mean_relative_humidity_pct === null ? "–" : `${w.mean_relative_humidity_pct}%`)],
    ["Hours RH ≥ 90%", (w) => String(w.hours_rh_at_or_above_90)],
    ["Rain", (w) => (w.precipitation_mm === null ? "–" : `${w.precipitation_mm} mm`)],
  ];
  const point = factor?.details.point;
  return (
    <div>
      <table className="w-full text-[11px]">
        <thead>
          <tr className="text-faint">
            <th className="pb-1 text-left font-normal" />
            <th className="pb-1 text-right font-normal">Last 7 days</th>
            <th className="pb-1 text-right font-normal">Next 7 days</th>
          </tr>
        </thead>
        <tbody className="tabular-nums">
          {rows.map(([label, value]) => (
            <tr key={label} className="border-t border-line">
              <td className="py-1 text-muted">{label}</td>
              <td className="py-1 text-right text-ink">{value(summary.past_7_days)}</td>
              <td className="py-1 text-right text-ink">{value(summary.next_7_days)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-2 text-[10px] leading-relaxed text-faint">
        Weather model data for one point
        {point ? ` (${point.latitude.toFixed(3)}, ${point.longitude.toFixed(3)})` : ""}: the past days are model
        analyses, not station observations.
      </p>
    </div>
  );
}

function PestRow({ pest }: { pest: PestEvaluation }) {
  return (
    <div>
      <p className="flex items-center gap-2 text-[12px]">
        <span className="font-medium text-ink">{pest.name}</span>
        {pest.thresholds === "PLACEHOLDER" && (
          <span className="rounded-[4px] border border-warn/50 px-1 text-[10px] font-semibold text-warn">PLACEHOLDER</span>
        )}
        <span className="ml-auto text-[11px] text-muted tabular-nums">
          index {pest.index === null ? "n/a" : pest.index.toFixed(2)}
        </span>
      </p>
      <DayStrip days={pest.days} />
      <p className="mt-1 text-[11px] leading-relaxed text-muted">{pest.conditions.join("; ")}</p>
    </div>
  );
}

function dayTitle(day: DayCheck): string {
  const state = day.favourable === null ? "not enough data" : day.favourable ? "favourable" : "not favourable";
  const values = Object.entries(day.values).map(([label, value]) => `${label}: ${value}`).join("; ");
  return `${day.date} (${day.period}): ${state}${values ? ` — ${values}` : ""}`;
}

function DayStrip({ days }: { days: DayCheck[] }) {
  const firstForecast = days.findIndex((d) => d.period === "forecast");
  return (
    <div className="mt-1.5 flex items-end gap-[3px]" role="list" aria-label="Days checked">
      {days.map((day, i) => (
        <div key={day.date} role="listitem" className={cx("flex flex-col items-center", i === firstForecast && "ml-2")}>
          <span
            title={dayTitle(day)}
            aria-label={dayTitle(day)}
            className={cx(
              "flex h-5 w-5 items-center justify-center rounded-[4px] border text-[9px] font-semibold",
              day.favourable === null && "border-dashed border-line-strong text-faint",
              day.favourable === false && "border-line-strong bg-surface",
              day.favourable === true && "border-transparent",
            )}
            // Dark ink on the serious step (about 8:1); white would fall below 3:1.
            style={day.favourable === true ? { background: LEVEL_COLOR.HIGH, color: "#0b0b0b" } : undefined}
          >
            {day.favourable === null ? "?" : day.favourable ? "✓" : ""}
          </span>
          <span className="mt-0.5 text-[9px] text-faint tabular-nums">{day.date.slice(8)}</span>
        </div>
      ))}
    </div>
  );
}

function DayLegend() {
  return (
    <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-muted">
      <span className="inline-flex items-center gap-1">
        <span className="h-3 w-3 rounded-[3px]" style={{ background: LEVEL_COLOR.HIGH }} /> favourable for the pest
      </span>
      <span className="inline-flex items-center gap-1">
        <span className="h-3 w-3 rounded-[3px] border border-line-strong" /> not favourable
      </span>
      <span className="inline-flex items-center gap-1">
        <span className="h-3 w-3 rounded-[3px] border border-dashed border-line-strong" /> not enough data
      </span>
      <span>Last 7 days, then the forecast from today. Hover a day for its values.</span>
    </p>
  );
}

function ReportsSection({ factor, label }: { factor?: FactorResult; label: string }) {
  if (!factor || factor.status === "unavailable") {
    return <Unavailable>Unavailable: {factor?.unavailable_reason ?? "no report source"}.</Unavailable>;
  }
  const reports: PestReport[] = factor.details.reports ?? [];
  return (
    <div className="flex flex-col gap-2">
      {factor.sample_data && (
        <p className="flex flex-wrap items-center gap-1.5 text-[11px] text-muted">
          <SampleLabel text={label} /> Synthetic reports, not real field observations.
        </p>
      )}
      <p className="text-[12px] text-ink">{factor.summary}.</p>
      {reports.length > 0 && (
        <ul className="flex flex-col divide-y divide-line text-[11px]">
          {reports.map((r) => (
            <li key={r.id} className="flex items-center gap-2 py-1">
              <span className="w-[74px] shrink-0 text-muted tabular-nums">{r.observed_on}</span>
              <span className="flex-1 text-ink capitalize">{pestName(r.pest)}</span>
              <span className="text-muted">{r.severity ?? "not scored"}</span>
              <span className="rounded-[4px] border border-warn/50 px-1 text-[9px] font-semibold text-warn">
                {r.status === "REAL" ? "REAL" : "SAMPLE"}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
