"use client";

import { useEffect, useRef, useState, type RefObject } from "react";
import { createPortal } from "react-dom";
import { useQueryStore } from "@/state/queryStore";
import { useFloatingRect } from "@/hooks/useFloatingRect";
import { renderAnswerWithCitations } from "@/components/query/AnswerCitations";
import SourcePanel from "@/components/query/SourcePanel";
import FollowUpQuestionChips from "@/components/query/FollowUpQuestionChips";
import AdvancedOptions from "@/components/query/AdvancedOptions";
import PipelineBadges from "@/components/query/PipelineBadges";
import { ArrowRightIcon, ResetIcon, SearchIcon, WarningIcon } from "@/components/ui/Icons";
import type { QueryMode } from "@/api/backendClient";

// Example questions. They show what the app is for and are also the default
// question when Ask is pressed with an empty box.
const SUGGESTIONS = [
  "Summarize the Q3 revenue report",
  "What are the key risks in the vendor contract?",
  "How does onboarding work for new hires?",
];

const MODE_INFO: Record<QueryMode, { label: string; description: string }> = {
  rag: { label: "RAG", description: "Searches your documents for the most relevant passages and grounds the answer in them, with citations." },
  multihop: { label: "Multi-hop", description: "Chains several retrieval steps together to connect facts that are spread across multiple documents." },
  direct: { label: "Direct", description: "Skips retrieval entirely and answers straight from the model's own knowledge, ungrounded." },
  compare: { label: "Compare", description: "Retrieves passages from each selected document separately and explicitly compares them by name." },
};

function ModeButton({ mode, active, onClick }: { mode: QueryMode; active: boolean; onClick: () => void }) {
  const [hover, setHover] = useState(false);
  const anchorRef = useRef<HTMLDivElement>(null);
  const rect = useFloatingRect(anchorRef, hover);
  const info = MODE_INFO[mode];
  return (
    <div
      ref={anchorRef}
      style={{ position: "relative" }}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      onFocus={() => setHover(true)}
      onBlur={() => setHover(false)}
    >
      <button type="button" className="seg-item" onClick={onClick} aria-pressed={active}>
        {info.label}
      </button>
      {hover && rect && typeof document !== "undefined" && createPortal(
        <div
          role="tooltip"
          className="menu"
          style={{
            position: "fixed",
            top: rect.bottom + 8,
            // Keep the 240px tooltip fully inside the viewport (120px = half its width, plus a margin).
            left: `clamp(128px, ${rect.left + rect.width / 2}px, calc(100vw - 128px))`,
            transform: "translateX(-50%)",
            width: 240,
            padding: "var(--space-3)",
            fontSize: "var(--fs-xs)",
            lineHeight: 1.5,
            color: "var(--text)",
            zIndex: 1000,
            pointerEvents: "none",
            animation: "rise var(--dur-fast) var(--ease) both",
          }}
        >
          {info.description}
        </div>,
        document.body
      )}
    </div>
  );
}

function BlinkingCursor() {
  return (
    <span aria-hidden style={{ display: "inline-block", width: 2, height: "1.05em", marginLeft: 2, verticalAlign: "text-bottom", background: "var(--accent)", animation: "blink 1s step-end infinite" }} />
  );
}

function SkeletonCard() {
  return (
    <div className="answer-grid">
      <div className="card">
        {[92, 88, 80, 60].map((w, i) => (
          <div key={i} className="skeleton" style={{ height: 14, width: `${w}%`, marginBottom: "var(--space-3)", animationDelay: `${i * 0.1}s` }} />
        ))}
      </div>
      <div className="stack" style={{ gap: "var(--space-3)" }}>
        {[0, 1].map((i) => (
          <div key={i} className="card skeleton" style={{ height: 92, animationDelay: `${i * 0.15}s` }} />
        ))}
      </div>
    </div>
  );
}

