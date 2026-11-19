"use client";

import { useEffect, useRef, useState, type CSSProperties, type RefObject } from "react";
import { createPortal } from "react-dom";
import { useQueryStore } from "@/state/queryStore";
import { useFloatingRect } from "@/hooks/useFloatingRect";
import { renderAnswerWithCitations } from "@/components/query/AnswerCitations";
import SourcePanel from "@/components/query/SourcePanel";
import FollowUpQuestionChips from "@/components/query/FollowUpQuestionChips";
import AdvancedOptions from "@/components/query/AdvancedOptions";
import PipelineBadges from "@/components/query/PipelineBadges";
import type { QueryMode } from "@/api/backendClient";

const SUGGESTIONS = [
  "Summarize the Q3 revenue report",
  "What are the key risks in the vendor contract?",
  "How does onboarding work for new hires?",
];


const segActive: CSSProperties = {
  border: "none", cursor: "pointer", fontFamily: "inherit", fontWeight: "var(--fw-semibold)", fontSize: "var(--fs-sm)",
  padding: "7px 14px", borderRadius: "var(--radius-sm)", color: "var(--on-accent)", background: "var(--accent)",
};
const segIdle: CSSProperties = {
  border: "none", cursor: "pointer", fontFamily: "inherit", fontWeight: "var(--fw-medium)", fontSize: "var(--fs-sm)",
  padding: "7px 14px", borderRadius: "var(--radius-sm)", color: "var(--muted)", background: "transparent",
};

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
    >
      <button onClick={onClick} aria-pressed={active} style={active ? segActive : segIdle}>
        {info.label}
      </button>
      {hover && rect && typeof document !== "undefined" && createPortal(
        <div
          role="tooltip"
          style={{
            position: "fixed",
            top: rect.bottom + 10,
            // Keep the 220px tooltip fully inside the viewport (110px = half its width + margin).
            left: `clamp(118px, ${rect.left + rect.width / 2}px, calc(100vw - 118px))`,
            transform: "translateX(-50%)",
            width: 220,
            padding: "10px 13px",
            borderRadius: "var(--radius-md)",
            background: "var(--overlay)",
            border: "1px solid var(--border)",
            color: "var(--text)",
            fontSize: "var(--fs-xs)",
            lineHeight: 1.5,
            fontWeight: "var(--fw-medium)",
            textAlign: "center",
            zIndex: 1000,
            boxShadow: "var(--shadow-overlay)",
            pointerEvents: "none",
            animation: "rise .15s ease both",
          }}
        >
          {info.description}
        </div>,
        document.body
      )}
    </div>
  );
}

function MagnifierIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--muted)" strokeWidth="2" strokeLinecap="round" style={{ flex: "none", marginLeft: 6 }} aria-hidden>
      <circle cx="11" cy="11" r="7" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  );
}

function SuggestionChip({ q, onPick }: { q: string; onPick: () => void }) {
  return (
    <button
      onClick={onPick}
      style={{
        display: "inline-flex", alignItems: "center", gap: 9, padding: "11px 17px", borderRadius: "var(--radius-md)",
        maxWidth: "100%", textAlign: "left", cursor: "pointer", fontFamily: "inherit", fontWeight: "var(--fw-medium)", fontSize: "var(--fs-sm)", color: "var(--text)",
        background: "var(--surface)", border: "1px solid var(--border)",
      }}
    >
      <span style={{ color: "var(--muted)", fontSize: "var(--fs-sm)" }}>try</span>
      {q}
      <span style={{ color: "var(--accent)", fontWeight: "var(--fw-semibold)" }}>→</span>
    </button>
  );
}

function Spinner() {
  return (
    <span aria-hidden style={{ width: 14, height: 14, borderRadius: "50%", border: "2px solid currentColor", borderTopColor: "transparent", display: "inline-block", animation: "spin .7s linear infinite" }} />
  );
}

