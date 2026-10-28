"use client";

import type { CSSProperties } from "react";
import { useQueryStore } from "@/state/queryStore";

type Chip = {
  key: string;
  label: string;
  hint: string;
  active: boolean;
  available: boolean;
  unavailableHint?: string;
  appliesTo: boolean;
  onToggle: () => void;
};

const chipBase: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: 6,
  padding: "6px 12px",
  borderRadius: 11,
  fontFamily: "inherit",
  fontSize: 12.5,
  fontWeight: 600,
  cursor: "pointer",
  border: "1px solid var(--card-border)",
  color: "var(--muted)",
  background: "var(--seg-bg)",
};

const chipActive: CSSProperties = {
  ...chipBase,
  color: "var(--onAccent)",
  border: "1px solid var(--accent)",
  background: "linear-gradient(135deg,var(--accent),var(--accent2))",
};

/**
 * Per-query switches for the optional NLP pipeline stages: cross-encoder
 * re-ranking, HyDE query expansion, NLI grounding and abstention. The server
 * reports which stages it can run (/api/query/capabilities); unavailable ones are
 * shown disabled with the reason. Unset = the server default.
 */
export default function AdvancedOptions() {
  const mode = useQueryStore((s) => s.mode);
  const caps = useQueryStore((s) => s.capabilities);
  const options = useQueryStore((s) => s.options);
  const setOption = useQueryStore((s) => s.setOption);

  if (!caps || mode === "direct" || mode === "compare") return null;

  const retrievalStages = mode === "rag"; // multi-hop has its own retrieval loop
  const rerank = options.rerank ?? caps.rerank.default;
  const hyde = (options.expansion ?? caps.expansion.default) === "hyde";
  const nli = (options.grounding ?? caps.grounding.default) === "nli";
  const abstain = options.abstain ?? caps.abstain.default;

  const chips: Chip[] = [
    {
      key: "rerank",
      label: "Re-rank",
      hint: `Re-score the top hybrid candidates with a cross-encoder (${caps.rerank.model}) for more precise passages.`,
      active: rerank,
      available: caps.rerank.available,
      unavailableHint: "Needs sentence-transformers on the server.",
      appliesTo: retrievalStages,
      onToggle: () => setOption("rerank", !rerank),
    },
    {
      key: "hyde",
      label: "HyDE",
      hint: "Query expansion: the model writes a hypothetical answer passage and retrieval searches with that instead of the bare question.",
      active: hyde,
      available: caps.expansion.available,
      appliesTo: retrievalStages,
      onToggle: () => setOption("expansion", hyde ? "none" : "hyde"),
    },
    {
      key: "nli",
      label: "NLI grounding",
      hint: `Check every answer sentence with an entailment model (${caps.grounding.model}) instead of the lexical overlap heuristic.`,
      active: nli,
      available: caps.grounding.available,
      unavailableHint: "Needs transformers/torch on the server.",
      appliesTo: true,
      onToggle: () => setOption("grounding", nli ? "lexical" : "nli"),
    },
    {
      key: "abstain",
      label: "Abstain if unsure",
      hint: caps.abstain.calibrated
        ? "Decline to answer when the best retrieved passage is not relevant enough, instead of guessing."
        : "Decline to answer when retrieval confidence is low. The server has no calibrated threshold yet, so this has no effect.",
      active: abstain,
      available: caps.abstain.available,
      appliesTo: true,
      onToggle: () => setOption("abstain", !abstain),
    },
  ];

  const customised = Object.keys(options).length > 0;

  return (
    <div
      role="group"
      aria-label="NLP pipeline options"
      style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", marginTop: 12 }}
    >
      <span style={{ fontSize: 11.5, fontWeight: 700, letterSpacing: ".05em", textTransform: "uppercase", color: "var(--muted)" }}>
        NLP pipeline
      </span>
      {chips.map((c) => {
        const disabled = !c.available || !c.appliesTo;
        const title = !c.available
          ? `${c.label} — unavailable. ${c.unavailableHint ?? ""}`
          : !c.appliesTo
          ? `${c.label} — does not apply in multi-hop mode.`
          : c.hint;
        return (
          <button
            key={c.key}
            type="button"
            title={title}
            aria-pressed={c.active && !disabled}
            disabled={disabled}
            onClick={c.onToggle}
            style={{ ...(c.active && !disabled ? chipActive : chipBase), opacity: disabled ? 0.5 : 1, cursor: disabled ? "not-allowed" : "pointer" }}
          >
            {c.label}
          </button>
        );
      })}
      {customised && (
        <button
          type="button"
          onClick={() => (["rerank", "expansion", "grounding", "abstain"] as const).forEach((k) => setOption(k, undefined))}
          style={{ border: "none", background: "transparent", cursor: "pointer", fontFamily: "inherit", fontSize: 12, fontWeight: 600, color: "var(--muted)" }}
        >
          ↺ server defaults
        </button>
      )}
    </div>
  );
}
