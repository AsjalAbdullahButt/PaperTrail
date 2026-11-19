"use client";

import { useEffect, useState, type CSSProperties } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ApiError, getSharedQuery, type SharedQuery } from "@/api/backendClient";
import { THEMES, useTheme } from "@/theme/themes";
import PaperTrailLogo from "@/components/layout/PaperTrailLogo";
import { renderAnswerWithCitations } from "@/components/query/AnswerCitations";

const MODE_LABEL: Record<string, string> = {
  rag: "Retrieved answer",
  multihop: "Multi-hop answer",
  direct: "Direct answer",
};

/** Public, unauthenticated view of a shared query — no AuthenticatedPageLayout (no nav,
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
  // Same rule as the main page: teal for a good result, amber for a weak one.
  const confChip = confPct === null ? "" : confPct >= 75 ? "chip-accent" : confPct < 50 ? "chip-warn" : "";

  return (
    <div className="page" style={t as CSSProperties}>
      <div className="page-inner" style={{ maxWidth: 720 }}>
        <Link href="/" className="app-brand" style={{ marginBottom: "var(--space-5)" }}>
          <PaperTrailLogo />
          PaperTrail
        </Link>

        <main>
          {loading && (
            <div className="empty" role="status">Loading shared answer…</div>
          )}

          {!loading && error && (
            <div role="alert" className="alert alert-danger">
              {error}
            </div>
          )}

          {!loading && data && (
            <article className="card">
              <div className="row" style={{ marginBottom: "var(--space-3)" }}>
                <span className="section-label">{MODE_LABEL[data.mode] ?? "Answer"}</span>
                {confPct !== null && (
                  <span className={`chip tabular-nums ${confChip}`} style={{ marginLeft: "auto" }}>
                    {confPct}% confidence
                  </span>
                )}
              </div>

              <h1 className="h-title" style={{ color: "var(--text-2)", marginBottom: "var(--space-4)" }}>{data.question}</h1>

              <div className="answer-text">
                {renderAnswerWithCitations(data.answer, data.source_count)}
              </div>

              <div className="row" style={{ gap: "var(--space-3)", marginTop: "var(--space-5)", paddingTop: "var(--space-4)", borderTop: "1px solid var(--border)", flexWrap: "wrap", fontSize: "var(--fs-sm)", color: "var(--text-2)" }}>
                <span>
                  {data.mode === "direct" ? "No retrieval" : `Grounded in ${data.source_count} source${data.source_count === 1 ? "" : "s"}`}
                </span>
                <span aria-hidden style={{ color: "var(--muted)" }}>·</span>
                <span>
                  shared from PaperTrail · {new Date(data.created_at).toLocaleDateString()}
                </span>
              </div>
            </article>
          )}
        </main>

        <p style={{ textAlign: "center", marginTop: "var(--space-5)", fontSize: "var(--fs-sm)", color: "var(--text-2)" }}>
          Want answers like this from your own documents? <Link href="/register" className="link">Try PaperTrail</Link>
        </p>
      </div>
    </div>
  );
}
