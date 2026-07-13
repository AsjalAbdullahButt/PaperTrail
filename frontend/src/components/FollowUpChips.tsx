"use client";

export default function FollowUpChips({
  questions,
  onPick,
}: {
  questions: string[];
  onPick: (q: string) => void;
}) {
  if (questions.length === 0) return null;
  return (
    <div style={{ marginTop: 20 }}>
      <div style={{ fontSize: 11.5, fontWeight: 700, letterSpacing: ".05em", textTransform: "uppercase", color: "var(--muted)", marginBottom: 10 }}>
        Follow-up questions
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
        {questions.map((q, i) => (
          <button
            key={i}
            onClick={() => onPick(q)}
            style={{ padding: "8px 13px", borderRadius: 12, cursor: "pointer", fontFamily: "inherit", fontSize: 13, color: "var(--text)", background: "var(--seg-bg)", border: "1px solid var(--card-border)" }}
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}