function BlinkingCursor() {
  return (
    <span aria-hidden style={{ display: "inline-block", width: 2, height: "1.05em", marginLeft: 2, verticalAlign: "text-bottom", background: "var(--accent)", animation: "blink 1s step-end infinite" }} />
  );
}

function SkeletonCard() {
  return (
    <div style={{ display: "flex", gap: 22, flexWrap: "wrap", alignItems: "flex-start" }}>
      <div style={{ flex: "1 1 520px", minWidth: "min(300px, 100%)", padding: "clamp(20px, 5vw, 30px) clamp(18px, 5vw, 32px)", borderRadius: "var(--radius-md)", background: "var(--surface)", border: "1px solid var(--border)", }}>
        {[92, 88, 80, 60].map((w, i) => (
          <div key={i} style={{ height: 14, width: `${w}%`, borderRadius: "var(--radius-sm)", margin: "0 0 14px", background: "var(--raised)", animation: "var(--anim-pulse)", animationDelay: `${i * 0.1}s` }} />
        ))}
      </div>
      <div style={{ flex: "1 1 300px", minWidth: "min(270px, 100%)", maxWidth: 380, display: "flex", flexDirection: "column", gap: 12 }}>
        {[0, 1].map((i) => (
          <div key={i} style={{ height: 92, borderRadius: "var(--radius-md)", background: "var(--surface)", border: "1px solid var(--border)", animation: "var(--anim-pulse)", animationDelay: `${i * 0.15}s` }} />
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

  function ask(q: string) {
    void runQuery(q, onUnauthorized);
  }

  const accentBtn: CSSProperties = { color: "var(--on-accent)", background: "var(--accent)", };

  return (
    <>
      <div style={{ marginTop: 40 }}>
        <div role="group" aria-label="Answer mode" style={{ display: "flex", gap: 3, padding: 4, borderRadius: "var(--radius-md)", background: "var(--raised)", border: "1px solid var(--border)", marginBottom: 14, width: "fit-content", maxWidth: "100%", flexWrap: "wrap" }}>
          <ModeButton mode="rag" active={mode === "rag"} onClick={() => setMode("rag")} />
          <ModeButton mode="multihop" active={mode === "multihop"} onClick={() => setMode("multihop")} />
          <ModeButton mode="direct" active={mode === "direct"} onClick={() => setMode("direct")} />
          <ModeButton mode="compare" active={mode === "compare"} onClick={() => setMode("compare")} />
        </div>

        <div data-ring-host style={{ display: "flex", alignItems: "center", gap: 10, padding: "9px 10px 9px 16px", borderRadius: "var(--radius-md)", background: "var(--surface)", border: "1px solid var(--border)", boxShadow: "var(--shadow-overlay)" }}>
          <MagnifierIcon />
          <input
            ref={queryInputRef}
            data-bare
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !compareBlocked) ask(query || SUGGESTIONS[0]); }}
            placeholder="Ask anything about your documents…"
            aria-label="Ask a question about your documents"
            style={{ flex: 1, minWidth: 0, background: "transparent", border: "none", outline: "none", fontFamily: "inherit", fontSize: "var(--fs-md)", color: "var(--text)", padding: "2px 4px" }}
          />
          <button
            onClick={() => ask(query || SUGGESTIONS[0])}
            disabled={asking || compareBlocked}
            style={{ display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 7, padding: "11px 20px", borderRadius: "var(--radius-md)", border: "none", cursor: asking || compareBlocked ? "default" : "pointer", fontFamily: "inherit", fontWeight: "var(--fw-medium)", fontSize: "var(--fs-sm)", flex: "none", opacity: asking || compareBlocked ? 0.75 : 1, ...accentBtn }}
          >
            {asking ? <Spinner /> : null}
            {asking ? "Asking…" : "Ask"}
            {!asking && <span style={{ fontSize: "var(--fs-md)", marginTop: -1 }}>→</span>}
          </button>
        </div>
        <AdvancedOptions />
        {conversationHistory.length > 0 && (
          <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 10 }}>
            <button
              onClick={startNewConversation}
              style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "6px 12px", borderRadius: "var(--radius-sm)", border: "none", background: "transparent", cursor: "pointer", fontFamily: "inherit", fontWeight: "var(--fw-medium)", fontSize: "var(--fs-xs)", color: "var(--muted)" }}
            >
              <span aria-hidden>↺</span> New conversation
            </button>
          </div>
        )}
        {error && (
          <div role="alert" style={{ marginTop: 12, padding: "10px 14px", borderRadius: "var(--radius-md)", fontSize: "var(--fs-sm)", color: "var(--danger)", background: "var(--danger-soft)", border: "1px solid var(--danger-line)" }}>
            {error}
          </div>
        )}
      </div>

      {mode === "compare" && (
        <div style={{ marginTop: 16, padding: "14px 16px", borderRadius: "var(--radius-md)", background: "var(--surface)", border: "1px solid var(--border)" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
            <span style={{ fontSize: "var(--fs-xs)", fontWeight: "var(--fw-semibold)", letterSpacing: ".04em", textTransform: "uppercase", color: "var(--muted)" }}>Documents to compare</span>
            {selectedDocIds.length < 2 && (
              <span style={{ fontSize: "var(--fs-xs)", color: "var(--muted)" }}>Select 2+ documents to compare.</span>
            )}
          </div>
          {compareDocs === null && <span style={{ fontSize: "var(--fs-sm)", color: "var(--muted)" }}>Loading documents…</span>}
          {compareDocs !== null && compareDocs.length === 0 && (
            <span style={{ fontSize: "var(--fs-sm)", color: "var(--muted)" }}>Upload at least two documents to use compare mode.</span>
          )}
          {compareDocs !== null && compareDocs.length > 0 && (
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
              {compareDocs.map((d) => {
                const selected = selectedDocIds.includes(d.id);
                return (
                  <button
                    key={d.id}
                    onClick={() => toggleSelectedDoc(d.id)}
                    aria-pressed={selected}
                    style={{ padding: "7px 13px", borderRadius: "var(--radius-md)", cursor: "pointer", fontFamily: "inherit", fontSize: "var(--fs-sm)", fontWeight: "var(--fw-medium)", color: selected ? "var(--on-accent)" : "var(--text)", background: selected ? "var(--accent)" : "var(--raised)", border: `1px solid ${selected ? "var(--accent)" : "var(--border)"}` }}
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
        <div style={{ textAlign: "center", marginTop: "clamp(40px, 12vw, 90px)", animation: "rise .5s ease both" }}>
          <div style={{ display: "inline-flex", alignItems: "center", gap: 7, padding: "6px 13px", borderRadius: "var(--radius-md)", background: "var(--surface)", border: "1px solid var(--border)", fontSize: "var(--fs-xs)", fontWeight: "var(--fw-medium)", color: "var(--muted)", letterSpacing: ".01em" }}>
            <span style={{ width: 7, height: 7, borderRadius: "50%", background: "var(--accent)", }} />
            Grounded in your documents
          </div>
          <h1 style={{ margin: "22px auto 0", maxWidth: 640, fontSize: "clamp(30px, 8vw, 44px)", lineHeight: 1.08, letterSpacing: "-.03em", fontWeight: "var(--fw-semibold)", color: "var(--text)" }}>
            Answers you can trace back<br />to the source.
          </h1>
          <p style={{ margin: "16px auto 0", maxWidth: 500, fontSize: "var(--fs-md)", lineHeight: 1.55, color: "var(--muted)" }}>
            Ask a question and PaperTrail retrieves the exact passages, cites them inline, and shows you how confident it is.
          </p>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 11, justifyContent: "center", marginTop: 34 }}>
            {SUGGESTIONS.map((q) => (
              <SuggestionChip key={q} q={q} onPick={() => ask(q)} />
            ))}
          </div>
        </div>
      )}

      {asking && !hasAnswer && (
        <div style={{ marginTop: 34, animation: "rise .35s ease both" }}>
          <SkeletonCard />
        </div>
      )}

      {hasAnswer && (
        <div style={{ display: "flex", gap: 22, marginTop: 34, flexWrap: "wrap", alignItems: "flex-start", animation: "rise .45s ease both" }}>
          <div style={{ flex: "1 1 520px", minWidth: "min(300px, 100%)", padding: "clamp(20px, 5vw, 30px) clamp(18px, 5vw, 32px)", borderRadius: "var(--radius-md)", background: "var(--surface)", border: "1px solid var(--border)", boxShadow: "var(--shadow-overlay)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 9, marginBottom: 18 }}>
              <div style={{ width: 22, height: 22, borderRadius: "var(--radius-sm)", background: "var(--accent)", flex: "none" }} />
              <span style={{ fontSize: "var(--fs-xs)", fontWeight: "var(--fw-semibold)", letterSpacing: ".04em", textTransform: "uppercase", color: "var(--muted)" }}>
                {answerMode === "direct" ? "Direct answer" : answerMode === "multihop" ? "Multi-hop answer" : answerMode === "compare" ? "Comparison answer" : "Retrieved answer"}
              </span>
              {answerMode !== "direct" && (
                <span className="tabular-nums" style={{ marginLeft: "auto", display: "inline-flex", alignItems: "center", padding: "3px 10px", borderRadius: "var(--radius-md)", fontSize: "var(--fs-xs)", fontWeight: "var(--fw-semibold)", color: "var(--accent)", background: "var(--accent-soft)", border: "1px solid var(--accent-line)" }}>
                  {isStreaming ? "Answering…" : `${confPct}% confidence`}
                </span>
              )}
            </div>
            {abstained && !isStreaming && (
              <div
                role="status"
                data-testid="abstained-banner"
                style={{ marginBottom: 14, padding: "10px 13px", borderRadius: "var(--radius-md)", fontSize: "var(--fs-sm)", lineHeight: 1.5, color: "var(--warn)", background: "var(--warn-soft)", border: "1px solid var(--warn-line)" }}
              >
                ⚠ Declined to answer: the best matching passage scored{" "}
                {pipeline?.retrieval_signal != null ? `${Math.round(pipeline.retrieval_signal * 100)}%` : "low"} relevance, below the
                abstention threshold. The retrieved passages are listed so you can judge for yourself.
              </div>
            )}
            <div style={{ fontSize: "clamp(16px, 4.2vw, 19px)", lineHeight: 1.62, letterSpacing: "-.01em", color: "var(--text)", fontWeight: "var(--fw-regular)", whiteSpace: isStreaming ? "pre-wrap" : undefined }}>
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
              <div style={{ display: "flex", alignItems: "center", gap: 14, marginTop: 26, paddingTop: 18, borderTop: "1px solid var(--border)", flexWrap: "wrap" }}>
                <span style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: "var(--fs-sm)", fontWeight: "var(--fw-medium)", color: "var(--text)" }}>
                  <span style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--accent)", }} />
                  {answerMode === "direct" ? "Direct answer" : abstained ? "Abstained" : confidenceLabel}
                </span>
                <span style={{ width: 4, height: 4, borderRadius: "50%", background: "var(--muted)", opacity: 0.5 }} />
                <span style={{ fontSize: "var(--fs-sm)", color: "var(--muted)" }}>
                  {answerMode === "direct" ? "No retrieval" : `Grounded in ${currentSources.length} source${currentSources.length === 1 ? "" : "s"}`}
                </span>
                <span style={{ width: 4, height: 4, borderRadius: "50%", background: "var(--muted)", opacity: 0.5 }} />
                <span style={{ fontSize: "var(--fs-sm)", color: "var(--muted)" }}>answered in {timing.toFixed(1)}s</span>
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
