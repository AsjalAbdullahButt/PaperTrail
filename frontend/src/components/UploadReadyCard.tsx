"use client";

import { useState, type CSSProperties } from "react";
import type { UploadResult } from "@/lib/api";

const ACCENT_GRADIENT = "linear-gradient(135deg,var(--accent),var(--accent2))";

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
        borderRadius: 20,
        background: "var(--card-bg)",
        border: "1px solid var(--card-border)",
        backdropFilter: "blur(22px) saturate(150%)",
        WebkitBackdropFilter: "blur(22px) saturate(150%)",
        boxShadow: "0 14px 40px var(--cardShadow)",
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
            borderRadius: 11,
            background: ACCENT_GRADIENT,
            color: "var(--onAccent)",
            fontWeight: 800,
            fontSize: 12,
            boxShadow: "0 4px 14px var(--accentGlow)",
            flex: "none",
          }}
        >
          {TYPE_ICON[result.file_type] || "DOC"}
        </div>
        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 9, flexWrap: "wrap" }}>
            <span
              style={{
                fontSize: 15.5,
                fontWeight: 700,
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
          <div style={{ marginTop: 3, fontSize: 12.5, color: "var(--muted)" }}>
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
              borderLeft: "3px solid var(--accent2)",
              borderRadius: 8,
              background: "var(--chip-bg)",
              fontSize: 14,
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
                  borderRadius: 8,
                  background: "var(--seg-bg)",
                  fontSize: 13.5,
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
                    fontSize: 13.5,
                    color: "var(--text)",
                    fontWeight: o.level === 1 ? 600 : 400,
                  }}
                >
                  <span style={{ color: "var(--accent2)", marginRight: 7 }}>
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
  borderRadius: 8,
  fontSize: 11,
  fontWeight: 700,
  color: "var(--accent)",
  background: "var(--chip-bg)",
  border: "1px solid var(--chip-border)",
};

const sectionLabel: CSSProperties = {
  fontSize: 11.5,
  fontWeight: 700,
  letterSpacing: ".05em",
  textTransform: "uppercase",
  color: "var(--muted)",
};

const dismissBtn: CSSProperties = {
  flex: "none",
  border: "1px solid var(--card-border)",
  background: "var(--seg-bg)",
  color: "var(--muted)",
  borderRadius: 9,
  width: 30,
  height: 30,
  cursor: "pointer",
  fontSize: 13,
};
