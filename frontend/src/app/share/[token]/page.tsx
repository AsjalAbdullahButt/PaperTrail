"use client";

import { useEffect, useState, type CSSProperties } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ApiError, getSharedQuery, type SharedQuery } from "@/lib/api";
import { THEMES, useTheme } from "@/lib/theme";
import Logo from "@/components/Logo";
import { renderAnswerWithCitations } from "@/components/Citations";

const MODE_LABEL: Record<string, string> = {
  rag: "Retrieved answer",
  multihop: "Multi-hop answer",
  direct: "Direct answer",
};

/** Public, unauthenticated view of a shared query — no PageShell (no nav,
 * no auth redirect): this is the one page in the app meant to be opened by
 * people who have never signed in. */
export default function SharedQueryPage() {
  const params = useParams<{ token: string }>();
  const token = params.token;
  const [theme] = useTheme();
  const t = THEMES[theme];

  const [data, setData] = useState<SharedQuery | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadedFor, setLoadedFor] = useState(token);

  // Reset during render when the token changes (e.g. following a different
  // share link without a full page reload), instead of a synchronous
  // setState at the top of the fetch effect below.
  if (token !== loadedFor) {
    setLoadedFor(token);
    setData(null);
    setError(null);
    setLoading(true);
  }

  useEffect(() => {
    let cancelled = false;
    getSharedQuery(token)
      .then((res) => { if (!cancelled) setData(res); })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.message : "This share link could not be loaded.");
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [token]);

  const confPct = data?.confidence_score != null ? Math.round(data.confidence_score * 100) : null;

  return (
    <div style={{ position: "relative", minHeight: "100vh", background: "var(--bg)", ...t } as CSSProperties}>
      <div style={{ position: "relative", zIndex: 1, maxWidth: 720, margin: "0 auto", padding: "28px 24px 80px" }}>
        <Link href="/" style={{ display: "inline-flex", alignItems: "center", gap: 11, textDecoration: "none", marginBottom: 30 }}>
          <Logo />
          <span style={{ fontWeight: 800, fontSize: 18, letterSpacing: "-.02em", color: "var(--text)" }}>PaperTrail</span>
        </Link>

        {loading && (
          <div style={{ padding: "40px 0", textAlign: "center", color: "var(--muted)", fontSize: 14 }}>
            Loading shared answer…
          </div>
        )}

        {!loading && error && (
          <div
            role="alert"
            style={{
              padding: "18px 20px", borderRadius: 16, fontSize: 14.5, color: "#ff8a80",
              background: "rgba(255,80,80,.10)", border: "1px solid rgba(255,120,120,.35)",
            }}
          >
            {error}
          </div>
        )}

        {!loading && data && (
          <div
            style={{
              padding: "30px 32px", borderRadius: 22, background: "var(--card-bg)",
              border: "1px solid var(--card-border)", backdropFilter: "blur(22px) saturate(150%)",
              WebkitBackdropFilter: "blur(22px) saturate(150%)", boxShadow: "0 18px 50px var(--cardShadow)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 9, marginBottom: 10 }}>
              <div style={{ width: 22, height: 22, borderRadius: 7, background: "linear-gradient(135deg,var(--accent),var(--accent2))", flex: "none" }} />
              <span style={{ fontSize: 12.5, fontWeight: 700, letterSpacing: ".04em", textTransform: "uppercase", color: "var(--muted)" }}>
                {MODE_LABEL[data.mode] ?? "Answer"}
              </span>
              {confPct !== null && (
                <span style={{ marginLeft: "auto", display: "inline-flex", alignItems: "center", padding: "3px 10px", borderRadius: 20, fontSize: 12, fontWeight: 700, color: "var(--accent)", background: "var(--chip-bg)", border: "1px solid var(--chip-border)" }}>
                  {confPct}% confidence
                </span>
              )}
            </div>

            <div style={{ fontSize: 15, fontWeight: 700, color: "var(--muted)", marginBottom: 18 }}>{data.question}</div>

            <div style={{ fontSize: 18, lineHeight: 1.62, letterSpacing: "-.01em", color: "var(--text)" }}>
              {renderAnswerWithCitations(data.answer, data.source_count)}
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: 14, marginTop: 26, paddingTop: 18, borderTop: "1px solid var(--card-border)", flexWrap: "wrap" }}>
              <span style={{ fontSize: 13, color: "var(--muted)" }}>
                {data.mode === "direct" ? "No retrieval" : `Grounded in ${data.source_count} source${data.source_count === 1 ? "" : "s"}`}
              </span>
              <span style={{ width: 4, height: 4, borderRadius: "50%", background: "var(--muted)", opacity: 0.5 }} />
              <span style={{ fontSize: 13, color: "var(--muted)" }}>
                shared from PaperTrail · {new Date(data.created_at).toLocaleDateString()}
              </span>
            </div>
          </div>
        )}

        <p style={{ textAlign: "center", marginTop: 26, fontSize: 13, color: "var(--muted)" }}>
          Want answers like this from your own documents? <Link href="/register" style={{ color: "var(--accent)", fontWeight: 600 }}>Try PaperTrail</Link>
        </p>
      </div>
    </div>
  );
}
