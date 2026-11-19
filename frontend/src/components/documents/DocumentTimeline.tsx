"use client";

import { useEffect, useState } from "react";
import { getDocumentTimeline, type TimelineEvent } from "@/api/backendClient";

/** Vertical timeline of a document's dated events: a rail on the left, the date
 *  and the event beside each marker. Single column, so it reads the same in a
 *  narrow card on a phone and a wide one on a desktop. */
export default function DocumentTimeline({ documentId }: { documentId: string }) {
  const [events, setEvents] = useState<TimelineEvent[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadedFor, setLoadedFor] = useState(documentId);

  // Reset to the loading state during render when documentId changes,
  // instead of a synchronous setState at the top of the fetch effect below.
  if (documentId !== loadedFor) {
    setLoadedFor(documentId);
    setEvents(null);
    setLoading(true);
  }

  useEffect(() => {
    let active = true;
    getDocumentTimeline(documentId)
      .then((e) => { if (active) setEvents(e); })
      .catch(() => { if (active) setEvents([]); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [documentId]);

  if (loading) return <div className="empty" role="status" style={{ padding: "var(--space-3)" }}>Extracting timeline…</div>;
  if (!events || events.length === 0) {
    return (
      <div className="empty" style={{ padding: "var(--space-3)" }}>
        No dated events detected in this document.
      </div>
    );
  }

  return (
    <ol style={{ listStyle: "none", margin: "var(--space-3) 0 0", padding: "0 0 0 var(--space-4)", borderLeft: "1px solid var(--border-strong)", display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
      {events.map((ev, i) => (
        <li key={i} style={{ position: "relative" }}>
          <span aria-hidden style={{ position: "absolute", left: "calc(var(--space-4) * -1 - 4px)", top: 6, width: 7, height: 7, borderRadius: "50%", background: "var(--accent)" }} />
          <div style={{ fontSize: "var(--fs-sm)", fontWeight: "var(--fw-semibold)", color: "var(--text)" }}>{ev.date}</div>
          <div style={{ fontSize: "var(--fs-sm)", color: "var(--text-2)", marginTop: "var(--space-1)", lineHeight: 1.45 }}>{ev.event}</div>
        </li>
      ))}
    </ol>
  );
}
