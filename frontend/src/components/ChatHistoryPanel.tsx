"use client";

import { useEffect, useState } from "react";
import { getChatHistory, type ChatHistoryItem } from "@/lib/api";
import SlideOver from "./SlideOver";

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
    <SlideOver open={open} onClose={onClose} title="Chat history">
      {items === null && !error && (
        <p style={{ fontSize: 14, color: "var(--muted)" }} aria-live="polite">
          Loading history…
        </p>
      )}

      {error && (
        <div role="alert" style={{ padding: "10px 14px", borderRadius: 12, fontSize: 13.5, color: "#ff8a80", background: "rgba(255,80,80,.10)", border: "1px solid rgba(255,120,120,.35)" }}>
          {error}
        </div>
      )}

      {items !== null && items.length === 0 && !error && (
        <div style={{ textAlign: "center", padding: "40px 10px", color: "var(--muted)" }}>
          <div style={{ fontSize: 15, fontWeight: 600, color: "var(--text)" }}>No history yet</div>
          <p style={{ fontSize: 13.5, marginTop: 6 }}>Your questions and answers will appear here.</p>
        </div>
      )}

      {items && items.length > 0 && (
        <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 12 }}>
          {items.map((it) => (
            <li
              key={it.id}
              style={{
                padding: "13px 14px",
                borderRadius: 14,
                background: "var(--doc-bg)",
                border: "1px solid var(--card-border)",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                <span
                  style={{
                    fontSize: 10.5,
                    fontWeight: 700,
                    letterSpacing: ".04em",
                    textTransform: "uppercase",
                    padding: "2px 7px",
                    borderRadius: 7,
                    color: "var(--accent)",
                    background: "var(--chip-bg)",
                    border: "1px solid var(--chip-border)",
                  }}
                >
                  {it.mode}
                </span>
                <time style={{ fontSize: 11.5, color: "var(--muted)" }} dateTime={it.created_at}>
                  {formatDate(it.created_at)}
                </time>
              </div>
              <div style={{ fontSize: 14, fontWeight: 700, color: "var(--text)" }}>{it.question}</div>
              <p
                style={{
                  margin: "6px 0 0",
                  fontSize: 13,
                  lineHeight: 1.5,
                  color: "var(--muted)",
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
    </SlideOver>
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
