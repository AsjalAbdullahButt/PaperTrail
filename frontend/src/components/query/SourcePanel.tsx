"use client";

import type { GroundingMethod, GroundingSentence, QueryMode, Source, UnsupportedSentence } from "@/api/backendClient";
import ConfidenceGauge from "@/components/query/ConfidenceGauge";
import GroundingPanel from "@/components/query/GroundingPanel";
import { WarningIcon } from "@/components/ui/Icons";

const pct = (x: number) => `${Math.round(x * 100)}%`;

// Same cut point the gauge uses for "high". Colour only: a high relevance gets
// the accent, everything else stays neutral so a weak score never looks like a
// success. The number itself is shown exactly as the server sent it.
const HIGH_RELEVANCE = 70;

function SourceCard({ src }: { src: Source }) {
  const typeLabel = `${src.title.split(".").pop()?.toUpperCase() || "DOC"} · p.${src.page_number}`;
  const whyRetrieved =
    `Relevance ${src.relevance_pct}% · similarity ${Math.round(src.similarity_score * 100)}%` +
    ` · importance ${Math.round(src.importance_score * 100)}%` +
    (src.rerank_prob != null ? ` · re-rank ${Math.round(src.rerank_prob * 100)}%` : "");
  const high = src.score >= HIGH_RELEVANCE;
  return (
    <div id={`src-${src.n}`} title={whyRetrieved} className="card card-compact source-card">
      <div style={{ display: "flex", alignItems: "flex-start", gap: "var(--space-3)" }}>
        <div
          aria-hidden
          style={{
            width: 28,
            height: 36,
            borderRadius: "var(--radius-sm)",
            background: "var(--raised)",
            border: "1px solid var(--border)",
            flex: "none",
            position: "relative",
            overflow: "hidden",
          }}
        >
          <div style={{ position: "absolute", top: 7, left: 5, right: 5, height: 2, borderRadius: "var(--radius-full)", background: "var(--muted)", opacity: 0.4 }} />
          <div style={{ position: "absolute", top: 12, left: 5, right: 9, height: 2, borderRadius: "var(--radius-full)", background: "var(--muted)", opacity: 0.4 }} />
          <div style={{ position: "absolute", top: 17, left: 5, right: 6, height: 2, borderRadius: "var(--radius-full)", background: "var(--muted)", opacity: 0.4 }} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", justifyContent: "space-between" }}>
            <span style={{ fontSize: "var(--fs-sm)", fontWeight: "var(--fw-semibold)", color: "var(--text)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {src.title}
            </span>
            <span className={`chip tabular-nums${high ? " chip-accent" : ""}`} style={{ flex: "none" }}>
              {src.score}%
            </span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", marginTop: "var(--space-1)", flexWrap: "wrap" }}>
            <span className="meta" style={{ color: "var(--accent)", fontWeight: "var(--fw-medium)" }}>[{src.n}]</span>
            <span className="meta">{typeLabel}</span>
            {src.section_heading && (
              <span className="meta" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 160 }}>
                · {src.section_heading}
              </span>
            )}
          </div>
          <p style={{ marginTop: "var(--space-2)", fontSize: "var(--fs-xs)", lineHeight: 1.5, color: "var(--text-2)" }}>{src.snippet}</p>
          {/* Retrieval inspector: how each stage scored this passage */}
          <div data-testid={`score-breakdown-${src.n}`} style={{ display: "flex", gap: "var(--space-1)", flexWrap: "wrap", marginTop: "var(--space-2)" }}>
            <span title="Dense (embedding) cosine similarity" className="chip tabular-nums">Dense {pct(src.similarity_score)}</span>
            <span title="BM25 keyword score, normalised over the collection" className="chip tabular-nums">BM25 {pct(src.sparse_score)}</span>
            <span title="Chunk importance (TF-IDF + position prior)" className="chip tabular-nums">Importance {pct(src.importance_score)}</span>
            {src.rerank_prob != null && (
              <span title={`Cross-encoder logit ${src.rerank_score?.toFixed(2)}`} className="chip chip-accent tabular-nums">
                Re-rank {pct(src.rerank_prob)}
              </span>
            )}
          </div>
          {/* Relevance meter */}
          <div title={`Relevance ${src.relevance_pct}%`} className="meter" style={{ marginTop: "var(--space-3)" }}>
            <span style={{ width: `${src.score}%`, background: high ? "var(--accent)" : "var(--text-2)" }} />
          </div>
          {/* Importance meter (second bar) */}
          <div title={`Importance ${Math.round(src.importance_score * 100)}%`} className="meter" style={{ marginTop: "var(--space-1)", height: 3 }}>
            <span style={{ width: `${Math.round(src.importance_score * 100)}%`, background: "var(--text-2)" }} />
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
    <div className="stack" style={{ gap: "var(--space-3)", minWidth: 0 }}>
      {mode !== "direct" && !isStreaming && (
        <div className="card card-compact" style={{ display: "flex", justifyContent: "center" }}>
          <ConfidenceGauge value={confidenceScore} />
        </div>
      )}

      {/* Hallucination guard: claims without a direct source */}
      {!isStreaming && unsupportedSentences.length > 0 && (
        <div className="alert alert-warn" style={{ fontSize: "var(--fs-xs)" }}>
          <WarningIcon size={14} style={{ marginTop: 1 }} />
          <span>
            {unsupportedSentences.length} claim
            {unsupportedSentences.length === 1 ? "" : "s"} without a direct source in your documents.
          </span>
        </div>
      )}

      {!isStreaming && mode !== "direct" && (
        <GroundingPanel grounding={grounding} method={groundingMethod} sources={sources} />
      )}

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: "var(--space-1)" }}>
        <span className="section-label">Sources</span>
        <span className="meta">
          {sources.length} document{sources.length === 1 ? "" : "s"}
        </span>
      </div>
      <div className="stack" style={{ gap: "var(--space-3)" }}>
        {sources.map((src) => (
          <SourceCard key={src.n} src={src} />
        ))}
      </div>
    </div>
  );
}
