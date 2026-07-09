"use client";

import { useState, type CSSProperties, type ReactNode } from "react";

type Block =
  | { kind: "heading"; level: 2 | 3; text: string }
  | { kind: "list"; items: string[] }
  | { kind: "para"; text: string };

/** Splits an answer into heading / list / paragraph blocks on ##, ###, and
 * "- " line markers. Everything else is a paragraph, joined back into one
 * line (there is no pre-wrap to preserve now that blocks carry their own
 * spacing — see renderAnswerWithCitations). */
function parseBlocks(answer: string): Block[] {
  const lines = answer.split("\n");
  const blocks: Block[] = [];
  let i = 0;
  while (i < lines.length) {
    const trimmed = lines[i].trim();

    if (trimmed === "") {
      i++;
      continue;
    }

    const heading = /^(#{2,3})\s+(.*)$/.exec(trimmed);
    if (heading) {
      blocks.push({ kind: "heading", level: heading[1].length === 2 ? 2 : 3, text: heading[2].trim() });
      i++;
      continue;
    }

    if (/^-\s+/.test(trimmed)) {
      const items: string[] = [];
      while (i < lines.length && /^-\s+/.test(lines[i].trim())) {
        items.push(lines[i].trim().replace(/^-\s+/, ""));
        i++;
      }
      blocks.push({ kind: "list", items });
      continue;
    }

    const paraLines: string[] = [];
    while (i < lines.length && lines[i].trim() !== "" && !/^(#{2,3})\s+/.test(lines[i].trim()) && !/^-\s+/.test(lines[i].trim())) {
      paraLines.push(lines[i].trim());
      i++;
    }
    blocks.push({ kind: "para", text: paraLines.join(" ") });
  }
  return blocks;
}

/** Splits plain text on [n] citation tokens, turning in-range ones into chip
 * links. The one piece of the original component preserved verbatim. */
function splitCitations(text: string, maxN: number, keyPrefix: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  const re = /\[(\d+)\]/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let key = 0;
  while ((m = re.exec(text)) !== null) {
    const n = parseInt(m[1], 10);
    if (m.index > last) nodes.push(text.slice(last, m.index));
    if (n >= 1 && n <= maxN) {
      nodes.push(<CitationChip key={`${keyPrefix}-c${key++}`} n={n} />);
    } else {
      nodes.push(m[0]);
    }
    last = re.lastIndex;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}

/** Parses **bold** spans, then re-runs citation splitting inside every
 * resulting segment (bold or not) — citations must still resolve to chips
 * whether or not they fall inside a bold run. */
function renderInline(text: string, maxN: number, keyPrefix: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  const boldRe = /\*\*(.+?)\*\*/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let seg = 0;
  while ((m = boldRe.exec(text)) !== null) {
    if (m.index > last) {
      nodes.push(...splitCitations(text.slice(last, m.index), maxN, `${keyPrefix}-t${seg++}`));
    }
    nodes.push(
      <strong key={`${keyPrefix}-b${seg}`}>{splitCitations(m[1], maxN, `${keyPrefix}-bt${seg++}`)}</strong>,
    );
    last = boldRe.lastIndex;
  }
  if (last < text.length) {
    nodes.push(...splitCitations(text.slice(last), maxN, `${keyPrefix}-t${seg++}`));
  }
  return nodes;
}

const headingStyle: Record<2 | 3, CSSProperties> = {
  2: { fontSize: 17, fontWeight: 700, letterSpacing: "-.01em" },
  3: { fontSize: 15, fontWeight: 700, letterSpacing: "-.005em" },
};
const listStyle: CSSProperties = { margin: "8px 0 0", paddingLeft: 22 };
const listItemStyle: CSSProperties = { marginBottom: 6 };

function renderBlock(block: Block, index: number, maxN: number): ReactNode {
  const key = `blk${index}`;
  const spaced = index > 0 ? { marginTop: 14 } : undefined;

  if (block.kind === "heading") {
    return (
      <div key={key} style={{ ...headingStyle[block.level], ...spaced }}>
        {renderInline(block.text, maxN, key)}
      </div>
    );
  }
  if (block.kind === "list") {
    return (
      <ul key={key} style={{ ...listStyle, ...spaced }}>
        {block.items.map((item, i) => (
          <li key={`${key}-li${i}`} style={listItemStyle}>
            {renderInline(item, maxN, `${key}-li${i}`)}
          </li>
        ))}
      </ul>
    );
  }
  return (
    <div key={key} style={spaced}>
      {renderInline(block.text, maxN, key)}
    </div>
  );
}

/** Renders an answer as real structure: ## / ### headings, **bold**, and
 * "- " lists become styled elements; [n] tokens become citation chip links
 * wherever they occur (including inside a heading, bold run, or list item). */
export function renderAnswerWithCitations(answer: string, maxN: number): ReactNode[] {
  return parseBlocks(answer).map((block, i) => renderBlock(block, i, maxN));
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
