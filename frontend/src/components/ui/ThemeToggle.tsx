"use client";

import { MoonIcon, SunIcon } from "@/components/ui/Icons";

/** The one theme switch used by every header and the auth pages. The label
 *  names the theme you switch TO, so it reads correctly to a screen reader. */
export default function ThemeToggle({ isDark, onToggle }: { isDark: boolean; onToggle: () => void }) {
  const label = isDark ? "Switch to light theme" : "Switch to dark theme";
  return (
    <button type="button" className="btn btn-ghost btn-icon" onClick={onToggle} aria-label={label} title={label}>
      {isDark ? <SunIcon /> : <MoonIcon />}
      <span className="toggle-label">{isDark ? "Light theme" : "Dark theme"}</span>
    </button>
  );
}
