"use client";

import { useState } from "react";
import type { QueryMode, Source, UnsupportedSentence } from "@/lib/api";
import ConfidenceGauge from "@/components/ConfidenceGauge";

function SourceCard({ src }: { src: Source }) {
  const [hover, setHover] = useState(false);
  const typeLabel = `${src.title.split(".").pop()?.toUpperCase() || "DOC"} · p.${src.page_number}`;
  const whyRetrieved =
    `Relevance ${src.relevance_pct}% · similarity ${Math.round(src.similarity_score * 100)}%` +
    ` · importance ${Math.round(src.importance_score * 100)}%`;
  return (
    <div
      id={`src-${src.n}`}
      title={whyRetrieved}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        padding: "16px 17px",
        borderRadius: 16,
        background: "var(--card-bg)",
        border: `1px solid ${hover ? "var(--accent)" : "var(--card-border)"}`,
        backdropFilter: "blur(18px) saturate(140%)",
        WebkitBackdropFilter: "blur(18px) saturate(140%)",
        boxShadow: "0 8px 24px var(--cardShadow)",
        transition: "border-color .15s ease",
      }}
    >
      <div style={{ display: "flex", alignItems: "flex-start", gap: 11 }}>
        <div
          style={{
            width: 30,
            height: 36,
            borderRadius: 6,
            background: "var(--doc-bg)",
            border: "1px solid var(--card-border)",
            flex: "none",
            position: "relative",
            overflow: "hidden",
          }}
        >
          <div style={{ position: "absolute", top: 6, left: 5, right: 5, height: 2, borderRadius: 2, background: "var(--muted)", opacity: 0.4 }} />
          <div style={{ position: "absolute", top: 11, left: 5, right: 9, height: 2, borderRadius: 2, background: "var(--muted)", opacity: 0.4 }} />
          <div style={{ position: "absolute", top: 16, left: 5, right: 6, height: 2, borderRadius: 2, background: "var(--muted)", opacity: 0.4 }} />
          <div style={{ position: "absolute", bottom: 5, left: 5, width: 14, height: 5, borderRadius: 2, background: "var(--accent)", opacity: 0.7 }} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, justifyContent: "space-between" }}>
            <span style={{ fontSize: 14, fontWeight: 700, color: "var(--text)", letterSpacing: "-.01em", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {src.title}
            </span>
            <span style={{ flex: "none", display: "inline-flex", alignItems: "center", padding: "3px 8px", borderRadius: 8, fontSize: 11.5, fontWeight: 700, color: "var(--accent)", background: "var(--chip-bg)", border: "1px solid var(--chip-border)" }}>
              {src.score}%
            </span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 3, flexWrap: "wrap" }}>
            <span style={{ fontSize: 11, fontWeight: 600, color: "var(--accent2)" }}>[{src.n}]</span>
            <span style={{ fontSize: 11.5, color: "var(--muted)" }}>{typeLabel}</span>
            {src.section_heading && (
              <span style={{ fontSize: 11.5, color: "var(--muted)", fontStyle: "italic", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 160 }}>
                · {src.section_heading}
              </span>
            )}
          </div>
          <p style={{ margin: "9px 0 0", fontSize: 12.5, lineHeight: 1.5, color: "var(--muted)" }}>{src.snippet}</p>
          {/* Relevance meter */}
          <div title={`Relevance ${src.relevance_pct}%`} style={{ marginTop: 11, height: 4, borderRadius: 3, background: "var(--seg-bg)", overflow: "hidden" }}>
            <div style={{ height: "100%", width: `${src.score}%`, borderRadius: 3, background: "linear-gradient(90deg,var(--accent),var(--accent2))" }} />
          </div>
          {/* Importance meter (second bar) */}
          <div title={`Importance ${Math.round(src.importance_score * 100)}%`} style={{ marginTop: 5, height: 3, borderRadius: 3, background: "var(--seg-bg)", overflow: "hidden" }}>
            <div style={{ height: "100%", width: `${Math.round(src.importance_score * 100)}%`, borderRadius: 3, background: "var(--accent2)", opacity: 0.7 }} />
          </div>
        </div>
      </div>
    </div>
  );
}

export default function SourcePanel({
  sources,
  confidenceScore,
  unsupportedSentences,
  mode,
  isStreaming,
}: {
  sources: Source[];
  confidenceScore: number;
  unsupportedSentences: UnsupportedSentence[];
  mode: QueryMode;
  isStreaming: boolean;
}) {
  if (sources.length === 0) return null;
  return (
    <div style={{ flex: "1 1 300px", minWidth: 270, maxWidth: 380 }}>
      {mode !== "direct" && !isStreaming && (
        <div style={{ display: "flex", justifyContent: "center", marginBottom: 12, padding: "12px 0", borderRadius: 16, background: "var(--card-bg)", border: "1px solid var(--card-border)" }}>
          <ConfidenceGauge value={confidenceScore} />
        </div>
      )}

      {/* Hallucination guard: claims without a direct source */}
      {!isStreaming && unsupportedSentences.length > 0 && (
        <div style={{ marginBottom: 12, padding: "10px 13px", borderRadius: 12, fontSize: 12.5, color: "#e0a53a", background: "rgba(224,165,58,.10)", border: "1px solid rgba(224,165,58,.35)" }}>
          ⚠ {unsupportedSentences.length} claim
          {unsupportedSentences.length === 1 ? "" : "s"} without a direct source in your documents.
        </div>
      )}

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", margin: "2px 4px 14px" }}>
        <span style={{ fontSize: 12.5, fontWeight: 700, letterSpacing: ".05em", textTransform: "uppercase", color: "var(--muted)" }}>Sources</span>
        <span style={{ fontSize: 12, fontWeight: 600, color: "var(--muted)" }}>
          {sources.length} document{sources.length === 1 ? "" : "s"}
        </span>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {sources.map((src) => (
          <SourceCard key={src.n} src={src} />
        ))}
      </div>
    </div>
  );
}
