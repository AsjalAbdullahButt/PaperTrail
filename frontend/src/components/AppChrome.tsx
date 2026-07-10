"use client";

import { useEffect, useState } from "react";
import { Toaster } from "react-hot-toast";
import { THEMES, useTheme } from "@/lib/theme";

/** Global chrome: toast host + an offline banner. Mounted once in the layout.
 *
 * The Toaster portals its DOM outside of any page's themed wrapper div, so it
 * can't see the CSS custom properties a page sets on its own root element.
 * Mirroring the current theme's variables onto :root (in addition to, not
 * instead of, each page's own copy) gives the portal something to inherit
 * without touching theme.ts/PageShell's per-page variable system itself. */
export default function AppChrome() {
  const [offline, setOffline] = useState(false);
  const [theme] = useTheme();

  useEffect(() => {
    const vars = THEMES[theme];
    for (const [key, value] of Object.entries(vars)) {
      document.documentElement.style.setProperty(key, value);
    }
    // Tells the browser which palette to use for native form controls (select
    // dropdowns, checkboxes, scrollbars) — without this they always render
    // with light-mode chrome regardless of our own CSS variables.
    document.documentElement.style.colorScheme = theme;
  }, [theme]);

  useEffect(() => {
    const update = () => setOffline(!navigator.onLine);
    update();
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    return () => {
      window.removeEventListener("online", update);
      window.removeEventListener("offline", update);
    };
  }, []);

  return (
    <>
      {offline && (
        <div
          role="status"
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            zIndex: 100,
            padding: "8px 16px",
            textAlign: "center",
            fontSize: 13.5,
            fontWeight: 600,
            color: "#3a2c05",
            background: "#e0a53a",
          }}
        >
          You&rsquo;re offline — queries and uploads are paused.
        </div>
      )}
      <Toaster
        position="bottom-right"
        toastOptions={{
          duration: 4000,
          style: {
            background: "var(--card-bg)",
            color: "var(--text)",
            border: "1px solid var(--card-border)",
            borderRadius: 12,
            fontSize: 13.5,
            backdropFilter: "blur(18px) saturate(140%)",
            boxShadow: "0 12px 34px var(--cardShadow)",
          },
          success: { iconTheme: { primary: "var(--accent)", secondary: "var(--onAccent)" } },
          error: { iconTheme: { primary: "#ff8a80", secondary: "var(--onAccent)" } },
        }}
      />
    </>
  );
}
