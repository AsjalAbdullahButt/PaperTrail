"use client";

import { useEffect, useState } from "react";
import {
  deleteDocument,
  listDocuments,
  type DocumentInfo,
} from "@/lib/api";
import SlideOver from "./SlideOver";

type Props = {
  open: boolean;
  onClose: () => void;
  /** Bumped by the parent when the document set changes (e.g. after upload). */
  refreshKey: number;
  /** Called after a successful delete so the parent can invalidate its state. */
  onChanged: () => void;
  onUnauthorized: () => void;
};

export default function DocumentManager({
  open,
  onClose,
  refreshKey,
  onChanged,
  onUnauthorized,
}: Props) {
  const [docs, setDocs] = useState<DocumentInfo[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [confirmId, setConfirmId] = useState<number | null>(null);

  useEffect(() => {
    if (!open) return;
    let active = true;
    (async () => {
      try {
        const data = await listDocuments();
        if (active) {
          setDocs(data);
          setError(null);
        }
      } catch (e) {
        if (!active) return;
        if (isUnauthorized(e)) return onUnauthorized();
        setError(e instanceof Error ? e.message : "Failed to load documents.");
        setDocs([]);
      }
    })();
    return () => {
      active = false;
    };
  }, [open, refreshKey, onUnauthorized]);

  async function handleDelete(id: number) {
    setDeletingId(id);
    setError(null);
    try {
      await deleteDocument(id);
      setConfirmId(null);
      setDocs((prev) => (prev ? prev.filter((d) => d.id !== id) : prev));
      onChanged();
    } catch (e) {
      if (isUnauthorized(e)) return onUnauthorized();
      setError(e instanceof Error ? e.message : "Failed to delete document.");
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <SlideOver open={open} onClose={onClose} title="Your documents">
      {docs === null && !error && (
        <p style={mutedText} aria-live="polite">
          Loading documents…
        </p>
      )}

      {error && (
        <div role="alert" style={errorBox}>
          {error}
        </div>
      )}

      {docs !== null && docs.length === 0 && !error && (
        <div style={{ textAlign: "center", padding: "40px 10px", color: "var(--muted)" }}>
          <div style={{ fontSize: 15, fontWeight: 600, color: "var(--text)" }}>No documents yet</div>
          <p style={{ fontSize: 13.5, marginTop: 6 }}>
            Upload a PDF, TXT, or Markdown file to start asking questions.
          </p>
        </div>
      )}

      {docs && docs.length > 0 && (
        <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 10 }}>
          {docs.map((d) => (
            <li
              key={d.id}
              style={{
                padding: "13px 14px",
                borderRadius: 14,
                background: "var(--doc-bg)",
                border: "1px solid var(--card-border)",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10 }}>
                <div style={{ minWidth: 0 }}>
                  <div
                    style={{
                      fontSize: 14,
                      fontWeight: 700,
                      color: "var(--text)",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {d.filename}
                  </div>
                  <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 3 }}>
                    {d.file_type.toUpperCase()} · {d.chunk_count ?? 0} chunk
                    {(d.chunk_count ?? 0) === 1 ? "" : "s"}
                    {d.page_count ? ` · ${d.page_count} pages` : ""}
                  </div>
                </div>

                {confirmId === d.id ? (
                  <div style={{ display: "flex", gap: 6, flex: "none" }}>
                    <button
                      onClick={() => handleDelete(d.id)}
                      disabled={deletingId === d.id}
                      style={dangerBtn}
                    >
                      {deletingId === d.id ? "Deleting…" : "Confirm"}
                    </button>
                    <button onClick={() => setConfirmId(null)} style={ghostBtn}>
                      Cancel
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={() => setConfirmId(d.id)}
                    aria-label={`Delete ${d.filename}`}
                    style={ghostBtn}
                  >
                    Delete
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </SlideOver>
  );
}

function isUnauthorized(e: unknown): boolean {
  return typeof e === "object" && e !== null && "status" in e && (e as { status: number }).status === 401;
}

const mutedText = { fontSize: 14, color: "var(--muted)" } as const;
const errorBox = {
  padding: "10px 14px",
  borderRadius: 12,
  fontSize: 13.5,
  color: "#ff8a80",
  background: "rgba(255,80,80,.10)",
  border: "1px solid rgba(255,120,120,.35)",
} as const;
const ghostBtn = {
  padding: "7px 12px",
  borderRadius: 10,
  border: "1px solid var(--card-border)",
  background: "transparent",
  color: "var(--text)",
  fontFamily: "inherit",
  fontSize: 13,
  fontWeight: 600,
  cursor: "pointer",
  flex: "none",
} as const;
const dangerBtn = {
  padding: "7px 12px",
  borderRadius: 10,
  border: "1px solid rgba(255,120,120,.4)",
  background: "rgba(255,80,80,.12)",
  color: "#ff8a80",
  fontFamily: "inherit",
  fontSize: 13,
  fontWeight: 700,
  cursor: "pointer",
  flex: "none",
} as const;
