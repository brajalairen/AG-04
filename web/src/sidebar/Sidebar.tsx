/** Left sidebar, one panel that widens rather than a separate rail-plus-popover: collapsed it is a
 *  narrow icon rail with the everyday actions; expanded it becomes a single wider panel whose own
 *  nav list (every section, labelled) stays visible above whichever section's content is open, so
 *  switching sections never means losing sight of the others. Nothing advanced is reachable until
 *  the user asks for it. */

import { CircleHelp, Layers, ListOrdered, MapPin, Search, Bookmark, SlidersHorizontal, X } from "lucide-react";
import { useAppStore, type SidebarSection } from "../state/useAppStore";
import { cx, IconButton, Surface } from "../ui/primitives";
import { SearchPanel } from "./SearchPanel";
import { AreaSelectionTools } from "./AreaSelectionTools";
import { LayersPanel } from "./LayersPanel";
import { SavedAreas } from "./SavedAreas";
import { HelpPanel } from "./HelpPanel";
import { PriorityPanel } from "../agri/PriorityPanel";

const ITEMS: { id: Exclude<SidebarSection, null>; label: string; icon: typeof Search }[] = [
  { id: "priority", label: "Priority areas (crop & pest risk)", icon: ListOrdered },
  { id: "search", label: "Search location", icon: Search },
  { id: "select", label: "Select area", icon: MapPin },
  { id: "layers", label: "Images and imagery settings", icon: Layers },
  { id: "saved", label: "Saved areas", icon: Bookmark },
];

const TITLES: Record<Exclude<SidebarSection, null>, string> = {
  priority: "Priority areas",
  search: "Search location",
  select: "Select area",
  layers: "Images",
  saved: "Saved areas",
  help: "Help",
};

export function Sidebar() {
  const open = useAppStore((s) => s.sidebarOpen);
  const section = useAppStore((s) => s.section);
  const openSection = useAppStore((s) => s.openSection);
  const closeSidebar = useAppStore((s) => s.closeSidebar);
  const layerCount = useAppStore((s) => s.layers.length);

  return (
    // Starts 64 px down (56 px on small screens) to leave room for the LouNgak AI wordmark above it
    // (ui/BrandMark.tsx), which is sized and placed to fit that space.
    <div className="pointer-events-none absolute top-16 bottom-4 left-4 z-30 flex items-start max-sm:top-14">
      {open && section ? (
        // Expanded: one panel. Its own nav list (every section, labelled) stays visible above the
        // active section's content, so switching sections never hides the others.
        <Surface
          raised
          className={cx(
            "pointer-events-auto flex max-h-full w-[320px] flex-col overflow-hidden",
            "max-sm:fixed max-sm:inset-x-4 max-sm:top-4 max-sm:bottom-24 max-sm:w-auto",
          )}
        >
          <header className="flex shrink-0 items-center justify-between px-3 py-2.5">
            <span className="px-1 text-[13px] font-semibold text-ink">LouNgak AI</span>
            <IconButton label="Collapse sidebar" side="left" onClick={closeSidebar} className="h-7 w-7">
              <X className="h-4 w-4" strokeWidth={2} />
            </IconButton>
          </header>
          <nav aria-label="Sidebar sections" className="shrink-0 px-1.5 pb-1.5">
            {ITEMS.map((item) => (
              <NavRow key={item.id} icon={item.icon} label={TITLES[item.id]} active={section === item.id}
                     badge={item.id === "layers" ? layerCount : 0} onClick={() => openSection(item.id)} />
            ))}
          </nav>
          <span className="mx-3 h-px shrink-0 bg-line" />
          <NavRow icon={CircleHelp} label="Help" active={section === "help"}
                 onClick={() => openSection("help")} className="mx-1.5 mt-1.5 shrink-0" />
          <div className="mt-1 min-h-0 flex-1 overflow-y-auto overscroll-contain border-t border-line">
            <h2 className="px-4 pt-3 pb-1 text-[11px] font-semibold tracking-wide text-muted uppercase">{TITLES[section]}</h2>
            {section === "priority" && <PriorityPanel />}
            {section === "search" && <SearchPanel />}
            {section === "select" && <AreaSelectionTools />}
            {section === "layers" && <LayersPanel />}
            {section === "saved" && <SavedAreas />}
            {section === "help" && <HelpPanel />}
          </div>
        </Surface>
      ) : (
        // Collapsed: the narrow icon rail, the entry point to everything else.
        <Surface className="pointer-events-auto flex flex-col gap-1 p-1.5">
          {ITEMS.map((item) => (
            <div key={item.id} className="relative">
              <IconButton label={item.label} onClick={() => openSection(item.id)}>
                <item.icon className="h-[18px] w-[18px]" strokeWidth={1.75} />
              </IconButton>
              {item.id === "layers" && layerCount > 0 && (
                <span
                  aria-hidden="true"
                  className="pointer-events-none absolute top-1 right-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-accent px-1 text-[10px] font-semibold text-accent-ink"
                >
                  {layerCount}
                </span>
              )}
            </div>
          ))}
          <span className="mx-1.5 my-0.5 h-px bg-line" />
          <IconButton label="Help" onClick={() => openSection("help")}>
            <CircleHelp className="h-[18px] w-[18px]" strokeWidth={1.75} />
          </IconButton>
        </Surface>
      )}
    </div>
  );
}

/** One labelled row of the expanded panel's nav list: the same sections the collapsed rail shows as
 *  icons alone, now with text, so every section stays visible and reachable while one is open. */
function NavRow({ icon: Icon, label, active, badge, onClick, className }: {
  icon: typeof Search;
  label: string;
  active: boolean;
  badge?: number;
  onClick: () => void;
  className?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-current={active ? "true" : undefined}
      className={cx(
        "flex w-full items-center gap-2.5 rounded-[var(--radius-sm)] px-2.5 py-2 text-left text-[13px] font-medium transition-colors",
        active ? "bg-accent-soft text-accent" : "text-ink hover:bg-hover",
        className,
      )}
    >
      <Icon className="h-[18px] w-[18px] shrink-0" strokeWidth={1.75} />
      <span className="min-w-0 flex-1 truncate">{label}</span>
      {!!badge && (
        <span
          aria-hidden="true"
          className="flex h-4 min-w-4 shrink-0 items-center justify-center rounded-full bg-accent px-1 text-[10px] font-semibold text-accent-ink"
        >
          {badge}
        </span>
      )}
    </button>
  );
}

/** Shared empty state, so every panel says what to do next in the same voice. */
export function EmptyState({ icon: Icon, children }: { icon: typeof SlidersHorizontal; children: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-2 px-6 py-10 text-center">
      <Icon className="h-5 w-5 text-faint" strokeWidth={1.5} />
      <p className="text-[12px] leading-relaxed text-muted">{children}</p>
    </div>
  );
}
