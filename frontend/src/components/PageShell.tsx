"use client";

import { useEffect, type CSSProperties, type ReactNode } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/authStore";
import { THEMES, useTheme } from "@/lib/theme";

const ACCENT_GRADIENT = "linear-gradient(135deg,var(--accent),var(--accent2))";

const NAV = [
  { href: "/", label: "Home" },
  { href: "/library", label: "Library" },
  { href: "/analytics", label: "Analytics" },
];

/** Themed page chrome (background + top nav) for secondary pages. Redirects to
 *  /login if the session can't be restored. */
export default function PageShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [theme, setTheme] = useTheme();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const ready = useAuthStore((s) => s.ready);
  const restoreSession = useAuthStore((s) => s.restoreSession);
  const logout = useAuthStore((s) => s.logout);

  useEffect(() => {
    restoreSession();
  }, [restoreSession]);
  useEffect(() => {
    if (ready && !isAuthenticated) router.replace("/login");
  }, [ready, isAuthenticated, router]);

  const t = THEMES[theme];
  const isDark = theme === "dark";

  return (
    <div style={{ position: "relative", minHeight: "100vh", background: "var(--bg)", ...t } as CSSProperties}>
      <div style={{ position: "absolute", inset: 0, overflow: "hidden", pointerEvents: "none", zIndex: 0 }}>
        <div style={{ position: "absolute", top: -140, left: -120, width: 560, height: 560, borderRadius: "50%", background: "var(--blob1)", filter: "blur(90px)", opacity: "var(--blobOp)" as unknown as number, animation: "floatA 18s ease-in-out infinite" }} />
        <div style={{ position: "absolute", bottom: -180, right: -120, width: 620, height: 620, borderRadius: "50%", background: "var(--blob2)", filter: "blur(100px)", opacity: "var(--blobOp)" as unknown as number, animation: "floatB 22s ease-in-out infinite" }} />
      </div>

      <div style={{ position: "relative", zIndex: 1, maxWidth: 1200, margin: "0 auto", padding: "22px 28px 80px" }}>
        <nav style={{ display: "flex", alignItems: "center", gap: 14, padding: "10px 16px", borderRadius: 18, background: "var(--card-bg)", border: "1px solid var(--card-border)", backdropFilter: "blur(18px) saturate(140%)", WebkitBackdropFilter: "blur(18px) saturate(140%)", flexWrap: "wrap" }}>
          <Link href="/" style={{ display: "flex", alignItems: "center", gap: 11, textDecoration: "none" }}>
            <div style={{ width: 30, height: 30, borderRadius: 9, background: ACCENT_GRADIENT, boxShadow: "0 4px 14px var(--accentGlow)" }} />
            <span style={{ fontWeight: 800, fontSize: 18, letterSpacing: "-.02em", color: "var(--text)" }}>PaperTrail</span>
          </Link>

          <div style={{ display: "flex", gap: 4, marginLeft: 10 }}>
            {NAV.map((n) => {
              const active = pathname === n.href;
              return (
                <Link
                  key={n.href}
                  href={n.href}
                  style={{
                    padding: "8px 14px",
                    borderRadius: 11,
                    fontSize: 13.5,
                    fontWeight: active ? 700 : 600,
                    textDecoration: "none",
                    color: active ? "var(--onAccent)" : "var(--muted)",
                    background: active ? ACCENT_GRADIENT : "transparent",
                    minHeight: 44,
                    display: "inline-flex",
                    alignItems: "center",
                  }}
                >
                  {n.label}
                </Link>
              );
            })}
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 10, marginLeft: "auto" }}>
            <button
              onClick={() => setTheme(isDark ? "light" : "dark")}
              aria-label={isDark ? "Switch to light theme" : "Switch to dark theme"}
              style={{ position: "relative", width: 60, height: 30, borderRadius: 16, border: "1px solid var(--card-border)", background: "var(--seg-bg)", cursor: "pointer", padding: 0 }}
            >
              <span style={{ position: "absolute", top: 3, left: isDark ? 33 : 3, width: 24, height: 24, borderRadius: "50%", background: ACCENT_GRADIENT, boxShadow: "0 2px 8px var(--accentGlow)", transition: "left .28s cubic-bezier(.4,0,.2,1)" }} />
            </button>
            <button
              onClick={() => { void logout(); router.replace("/login"); }}
              style={{ padding: "9px 14px", borderRadius: 12, border: "1px solid var(--card-border)", background: "var(--seg-bg)", color: "var(--text)", fontFamily: "inherit", fontWeight: 600, fontSize: 13.5, cursor: "pointer", minHeight: 44 }}
            >
              Sign out
            </button>
          </div>
        </nav>

        <div style={{ marginTop: 26 }}>{ready && isAuthenticated ? children : null}</div>
      </div>
    </div>
  );
}
