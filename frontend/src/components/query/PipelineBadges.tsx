"use client";

import type { PipelineInfo } from "@/api/backendClient";

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
    <div data-testid="pipeline-badges" style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)", marginTop: "var(--space-4)" }}>
      <div style={{ display: "flex", gap: "var(--space-2)", flexWrap: "wrap" }}>
        {items.map((label) => (
          <span key={label} className="chip">
            {label}
          </span>
        ))}
      </div>
      {pipeline.notes.map((note) => (
        <span key={note} className="meta">
          {note}
        </span>
      ))}
    </div>
  );
}
