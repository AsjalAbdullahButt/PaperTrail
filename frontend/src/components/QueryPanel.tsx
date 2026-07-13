"use client";

import { useEffect, useRef, useState, type CSSProperties, type RefObject } from "react";
import { createPortal } from "react-dom";
import { useQueryStore } from "@/stores/queryStore";
import { useFloatingRect } from "@/hooks/useFloatingRect";
import { renderAnswerWithCitations } from "@/components/Citations";
import SourcePanel from "@/components/SourcePanel";
import FollowUpChips from "@/components/FollowUpChips";
import type { QueryMode } from "@/lib/api";

const SUGGESTIONS = [
  "Summarize the Q3 revenue report",
  "What are the key risks in the vendor contract?",
  "How does onboarding work for new hires?",
];

const ACCENT_GRADIENT = "linear-gradient(135deg,var(--accent),var(--accent2))";

const segActive: CSSProperties = {
  border: "none", cursor: "pointer", fontFamily: "inherit", fontWeight: 700, fontSize: 13,
  padding: "7px 14px", borderRadius: 10, color: "var(--onAccent)", background: ACCENT_GRADIENT,
  boxShadow: "0 3px 10px var(--accentGlow)",
};
const segIdle: CSSProperties = {
  border: "none", cursor: "pointer", fontFamily: "inherit", fontWeight: 600, fontSize: 13,
  padding: "7px 14px", borderRadius: 10, color: "var(--muted)", background: "transparent",
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
            left: rect.left + rect.width / 2,
            transform: "translateX(-50%)",
            width: 220,
            padding: "10px 13px",
            borderRadius: 12,
            background: "var(--menu-bg)",
            border: "1px solid var(--card-border)",
            color: "var(--text)",
            fontSize: 12.5,
            lineHeight: 1.5,
            fontWeight: 500,
            textAlign: "center",
            zIndex: 1000,
            boxShadow: "0 12px 30px var(--cardShadow)",
            backdropFilter: "blur(18px) saturate(140%)",
            WebkitBackdropFilter: "blur(18px) saturate(140%)",
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
        display: "inline-flex", alignItems: "center", gap: 9, padding: "11px 17px", borderRadius: 14,
        cursor: "pointer", fontFamily: "inherit", fontWeight: 500, fontSize: 14, color: "var(--text)",
        background: "var(--card-bg)", border: "1px solid var(--card-border)",
        backdropFilter: "blur(14px) saturate(140%)", WebkitBackdropFilter: "blur(14px)",
      }}
    >
      <span style={{ color: "var(--muted)", fontSize: 13 }}>try</span>
      {q}
      <span style={{ color: "var(--accent)", fontWeight: 700 }}>→</span>
    </button>
  );
}

