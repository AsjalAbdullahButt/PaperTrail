"use client";

import type { PipelineInfo } from "@/api/backendClient";

const badge = {
  display: "inline-flex",
  alignItems: "center",
  padding: "2px 9px",
  borderRadius: 20,
  fontSize: 11.5,
  fontWeight: 700,
  color: "var(--accent)",
  background: "var(--chip-bg)",
  border: "1px solid var(--chip-border)",
} as const;

/** Compact record of which NLP stages produced this answer (so a result is never
 * mistaken for a different configuration), plus any fallback notes. */
export default function PipelineBadges({ pipeline }: { pipeline: PipelineInfo | null }) {
  if (!pipeline) return null;
  const items = [
    "Hybrid retrieval",
    pipeline.reranked ? "Cross-encoder re-rank" : null,
    pipeline.expansion === "hyde" ? "HyDE query expansion" : null,
    pipeline.grounding_method === "nli" ? "NLI grounding" : "Lexical grounding",
  ].filter((x): x is string => x !== null);

  return (
    <div data-testid="pipeline-badges" style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 14 }}>
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
        {items.map((label) => (
          <span key={label} style={badge}>
            {label}
          </span>
        ))}
      </div>
      {pipeline.notes.map((note) => (
        <span key={note} style={{ fontSize: 12, color: "var(--muted)" }}>
          ℹ {note}
        </span>
      ))}
    </div>
  );
}
