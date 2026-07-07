"use client";

import { useState, type ReactNode } from "react";

/** Renders answer text, turning [n] tokens into citation chip links. */
export function renderAnswerWithCitations(answer: string, maxN: number): ReactNode[] {
  const nodes: ReactNode[] = [];
  const re = /\[(\d+)\]/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let key = 0;
  while ((m = re.exec(answer)) !== null) {
    const n = parseInt(m[1], 10);
    if (m.index > last) nodes.push(answer.slice(last, m.index));
    if (n >= 1 && n <= maxN) {
      nodes.push(<CitationChip key={`c${key++}`} n={n} />);
    } else {
      nodes.push(m[0]);
    }
    last = re.lastIndex;
  }
  if (last < answer.length) nodes.push(answer.slice(last));
  return nodes;
}

export function CitationChip({ n }: { n: number }) {
  const [active, setActive] = useState(false);
  return (
    <a
      href={`#src-${n}`}
      aria-label={`Citation ${n}, jump to source ${n}`}
      onMouseEnter={() => setActive(true)}
      onMouseLeave={() => setActive(false)}
      onFocus={() => setActive(true)}
      onBlur={() => setActive(false)}
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        minWidth: 20,
        height: 20,
        padding: "0 5px",
        margin: "0 1px",
        borderRadius: 6,
        fontSize: 11.5,
        fontWeight: 700,
        textDecoration: "none",
        color: active ? "var(--onAccent)" : "var(--accent)",
        background: active ? "var(--accent)" : "var(--chip-bg)",
        border: "1px solid var(--chip-border)",
        outline: active ? "2px solid var(--accent)" : "none",
        outlineOffset: 1,
        verticalAlign: "middle",
        transform: "translateY(-1px)",
      }}
    >
      {n}
    </a>
  );
}