function Spinner() {
  return (
    <span aria-hidden style={{ width: 14, height: 14, borderRadius: "50%", border: "2px solid rgba(255,255,255,.45)", borderTopColor: "#fff", display: "inline-block", animation: "spin .7s linear infinite" }} />
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
      <div style={{ flex: "1 1 520px", minWidth: 300, padding: "30px 32px", borderRadius: 22, background: "var(--card-bg)", border: "1px solid var(--card-border)", backdropFilter: "blur(22px)" }}>
        {[92, 88, 80, 60].map((w, i) => (
          <div key={i} style={{ height: 14, width: `${w}%`, borderRadius: 7, margin: "0 0 14px", background: "var(--seg-bg)", animation: "pulse 1.2s ease-in-out infinite", animationDelay: `${i * 0.1}s` }} />
        ))}
      </div>
      <div style={{ flex: "1 1 300px", minWidth: 270, maxWidth: 380, display: "flex", flexDirection: "column", gap: 12 }}>
        {[0, 1].map((i) => (
          <div key={i} style={{ height: 92, borderRadius: 16, background: "var(--card-bg)", border: "1px solid var(--card-border)", animation: "pulse 1.2s ease-in-out infinite", animationDelay: `${i * 0.15}s` }} />
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

  const compareBlocked = mode === "compare" && selectedDocIds.length < 2;
  const confPct = Math.round(confidenceScore * 100);
  const confidenceLabel = confPct >= 75 ? "High confidence" : confPct >= 50 ? "Moderate" : "Low confidence";

  function ask(q: string) {
    void runQuery(q, onUnauthorized);
  }

  const accentBtn: CSSProperties = { color: "var(--onAccent)", background: ACCENT_GRADIENT, boxShadow: "0 4px 14px var(--accentGlow)" };

  return (
    <>
      <div style={{ marginTop: 40 }}>
        <div role="group" aria-label="Answer mode" style={{ display: "flex", gap: 3, padding: 4, borderRadius: 13, background: "var(--seg-bg)", border: "1px solid var(--card-border)", marginBottom: 14, width: "fit-content" }}>
          <ModeButton mode="rag" active={mode === "rag"} onClick={() => setMode("rag")} />
          <ModeButton mode="multihop" active={mode === "multihop"} onClick={() => setMode("multihop")} />
          <ModeButton mode="direct" active={mode === "direct"} onClick={() => setMode("direct")} />
          <ModeButton mode="compare" active={mode === "compare"} onClick={() => setMode("compare")} />
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "9px 10px 9px 16px", borderRadius: 20, background: "var(--card-bg)", border: "1px solid var(--card-border)", backdropFilter: "blur(22px) saturate(150%)", WebkitBackdropFilter: "blur(22px) saturate(150%)", boxShadow: "0 14px 40px var(--cardShadow)" }}>
          <MagnifierIcon />
          <input
            ref={queryInputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !compareBlocked) ask(query || SUGGESTIONS[0]); }}
            placeholder="Ask anything about your documents…"
            aria-label="Ask a question about your documents"
            style={{ flex: 1, minWidth: 0, background: "transparent", border: "none", outline: "none", fontFamily: "inherit", fontSize: 16.5, color: "var(--text)", padding: "2px 4px" }}
          />
          <button
            onClick={() => ask(query || SUGGESTIONS[0])}
            disabled={asking || compareBlocked}
            style={{ display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 7, padding: "11px 20px", borderRadius: 14, border: "none", cursor: asking || compareBlocked ? "default" : "pointer", fontFamily: "inherit", fontWeight: 600, fontSize: 14, flex: "none", opacity: asking || compareBlocked ? 0.75 : 1, ...accentBtn }}
          >
            {asking ? <Spinner /> : null}
            {asking ? "Asking…" : "Ask"}
            {!asking && <span style={{ fontSize: 15, marginTop: -1 }}>→</span>}
          </button>
        </div>
        {conversationHistory.length > 0 && (
          <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 10 }}>
            <button
              onClick={startNewConversation}
              style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "6px 12px", borderRadius: 10, border: "none", background: "transparent", cursor: "pointer", fontFamily: "inherit", fontWeight: 600, fontSize: 12.5, color: "var(--muted)" }}
            >
              <span aria-hidden>↺</span> New conversation
            </button>
          </div>
        )}
        {error && (
          <div role="alert" style={{ marginTop: 12, padding: "10px 14px", borderRadius: 12, fontSize: 13.5, color: "#ff8a80", background: "rgba(255,80,80,.10)", border: "1px solid rgba(255,120,120,.35)" }}>
            {error}
          </div>
        )}
      </div>

      {mode === "compare" && (
        <div style={{ marginTop: 16, padding: "14px 16px", borderRadius: 16, background: "var(--card-bg)", border: "1px solid var(--card-border)" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
            <span style={{ fontSize: 12.5, fontWeight: 700, letterSpacing: ".04em", textTransform: "uppercase", color: "var(--muted)" }}>Documents to compare</span>
            {selectedDocIds.length < 2 && (
              <span style={{ fontSize: 12.5, color: "var(--muted)" }}>Select 2+ documents to compare.</span>
            )}
          </div>
          {compareDocs === null && <span style={{ fontSize: 13, color: "var(--muted)" }}>Loading documents…</span>}
          {compareDocs !== null && compareDocs.length === 0 && (
            <span style={{ fontSize: 13, color: "var(--muted)" }}>Upload at least two documents to use compare mode.</span>
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
                    style={{ padding: "7px 13px", borderRadius: 12, cursor: "pointer", fontFamily: "inherit", fontSize: 13, fontWeight: 600, color: selected ? "var(--onAccent)" : "var(--text)", background: selected ? ACCENT_GRADIENT : "var(--seg-bg)", border: `1px solid ${selected ? "var(--accent)" : "var(--card-border)"}` }}
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
        <div style={{ textAlign: "center", marginTop: 90, animation: "rise .5s ease both" }}>
          <div style={{ display: "inline-flex", alignItems: "center", gap: 7, padding: "6px 13px", borderRadius: 20, background: "var(--card-bg)", border: "1px solid var(--card-border)", backdropFilter: "blur(14px)", fontSize: 12.5, fontWeight: 600, color: "var(--muted)", letterSpacing: ".01em" }}>
            <span style={{ width: 7, height: 7, borderRadius: "50%", background: "var(--accent)", boxShadow: "0 0 8px var(--accent)" }} />
            Grounded in your documents
          </div>
          <h1 style={{ margin: "22px auto 0", maxWidth: 640, fontSize: 44, lineHeight: 1.08, letterSpacing: "-.03em", fontWeight: 800, color: "var(--text)" }}>
            Answers you can trace back<br />to the source.
          </h1>
          <p style={{ margin: "16px auto 0", maxWidth: 500, fontSize: 16, lineHeight: 1.55, color: "var(--muted)" }}>
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
          <div style={{ flex: "1 1 520px", minWidth: 300, padding: "30px 32px", borderRadius: 22, background: "var(--card-bg)", border: "1px solid var(--card-border)", backdropFilter: "blur(22px) saturate(150%)", WebkitBackdropFilter: "blur(22px) saturate(150%)", boxShadow: "0 18px 50px var(--cardShadow)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 9, marginBottom: 18 }}>
              <div style={{ width: 22, height: 22, borderRadius: 7, background: ACCENT_GRADIENT, flex: "none" }} />
              <span style={{ fontSize: 12.5, fontWeight: 700, letterSpacing: ".04em", textTransform: "uppercase", color: "var(--muted)" }}>
                {answerMode === "direct" ? "Direct answer" : answerMode === "multihop" ? "Multi-hop answer" : answerMode === "compare" ? "Comparison answer" : "Retrieved answer"}
              </span>
              {answerMode !== "direct" && (
                <span style={{ marginLeft: "auto", display: "inline-flex", alignItems: "center", padding: "3px 10px", borderRadius: 20, fontSize: 12, fontWeight: 700, color: "var(--accent)", background: "var(--chip-bg)", border: "1px solid var(--chip-border)" }}>
                  {isStreaming ? "Answering…" : `${confPct}% confidence`}
                </span>
              )}
            </div>
            <div style={{ fontSize: 19, lineHeight: 1.62, letterSpacing: "-.01em", color: "var(--text)", fontWeight: 400, whiteSpace: isStreaming ? "pre-wrap" : undefined }}>
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
              <div style={{ display: "flex", alignItems: "center", gap: 14, marginTop: 26, paddingTop: 18, borderTop: "1px solid var(--card-border)", flexWrap: "wrap" }}>
                <span style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: 13, fontWeight: 600, color: "var(--text)" }}>
                  <span style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--accent)", boxShadow: "0 0 8px var(--accent)" }} />
                  {answerMode === "direct" ? "Direct answer" : confidenceLabel}
                </span>
                <span style={{ width: 4, height: 4, borderRadius: "50%", background: "var(--muted)", opacity: 0.5 }} />
                <span style={{ fontSize: 13, color: "var(--muted)" }}>
                  {answerMode === "direct" ? "No retrieval" : `Grounded in ${currentSources.length} source${currentSources.length === 1 ? "" : "s"}`}
                </span>
                <span style={{ width: 4, height: 4, borderRadius: "50%", background: "var(--muted)", opacity: 0.5 }} />
                <span style={{ fontSize: 13, color: "var(--muted)" }}>answered in {timing.toFixed(1)}s</span>
              </div>
            )}
            {!isStreaming && <FollowUpChips questions={followupQuestions} onPick={ask} />}
          </div>

          <SourcePanel
            sources={currentSources}
            confidenceScore={confidenceScore}
            unsupportedSentences={unsupportedSentences}
            mode={answerMode}
            isStreaming={isStreaming}
          />
        </div>
      )}
    </>
  );
}
