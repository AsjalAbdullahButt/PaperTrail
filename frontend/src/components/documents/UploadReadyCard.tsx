"use client";

import { useState } from "react";
import type { UploadResult } from "@/api/backendClient";
import { ChevronDownIcon, CloseIcon } from "@/components/ui/Icons";

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
    <div className="card" style={{ marginTop: "var(--space-5)", animation: "rise var(--dur-base) var(--ease) both" }}>
      <div className="row" style={{ gap: "var(--space-3)" }}>
        <div
          aria-hidden
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            width: 40,
            height: 40,
            borderRadius: "var(--radius-sm)",
            background: "var(--raised)",
            border: "1px solid var(--border)",
            color: "var(--text-2)",
            fontWeight: "var(--fw-medium)",
            fontSize: "var(--fs-xs)",
            flex: "none",
          }}
        >
          {TYPE_ICON[result.file_type] || "DOC"}
        </div>
        <div style={{ minWidth: 0, flex: 1 }}>
          <div className="row" style={{ flexWrap: "wrap" }}>
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
            <span className="chip chip-accent">Ready</span>
          </div>
          <div className="meta" style={{ marginTop: "var(--space-1)" }}>
            {result.file_type.toUpperCase()}
            {result.page_count ? ` · ${result.page_count} page${result.page_count === 1 ? "" : "s"}` : ""}
            {` · ${result.word_count.toLocaleString()} words`}
            {` · ${result.chunks_created} chunk${result.chunks_created === 1 ? "" : "s"}`}
          </div>
        </div>
        <button type="button" onClick={onDismiss} aria-label="Dismiss" title="Dismiss" className="btn btn-ghost btn-icon btn-sm">
          <CloseIcon />
        </button>
      </div>

      {result.summary && (
        <div style={{ marginTop: "var(--space-5)" }}>
          <div className="section-label">Summary</div>
          <blockquote
            style={{
              margin: "var(--space-2) 0 0",
              padding: "var(--space-3) var(--space-4)",
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
        <div style={{ marginTop: "var(--space-5)" }}>
          <div className="section-label">Highlights</div>
          <div className="stack" style={{ gap: "var(--space-2)", marginTop: "var(--space-2)" }}>
            {topHighlights.map((h, i) => (
              <blockquote
                key={i}
                style={{
                  margin: 0,
                  padding: "var(--space-3) var(--space-4)",
                  borderLeft: "3px solid var(--border-strong)",
                  borderRadius: "var(--radius-sm)",
                  background: "var(--raised)",
                  fontSize: "var(--fs-sm)",
                  lineHeight: 1.5,
                  color: "var(--text-2)",
                }}
              >
                {h.text}
              </blockquote>
            ))}
          </div>
        </div>
      )}

      {result.outline.length > 0 && (
        <div style={{ marginTop: "var(--space-5)" }}>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => setOutlineOpen((v) => !v)}
            aria-expanded={outlineOpen}
            style={{ marginLeft: "calc(var(--space-3) * -1)" }}
          >
            <span style={{ display: "inline-flex", transform: outlineOpen ? "none" : "rotate(-90deg)" }}>
              <ChevronDownIcon size={14} />
            </span>
            Outline ({result.outline.length})
          </button>
          {outlineOpen && (
            <ul style={{ listStyle: "none", margin: "var(--space-2) 0 0", padding: 0 }}>
              {result.outline.map((o, i) => (
                <li
                  key={i}
                  style={{
                    padding: "var(--space-1) 0",
                    paddingLeft: (o.level - 1) * 16,
                    fontSize: "var(--fs-sm)",
                    color: "var(--text)",
                    fontWeight: o.level === 1 ? "var(--fw-medium)" : "var(--fw-regular)",
                  }}
                >
                  <span style={{ color: "var(--accent)", marginRight: "var(--space-2)" }}>
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
