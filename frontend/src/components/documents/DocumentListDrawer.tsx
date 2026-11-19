"use client";

import { useEffect, useState } from "react";
import {
  deleteDocument,
  listDocuments,
  type DocumentInfo,
} from "@/api/backendClient";
import RightSideDrawer from "../ui/RightSideDrawer";

type Props = {
  open: boolean;
  onClose: () => void;
  /** Bumped by the parent when the document set changes (e.g. after upload). */
  refreshKey: number;
  /** Called after a successful delete so the parent can invalidate its state. */
  onChanged: () => void;
  onUnauthorized: () => void;
};

export default function DocumentListDrawer({
  open,
  onClose,
  refreshKey,
  onChanged,
  onUnauthorized,
}: Props) {
  const [docs, setDocs] = useState<DocumentInfo[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [confirmId, setConfirmId] = useState<string | null>(null);

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

  async function handleDelete(id: string) {
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
    <RightSideDrawer open={open} onClose={onClose} title="Your documents">
      {docs === null && !error && (
        <p className="meta" style={{ fontSize: "var(--fs-sm)" }} aria-live="polite">
          Loading documents…
        </p>
      )}

      {error && (
        <div role="alert" className="alert alert-danger" style={{ marginBottom: "var(--space-3)" }}>
          {error}
        </div>
      )}

      {docs !== null && docs.length === 0 && !error && (
        <div className="empty">
          <div className="empty-title">No documents yet</div>
          <p>Upload a PDF, TXT, or Markdown file to start asking questions.</p>
        </div>
      )}

      {docs && docs.length > 0 && (
        <ul className="stack" style={{ listStyle: "none", margin: 0, padding: 0, gap: "var(--space-2)" }}>
          {docs.map((d) => (
            <li key={d.id} className="card card-compact" style={{ background: "var(--raised)" }}>
              <div className="row" style={{ justifyContent: "space-between", gap: "var(--space-3)" }}>
                <div style={{ minWidth: 0 }}>
                  <div
                    style={{
                      fontSize: "var(--fs-sm)",
                      fontWeight: "var(--fw-semibold)",
                      color: "var(--text)",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {d.filename}
                  </div>
                  <div className="meta" style={{ marginTop: "var(--space-1)" }}>
                    {d.file_type.toUpperCase()} · {d.chunk_count ?? 0} chunk
                    {(d.chunk_count ?? 0) === 1 ? "" : "s"}
                    {d.page_count ? ` · ${d.page_count} pages` : ""}
                  </div>
                  {d.summary && (
                    <div
                      className="meta"
                      style={{
                        marginTop: "var(--space-1)",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {d.summary}
                    </div>
                  )}
                </div>

                {confirmId === d.id ? (
                  <div className="row" style={{ gap: "var(--space-2)", flex: "none" }}>
                    <button
                      type="button"
                      className="btn btn-sm btn-danger"
                      onClick={() => handleDelete(d.id)}
                      disabled={deletingId === d.id}
                    >
                      {deletingId === d.id ? "Deleting…" : "Confirm"}
                    </button>
                    <button type="button" className="btn btn-sm" onClick={() => setConfirmId(null)}>
                      Cancel
                    </button>
                  </div>
                ) : (
                  <button
                    type="button"
                    className="btn btn-sm"
                    onClick={() => setConfirmId(d.id)}
                    aria-label={`Delete ${d.filename}`}
                    style={{ flex: "none" }}
                  >
                    Delete
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </RightSideDrawer>
  );
}

function isUnauthorized(e: unknown): boolean {
  return typeof e === "object" && e !== null && "status" in e && (e as { status: number }).status === 401;
}
