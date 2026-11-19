"use client";

import { useState, type CSSProperties } from "react";
import type { UploadResult } from "@/api/backendClient";


const TYPE_ICON: Record<string, string> = {
  pdf: "PDF",
  docx: "DOC",
  pptx: "PPT",
  txt: "TXT",
  md: "MD",
  xlsx: "XLS",
  csv: "CSV",
};

/** "Document Ready" summary shown right after a successful upload: metadata,
 *  top highlights as pull-quotes, and a collapsible outline tree. */
export default function UploadReadyCard({
  result,
  onDismiss,
}: {
  result: UploadResult;
  onDismiss: () => void;
}) {
  const [outlineOpen, setOutlineOpen] = useState(true);
  const topHighlights = result.highlights.slice(0, 3);

  return (
    <div
      style={{
        marginTop: 20,
        padding: "22px 24px",
        borderRadius: "var(--radius-md)",
        background: "var(--surface)",
        border: "1px solid var(--border)",
        boxShadow: "var(--shadow-overlay)",
        animation: "rise .4s ease both",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            width: 42,
            height: 42,
            borderRadius: "var(--radius-md)",
            background: "var(--accent)",
            color: "var(--on-accent)",
            fontWeight: "var(--fw-semibold)",
            fontSize: "var(--fs-xs)",
            flex: "none",
          }}
        >
          {TYPE_ICON[result.file_type] || "DOC"}
        </div>
        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 9, flexWrap: "wrap" }}>
            <span
              style={{
                fontSize: "var(--fs-md)",
                fontWeight: "var(--fw-semibold)",
                color: "var(--text)",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {result.filename}
            </span>
            <span style={badge}>Ready</span>
          </div>
          <div style={{ marginTop: 3, fontSize: "var(--fs-xs)", color: "var(--muted)" }}>
            {result.file_type.toUpperCase()}
            {result.page_count ? ` · ${result.page_count} page${result.page_count === 1 ? "" : "s"}` : ""}
            {` · ${result.word_count.toLocaleString()} words`}
            {` · ${result.chunks_created} chunk${result.chunks_created === 1 ? "" : "s"}`}
          </div>
        </div>
        <button onClick={onDismiss} aria-label="Dismiss" style={dismissBtn}>
          ✕
        </button>
      </div>

      {result.summary && (
        <div style={{ marginTop: 18 }}>
          <div style={sectionLabel}>✦ Summary</div>
          <blockquote
            style={{
              margin: "10px 0 0",
              padding: "12px 15px",
              borderLeft: "3px solid var(--accent)",
              borderRadius: "var(--radius-sm)",
              background: "var(--accent-soft)",
              fontSize: "var(--fs-sm)",
              lineHeight: 1.55,
              color: "var(--text)",
            }}
          >
            {result.summary}
          </blockquote>
        </div>
      )}

      {topHighlights.length > 0 && (
        <div style={{ marginTop: 18 }}>
          <div style={sectionLabel}>Highlights</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 10 }}>
            {topHighlights.map((h, i) => (
              <blockquote
                key={i}
                style={{
                  margin: 0,
                  padding: "10px 14px",
                  borderLeft: "3px solid var(--accent)",
                  borderRadius: "var(--radius-sm)",
                  background: "var(--raised)",
                  fontSize: "var(--fs-sm)",
                  lineHeight: 1.5,
                  color: "var(--muted)",
                }}
              >
                {h.text}
              </blockquote>
            ))}
          </div>
        </div>
      )}

      {result.outline.length > 0 && (
        <div style={{ marginTop: 18 }}>
          <button
            onClick={() => setOutlineOpen((v) => !v)}
            aria-expanded={outlineOpen}
            style={{
              ...sectionLabel,
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              border: "none",
              background: "none",
              cursor: "pointer",
              padding: 0,
            }}
          >
            <span style={{ transform: outlineOpen ? "rotate(90deg)" : "none", transition: "transform .15s" }}>
              ▸
            </span>
            Outline ({result.outline.length})
          </button>
          {outlineOpen && (
            <ul style={{ listStyle: "none", margin: "10px 0 0", padding: 0 }}>
              {result.outline.map((o, i) => (
                <li
                  key={i}
                  style={{
                    padding: "4px 0",
                    paddingLeft: (o.level - 1) * 16,
                    fontSize: "var(--fs-sm)",
                    color: "var(--text)",
                    fontWeight: o.level === 1 ? "var(--fw-medium)" : "var(--fw-regular)",
                  }}
                >
                  <span style={{ color: "var(--accent)", marginRight: 7 }}>
                    {"·".repeat(o.level)}
                  </span>
                  {o.heading}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

const badge: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  padding: "2px 9px",
  borderRadius: "var(--radius-sm)",
  fontSize: "var(--fs-xs)",
  fontWeight: "var(--fw-semibold)",
  color: "var(--accent)",
  background: "var(--accent-soft)",
  border: "1px solid var(--accent-line)",
};

const sectionLabel: CSSProperties = {
  fontSize: "var(--fs-xs)",
  fontWeight: "var(--fw-semibold)",
  letterSpacing: ".05em",
  textTransform: "uppercase",
  color: "var(--muted)",
};

const dismissBtn: CSSProperties = {
  flex: "none",
  border: "1px solid var(--border)",
  background: "var(--raised)",
  color: "var(--muted)",
  borderRadius: "var(--radius-sm)",
  width: 30,
  height: 30,
  cursor: "pointer",
  fontSize: "var(--fs-sm)",
};
