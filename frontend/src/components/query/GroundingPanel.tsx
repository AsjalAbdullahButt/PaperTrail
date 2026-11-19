"use client";

import type { GroundingMethod, GroundingSentence, Source } from "@/api/backendClient";

const OK = "var(--ok)";
const WARN = "var(--warn)";
const BAD = "var(--danger)";

function verdictColor(g: GroundingSentence): string {
  if (g.supported) return OK;
  return g.label === "contradicted" ? BAD : WARN;
}

function verdictText(g: GroundingSentence, method: GroundingMethod): string {
  if (method === "nli" && g.entailment != null) {
    const pct = Math.round(g.entailment * 100);
    return g.supported ? `Entailed by a source passage (${pct}%)` : g.label === "contradicted" ? `Contradicted by the sources (entailment ${pct}%)` : `Not entailed by any retrieved passage (${pct}%)`;
  }
  return g.supported ? "Key terms found in a source passage" : "Few key terms overlap with any source passage";
}

/**
 * Claim-by-claim grounding of the answer. With NLI grounding each sentence shows
 * the best entailment probability over the retrieved passages; with the lexical
 * heuristic it shows only supported / unsupported. Clicking a supported sentence
 * jumps to the source card that backs it.
 */
export default function GroundingPanel({
  grounding,
  method,
  sources,
}: {
  grounding: GroundingSentence[];
  method: GroundingMethod;
  sources: Source[];
}) {
  if (grounding.length === 0) return null;
  const supported = grounding.filter((g) => g.supported).length;

  function jump(g: GroundingSentence) {
    const src = sources.find((s) => s.chunk_id === g.source_chunk_id);
    if (src) document.getElementById(`src-${src.n}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  return (
    <details
      data-testid="grounding-panel"
      style={{ marginBottom: 12, borderRadius: "var(--radius-md)", background: "var(--surface)", border: "1px solid var(--border)", padding: "10px 13px" }}
    >
      <summary style={{ cursor: "pointer", fontSize: "var(--fs-xs)", fontWeight: "var(--fw-semibold)", color: "var(--text)", listStyle: "none" }}>
        {method === "nli" ? "NLI grounding" : "Lexical grounding"} · {supported}/{grounding.length} claims supported
      </summary>
      <p style={{ margin: "8px 0 10px", fontSize: "var(--fs-xs)", lineHeight: 1.45, color: "var(--muted)" }}>
        {method === "nli"
          ? "Each answer sentence is tested against the retrieved passages with a natural-language-inference model."
          : "Heuristic: a sentence is flagged when too few of its key terms appear in any retrieved passage. It is not proof of grounding."}
      </p>
      <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 8 }}>
        {grounding.map((g, i) => (
          <li
            key={i}
            title={verdictText(g, method)}
            onClick={() => g.supported && jump(g)}
            style={{ display: "flex", gap: 8, alignItems: "flex-start", cursor: g.supported ? "pointer" : "default" }}
          >
            <span aria-hidden style={{ flex: "none", width: 8, height: 8, borderRadius: "50%", marginTop: 6, background: verdictColor(g) }} />
            <span style={{ fontSize: "var(--fs-xs)", lineHeight: 1.5, color: "var(--text)" }}>
              {g.sentence}
              {method === "nli" && g.entailment != null && (
                <span className="tabular-nums" style={{ marginLeft: 6, fontSize: "var(--fs-xs)", fontWeight: "var(--fw-semibold)", color: verdictColor(g) }}>
                  {Math.round(g.entailment * 100)}%
                </span>
              )}
            </span>
          </li>
        ))}
      </ul>
    </details>
  );
}
