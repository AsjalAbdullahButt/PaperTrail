"use client";

import { useState } from "react";
import type { GroundingMethod, GroundingSentence, QueryMode, Source, UnsupportedSentence } from "@/api/backendClient";
import ConfidenceGauge from "@/components/query/ConfidenceGauge";
import GroundingPanel from "@/components/query/GroundingPanel";

const scoreChip = {
  display: "inline-flex",
  alignItems: "center",
  gap: 4,
  padding: "2px 7px",
  borderRadius: "var(--radius-sm)",
  fontSize: "var(--fs-xs)",
  fontWeight: "var(--fw-medium)",
  color: "var(--muted)",
  background: "var(--raised)",
  border: "1px solid var(--border)",
} as const;

const pct = (x: number) => `${Math.round(x * 100)}%`;

function SourceCard({ src }: { src: Source }) {
  const [hover, setHover] = useState(false);
  const typeLabel = `${src.title.split(".").pop()?.toUpperCase() || "DOC"} · p.${src.page_number}`;
  const whyRetrieved =
    `Relevance ${src.relevance_pct}% · similarity ${Math.round(src.similarity_score * 100)}%` +
    ` · importance ${Math.round(src.importance_score * 100)}%` +
    (src.rerank_prob != null ? ` · re-rank ${Math.round(src.rerank_prob * 100)}%` : "");
  return (
    <div
      id={`src-${src.n}`}
      title={whyRetrieved}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        padding: "16px 17px",
        borderRadius: "var(--radius-md)",
        background: "var(--surface)",
        border: `1px solid ${hover ? "var(--accent)" : "var(--border)"}`,
        transition: "border-color .15s ease",
      }}
    >
      <div style={{ display: "flex", alignItems: "flex-start", gap: 11 }}>
        <div
          style={{
            width: 30,
            height: 36,
            borderRadius: "var(--radius-sm)",
            background: "var(--raised)",
            border: "1px solid var(--border)",
            flex: "none",
            position: "relative",
            overflow: "hidden",
          }}
        >
          <div style={{ position: "absolute", top: 6, left: 5, right: 5, height: 2, borderRadius: "var(--radius-full)", background: "var(--muted)", opacity: 0.4 }} />
          <div style={{ position: "absolute", top: 11, left: 5, right: 9, height: 2, borderRadius: "var(--radius-full)", background: "var(--muted)", opacity: 0.4 }} />
          <div style={{ position: "absolute", top: 16, left: 5, right: 6, height: 2, borderRadius: "var(--radius-full)", background: "var(--muted)", opacity: 0.4 }} />
          <div style={{ position: "absolute", bottom: 5, left: 5, width: 14, height: 5, borderRadius: "var(--radius-full)", background: "var(--accent)", opacity: 0.7 }} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, justifyContent: "space-between" }}>
            <span style={{ fontSize: "var(--fs-sm)", fontWeight: "var(--fw-semibold)", color: "var(--text)", letterSpacing: "-.01em", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {src.title}
            </span>
            <span style={{ flex: "none", display: "inline-flex", alignItems: "center", padding: "3px 8px", borderRadius: "var(--radius-sm)", fontSize: "var(--fs-xs)", fontWeight: "var(--fw-semibold)", color: "var(--accent)", background: "var(--accent-soft)", border: "1px solid var(--accent-line)" }}>
              {src.score}%
            </span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 3, flexWrap: "wrap" }}>
            <span style={{ fontSize: "var(--fs-xs)", fontWeight: "var(--fw-medium)", color: "var(--accent)" }}>[{src.n}]</span>
            <span style={{ fontSize: "var(--fs-xs)", color: "var(--muted)" }}>{typeLabel}</span>
            {src.section_heading && (
              <span style={{ fontSize: "var(--fs-xs)", color: "var(--muted)", fontStyle: "italic", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 160 }}>
                · {src.section_heading}
              </span>
            )}
          </div>
          <p style={{ margin: "9px 0 0", fontSize: "var(--fs-xs)", lineHeight: 1.5, color: "var(--muted)" }}>{src.snippet}</p>
          {/* Retrieval inspector: how each stage scored this passage */}
          <div data-testid={`score-breakdown-${src.n}`} style={{ display: "flex", gap: 5, flexWrap: "wrap", marginTop: 9 }}>
            <span title="Dense (embedding) cosine similarity" style={scoreChip}>Dense {pct(src.similarity_score)}</span>
            <span title="BM25 keyword score, normalised over the collection" style={scoreChip}>BM25 {pct(src.sparse_score)}</span>
            <span title="Chunk importance (TF-IDF + position prior)" style={scoreChip}>Importance {pct(src.importance_score)}</span>
            {src.rerank_prob != null && (
              <span title={`Cross-encoder logit ${src.rerank_score?.toFixed(2)}`} style={{ ...scoreChip, color: "var(--accent)", border: "1px solid var(--accent-line)", background: "var(--accent-soft)" }}>
                Re-rank {pct(src.rerank_prob)}
              </span>
            )}
          </div>
          {/* Relevance meter */}
          <div title={`Relevance ${src.relevance_pct}%`} style={{ marginTop: 11, height: 4, borderRadius: "var(--radius-full)", background: "var(--raised)", overflow: "hidden" }}>
            <div style={{ height: "100%", width: `${src.score}%`, borderRadius: "var(--radius-full)", background: "var(--accent)" }} />
          </div>
          {/* Importance meter (second bar) */}
          <div title={`Importance ${Math.round(src.importance_score * 100)}%`} style={{ marginTop: 5, height: 3, borderRadius: "var(--radius-full)", background: "var(--raised)", overflow: "hidden" }}>
            <div style={{ height: "100%", width: `${Math.round(src.importance_score * 100)}%`, borderRadius: "var(--radius-full)", background: "var(--text-2)" }} />
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
  grounding = [],
  groundingMethod = "lexical",
}: {
  sources: Source[];
  confidenceScore: number;
  unsupportedSentences: UnsupportedSentence[];
  mode: QueryMode;
  isStreaming: boolean;
  grounding?: GroundingSentence[];
  groundingMethod?: GroundingMethod;
}) {
  if (sources.length === 0) return null;
  return (
    <div style={{ flex: "1 1 300px", minWidth: "min(270px, 100%)", maxWidth: 380 }}>
      {mode !== "direct" && !isStreaming && (
        <div style={{ display: "flex", justifyContent: "center", marginBottom: 12, padding: "12px 0", borderRadius: "var(--radius-md)", background: "var(--surface)", border: "1px solid var(--border)" }}>
          <ConfidenceGauge value={confidenceScore} />
        </div>
      )}

      {/* Hallucination guard: claims without a direct source */}
      {!isStreaming && unsupportedSentences.length > 0 && (
        <div style={{ marginBottom: 12, padding: "10px 13px", borderRadius: "var(--radius-md)", fontSize: "var(--fs-xs)", color: "var(--warn)", background: "var(--warn-soft)", border: "1px solid var(--warn-line)" }}>
          ⚠ {unsupportedSentences.length} claim
          {unsupportedSentences.length === 1 ? "" : "s"} without a direct source in your documents.
        </div>
      )}

      {!isStreaming && mode !== "direct" && (
        <GroundingPanel grounding={grounding} method={groundingMethod} sources={sources} />
      )}

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", margin: "2px 4px 14px" }}>
        <span style={{ fontSize: "var(--fs-xs)", fontWeight: "var(--fw-semibold)", letterSpacing: ".05em", textTransform: "uppercase", color: "var(--muted)" }}>Sources</span>
        <span style={{ fontSize: "var(--fs-xs)", fontWeight: "var(--fw-medium)", color: "var(--muted)" }}>
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
