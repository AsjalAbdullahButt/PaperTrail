"use client";

// PaperTrail colour tokens (one source of truth, see frontend/DESIGN.md) plus
// the theme persistence hook. Colours and shadows live here because they
// change with the theme; spacing, radius, type and motion tokens are theme
// independent and live in app/globals.css. Persisted to localStorage and
// synced across tabs.
//
// One solid accent (teal) carries primary actions, active tabs, links, the
// focus ring and meters. There are no gradients, glows or colour blobs.
// Every text/background pair below is measured for WCAG AA (4.5:1) in
// DESIGN.md.

import { useEffect, useState } from "react";

export type ThemeName = "dark" | "light";
export type ThemeVars = Record<string, string>;

export const THEMES: Record<ThemeName, ThemeVars> = {
  dark: {
    // Surfaces: a neutral ramp, flat. Depth comes from a step in tone plus a hairline.
    "--bg": "#111215",
    "--surface": "#181a1e",
    "--raised": "#1f2227",
    // Floating layers (menus, modals, drawers, toasts) are opaque.
    "--overlay": "#1f2227",
    "--scrim": "rgba(0,0,0,.55)",
    "--border": "rgba(236,236,233,.10)",
    "--border-strong": "rgba(236,236,233,.20)",
    // Text: three roles.
    "--text": "#ecece9",
    "--text-2": "#a9acb2",
    "--muted": "#8f939b",
    // The one accent.
    "--accent": "#2dd4bf",
    "--accent-hover": "#5eead4",
    "--on-accent": "#0b1f1c",
    "--accent-soft": "rgba(45,212,191,.12)",
    "--accent-line": "rgba(45,212,191,.32)",
    // Status colours carry meaning only (error, caution, success).
    "--danger": "#ff8f86",
    "--danger-soft": "rgba(255,143,134,.10)",
    "--danger-line": "rgba(255,143,134,.35)",
    "--warn": "#e8b84f",
    "--warn-soft": "rgba(232,184,79,.10)",
    "--warn-line": "rgba(232,184,79,.35)",
    "--ok": "#5fd08a",
    "--ok-soft": "rgba(95,208,138,.10)",
    "--ok-line": "rgba(95,208,138,.35)",
    // Interaction.
    "--ring": "#2dd4bf",
    "--selection": "rgba(45,212,191,.28)",
    "--scrollbar": "rgba(236,236,233,.16)",
    "--scrollbar-hover": "rgba(236,236,233,.28)",
    // One shadow, for floating layers only. Cards have none.
    "--shadow-overlay": "0 8px 32px rgba(0,0,0,.5)",
  },
  light: {
    "--bg": "#f6f5f1",
    "--surface": "#ffffff",
    "--raised": "#efeee9",
    "--overlay": "#ffffff",
    "--scrim": "rgba(27,29,33,.40)",
    "--border": "rgba(27,29,33,.12)",
    "--border-strong": "rgba(27,29,33,.24)",
    "--text": "#1b1d21",
    "--text-2": "#484c53",
    "--muted": "#5c616a",
    "--accent": "#0d6b64",
    "--accent-hover": "#0a524d",
    "--on-accent": "#ffffff",
    "--accent-soft": "rgba(13,107,100,.08)",
    "--accent-line": "rgba(13,107,100,.30)",
    "--danger": "#b3261e",
    "--danger-soft": "rgba(179,38,30,.07)",
    "--danger-line": "rgba(179,38,30,.30)",
    "--warn": "#8a5a00",
    "--warn-soft": "rgba(138,90,0,.08)",
    "--warn-line": "rgba(138,90,0,.30)",
    "--ok": "#25704a",
    "--ok-soft": "rgba(37,112,74,.08)",
    "--ok-line": "rgba(37,112,74,.30)",
    "--ring": "#0d6b64",
    "--selection": "rgba(13,107,100,.20)",
    "--scrollbar": "rgba(27,29,33,.20)",
    "--scrollbar-hover": "rgba(27,29,33,.34)",
    "--shadow-overlay": "0 8px 28px rgba(27,29,33,.14)",
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
