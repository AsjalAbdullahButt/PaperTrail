"use client";

import {
  useRef,
  useState,
  type ChangeEvent,
  type CSSProperties,
} from "react";
import {
  ApiError,
  askQuery,
  logout,
  uploadDocument,
  type QueryResponse,
  type Source,
} from "@/lib/api";
import { useAuthState } from "@/lib/useAuth";
import AuthScreen from "@/components/AuthScreen";
import DocumentManager from "@/components/DocumentManager";
import ChatHistoryPanel from "@/components/ChatHistoryPanel";
import { renderAnswerWithCitations } from "@/components/Citations";

/* ----------------------------- Theme tokens ------------------------------ */
type ThemeVars = Record<string, string>;

const THEMES: Record<"dark" | "light", ThemeVars> = {
  dark: {
    "--bg":
      "radial-gradient(1200px 800px at 20% 0%, #14161d 0%, #0a0b0f 55%, #08090c 100%)",
    "--text": "#f3f4f7",
    "--muted": "rgba(243,244,247,.55)",
    "--onAccent": "#08130f",
    "--card-bg": "rgba(255,255,255,.045)",
    "--card-border": "rgba(255,255,255,.10)",
    "--seg-bg": "rgba(255,255,255,.05)",
    "--doc-bg": "rgba(255,255,255,.05)",
    "--accent": "#34d399",
    "--accent2": "#a78bfa",
    "--accentGlow": "rgba(52,211,153,.28)",
    "--chip-bg": "rgba(52,211,153,.13)",
    "--chip-border": "rgba(52,211,153,.30)",
    "--blob1": "#10b981",
    "--blob2": "#8b5cf6",
    "--blob3": "#22d3ee",
    "--blobOp": ".22",
    "--blobOp3": ".12",
    "--cardShadow": "rgba(0,0,0,.5)",
    "--sel": "rgba(52,211,153,.3)",
  },
  light: {
    "--bg":
      "radial-gradient(1200px 800px at 15% -5%, #ffffff 0%, #f4f5f2 55%, #eef0ec 100%)",
    "--text": "#171a20",
    "--muted": "rgba(23,26,32,.55)",
    "--onAccent": "#ffffff",
    "--card-bg": "rgba(255,255,255,.58)",
    "--card-border": "rgba(20,25,35,.09)",
    "--seg-bg": "rgba(20,25,35,.05)",
    "--doc-bg": "rgba(255,255,255,.7)",
    "--accent": "#0d9488",
    "--accent2": "#4f46e5",
    "--accentGlow": "rgba(13,148,136,.22)",
    "--chip-bg": "rgba(13,148,136,.11)",
    "--chip-border": "rgba(13,148,136,.28)",
    "--blob1": "#2dd4bf",
    "--blob2": "#6366f1",
    "--blob3": "#5eead4",
    "--blobOp": ".30",
    "--blobOp3": ".20",
    "--cardShadow": "rgba(30,40,60,.12)",
    "--sel": "rgba(13,148,136,.2)",
  },
};

const SUGGESTIONS = [
  "Summarize the Q3 revenue report",
  "What are the key risks in the vendor contract?",
  "How does onboarding work for new hires?",
];

const ACCENT_GRADIENT = "linear-gradient(135deg,var(--accent),var(--accent2))";

/* ------------------------------ Small parts ------------------------------ */
function MagnifierIcon() {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="var(--muted)"
      strokeWidth="2"
      strokeLinecap="round"
      style={{ flex: "none", marginLeft: 6 }}
      aria-hidden
    >
      <circle cx="11" cy="11" r="7" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  );
}

