import { describe, it, expect, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AdvancedOptions from "./AdvancedOptions";
import GroundingPanel from "./GroundingPanel";
import PipelineBadges from "./PipelineBadges";
import { useQueryStore } from "@/state/queryStore";
import type { GroundingSentence, PipelineInfo, QueryCapabilities, Source } from "@/api/backendClient";

const initial = useQueryStore.getState();

const caps: QueryCapabilities = {
  rerank: { available: true, default: false, model: "cross-encoder/ms-marco-MiniLM-L-6-v2" },
  expansion: { available: true, default: "none", options: ["none", "hyde"] },
  grounding: { available: false, default: "lexical", options: ["lexical"], model: "cross-encoder/nli-deberta-v3-small" },
  abstain: { available: true, default: false, calibrated: true },
  contextual_chunk_headers: false,
};

describe("AdvancedOptions", () => {
  beforeEach(() => useQueryStore.setState(initial, true));

  it("renders nothing until the server capabilities are known", () => {
    const { container } = render(<AdvancedOptions />);
    expect(container).toBeEmptyDOMElement();
  });

  it("toggles a stage on, stores it as a per-query option, and can reset to server defaults", async () => {
    useQueryStore.setState({ capabilities: caps });
    render(<AdvancedOptions />);
    const rerank = screen.getByRole("button", { name: "Re-rank" });
    expect(rerank).toHaveAttribute("aria-pressed", "false");

    await userEvent.click(rerank);
    expect(useQueryStore.getState().options.rerank).toBe(true);
    expect(screen.getByRole("button", { name: "Re-rank" })).toHaveAttribute("aria-pressed", "true");

    await userEvent.click(screen.getByRole("button", { name: /server defaults/i }));
    expect(useQueryStore.getState().options).toEqual({});
  });

  it("disables a stage the server cannot run and explains why", () => {
    useQueryStore.setState({ capabilities: caps });
    render(<AdvancedOptions />);
    const nli = screen.getByRole("button", { name: "NLI grounding" });
    expect(nli).toBeDisabled();
    expect(nli).toHaveAttribute("title", expect.stringContaining("unavailable"));
  });

  it("hides itself in direct and compare modes", () => {
    useQueryStore.setState({ capabilities: caps, mode: "direct" });
    const { container } = render(<AdvancedOptions />);
    expect(container).toBeEmptyDOMElement();
  });

  it("disables retrieval-side stages in multi-hop mode", () => {
    useQueryStore.setState({ capabilities: caps, mode: "multihop" });
    render(<AdvancedOptions />);
    expect(screen.getByRole("button", { name: "Re-rank" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "HyDE" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Abstain if unsure" })).toBeEnabled();
  });
});

const sources = [{ n: 1, chunk_id: "c1" }] as Source[];
const grounding: GroundingSentence[] = [
  { sentence: "The model has eight heads.", supported: true, source_chunk_id: "c1", entailment: 0.97, contradiction: 0.01, label: "entailed" },
  { sentence: "It was trained on a million GPUs.", supported: false, source_chunk_id: null, entailment: 0.04, contradiction: 0.6, label: "contradicted" },
];

describe("GroundingPanel", () => {
  it("summarises supported claims and shows entailment percentages for NLI", () => {
    render(<GroundingPanel grounding={grounding} method="nli" sources={sources} />);
    expect(screen.getByText(/NLI grounding · 1\/2 claims supported/)).toBeInTheDocument();
    expect(screen.getByText("97%")).toBeInTheDocument();
    expect(screen.getByText("4%")).toBeInTheDocument();
  });

  it("labels the lexical method as a heuristic and hides percentages", () => {
    render(
      <GroundingPanel
        grounding={grounding.map((g) => ({ ...g, entailment: null, label: null }))}
        method="lexical"
        sources={sources}
      />,
    );
    expect(screen.getByText(/Lexical grounding/)).toBeInTheDocument();
    expect(screen.getByText(/not proof of grounding/i)).toBeInTheDocument();
    expect(screen.queryByText("97%")).not.toBeInTheDocument();
  });

  it("renders nothing when there is no grounding data", () => {
    const { container } = render(<GroundingPanel grounding={[]} method="nli" sources={sources} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("PipelineBadges", () => {
  const base: PipelineInfo = {
    reranked: false, expansion: "none", grounding_method: "lexical", abstention_checked: false,
    retrieval_signal: 0.4, signal_kind: "dense", notes: [],
  };

  it("lists only the stages that actually ran", () => {
    render(<PipelineBadges pipeline={{ ...base, reranked: true, expansion: "hyde", grounding_method: "nli" }} />);
    for (const label of ["Hybrid retrieval", "Cross-encoder re-rank", "HyDE query expansion", "NLI grounding"]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
    expect(screen.queryByText("Lexical grounding")).not.toBeInTheDocument();
  });

  it("surfaces fallback notes so a skipped stage is never silent", () => {
    render(<PipelineBadges pipeline={{ ...base, notes: ["Re-ranking skipped: sentence-transformers is not installed on the server."] }} />);
    expect(screen.getByText(/Re-ranking skipped/)).toBeInTheDocument();
    expect(screen.getByText("Lexical grounding")).toBeInTheDocument();
  });

  it("renders nothing without pipeline info", () => {
    const { container } = render(<PipelineBadges pipeline={null} />);
    expect(container).toBeEmptyDOMElement();
  });
});
