/** Always visible at the top of the map: what this dashboard is, and that it is a prototype whose
 *  thresholds are placeholders and whose pest reports are SAMPLE data. Never hidden while true. */

import { AlertTriangle } from "lucide-react";
import { Surface } from "../ui/primitives";
import { useAgriStore } from "./useAgriStore";

export function StatusStrip() {
  const overview = useAgriStore((s) => s.overview);
  const placeholder = overview ? overview.thresholds_status === "PLACEHOLDER" : true;
  const sample = overview?.includes_sample_data ?? true;
  return (
    <div className="pointer-events-none absolute inset-x-0 top-4 z-20 flex justify-center px-4 max-md:hidden">
      <Surface className="pointer-events-auto flex items-center gap-2 px-3 py-1.5 text-[12px]">
        <span className="font-semibold text-ink">Crop &amp; Pest Risk Monitoring · {overview?.region ?? "Manipur"}</span>
        {(placeholder || sample) && (
          <span className="flex items-center gap-1 border-l border-line pl-2 font-medium text-warn">
            <AlertTriangle className="h-3.5 w-3.5" strokeWidth={2} aria-hidden="true" />
            Prototype
            {placeholder && " · PLACEHOLDER thresholds"}
            {sample && " · SAMPLE pest reports"}
          </span>
        )}
      </Surface>
    </div>
  );
}
