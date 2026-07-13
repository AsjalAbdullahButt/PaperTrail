"use client";

import { useEffect, useRef, useState, type ChangeEvent, type CSSProperties, type RefObject } from "react";
import { useRouter } from "next/navigation";
import { createPortal } from "react-dom";
import { ApiError, exportMyData, shareQuery, type QueryMode, type Source } from "@/lib/api";
import { useFloatingRect } from "@/hooks/useFloatingRect";
import { useQueryStore } from "@/stores/queryStore";
import Logo from "@/components/Logo";

const ACCENT_GRADIENT = "linear-gradient(135deg,var(--accent),var(--accent2))";

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

/** Opens a print-formatted window for the current answer; the browser's own
 * "Save as PDF" print destination is the export mechanism (no PDF library
 * dependency needed). Takes plain values (not the store directly) so it stays
 * a plain function, not something named like a hook. */
function downloadAnswerAsPdf(
  askedQuestion: string,
  currentAnswer: string,
  currentSources: Source[],
  confidenceScore: number,
  answerMode: QueryMode,
): void {
  const win = window.open("", "_blank", "noopener,noreferrer,width=820,height=1000");
  if (!win) return;
  const sourcesHtml = currentSources
    .map(
      (s) => `<li><strong>[${s.n}] ${escapeHtml(s.title)}</strong> — p.${s.page_number} · ${s.score}% relevance<br><span class="snippet">${escapeHtml(s.snippet)}</span></li>`
    )
    .join("");
  const confPct = Math.round(confidenceScore * 100);
  win.document.write(`<!doctype html><html><head><meta charset="utf-8"><title>PaperTrail — ${escapeHtml(askedQuestion).slice(0, 60)}</title>
<style>
  body { font-family: -apple-system, "Segoe UI", Roboto, sans-serif; color: #16181d; padding: 48px; max-width: 720px; margin: 0 auto; line-height: 1.6; }
  .brand { font-weight: 800; font-size: 15px; letter-spacing: -.02em; color: #10b981; margin-bottom: 22px; }
  h1 { font-size: 19px; margin: 0 0 20px; }
  .answer { font-size: 15px; white-space: pre-wrap; margin-bottom: 30px; }
  h2 { font-size: 12px; text-transform: uppercase; letter-spacing: .06em; color: #666; border-top: 1px solid #ddd; padding-top: 18px; margin-top: 6px; }
  ol { padding-left: 20px; margin: 12px 0 0; }
  li { margin-bottom: 14px; font-size: 12.5px; }
  .snippet { color: #555; }
  .meta { font-size: 12px; color: #888; margin-top: 26px; }
  @media print { body { padding: 0 32px; } }
</style></head>
<body>
  <div class="brand">PaperTrail</div>
  <h1>${escapeHtml(askedQuestion) || "Untitled question"}</h1>
  <div class="answer">${escapeHtml(currentAnswer)}</div>
  ${currentSources.length ? `<h2>Sources</h2><ol>${sourcesHtml}</ol>` : ""}
  <div class="meta">${answerMode === "direct" ? "Direct answer · no retrieval" : `Confidence ${confPct}% · grounded in ${currentSources.length} source${currentSources.length === 1 ? "" : "s"}`}</div>
</body></html>`);
  win.document.close();
  win.focus();
  win.onload = () => win.print();
}

function DownloadIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 3v12" />
      <path d="M7 10l5 5 5-5" />
      <path d="M5 21h14" />
    </svg>
  );
}
function LinkIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 17H7a5 5 0 0 1 0-10h2" />
      <path d="M15 7h2a5 5 0 0 1 0 10h-2" />
      <line x1="8" y1="12" x2="16" y2="12" />
    </svg>
  );
}
function FileTextIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" />
      <path d="M14 2v6h6" />
      <line x1="8" y1="13" x2="16" y2="13" />
      <line x1="8" y1="17" x2="13" y2="17" />
    </svg>
  );
}
function ChevronDownIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M6 9l6 6 6-6" />
    </svg>
  );
}

