"use client";

export default function OnboardingModal({ onDismiss }: { onDismiss: () => void }) {
  return (
    <div
      style={{ position: "fixed", inset: 0, zIndex: 80, background: "var(--scrim)", display: "flex", alignItems: "center", justifyContent: "center", padding: "var(--space-4)" }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="onboarding-title"
        className="card"
        style={{ maxWidth: 440, maxHeight: "100%", overflowY: "auto", boxShadow: "var(--shadow-overlay)" }}
      >
        <h2 id="onboarding-title" className="h-title" style={{ marginBottom: "var(--space-3)" }}>Getting started</h2>
        <ol style={{ margin: "0 0 var(--space-5)", paddingLeft: "var(--space-5)", color: "var(--text-2)", fontSize: "var(--fs-sm)", lineHeight: 1.9 }}>
          <li><strong style={{ color: "var(--text)" }}>Upload</strong> a document (top-right, or Ctrl+U).</li>
          <li>Ask a question in the <strong style={{ color: "var(--text)" }}>search bar</strong> (press /).</li>
          <li>Switch <strong style={{ color: "var(--text)" }}>RAG / Multi-hop / Direct</strong> modes.</li>
          <li>Try the <strong style={{ color: "var(--text)" }}>NLP pipeline</strong> switches (re-rank, HyDE, NLI grounding, abstain).</li>
          <li>Trace answers to their <strong style={{ color: "var(--text)" }}>source cards</strong>.</li>
          <li>Browse everything in the <strong style={{ color: "var(--text)" }}>Library</strong>.</li>
        </ol>
        <div style={{ display: "flex", justifyContent: "flex-end" }}>
          <button type="button" className="btn btn-primary" onClick={onDismiss} autoFocus>
            Got it
          </button>
        </div>
      </div>
    </div>
  );
}
