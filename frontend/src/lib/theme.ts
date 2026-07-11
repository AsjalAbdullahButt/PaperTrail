"use client";

// Shared PaperTrail theme tokens + a persistence hook. The token values match
// the design system exactly (previously inline in page.tsx). Persisted to
// localStorage and synced across tabs (Phase 9.3).

import { useEffect, useState } from "react";

export type ThemeName = "dark" | "light";
export type ThemeVars = Record<string, string>;

export const THEMES: Record<ThemeName, ThemeVars> = {
  dark: {
    "--bg": "radial-gradient(1200px 800px at 20% 0%, #14161d 0%, #0a0b0f 55%, #08090c 100%)",
    "--text": "#f3f4f7",
    "--muted": "rgba(243,244,247,.55)",
    "--onAccent": "#08130f",
    "--card-bg": "rgba(255,255,255,.045)",
    "--card-border": "rgba(255,255,255,.10)",
    "--seg-bg": "rgba(255,255,255,.05)",
    "--doc-bg": "rgba(255,255,255,.05)",
    "--accent": "#34d399",
    "--accent2": "#a78bfa",
    "--accentGlow": "rgba(52,211,153,.28)",
    "--chip-bg": "rgba(52,211,153,.13)",
    "--chip-border": "rgba(52,211,153,.30)",
    "--blob1": "#10b981",
    "--blob2": "#8b5cf6",
    "--blob3": "#22d3ee",
    "--blobOp": ".22",
    "--blobOp3": ".12",
    "--cardShadow": "rgba(0,0,0,.5)",
    "--sel": "rgba(52,211,153,.3)",
    // Near-opaque (unlike --card-bg) so floating menus/tooltips stay legible
    // over whatever they overlap even where backdrop-filter isn't rendered.
    "--menu-bg": "rgba(17,19,25,.98)",
  },
  light: {
    "--bg": "radial-gradient(1200px 800px at 15% -5%, #ffffff 0%, #f4f5f2 55%, #eef0ec 100%)",
    "--text": "#171a20",
    "--muted": "rgba(23,26,32,.55)",
    "--onAccent": "#ffffff",
    "--card-bg": "rgba(255,255,255,.58)",
    "--card-border": "rgba(20,25,35,.09)",
    "--seg-bg": "rgba(20,25,35,.05)",
    "--doc-bg": "rgba(255,255,255,.7)",
    "--accent": "#0d9488",
    "--accent2": "#4f46e5",
    "--accentGlow": "rgba(13,148,136,.22)",
    "--chip-bg": "rgba(13,148,136,.11)",
    "--chip-border": "rgba(13,148,136,.28)",
    "--blob1": "#2dd4bf",
    "--blob2": "#6366f1",
    "--blob3": "#5eead4",
    "--blobOp": ".30",
    "--blobOp3": ".20",
    "--cardShadow": "rgba(30,40,60,.12)",
    "--sel": "rgba(13,148,136,.2)",
    "--menu-bg": "rgba(255,255,255,.98)",
  },
};

const THEME_KEY = "papertrail_theme";

export function useTheme(): [ThemeName, (t: ThemeName) => void] {
  const [theme, setThemeState] = useState<ThemeName>("dark");

  // Read persisted preference after mount (avoids SSR hydration mismatch) —
  // localStorage is a browser-only external system, unreadable during render,
  // so this genuinely needs an effect rather than the render-phase "adjusting
  // state" pattern used elsewhere in the app.
  useEffect(() => {
    const saved = window.localStorage.getItem(THEME_KEY);
    // eslint-disable-next-line react-hooks/set-state-in-effect -- syncing from localStorage, not derivable during render (see comment above)
    if (saved === "dark" || saved === "light") setThemeState(saved);
    const onStorage = (e: StorageEvent) => {
      if (e.key === THEME_KEY && (e.newValue === "dark" || e.newValue === "light")) {
        setThemeState(e.newValue);
      }
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  const setTheme = (t: ThemeName) => {
    setThemeState(t);
    window.localStorage.setItem(THEME_KEY, t);
  };
  return [theme, setTheme];
}
