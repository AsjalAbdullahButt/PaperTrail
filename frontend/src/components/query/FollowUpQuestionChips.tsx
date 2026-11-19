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
    <div style={{ marginTop: "var(--space-5)" }}>
      <div className="section-label" style={{ marginBottom: "var(--space-2)" }}>
        Follow-up questions
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-2)" }}>
        {questions.map((q, i) => (
          <button key={i} type="button" className="btn btn-wrap btn-sm" onClick={() => onPick(q)}>
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}
