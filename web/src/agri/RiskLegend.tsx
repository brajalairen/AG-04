/** Map legend: what the fills, outlines and numbers on the risk map mean. */

import { Surface } from "../ui/primitives";
import { LEVEL_COLOR, LEVEL_LABEL, LEVELS } from "./format";
import { useAgriStore } from "./useAgriStore";

export function RiskLegend() {
  const overview = useAgriStore((s) => s.overview);
  if (!overview?.areas.length) return null;
  return (
    <Surface className="w-[208px] px-3 py-2.5 text-[11px] max-sm:hidden" aria-label="Risk map legend">
      <p className="mb-1.5 font-semibold text-ink">Estimated risk level</p>
      <ul className="flex flex-col gap-1">
        {LEVELS.map((level) => (
          <li key={level} className="flex items-center gap-2 text-muted">
            <span
              aria-hidden="true"
              className="h-3 w-4 rounded-[3px] border border-line"
              style={{ background: LEVEL_COLOR[level], opacity: 0.75 }}
            />
            {LEVEL_LABEL[level]}
          </li>
        ))}
      </ul>
      <ul className="mt-2 flex flex-col gap-1 border-t border-line pt-2 text-muted">
        <li className="flex items-center gap-2">
          <span aria-hidden="true" className="h-0 w-4 border-t-2 border-dashed border-ink" />
          Demo area, not a boundary
        </li>
        <li className="flex items-center gap-2">
          <span aria-hidden="true" className="h-0 w-4 border-t-2 border-solid border-ink" />
          {overview.official_boundaries ? "District boundary" : "District boundary (none loaded)"}
        </li>
        <li className="flex items-center gap-2">
          <span className="rounded-full border border-line px-1 text-[10px] font-semibold text-ink">#1</span>
          Priority rank
        </li>
      </ul>
      {overview.thresholds_status === "PLACEHOLDER" && (
        <p className="mt-2 border-t border-line pt-2 font-semibold text-warn">PLACEHOLDER thresholds</p>
      )}
    </Surface>
  );
}