function ExportMenu({
  hasAnswer,
  onExportZip,
  onDownloadPdf,
  onCopyLink,
}: {
  hasAnswer: boolean;
  onExportZip: () => void;
  onDownloadPdf: () => void;
  onCopyLink: () => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const rect = useFloatingRect(ref, open);

  useEffect(() => {
    if (!open) return;
    function onDocClick(e: MouseEvent) {
      const target = e.target as Node;
      if (ref.current?.contains(target)) return;
      if (menuRef.current?.contains(target)) return;
      setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const itemStyle: CSSProperties = {
    display: "flex", alignItems: "center", gap: 10, width: "100%", padding: "10px 12px",
    border: "none", background: "none", color: "var(--text)", fontFamily: "inherit",
    fontSize: 13.5, fontWeight: 600, cursor: "pointer", textAlign: "left", borderRadius: 10,
  };
  const disabledItemStyle: CSSProperties = { ...itemStyle, color: "var(--muted)", cursor: "default", opacity: 0.5 };

  return (
    <div ref={ref} style={{ position: "relative", flex: "none" }}>
      <button
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        style={{
          display: "inline-flex", alignItems: "center", gap: 7, padding: "9px 14px", borderRadius: 12,
          border: `1px solid ${open ? "var(--accent)" : "var(--card-border)"}`, background: "var(--seg-bg)",
          color: "var(--text)", fontFamily: "inherit", fontWeight: 600, fontSize: 13.5, cursor: "pointer",
        }}
      >
        <DownloadIcon />
        Export
        <span style={{ display: "inline-flex", transform: open ? "rotate(180deg)" : "none", transition: "transform .15s ease" }}>
          <ChevronDownIcon />
        </span>
      </button>
      {open && rect && typeof document !== "undefined" && createPortal(
        <div
          ref={menuRef}
          role="menu"
          style={{
            position: "fixed", top: rect.bottom + 8, left: rect.right - 250, width: 250, padding: 6, borderRadius: 14,
            background: "var(--menu-bg)", border: "1px solid var(--card-border)", backdropFilter: "blur(22px) saturate(150%)",
            WebkitBackdropFilter: "blur(22px) saturate(150%)", boxShadow: "0 18px 40px var(--cardShadow)", zIndex: 1000,
            animation: "rise .15s ease both",
          }}
        >
          <button
            role="menuitem"
            disabled={!hasAnswer}
            style={hasAnswer ? itemStyle : disabledItemStyle}
            onClick={() => { if (hasAnswer) { onDownloadPdf(); setOpen(false); } }}
          >
            <FileTextIcon /> Download this answer as PDF
          </button>
          <button
            role="menuitem"
            disabled={!hasAnswer}
            style={hasAnswer ? itemStyle : disabledItemStyle}
            onClick={() => { if (hasAnswer) { onCopyLink(); setOpen(false); } }}
          >
            <LinkIcon /> Copy share link
          </button>
          <div style={{ height: 1, background: "var(--card-border)", margin: "6px 4px" }} />
          <button role="menuitem" style={itemStyle} onClick={() => { onExportZip(); setOpen(false); }}>
            <DownloadIcon /> Download account data (.zip)
          </button>
        </div>,
        document.body
      )}
    </div>
  );
}

function HeaderButton({ label, onClick }: { label: string; onClick: () => void }) {
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

export default function Header({
  isDark,
  onToggleTheme,
  onDocsOpen,
  onHistoryOpen,
  uploading,
  fileRef,
  onFileChange,
  onSignOut,
  onUnauthorized,
  showToast,
}: {
  isDark: boolean;
  onToggleTheme: () => void;
  onDocsOpen: () => void;
  onHistoryOpen: () => void;
  uploading: boolean;
  fileRef: RefObject<HTMLInputElement | null>;
  onFileChange: (e: ChangeEvent<HTMLInputElement>) => void;
  onSignOut: () => void;
  onUnauthorized: () => void;
  showToast: (kind: "ok" | "err", text: string) => void;
}) {
  const router = useRouter();
  const hasAnswer = useQueryStore((s) => s.hasAnswer);
  const queryId = useQueryStore((s) => s.queryId);
  const askedQuestion = useQueryStore((s) => s.askedQuestion);
  const currentAnswer = useQueryStore((s) => s.currentAnswer);
  const currentSources = useQueryStore((s) => s.currentSources);
  const confidenceScore = useQueryStore((s) => s.confidenceScore);
  const answerMode = useQueryStore((s) => s.answerMode);

  const accentBtn: CSSProperties = {
    color: "var(--onAccent)",
    background: ACCENT_GRADIENT,
    boxShadow: "0 4px 14px var(--accentGlow)",
  };

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 14, padding: "10px 16px", borderRadius: 18, background: "var(--card-bg)", border: "1px solid var(--card-border)", backdropFilter: "blur(18px) saturate(140%)", WebkitBackdropFilter: "blur(18px) saturate(140%)", flexWrap: "wrap" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 11, minWidth: 0 }}>
        <Logo />
        <span style={{ fontWeight: 800, fontSize: 18, letterSpacing: "-.02em", color: "var(--text)" }}>PaperTrail</span>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 10, marginLeft: "auto", flexWrap: "wrap" }}>
        <HeaderButton label="Library" onClick={() => router.push("/library")} />
        <HeaderButton label="Analytics" onClick={() => router.push("/analytics")} />
        <HeaderButton label="Documents" onClick={onDocsOpen} />
        <HeaderButton label="History" onClick={onHistoryOpen} />
        <ExportMenu
          hasAnswer={hasAnswer}
          onExportZip={async () => {
            try { await exportMyData(); showToast("ok", "Your data export is ready"); }
            catch (e) { showToast("err", e instanceof ApiError && e.status === 429 ? "Export limit reached — try again later." : "Export failed"); }
          }}
          onDownloadPdf={() =>
            downloadAnswerAsPdf(askedQuestion, currentAnswer, currentSources, confidenceScore, answerMode)
          }
          onCopyLink={async () => {
            if (!queryId) { showToast("err", "This answer can't be shared."); return; }
            try {
              const { token } = await shareQuery(queryId);
              await navigator.clipboard.writeText(`${window.location.origin}/share/${token}`);
              showToast("ok", "Share link copied to clipboard");
            } catch (e) {
              if (e instanceof ApiError && e.status === 401) return onUnauthorized();
              showToast("err", e instanceof ApiError ? e.message : "Could not create share link");
            }
          }}
        />
        <button
          onClick={onToggleTheme}
          aria-label={isDark ? "Switch to light theme" : "Switch to dark theme"}
          style={{ position: "relative", width: 60, height: 30, borderRadius: 16, border: "1px solid var(--card-border)", background: "var(--seg-bg)", cursor: "pointer", padding: 0, flex: "none" }}
        >
          <span style={{ position: "absolute", top: 3, left: isDark ? 33 : 3, width: 24, height: 24, borderRadius: "50%", background: ACCENT_GRADIENT, boxShadow: "0 2px 8px var(--accentGlow)", transition: "left .28s cubic-bezier(.4,0,.2,1)" }} />
        </button>
        <button
          onClick={() => fileRef.current?.click()}
          disabled={uploading}
          style={{ display: "inline-flex", alignItems: "center", gap: 8, padding: "9px 15px", borderRadius: 12, border: "none", cursor: uploading ? "default" : "pointer", fontFamily: "inherit", fontWeight: 600, fontSize: 13.5, opacity: uploading ? 0.7 : 1, ...accentBtn }}
        >
          {uploading ? <Spinner /> : <span style={{ fontSize: 15, lineHeight: 1, marginTop: -1 }}>+</span>}
          {uploading ? "Uploading…" : "Upload document"}
        </button>
        <input ref={fileRef} type="file" accept=".pdf,.docx,.pptx,.txt,.md,.xlsx,.csv" onChange={onFileChange} style={{ display: "none" }} />
        <HeaderButton label="Profile" onClick={() => router.push("/profile")} />
        <HeaderButton label="Sign out" onClick={onSignOut} />
      </div>
    </div>
  );
}
