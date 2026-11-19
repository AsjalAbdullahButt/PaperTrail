"use client";

import { ResetIcon } from "@/components/ui/Icons";
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
      style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", flexWrap: "wrap", marginTop: "var(--space-3)" }}
    >
      <span className="section-label">NLP pipeline</span>
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
            className="chip"
            title={title}
            aria-pressed={c.active && !disabled}
            disabled={disabled}
            onClick={c.onToggle}
            style={{ minHeight: 28, padding: "0 var(--space-3)" }}
          >
            {c.label}
          </button>
        );
      })}
      {customised && (
        <button
          type="button"
          className="btn btn-ghost btn-sm"
          onClick={() => (["rerank", "expansion", "grounding", "abstain"] as const).forEach((k) => setOption(k, undefined))}
        >
          <ResetIcon size={14} /> server defaults
        </button>
      )}
    </div>
  );
}
