/** Layers: the base map, plus the AG-04 map layers. Presentation only: hiding a layer never changes a
 *  figure, and the analysis never sees the base map. Replaces the basemap-only picker.
 *
 *  Only layers backed by data are offered. District outlines stay disabled, with the reason, until
 *  verified boundaries are loaded; there is no block layer until verified block data exists. */

import { useCallback, useState, type ReactNode } from "react";
import { Layers } from "lucide-react";
import { BASEMAPS } from "../map/basemap";
import { useAppStore } from "../state/useAppStore";
import { cx, IconButton, MenuItem, Popover, Surface } from "../ui/primitives";
import { useAgriStore } from "./useAgriStore";

export function MapLayersControl() {
  const basemap = useAppStore((s) => s.basemap);
  const setBasemap = useAppStore((s) => s.setBasemap);
  const layers = useAgriStore((s) => s.layers);
  const toggleLayer = useAgriStore((s) => s.toggleLayer);
  const districtOutlines = useAgriStore((s) => s.overview?.districts.some((d) => d.has_boundary) ?? false);
  const [open, setOpen] = useState(false);
  const close = useCallback(() => setOpen(false), []);

  return (
    <div className="relative">
      <Surface className="overflow-hidden p-0">
        <IconButton
          label="Layers"
          side="left"
          active={open}
          showTooltip={!open}
          aria-haspopup="menu"
          aria-expanded={open}
          // Keeps the press that toggles the menu from also counting as an outside press that closes it.
          onPointerDown={(event) => open && event.stopPropagation()}
          onClick={() => setOpen((value) => !value)}
          className="rounded-none"
        >
          <Layers className="h-4 w-4" strokeWidth={2} />
        </IconButton>
      </Surface>

      {/* Opens upward and to the left: below the button there is only the zoom control and the screen edge. */}
      <Popover open={open} onClose={close} className="right-full bottom-0 mr-2 w-60">
        <div role="menu" aria-label="Layers">
          <Heading>Base map</Heading>
          {BASEMAPS.map((option) => (
            <MenuItem
              key={option.id}
              checked={option.id === basemap}
              icon={<Radio selected={option.id === basemap} />}
              onClick={() => setBasemap(option.id)}
            >
              {option.label}
            </MenuItem>
          ))}

          <Heading divider>Administrative</Heading>
          <Check
            label="District boundaries"
            checked={districtOutlines && layers.districts}
            disabled={!districtOutlines}
            note="Not loaded yet: pending verified boundary data"
            onToggle={() => toggleLayer("districts")}
          />

          <Heading divider>Risk &amp; monitoring</Heading>
          <Check label="Monitoring zones" checked={layers.zones} onToggle={() => toggleLayer("zones")} />
          <Check label="Priority markers (#1, #2…)" checked={layers.ranks} onToggle={() => toggleLayer("ranks")} />

          <p className="mt-1 border-t border-line px-3 pt-2 pb-1 text-[10px] leading-relaxed text-faint">
            Display only. Risk is scored per monitored agricultural zone; districts are context and are never coloured
            by risk.
          </p>
        </div>
      </Popover>
    </div>
  );
}

function Heading({ children, divider }: { children: ReactNode; divider?: boolean }) {
  return (
    <p
      className={cx(
        "px-3 pt-1.5 pb-1 text-[11px] font-semibold tracking-wide text-muted uppercase",
        divider && "mt-1 border-t border-line pt-2",
      )}
    >
      {children}
    </p>
  );
}

function Check({
  label,
  checked,
  disabled,
  note,
  onToggle,
}: {
  label: string;
  checked: boolean;
  disabled?: boolean;
  note?: string;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      role="menuitemcheckbox"
      aria-checked={checked}
      disabled={disabled}
      onClick={onToggle}
      title={disabled ? note : undefined}
      className={cx(
        "flex w-full items-start gap-2.5 px-3 py-2 text-left text-[13px] transition-colors",
        disabled ? "cursor-not-allowed text-faint" : "text-ink hover:bg-hover",
      )}
    >
      <span
        aria-hidden="true"
        className={cx(
          "mt-0.5 flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-[3px] border",
          checked ? "border-accent bg-accent" : "border-line-strong",
        )}
      >
        {checked && <span className="h-1.5 w-1.5 rounded-[1px] bg-accent-ink" />}
      </span>
      <span className="flex-1">
        {label}
        {disabled && note && <span className="block text-[10px] text-faint">{note}</span>}
      </span>
    </button>
  );
}

function Radio({ selected }: { selected: boolean }) {
  return (
    <span
      aria-hidden="true"
      className={cx(
        "flex h-3.5 w-3.5 items-center justify-center rounded-full border",
        selected ? "border-accent" : "border-line",
      )}
    >
      {selected && <span className="h-1.5 w-1.5 rounded-full bg-accent" />}
    </span>
  );
}
