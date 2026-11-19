"use client";

import { useEffect, type CSSProperties, type ReactNode } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuthStore } from "@/state/authStore";
import { THEMES, useTheme } from "@/theme/themes";
import PaperTrailLogo from "@/components/layout/PaperTrailLogo";


const NAV = [
  { href: "/", label: "Home" },
  { href: "/library", label: "Library" },
  { href: "/analytics", label: "Analytics" },
  { href: "/profile", label: "Profile" },
];

/** Themed page chrome (background + top nav) for secondary pages. Redirects to
 *  /login if the session can't be restored. */
export default function AuthenticatedPageLayout({ children }: { children: ReactNode }) {
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
      <div style={{ position: "relative", zIndex: 1, maxWidth: 1200, margin: "0 auto", padding: "22px clamp(14px, 4vw, 28px) 80px" }}>
        <nav style={{ display: "flex", alignItems: "center", gap: 14, padding: "10px 16px", borderRadius: "var(--radius-md)", background: "var(--surface)", border: "1px solid var(--border)", flexWrap: "wrap" }}>
          <Link href="/" style={{ display: "flex", alignItems: "center", gap: 11, textDecoration: "none" }}>
            <PaperTrailLogo />
            <span style={{ fontWeight: "var(--fw-semibold)", fontSize: "var(--fs-lg)", letterSpacing: "-.02em", color: "var(--text)" }}>PaperTrail</span>
          </Link>

          <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginLeft: 10 }}>
            {NAV.map((n) => {
              const active = pathname === n.href;
              return (
                <Link
                  key={n.href}
                  href={n.href}
                  style={{
                    padding: "8px 14px",
                    borderRadius: "var(--radius-md)",
                    fontSize: "var(--fs-sm)",
                    fontWeight: active ? "var(--fw-semibold)" : "var(--fw-medium)",
                    textDecoration: "none",
                    color: active ? "var(--on-accent)" : "var(--muted)",
                    background: active ? "var(--accent)" : "transparent",
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
              style={{ position: "relative", width: 60, height: 30, borderRadius: "var(--radius-md)", border: "1px solid var(--border)", background: "var(--raised)", cursor: "pointer", padding: 0 }}
            >
              <span style={{ position: "absolute", top: 3, left: isDark ? 33 : 3, width: 24, height: 24, borderRadius: "50%", background: "var(--accent)", transition: "left .28s cubic-bezier(.4,0,.2,1)" }} />
            </button>
            <button
              onClick={() => { void logout(); router.replace("/login"); }}
              style={{ padding: "9px 14px", borderRadius: "var(--radius-md)", border: "1px solid var(--border)", background: "var(--raised)", color: "var(--text)", fontFamily: "inherit", fontWeight: "var(--fw-medium)", fontSize: "var(--fs-sm)", cursor: "pointer", minHeight: 44 }}
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