function SuggestionChip({ q, onPick }: { q: string; onPick: () => void }) {
  const [hover, setHover] = useState(false);
  return (
    <button
      onClick={onPick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 9,
        padding: "11px 17px",
        borderRadius: 14,
        cursor: "pointer",
        fontFamily: "inherit",
        fontWeight: 500,
        fontSize: 14,
        color: "var(--text)",
        background: "var(--card-bg)",
        border: `1px solid ${hover ? "var(--accent)" : "var(--card-border)"}`,
        backdropFilter: "blur(14px) saturate(140%)",
        WebkitBackdropFilter: "blur(14px)",
        transform: hover ? "translateY(-1px)" : "none",
        transition: "transform .15s ease, border-color .15s ease",
      }}
    >
      <span style={{ color: "var(--muted)", fontSize: 13 }}>try</span>
      {q}
      <span style={{ color: "var(--accent)", fontWeight: 700 }}>→</span>
    </button>
  );
}

function SourceCard({ src }: { src: Source }) {
  const [hover, setHover] = useState(false);
  const typeLabel = `${src.title.split(".").pop()?.toUpperCase() || "DOC"} · chunk ${
    src.chunk_index + 1
  }`;
  return (
    <div
      id={`src-${src.n}`}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        padding: "16px 17px",
        borderRadius: 16,
        background: "var(--card-bg)",
        border: `1px solid ${hover ? "var(--accent)" : "var(--card-border)"}`,
        backdropFilter: "blur(18px) saturate(140%)",
        WebkitBackdropFilter: "blur(18px) saturate(140%)",
        boxShadow: "0 8px 24px var(--cardShadow)",
        transition: "border-color .15s ease",
      }}
    >
      <div style={{ display: "flex", alignItems: "flex-start", gap: 11 }}>
        <div
          style={{
            width: 30,
            height: 36,
            borderRadius: 6,
            background: "var(--doc-bg)",
            border: "1px solid var(--card-border)",
            flex: "none",
            position: "relative",
            overflow: "hidden",
          }}
        >
          <div style={{ position: "absolute", top: 6, left: 5, right: 5, height: 2, borderRadius: 2, background: "var(--muted)", opacity: 0.4 }} />
          <div style={{ position: "absolute", top: 11, left: 5, right: 9, height: 2, borderRadius: 2, background: "var(--muted)", opacity: 0.4 }} />
          <div style={{ position: "absolute", top: 16, left: 5, right: 6, height: 2, borderRadius: 2, background: "var(--muted)", opacity: 0.4 }} />
          <div style={{ position: "absolute", bottom: 5, left: 5, width: 14, height: 5, borderRadius: 2, background: "var(--accent)", opacity: 0.7 }} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, justifyContent: "space-between" }}>
            <span style={{ fontSize: 14, fontWeight: 700, color: "var(--text)", letterSpacing: "-.01em", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {src.title}
            </span>
            <span style={{ flex: "none", display: "inline-flex", alignItems: "center", padding: "3px 8px", borderRadius: 8, fontSize: 11.5, fontWeight: 700, color: "var(--accent)", background: "var(--chip-bg)", border: "1px solid var(--chip-border)" }}>
              {src.score}%
            </span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 3 }}>
            <span style={{ fontSize: 11, fontWeight: 600, color: "var(--accent2)" }}>[{src.n}]</span>
            <span style={{ fontSize: 11.5, color: "var(--muted)" }}>{typeLabel}</span>
          </div>
          <p style={{ margin: "9px 0 0", fontSize: 12.5, lineHeight: 1.5, color: "var(--muted)" }}>{src.snippet}</p>
          <div style={{ marginTop: 11, height: 4, borderRadius: 3, background: "var(--seg-bg)", overflow: "hidden" }}>
            <div style={{ height: "100%", width: `${src.score}%`, borderRadius: 3, background: "linear-gradient(90deg,var(--accent),var(--accent2))" }} />
          </div>
        </div>
      </div>
    </div>
  );
}

