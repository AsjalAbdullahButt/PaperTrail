"use client";

const ACCENT_GRADIENT = "linear-gradient(135deg,var(--accent),var(--accent2))";

export default function OnboardingModal({ onDismiss }: { onDismiss: () => void }) {
  return (
    <div style={{ position: "fixed", inset: 0, zIndex: 80, background: "rgba(0,0,0,.5)", display: "flex", alignItems: "center", justifyContent: "center", padding: 20 }}>
      <div style={{ maxWidth: 440, padding: "28px 30px", borderRadius: 20, background: "var(--card-bg)", border: "1px solid var(--card-border)", backdropFilter: "blur(22px) saturate(150%)", boxShadow: "0 24px 60px var(--cardShadow)" }}>
        <h2 style={{ margin: "0 0 10px", fontSize: 20, fontWeight: 800, color: "var(--text)" }}>Welcome to PaperTrail</h2>
        <ol style={{ margin: "0 0 18px", paddingLeft: 20, color: "var(--muted)", fontSize: 14, lineHeight: 1.9 }}>
          <li><strong style={{ color: "var(--text)" }}>Upload</strong> a document (top-right, or Ctrl+U).</li>
          <li>Ask a question in the <strong style={{ color: "var(--text)" }}>search bar</strong> (press /).</li>
          <li>Switch <strong style={{ color: "var(--text)" }}>RAG / Multi-hop / Direct</strong> modes.</li>
          <li>Trace answers to their <strong style={{ color: "var(--text)" }}>source cards</strong>.</li>
          <li>Browse everything in the <strong style={{ color: "var(--text)" }}>Library</strong>.</li>
        </ol>
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
          <button onClick={onDismiss} style={{ padding: "10px 18px", borderRadius: 12, border: "none", cursor: "pointer", fontFamily: "inherit", fontWeight: 700, fontSize: 14, color: "var(--onAccent)", background: ACCENT_GRADIENT }}>
            Got it
          </button>
        </div>
      </div>
    </div>
  );
}
