"use client";

import { useEffect, useState } from "react";
import { getDocumentTimeline, type TimelineEvent } from "@/lib/api";

/** Vertical alternating-card timeline of a document's dated events. */
export default function Timeline({ documentId }: { documentId: string }) {
  const [events, setEvents] = useState<TimelineEvent[] | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    setLoading(true);
    getDocumentTimeline(documentId)
      .then((e) => { if (active) setEvents(e); })
      .catch(() => { if (active) setEvents([]); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [documentId]);

  if (loading) return <div style={{ color: "var(--muted)", fontSize: 13, padding: 12 }}>Extracting timeline…</div>;
  if (!events || events.length === 0) {
    return (
      <div style={{ color: "var(--muted)", fontSize: 13, padding: 12 }}>
        No dated events detected in this document.
      </div>
    );
  }

  return (
    <div style={{ position: "relative", padding: "10px 0", marginTop: 8 }}>
      {/* Center spine */}
      <div style={{ position: "absolute", left: "50%", top: 0, bottom: 0, width: 2, background: "var(--card-border)", transform: "translateX(-1px)" }} />
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        {events.map((ev, i) => {
          const left = i % 2 === 0;
          return (
            <div key={i} style={{ display: "flex", justifyContent: left ? "flex-start" : "flex-end" }}>
              <div style={{ width: "46%", padding: "12px 14px", borderRadius: 14, background: "var(--card-bg)", border: "1px solid var(--card-border)", boxShadow: "0 6px 18px var(--cardShadow)" }}>
                <div style={{ fontSize: 13, fontWeight: 800, color: "var(--accent)" }}>{ev.date}</div>
                <div style={{ fontSize: 13, color: "var(--text)", marginTop: 4, lineHeight: 1.45 }}>{ev.event}</div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
