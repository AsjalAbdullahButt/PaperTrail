"use client";

import { useEffect, useRef, useState, type ChangeEvent, type RefObject } from "react";
import { useRouter } from "next/navigation";
import { createPortal } from "react-dom";
import { ApiError, exportMyData, shareQuery, type QueryMode, type Source } from "@/api/backendClient";
import { useFloatingRect } from "@/hooks/useFloatingRect";
import { useQueryStore } from "@/state/queryStore";
import PaperTrailLogo from "@/components/layout/PaperTrailLogo";
import ThemeToggle from "@/components/ui/ThemeToggle";
import { ChevronDownIcon, CloseIcon, DownloadIcon, FileTextIcon, LinkIcon, MenuIcon, UploadIcon } from "@/components/ui/Icons";

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
  // The print window is its own white document, so it carries its own small
  // stylesheet (same family of values as the app tokens, AA contrast on white).
  win.document.write(`<!doctype html><html><head><meta charset="utf-8"><title>PaperTrail — ${escapeHtml(askedQuestion).slice(0, 60)}</title>
<style>
  @page { margin: 20mm; }
  body { font-family: -apple-system, "Segoe UI", Roboto, sans-serif; color: #1b1d21; padding: 48px; max-width: 720px; margin: 0 auto; line-height: 1.6; }
  .brand { font-weight: 600; font-size: 16px; color: #0d6b64; margin-bottom: 24px; }
  h1 { font-size: 20px; font-weight: 600; line-height: 1.25; margin: 0 0 20px; }
  .answer { font-size: 16px; white-space: pre-wrap; margin-bottom: 32px; }
  h2 { font-size: 14px; font-weight: 600; color: #484c53; border-top: 1px solid #d9d8d2; padding-top: 16px; margin: 8px 0 0; }
  ol { padding-left: 20px; margin: 12px 0 0; }
  li { margin-bottom: 12px; font-size: 14px; }
  .snippet { color: #484c53; }
  .meta { font-size: 12px; color: #5c616a; margin-top: 24px; }
  @media print { body { padding: 0; } }
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

  return (
    <div ref={ref} className="app-export" style={{ position: "relative", flex: "none" }}>
      <button
        type="button"
        className="btn"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <DownloadIcon />
        Export
        <ChevronDownIcon size={14} />
      </button>
      {open && rect && typeof document !== "undefined" && createPortal(
        <div
          ref={menuRef}
          role="menu"
          className="menu"
          style={{
            // Right-align to the trigger but never spill past either viewport edge on a phone.
            position: "fixed", top: rect.bottom + 8, left: `clamp(8px, ${rect.right - 272}px, calc(100vw - 280px))`, width: "min(272px, calc(100vw - 16px))", zIndex: 1000,
            animation: "rise var(--dur-fast) var(--ease) both",
          }}
        >
          <button
            type="button"
            role="menuitem"
            className="menu-item"
            disabled={!hasAnswer}
            onClick={() => { if (hasAnswer) { onDownloadPdf(); setOpen(false); } }}
          >
            <FileTextIcon /> Download this answer as PDF
          </button>
          <button
            type="button"
            role="menuitem"
            className="menu-item"
            disabled={!hasAnswer}
            onClick={() => { if (hasAnswer) { onCopyLink(); setOpen(false); } }}
          >
            <LinkIcon /> Copy share link
          </button>
          <div className="menu-sep" />
          <button type="button" role="menuitem" className="menu-item" onClick={() => { onExportZip(); setOpen(false); }}>
            <DownloadIcon /> Download account data (.zip)
          </button>
        </div>,
        document.body
      )}
    </div>
  );
}

export default function HomeHeader({
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
  // Phone only: whether the folded menu is open. Purely presentational.
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    if (!menuOpen) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setMenuOpen(false); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [menuOpen]);

  const act = (fn: () => void) => () => { setMenuOpen(false); fn(); };

  return (
    <header className="app-header" data-open={menuOpen}>
      <div className="app-brand">
        <PaperTrailLogo />
        PaperTrail
      </div>

      <div id="app-menu" className="app-actions">
        <nav className="app-nav" aria-label="Main">
          <button type="button" className="btn btn-ghost" onClick={act(() => router.push("/library"))}>Library</button>
          <button type="button" className="btn btn-ghost" onClick={act(() => router.push("/analytics"))}>Analytics</button>
          <button type="button" className="btn btn-ghost" onClick={act(onDocsOpen)}>Documents</button>
          <button type="button" className="btn btn-ghost" onClick={act(onHistoryOpen)}>History</button>
        </nav>
        <span className="app-spacer" />
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
        <div className="app-account">
          <button type="button" className="btn btn-ghost" onClick={act(() => router.push("/profile"))}>Profile</button>
          <button type="button" className="btn btn-ghost" onClick={act(onSignOut)}>Sign out</button>
          <ThemeToggle isDark={isDark} onToggle={onToggleTheme} />
        </div>
      </div>

      <button
        type="button"
        className="btn btn-primary app-primary-slot"
        onClick={() => fileRef.current?.click()}
        disabled={uploading}
        aria-label={uploading ? undefined : "Upload document"}
      >
        {uploading ? <span className="spinner" aria-hidden="true" /> : <UploadIcon />}
        {uploading ? "Uploading…" : <>Upload<span className="hide-xs"> document</span></>}
      </button>
      <input ref={fileRef} type="file" accept=".pdf,.docx,.pptx,.txt,.md,.xlsx,.csv" onChange={onFileChange} style={{ display: "none" }} />

      <button
        type="button"
        className="btn btn-ghost btn-icon app-menu-toggle"
        onClick={() => setMenuOpen((v) => !v)}
        aria-expanded={menuOpen}
        aria-controls="app-menu"
        aria-label={menuOpen ? "Close menu" : "Open menu"}
      >
        {menuOpen ? <CloseIcon /> : <MenuIcon />}
      </button>
    </header>
  );
}
