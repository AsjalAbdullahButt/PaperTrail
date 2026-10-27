"use client";

import { useEffect, useRef, useState, type CSSProperties } from "react";
import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/state/authStore";
import { useQueryStore } from "@/state/queryStore";
import { useToast } from "@/hooks/useToast";
import { useDocumentUpload } from "@/hooks/useDocumentUpload";
import { useKeyboardShortcuts } from "@/hooks/useKeyboardShortcuts";
import { useMouseParallax } from "@/hooks/useMouseParallax";
import { useOnboardingHint } from "@/hooks/useOnboardingHint";
import { THEMES, useTheme } from "@/theme/themes";
import AmbientBackground from "@/components/layout/AmbientBackground";
import HomeHeader from "@/components/layout/HomeHeader";
import QueryPanel from "@/components/query/QueryPanel";
import DocumentListDrawer from "@/components/documents/DocumentListDrawer";
import ChatHistoryPanel from "@/components/query/ChatHistoryPanel";
import UploadReadyCard from "@/components/documents/UploadReadyCard";
import CommandPalette from "@/components/ui/CommandPalette";
import ToastViewport from "@/components/ui/ToastViewport";

// Only rendered after a first answer / on a first login, so keep them out of
// the initial bundle.
const QueryMindMap = dynamic(() => import("@/components/query/QueryMindMap"));
const OnboardingModal = dynamic(() => import("@/components/ui/OnboardingModal"));

export default function Home() {
  const router = useRouter();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const ready = useAuthStore((s) => s.ready);
  const restoreSession = useAuthStore((s) => s.restoreSession);
  const storeLogout = useAuthStore((s) => s.logout);

  useEffect(() => { restoreSession(); }, [restoreSession]);
  useEffect(() => {
    if (ready && !isAuthenticated) router.replace("/login");
  }, [ready, isAuthenticated, router]);
  const authed = ready ? isAuthenticated : null;

  const [theme, setTheme] = useTheme();
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [docsOpen, setDocsOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [docRefreshKey, setDocRefreshKey] = useState(0);
  const queryInputRef = useRef<HTMLInputElement>(null);
  const parallax = useMouseParallax();
  const { showOnboarding, dismissOnboarding } = useOnboardingHint(authed);

  const { toast, showToast } = useToast();
  const setQuery = useQueryStore((s) => s.setQuery);
  const runQuery = useQueryStore((s) => s.runQuery);
  const startNewConversation = useQueryStore((s) => s.startNewConversation);
  const hasAnswer = useQueryStore((s) => s.hasAnswer);
  const answerMode = useQueryStore((s) => s.answerMode);
  const queryId = useQueryStore((s) => s.queryId);

  function handleUnauthorized() {
    void storeLogout();
    startNewConversation();
    setDocsOpen(false);
    setHistoryOpen(false);
    showToast("err", "Your session expired. Please sign in again.");
    router.replace("/login");
  }

  const { uploading, lastUpload, setLastUpload, fileRef, handleFile } = useDocumentUpload({
    onUnauthorized: handleUnauthorized,
    onUploaded: () => setDocRefreshKey((k) => k + 1),
    showToast,
  });

  function signOut() {
    void storeLogout();
    startNewConversation();
    setQuery("");
    router.replace("/login");
  }

  useKeyboardShortcuts({
    focusQuery: () => queryInputRef.current?.focus(),
    escape: () => { setPaletteOpen(false); setDocsOpen(false); setHistoryOpen(false); },
    commandPalette: () => setPaletteOpen((v) => !v),
    upload: () => fileRef.current?.click(),
    history: () => setHistoryOpen((v) => !v),
    shortcutsHelp: () => showToast("ok", "/ focus · Ctrl+K palette · Ctrl+U upload · Ctrl+H history"),
  });

  const isDark = theme === "dark";

  return (
    <div style={{ position: "relative", minHeight: "100vh", background: "var(--bg)", transition: "background .4s ease", ...THEMES[theme] } as CSSProperties}>
      <AmbientBackground parallax={parallax} />

      <div style={{ position: "relative", zIndex: 1, maxWidth: 1200, margin: "0 auto", padding: "22px 28px 80px" }}>
        {authed === true && (
          <>
            <HomeHeader
              isDark={isDark}
              onToggleTheme={() => setTheme(isDark ? "light" : "dark")}
              onDocsOpen={() => setDocsOpen(true)}
              onHistoryOpen={() => setHistoryOpen(true)}
              uploading={uploading}
              fileRef={fileRef}
              onFileChange={handleFile}
              onSignOut={signOut}
              onUnauthorized={handleUnauthorized}
              showToast={showToast}
            />
            <QueryPanel queryInputRef={queryInputRef} onUnauthorized={handleUnauthorized} />
            {lastUpload && !hasAnswer && (
              <UploadReadyCard result={lastUpload} onDismiss={() => setLastUpload(null)} />
            )}
            {hasAnswer && answerMode !== "direct" && queryId && <QueryMindMap queryId={queryId} />}
          </>
        )}
      </div>

      {authed === true && (
        <>
          <DocumentListDrawer open={docsOpen} onClose={() => setDocsOpen(false)} refreshKey={docRefreshKey} onChanged={() => setDocRefreshKey((k) => k + 1)} onUnauthorized={handleUnauthorized} />
          <ChatHistoryPanel open={historyOpen} onClose={() => setHistoryOpen(false)} refreshKey={docRefreshKey} onUnauthorized={handleUnauthorized} />
          <CommandPalette
            open={paletteOpen}
            onClose={() => setPaletteOpen(false)}
            onPickQuery={(q) => { setQuery(q); setPaletteOpen(false); void runQuery(q, handleUnauthorized); }}
          />
          {showOnboarding && <OnboardingModal onDismiss={dismissOnboarding} />}
        </>
      )}

      <ToastViewport toast={toast} />
    </div>
  );
}
