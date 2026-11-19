"use client";

import { useEffect, useState } from "react";
import { getChatHistory, type ChatHistoryItem } from "@/api/backendClient";
import RightSideDrawer from "../ui/RightSideDrawer";

type Props = {
  open: boolean;
  onClose: () => void;
  refreshKey: number;
  onUnauthorized: () => void;
};

// Past entries here are read-only (no click-to-rerun action exists yet). If
// one is ever made clickable to restore a query, it must run as a standalone
// query with an empty conversation_history — history entries predate the
// current live conversation and re-running one is not a continuation of it.
export default function ChatHistoryPanel({ open, onClose, refreshKey, onUnauthorized }: Props) {
  const [items, setItems] = useState<ChatHistoryItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    let active = true;
    (async () => {
      try {
        const page = await getChatHistory(50, 0);
        if (active) {
          setItems(page.items);
          setError(null);
        }
      } catch (e) {
        if (!active) return;
        if (typeof e === "object" && e !== null && "status" in e && (e as { status: number }).status === 401) {
          return onUnauthorized();
        }
        setError(e instanceof Error ? e.message : "Failed to load history.");
        setItems([]);
      }
    })();
    return () => {
      active = false;
    };
  }, [open, refreshKey, onUnauthorized]);

  return (
    <RightSideDrawer open={open} onClose={onClose} title="Chat history">
      {items === null && !error && (
        <p className="meta" style={{ fontSize: "var(--fs-sm)" }} aria-live="polite">
          Loading history…
        </p>
      )}

      {error && (
        <div role="alert" className="alert alert-danger" style={{ marginBottom: "var(--space-3)" }}>
          {error}
        </div>
      )}

      {items !== null && items.length === 0 && !error && (
        <div className="empty">
          <div className="empty-title">No history yet</div>
          <p>Your questions and answers will appear here.</p>
        </div>
      )}

      {items && items.length > 0 && (
        <ul className="stack" style={{ listStyle: "none", margin: 0, padding: 0, gap: "var(--space-3)" }}>
          {items.map((it) => (
            <li key={it.id} className="card card-compact" style={{ background: "var(--raised)" }}>
              <div className="row" style={{ marginBottom: "var(--space-2)" }}>
                <span className="chip chip-accent">{it.mode}</span>
                <time className="meta" dateTime={it.created_at}>
                  {formatDate(it.created_at)}
                </time>
              </div>
              <div style={{ fontSize: "var(--fs-sm)", fontWeight: "var(--fw-semibold)", color: "var(--text)" }}>{it.question}</div>
              <p
                style={{
                  marginTop: "var(--space-2)",
                  fontSize: "var(--fs-sm)",
                  lineHeight: 1.5,
                  color: "var(--text-2)",
                  display: "-webkit-box",
                  WebkitLineClamp: 3,
                  WebkitBoxOrient: "vertical",
                  overflow: "hidden",
                }}
              >
                {it.answer}
              </p>
            </li>
          ))}
        </ul>
      )}
    </RightSideDrawer>
  );
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
