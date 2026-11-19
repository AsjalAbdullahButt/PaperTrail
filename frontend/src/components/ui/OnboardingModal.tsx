"use client";


export default function OnboardingModal({ onDismiss }: { onDismiss: () => void }) {
  return (
    <div style={{ position: "fixed", inset: 0, zIndex: 80, background: "var(--scrim)", display: "flex", alignItems: "center", justifyContent: "center", padding: 20 }}>
      <div style={{ maxWidth: 440, maxHeight: "100%", overflowY: "auto", padding: "clamp(20px, 5vw, 28px) clamp(18px, 5vw, 30px)", borderRadius: "var(--radius-md)", background: "var(--surface)", border: "1px solid var(--border)", boxShadow: "var(--shadow-overlay)" }}>
        <h2 style={{ margin: "0 0 10px", fontSize: "var(--fs-lg)", fontWeight: "var(--fw-semibold)", color: "var(--text)" }}>Welcome to PaperTrail</h2>
        <ol style={{ margin: "0 0 18px", paddingLeft: 20, color: "var(--muted)", fontSize: "var(--fs-sm)", lineHeight: 1.9 }}>
          <li><strong style={{ color: "var(--text)" }}>Upload</strong> a document (top-right, or Ctrl+U).</li>
          <li>Ask a question in the <strong style={{ color: "var(--text)" }}>search bar</strong> (press /).</li>
          <li>Switch <strong style={{ color: "var(--text)" }}>RAG / Multi-hop / Direct</strong> modes.</li>
          <li>Try the <strong style={{ color: "var(--text)" }}>NLP pipeline</strong> switches (re-rank, HyDE, NLI grounding, abstain).</li>
          <li>Trace answers to their <strong style={{ color: "var(--text)" }}>source cards</strong>.</li>
          <li>Browse everything in the <strong style={{ color: "var(--text)" }}>Library</strong>.</li>
        </ol>
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
          <button onClick={onDismiss} style={{ padding: "10px 18px", borderRadius: "var(--radius-md)", border: "none", cursor: "pointer", fontFamily: "inherit", fontWeight: "var(--fw-semibold)", fontSize: "var(--fs-sm)", color: "var(--on-accent)", background: "var(--accent)" }}>
            Got it
          </button>
        </div>
      </div>
    </div>
  );
}
