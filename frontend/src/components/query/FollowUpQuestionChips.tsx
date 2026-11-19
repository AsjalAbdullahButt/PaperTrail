"use client";

export default function FollowUpQuestionChips({
  questions,
  onPick,
}: {
  questions: string[];
  onPick: (q: string) => void;
}) {
  if (questions.length === 0) return null;
  return (
    <div style={{ marginTop: 20 }}>
      <div style={{ fontSize: "var(--fs-xs)", fontWeight: "var(--fw-semibold)", letterSpacing: ".05em", textTransform: "uppercase", color: "var(--muted)", marginBottom: 10 }}>
        Follow-up questions
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
        {questions.map((q, i) => (
          <button
            key={i}
            onClick={() => onPick(q)}
            style={{ padding: "8px 13px", borderRadius: "var(--radius-md)", cursor: "pointer", fontFamily: "inherit", fontSize: "var(--fs-sm)", color: "var(--text)", background: "var(--raised)", border: "1px solid var(--border)" }}
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}
