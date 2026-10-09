/** The LouNgak AI wordmark, top-left, directly above the sidebar's control rail.
 *
 *  Plain text, not an image: white ink on dark maps, dark ink on light ones. Only the Standard
 *  basemap in light mode is a light map; Satellite, Hybrid and everything in dark mode get the white
 *  variant. It switches the moment the theme or basemap changes. The dark variant's colour is the
 *  app's own light-theme ink (--text in index.css), not a new colour; white is plain white. Neither
 *  depends on the app's current theme class, because a dark basemap (Satellite, Hybrid) needs white
 *  ink even while the app chrome itself is in light theme.
 *
 *  It floats above the map, not in it, so panning, zooming and basemap changes never move it. It
 *  takes no pointer events, so the map and area drawing work underneath it. It shares the rail's
 *  layer (z-30) and is rendered before the sidebar, so a panel that opens over it covers it. */

import type { BasemapId } from "../map/basemap";
import { useAppStore } from "../state/useAppStore";

const VARIANT_CLASS = { white: "text-white", dark: "text-[rgb(24,26,31)]" };

export type LogoVariant = keyof typeof VARIANT_CLASS;

/** Dark ink where the map is light (Standard in light mode); white ink everywhere else. */
export function logoVariant(basemap: BasemapId, theme: "light" | "dark"): LogoVariant {
  return basemap === "standard" && theme === "light" ? "dark" : "white";
}

export function BrandMark() {
  const variant = useAppStore((s) => logoVariant(s.basemap, s.theme));
  return (
    <div
      // Centred on the top control row (same top-6 the image wordmark used), with a small gap above
      // the toolbar, which stays where it is (Sidebar.tsx).
      className="pointer-events-none absolute top-6 left-4 z-30 flex h-7 items-center select-none max-sm:h-6"
      data-variant={variant}
    >
      <span className={`text-[20px] leading-none font-semibold tracking-tight max-sm:text-[17px] ${VARIANT_CLASS[variant]}`}>
        LouNgak AI
      </span>
    </div>
  );
}
