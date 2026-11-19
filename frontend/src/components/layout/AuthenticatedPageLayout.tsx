"use client";

import { useEffect, useState, type CSSProperties, type ReactNode } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuthStore } from "@/state/authStore";
import { THEMES, useTheme } from "@/theme/themes";
import PaperTrailLogo from "@/components/layout/PaperTrailLogo";
import ThemeToggle from "@/components/ui/ThemeToggle";
import { CloseIcon, MenuIcon } from "@/components/ui/Icons";

const NAV = [
  { href: "/", label: "Home" },
  { href: "/library", label: "Library" },
  { href: "/analytics", label: "Analytics" },
  { href: "/profile", label: "Profile" },
];

/** Themed page chrome (background + top nav) for secondary pages. Redirects to
 *  /login if the session can't be restored. Uses the same header classes as the
 *  home page so both read as one app. */
export default function AuthenticatedPageLayout({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [theme, setTheme] = useTheme();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const ready = useAuthStore((s) => s.ready);
  const restoreSession = useAuthStore((s) => s.restoreSession);
  const logout = useAuthStore((s) => s.logout);
  // Phone only: whether the folded menu is open. Purely presentational.
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    restoreSession();
  }, [restoreSession]);
  useEffect(() => {
    if (ready && !isAuthenticated) router.replace("/login");
  }, [ready, isAuthenticated, router]);
  useEffect(() => {
    if (!menuOpen) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setMenuOpen(false); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [menuOpen]);

  const isDark = theme === "dark";

  return (
    <div className="page" style={THEMES[theme] as CSSProperties}>
      <div className="page-inner">
        <header className="app-header" data-open={menuOpen}>
          <Link href="/" className="app-brand">
            <PaperTrailLogo />
            PaperTrail
          </Link>

          <div id="app-menu" className="app-actions">
            <nav className="app-nav" aria-label="Main">
              {NAV.map((n) => (
                <Link
                  key={n.href}
                  href={n.href}
                  className="btn btn-ghost"
                  aria-current={pathname === n.href ? "page" : undefined}
                  onClick={() => setMenuOpen(false)}
                >
                  {n.label}
                </Link>
              ))}
            </nav>
            <span className="app-spacer" />
            <div className="app-account">
              <button type="button" className="btn btn-ghost" onClick={() => { void logout(); router.replace("/login"); }}>
                Sign out
              </button>
              <ThemeToggle isDark={isDark} onToggle={() => setTheme(isDark ? "light" : "dark")} />
            </div>
          </div>

          <button
            type="button"
            className="btn btn-ghost btn-icon app-menu-toggle"
            onClick={() => setMenuOpen((v) => !v)}
            aria-expanded={menuOpen}
            aria-controls="app-menu"
            aria-label={menuOpen ? "Close menu" : "Open menu"}
            style={{ marginLeft: "auto" }}
          >
            {menuOpen ? <CloseIcon /> : <MenuIcon />}
          </button>
        </header>

        <main style={{ marginTop: "var(--space-5)" }}>{ready && isAuthenticated ? children : null}</main>
      </div>
    </div>
  );
}