export default function QueryPanel({
  queryInputRef,
  onUnauthorized,
}: {
  queryInputRef: RefObject<HTMLInputElement | null>;
  onUnauthorized: () => void;
}) {
  const mode = useQueryStore((s) => s.mode);
  const setMode = useQueryStore((s) => s.setMode);
  const query = useQueryStore((s) => s.query);
  const setQuery = useQueryStore((s) => s.setQuery);
  const asking = useQueryStore((s) => s.asking);
  const isStreaming = useQueryStore((s) => s.isStreaming);
  const error = useQueryStore((s) => s.error);
  const hasAnswer = useQueryStore((s) => s.hasAnswer);
  const currentAnswer = useQueryStore((s) => s.currentAnswer);
  const currentSources = useQueryStore((s) => s.currentSources);
  const confidenceScore = useQueryStore((s) => s.confidenceScore);
  const followupQuestions = useQueryStore((s) => s.followupQuestions);
  const unsupportedSentences = useQueryStore((s) => s.unsupportedSentences);
  const grounding = useQueryStore((s) => s.grounding);
  const abstained = useQueryStore((s) => s.abstained);
  const pipeline = useQueryStore((s) => s.pipeline);
  const loadCapabilities = useQueryStore((s) => s.loadCapabilities);
  const answerMode = useQueryStore((s) => s.answerMode);
  const timing = useQueryStore((s) => s.timing);
  const conversationHistory = useQueryStore((s) => s.conversationHistory);
  const selectedDocIds = useQueryStore((s) => s.selectedDocIds);
  const toggleSelectedDoc = useQueryStore((s) => s.toggleSelectedDoc);
  const compareDocs = useQueryStore((s) => s.compareDocs);
  const loadCompareDocsIfNeeded = useQueryStore((s) => s.loadCompareDocsIfNeeded);
  const startNewConversation = useQueryStore((s) => s.startNewConversation);
  const runQuery = useQueryStore((s) => s.runQuery);

  useEffect(() => {
    if (mode === "compare") void loadCompareDocsIfNeeded();
  }, [mode, loadCompareDocsIfNeeded]);

  useEffect(() => {
    void loadCapabilities();
  }, [loadCapabilities]);

  const compareBlocked = mode === "compare" && selectedDocIds.length < 2;
  const confPct = Math.round(confidenceScore * 100);
  const confidenceLabel = confPct >= 75 ? "High confidence" : confPct >= 50 ? "Moderate" : "Low confidence";
  // Colour follows the word: teal only for a good result, amber for a weak one,
  // neutral in between. The label stays the main signal.
  const confTone = confPct >= 75 ? "high" : confPct >= 50 ? "mid" : "low";
  const confChip = confTone === "high" ? "chip-accent" : confTone === "low" ? "chip-warn" : "";
  const confDot = abstained || confTone === "low" ? "var(--warn)" : confTone === "high" ? "var(--accent)" : "var(--text-2)";

  function ask(q: string) {
    void runQuery(q, onUnauthorized);
  }

  const heading =
    answerMode === "direct" ? "Direct answer" : answerMode === "multihop" ? "Multi-hop answer" : answerMode === "compare" ? "Comparison answer" : "Retrieved answer";

  return (
    <>
      <div style={{ marginTop: "var(--space-6)" }}>
        <div role="group" aria-label="Answer mode" className="seg" style={{ marginBottom: "var(--space-3)" }}>
          <ModeButton mode="rag" active={mode === "rag"} onClick={() => setMode("rag")} />
          <ModeButton mode="multihop" active={mode === "multihop"} onClick={() => setMode("multihop")} />
          <ModeButton mode="direct" active={mode === "direct"} onClick={() => setMode("direct")} />
          <ModeButton mode="compare" active={mode === "compare"} onClick={() => setMode("compare")} />
        </div>

        <div data-ring-host className="query-bar">
          <SearchIcon size={18} />
          <input
            ref={queryInputRef}
            data-bare
            className="query-input"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !compareBlocked) ask(query || SUGGESTIONS[0]); }}
            placeholder="Ask anything about your documents…"
            aria-label="Ask a question about your documents"
          />
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => ask(query || SUGGESTIONS[0])}
            disabled={asking || compareBlocked}
            style={{ flex: "none" }}
          >
            {asking ? <span className="spinner" aria-hidden="true" /> : null}
            {asking ? "Asking…" : "Ask"}
            {!asking && <ArrowRightIcon />}
          </button>
        </div>
        <AdvancedOptions />
        {conversationHistory.length > 0 && (
          <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "var(--space-2)" }}>
            <button type="button" className="btn btn-ghost btn-sm" onClick={startNewConversation}>
              <ResetIcon /> New conversation
            </button>
          </div>
        )}
        {error && (
          <div role="alert" className="alert alert-danger" style={{ marginTop: "var(--space-3)" }}>
            {error}
          </div>
        )}
      </div>

      {mode === "compare" && (
        <div className="card card-compact" style={{ marginTop: "var(--space-4)" }}>
          <div className="row" style={{ justifyContent: "space-between", marginBottom: "var(--space-3)" }}>
            <span className="section-label">Documents to compare</span>
            {selectedDocIds.length < 2 && <span className="meta">Select 2+ documents to compare.</span>}
          </div>
          {compareDocs === null && <span className="meta" style={{ fontSize: "var(--fs-sm)" }}>Loading documents…</span>}
          {compareDocs !== null && compareDocs.length === 0 && (
            <span className="meta" style={{ fontSize: "var(--fs-sm)" }}>Upload at least two documents to use compare mode.</span>
          )}
          {compareDocs !== null && compareDocs.length > 0 && (
            <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-2)" }}>
              {compareDocs.map((d) => {
                const selected = selectedDocIds.includes(d.id);
                return (
                  <button
                    key={d.id}
                    type="button"
                    className={`btn btn-sm${selected ? " btn-primary" : ""}`}
                    onClick={() => toggleSelectedDoc(d.id)}
                    aria-pressed={selected}
                  >
                    {d.filename}
                  </button>
                );
              })}
            </div>
          )}
        </div>
      )}

      {!hasAnswer && !asking && (
        <div className="hero">
          <h1>Answers you can trace back to the source</h1>
          <p>Ask a question and PaperTrail retrieves the exact passages, cites them inline, and shows you how confident it is.</p>
          <div className="section-label" style={{ marginTop: "var(--space-5)" }}>Example questions</div>
          <div className="hero-examples" style={{ marginTop: "var(--space-2)" }}>
            {SUGGESTIONS.map((q) => (
              <button key={q} type="button" className="btn btn-wrap" onClick={() => ask(q)}>
                {q}
              </button>
            ))}
          </div>
        </div>
      )}

      {asking && !hasAnswer && (
        <div style={{ marginTop: "var(--space-5)" }}>
          <SkeletonCard />
        </div>
      )}

      {hasAnswer && (
        <div className="answer-grid">
          <div className="card">
            <div className="row" style={{ marginBottom: "var(--space-4)" }}>
              <span className="section-label">{heading}</span>
              {answerMode !== "direct" && (
                <span className={`chip tabular-nums ${isStreaming ? "" : confChip}`} style={{ marginLeft: "auto" }}>
                  {isStreaming ? "Answering…" : `${confPct}% confidence`}
                </span>
              )}
            </div>
            {abstained && !isStreaming && (
              <div role="status" data-testid="abstained-banner" className="alert alert-warn" style={{ marginBottom: "var(--space-4)" }}>
                <WarningIcon style={{ marginTop: 2 }} />
                <span>
                  Declined to answer: the best matching passage scored{" "}
                  {pipeline?.retrieval_signal != null ? `${Math.round(pipeline.retrieval_signal * 100)}%` : "low"} relevance, below the
                  abstention threshold. The retrieved passages are listed so you can judge for yourself.
                </span>
              </div>
            )}
            <div className="answer-text" style={{ whiteSpace: isStreaming ? "pre-wrap" : undefined }}>
              {isStreaming ? (
                <>
                  {currentAnswer}
                  <BlinkingCursor />
                </>
              ) : (
                renderAnswerWithCitations(currentAnswer, currentSources.length)
              )}
            </div>
            {!isStreaming && (
              <div className="row" style={{ gap: "var(--space-3)", marginTop: "var(--space-5)", paddingTop: "var(--space-4)", borderTop: "1px solid var(--border)", flexWrap: "wrap", fontSize: "var(--fs-sm)" }}>
                <span className="row" style={{ gap: "var(--space-2)", fontWeight: "var(--fw-medium)", color: "var(--text)" }}>
                  <span aria-hidden style={{ width: 8, height: 8, borderRadius: "50%", background: answerMode === "direct" ? "var(--text-2)" : confDot }} />
                  {answerMode === "direct" ? "Direct answer" : abstained ? "Abstained" : confidenceLabel}
                </span>
                <span aria-hidden style={{ color: "var(--muted)" }}>·</span>
                <span style={{ color: "var(--text-2)" }}>
                  {answerMode === "direct" ? "No retrieval" : `Grounded in ${currentSources.length} source${currentSources.length === 1 ? "" : "s"}`}
                </span>
                <span aria-hidden style={{ color: "var(--muted)" }}>·</span>
                <span style={{ color: "var(--text-2)" }}>answered in {timing.toFixed(1)}s</span>
              </div>
            )}
            {!isStreaming && answerMode !== "direct" && <PipelineBadges pipeline={pipeline} />}
            {!isStreaming && <FollowUpQuestionChips questions={followupQuestions} onPick={ask} />}
          </div>

          <SourcePanel
            sources={currentSources}
            confidenceScore={confidenceScore}
            unsupportedSentences={unsupportedSentences}
            mode={answerMode}
            isStreaming={isStreaming}
            grounding={grounding}
            groundingMethod={pipeline?.grounding_method ?? "lexical"}
          />
        </div>
      )}
    </>
  );
}