function HeaderButton({
  label,
  onClick,
}: {
  label: string;
  onClick: () => void;
}) {
  const [hover, setHover] = useState(false);
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        padding: "9px 14px",
        borderRadius: 12,
        border: `1px solid ${hover ? "var(--accent)" : "var(--card-border)"}`,
        background: "var(--seg-bg)",
        color: "var(--text)",
        fontFamily: "inherit",
        fontWeight: 600,
        fontSize: 13.5,
        cursor: "pointer",
        flex: "none",
      }}
    >
      {label}
    </button>
  );
}

/* -------------------------------- Page ----------------------------------- */
export default function Home() {
  const authed = useAuthState();
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [mode, setMode] = useState<"rag" | "direct">("rag");
  const [query, setQuery] = useState("");

  const [result, setResult] = useState<QueryResponse | null>(null);
  const [answerMode, setAnswerMode] = useState<"rag" | "direct">("rag");
  const [timing, setTiming] = useState(0);
  const [asking, setAsking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [uploading, setUploading] = useState(false);
  const [toast, setToast] = useState<{ kind: "ok" | "err"; text: string } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const [docsOpen, setDocsOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [docRefreshKey, setDocRefreshKey] = useState(0);

  const isDark = theme === "dark";
  const t = THEMES[theme];
  const answered = result !== null;

  function showToast(kind: "ok" | "err", text: string) {
    setToast({ kind, text });
    window.setTimeout(() => setToast(null), 4000);
  }

  function handleUnauthorized() {
    logout();
    setAuthed(false);
    setResult(null);
    setDocsOpen(false);
    setHistoryOpen(false);
    showToast("err", "Your session expired. Please sign in again.");
  }

  function signOut() {
    logout();
    setAuthed(false);
    setResult(null);
    setQuery("");
  }

  async function runQuery(q: string) {
    const question = q.trim();
    if (!question || asking) return;
    setAsking(true);
    setError(null);
    const start = performance.now();
    try {
      const data = await askQuery(question, mode);
      setResult(data);
      setAnswerMode(mode);
      setTiming((performance.now() - start) / 1000);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) return handleUnauthorized();
      setError(e instanceof Error ? e.message : "Something went wrong.");
      setResult(null);
    } finally {
      setAsking(false);
    }
  }

  async function handleFile(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = ""; // allow re-uploading the same file
    if (!file) return;
    setUploading(true);
    try {
      const res = await uploadDocument(file);
      showToast("ok", `Uploaded ${res.filename} · ${res.chunks_created} chunks`);
      setDocRefreshKey((k) => k + 1); // refresh the document manager
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) return handleUnauthorized();
      showToast("err", err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  const segActive: CSSProperties = {
    border: "none",
    cursor: "pointer",
    fontFamily: "inherit",
    fontWeight: 700,
    fontSize: 13,
    padding: "7px 14px",
    borderRadius: 10,
    color: "var(--onAccent)",
    background: ACCENT_GRADIENT,
    boxShadow: "0 3px 10px var(--accentGlow)",
  };
  const segIdle: CSSProperties = {
    border: "none",
    cursor: "pointer",
    fontFamily: "inherit",
    fontWeight: 600,
    fontSize: 13,
    padding: "7px 14px",
    borderRadius: 10,
    color: "var(--muted)",
    background: "transparent",
  };

  const accentBtn: CSSProperties = {
    color: "var(--onAccent)",
    background: ACCENT_GRADIENT,
    boxShadow: "0 4px 14px var(--accentGlow)",
  };

  const topScore = result?.sources?.[0]?.score ?? 0;
  const confidence = topScore >= 50 ? "High confidence" : topScore >= 25 ? "Medium confidence" : "Low confidence";

  return (
    <div
      style={{
        position: "relative",
        minHeight: "100vh",
        background: "var(--bg)",
        transition: "background .4s ease",
        ...t,
      } as CSSProperties}
    >
      {/* Ambient animated blobs */}
      <div style={{ position: "absolute", inset: 0, overflow: "hidden", pointerEvents: "none", zIndex: 0 }}>
        <div style={{ position: "absolute", top: -140, left: -120, width: 560, height: 560, borderRadius: "50%", background: "var(--blob1)", filter: "blur(90px)", opacity: "var(--blobOp)" as unknown as number, animation: "floatA 18s ease-in-out infinite" }} />
        <div style={{ position: "absolute", bottom: -180, right: -120, width: 620, height: 620, borderRadius: "50%", background: "var(--blob2)", filter: "blur(100px)", opacity: "var(--blobOp)" as unknown as number, animation: "floatB 22s ease-in-out infinite" }} />
        <div style={{ position: "absolute", top: "32%", left: "44%", width: 420, height: 420, borderRadius: "50%", background: "var(--blob3)", filter: "blur(110px)", opacity: "var(--blobOp3)" as unknown as number, animation: "floatC 26s ease-in-out infinite" }} />
      </div>

      <div style={{ position: "relative", zIndex: 1, maxWidth: 1200, margin: "0 auto", padding: "22px 28px 80px" }}>
        {authed === false && <AuthScreen onAuthed={() => setAuthed(true)} />}

        {authed === true && (
          <>
            {/* TOP BAR */}
            <div style={{ display: "flex", alignItems: "center", gap: 14, padding: "10px 16px", borderRadius: 18, background: "var(--card-bg)", border: "1px solid var(--card-border)", backdropFilter: "blur(18px) saturate(140%)", WebkitBackdropFilter: "blur(18px) saturate(140%)", flexWrap: "wrap" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 11, minWidth: 0 }}>
                <div style={{ width: 30, height: 30, borderRadius: 9, background: ACCENT_GRADIENT, display: "flex", alignItems: "center", justifyContent: "center", boxShadow: "0 4px 14px var(--accentGlow)" }}>
                  <div style={{ width: 11, height: 11, borderRadius: 3, background: "#fff", opacity: 0.95 }} />
                </div>
                <span style={{ fontWeight: 800, fontSize: 18, letterSpacing: "-.02em", color: "var(--text)" }}>PaperTrail</span>
              </div>

              {/* Segmented mode toggle */}
              <div role="group" aria-label="Answer mode" style={{ display: "flex", gap: 3, padding: 4, borderRadius: 13, background: "var(--seg-bg)", border: "1px solid var(--card-border)" }}>
                <button onClick={() => setMode("rag")} aria-pressed={mode === "rag"} style={mode === "rag" ? segActive : segIdle}>RAG mode</button>
                <button onClick={() => setMode("direct")} aria-pressed={mode === "direct"} style={mode === "direct" ? segActive : segIdle}>Direct mode</button>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: 10, marginLeft: "auto", flexWrap: "wrap" }}>
                <HeaderButton label="Documents" onClick={() => setDocsOpen(true)} />
                <HeaderButton label="History" onClick={() => setHistoryOpen(true)} />
                {/* Theme switch */}
                <button
                  onClick={() => setTheme(isDark ? "light" : "dark")}
                  aria-label={isDark ? "Switch to light theme" : "Switch to dark theme"}
                  style={{ position: "relative", width: 60, height: 30, borderRadius: 16, border: "1px solid var(--card-border)", background: "var(--seg-bg)", cursor: "pointer", padding: 0, flex: "none" }}
                >
                  <span style={{ position: "absolute", top: 3, left: isDark ? 33 : 3, width: 24, height: 24, borderRadius: "50%", background: ACCENT_GRADIENT, boxShadow: "0 2px 8px var(--accentGlow)", transition: "left .28s cubic-bezier(.4,0,.2,1)" }} />
                </button>
                {/* Upload */}
                <button
                  onClick={() => fileRef.current?.click()}
                  disabled={uploading}
                  style={{ display: "inline-flex", alignItems: "center", gap: 8, padding: "9px 15px", borderRadius: 12, border: "none", cursor: uploading ? "default" : "pointer", fontFamily: "inherit", fontWeight: 600, fontSize: 13.5, opacity: uploading ? 0.7 : 1, ...accentBtn }}
                >
                  {uploading ? <Spinner /> : <span style={{ fontSize: 15, lineHeight: 1, marginTop: -1 }}>+</span>}
                  {uploading ? "Uploading…" : "Upload document"}
                </button>
                <input ref={fileRef} type="file" accept=".pdf,.txt,.md" onChange={handleFile} style={{ display: "none" }} />
                <HeaderButton label="Sign out" onClick={signOut} />
              </div>
            </div>

            {/* SEARCH BAR */}
            <div style={{ marginTop: 40 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "9px 10px 9px 16px", borderRadius: 20, background: "var(--card-bg)", border: "1px solid var(--card-border)", backdropFilter: "blur(22px) saturate(150%)", WebkitBackdropFilter: "blur(22px) saturate(150%)", boxShadow: "0 14px 40px var(--cardShadow)" }}>
                <MagnifierIcon />
                <input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") runQuery(query || SUGGESTIONS[0]); }}
                  placeholder="Ask anything about your documents…"
                  aria-label="Ask a question about your documents"
                  style={{ flex: 1, minWidth: 0, background: "transparent", border: "none", outline: "none", fontFamily: "inherit", fontSize: 16.5, color: "var(--text)", padding: "2px 4px" }}
                />
                <button
                  onClick={() => runQuery(query || SUGGESTIONS[0])}
                  disabled={asking}
                  style={{ display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 7, padding: "11px 20px", borderRadius: 14, border: "none", cursor: asking ? "default" : "pointer", fontFamily: "inherit", fontWeight: 600, fontSize: 14, flex: "none", opacity: asking ? 0.75 : 1, ...accentBtn }}
                >
                  {asking ? <Spinner /> : null}
                  {asking ? "Asking…" : "Ask"}
                  {!asking && <span style={{ fontSize: 15, marginTop: -1 }}>→</span>}
                </button>
              </div>
              {error && (
                <div role="alert" style={{ marginTop: 12, padding: "10px 14px", borderRadius: 12, fontSize: 13.5, color: "#ff8a80", background: "rgba(255,80,80,.10)", border: "1px solid rgba(255,120,120,.35)" }}>
                  {error}
                </div>
              )}
            </div>

            {/* EMPTY / LANDING STATE */}
            {!answered && !asking && (
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
                    <SuggestionChip key={q} q={q} onPick={() => { setQuery(q); runQuery(q); }} />
                  ))}
                </div>
              </div>
            )}

            {/* LOADING SKELETON */}
            {asking && !answered && (
              <div style={{ marginTop: 34, animation: "rise .35s ease both" }}>
                <SkeletonCard />
              </div>
            )}

            {/* ANSWERED STATE */}
            {result && (
              <div style={{ display: "flex", gap: 22, marginTop: 34, flexWrap: "wrap", alignItems: "flex-start", animation: "rise .45s ease both" }}>
                <div style={{ flex: "1 1 520px", minWidth: 300, padding: "30px 32px", borderRadius: 22, background: "var(--card-bg)", border: "1px solid var(--card-border)", backdropFilter: "blur(22px) saturate(150%)", WebkitBackdropFilter: "blur(22px) saturate(150%)", boxShadow: "0 18px 50px var(--cardShadow)" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 9, marginBottom: 18 }}>
                    <div style={{ width: 22, height: 22, borderRadius: 7, background: ACCENT_GRADIENT, flex: "none" }} />
                    <span style={{ fontSize: 12.5, fontWeight: 700, letterSpacing: ".04em", textTransform: "uppercase", color: "var(--muted)" }}>
                      {answerMode === "rag" ? "Retrieved answer" : "Direct answer"}
                    </span>
                  </div>
                  <div style={{ fontSize: 19, lineHeight: 1.62, letterSpacing: "-.01em", color: "var(--text)", fontWeight: 400, whiteSpace: "pre-wrap" }}>
                    {renderAnswerWithCitations(result.answer, result.sources.length)}
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 14, marginTop: 26, paddingTop: 18, borderTop: "1px solid var(--card-border)", flexWrap: "wrap" }}>
                    <span style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: 13, fontWeight: 600, color: "var(--text)" }}>
                      <span style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--accent)", boxShadow: "0 0 8px var(--accent)" }} />
                      {answerMode === "rag" ? confidence : "Direct answer"}
                    </span>
                    <span style={{ width: 4, height: 4, borderRadius: "50%", background: "var(--muted)", opacity: 0.5 }} />
                    <span style={{ fontSize: 13, color: "var(--muted)" }}>
                      {answerMode === "rag"
                        ? `Grounded in ${result.sources.length} source${result.sources.length === 1 ? "" : "s"}`
                        : "No retrieval"}
                    </span>
                    <span style={{ width: 4, height: 4, borderRadius: "50%", background: "var(--muted)", opacity: 0.5 }} />
                    <span style={{ fontSize: 13, color: "var(--muted)" }}>answered in {timing.toFixed(1)}s</span>
                  </div>
                </div>

                {result.sources.length > 0 && (
                  <div style={{ flex: "1 1 300px", minWidth: 270, maxWidth: 380 }}>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", margin: "2px 4px 14px" }}>
                      <span style={{ fontSize: 12.5, fontWeight: 700, letterSpacing: ".05em", textTransform: "uppercase", color: "var(--muted)" }}>Sources</span>
                      <span style={{ fontSize: 12, fontWeight: 600, color: "var(--muted)" }}>
                        {result.sources.length} document{result.sources.length === 1 ? "" : "s"}
                      </span>
                    </div>
                    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                      {result.sources.map((src) => (
                        <SourceCard key={src.n} src={src} />
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>

      {/* Slide-over panels */}
      {authed === true && (
        <>
          <DocumentManager
            open={docsOpen}
            onClose={() => setDocsOpen(false)}
            refreshKey={docRefreshKey}
            onChanged={() => setDocRefreshKey((k) => k + 1)}
            onUnauthorized={handleUnauthorized}
          />
          <ChatHistoryPanel
            open={historyOpen}
            onClose={() => setHistoryOpen(false)}
            refreshKey={docRefreshKey}
            onUnauthorized={handleUnauthorized}
          />
        </>
      )}

      {/* TOAST */}
      <div aria-live="polite" role="status" style={{ position: "fixed", bottom: 22, right: 22, zIndex: 70 }}>
        {toast && (
          <div
            style={{
              padding: "12px 16px",
              borderRadius: 12,
              fontSize: 13.5,
              fontWeight: 600,
              color: "var(--text)",
              background: "var(--card-bg)",
              border: `1px solid ${toast.kind === "ok" ? "var(--chip-border)" : "rgba(255,120,120,.4)"}`,
              backdropFilter: "blur(18px) saturate(150%)",
              WebkitBackdropFilter: "blur(18px) saturate(150%)",
              boxShadow: "0 10px 30px var(--cardShadow)",
              animation: "rise .3s ease both",
            }}
          >
            <span style={{ marginRight: 8 }} aria-hidden>
              {toast.kind === "ok" ? "✓" : "⚠"}
            </span>
            {toast.text}
          </div>
        )}
      </div>
    </div>
  );
}

/* ------------------------------ Utilities -------------------------------- */
function Spinner() {
  return (
    <span
      aria-hidden
      style={{
        width: 14,
        height: 14,
        borderRadius: "50%",
        border: "2px solid rgba(255,255,255,.45)",
        borderTopColor: "#fff",
        display: "inline-block",
        animation: "spin .7s linear infinite",
      }}
    />
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
