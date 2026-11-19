"use client";

import type { CSSProperties, FormEvent, ReactNode } from "react";
import { THEMES, useTheme } from "@/theme/themes";
import PaperTrailLogo from "@/components/layout/PaperTrailLogo";
import ThemeToggle from "@/components/ui/ThemeToggle";

/** Shared frame for login, register, forgot and reset. The theme toggle sits in
 *  the page flow above the card (never absolutely positioned), so on short
 *  phones the card can scroll and nothing overlaps. */
export default function AuthShell({
  title,
  subtitle,
  onSubmit,
  busy,
  submitLabel,
  error,
  footer,
  children,
}: {
  title: string;
  subtitle: string;
  onSubmit: (e: FormEvent) => void;
  busy: boolean;
  submitLabel: string;
  error: string | null;
  footer: ReactNode;
  children: ReactNode;
}) {
  const [theme, setTheme] = useTheme();
  const isDark = theme === "dark";

  return (
    <div className="auth-page" style={THEMES[theme] as CSSProperties}>
      <div className="auth-top">
        <ThemeToggle isDark={isDark} onToggle={() => setTheme(isDark ? "light" : "dark")} />
      </div>
      <main className="auth-main">
        <form onSubmit={onSubmit} noValidate aria-label={title} className="card auth-card">
          <div className="app-brand">
            <PaperTrailLogo />
            PaperTrail
          </div>
          <h1 className="h-title" style={{ marginTop: "var(--space-5)" }}>
            {title}
          </h1>
          <p style={{ marginTop: "var(--space-1)", fontSize: "var(--fs-sm)", color: "var(--text-2)" }}>{subtitle}</p>

          <div className="stack" style={{ marginTop: "var(--space-5)" }}>
            {children}
          </div>

          {error && (
            <div role="alert" className="alert alert-danger" style={{ marginTop: "var(--space-4)" }}>
              {error}
            </div>
          )}

          <button type="submit" disabled={busy} className="btn btn-primary btn-block" style={{ marginTop: "var(--space-5)" }}>
            {busy ? "Please wait…" : submitLabel}
          </button>

          <p style={{ marginTop: "var(--space-4)", fontSize: "var(--fs-sm)", color: "var(--text-2)", textAlign: "center" }}>
            {footer}
          </p>
        </form>
      </main>
    </div>
  );
}
