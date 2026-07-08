"use client";

import { useEffect, useState, type CSSProperties } from "react";
import PageShell from "@/components/PageShell";
import {
  getAnalyticsOverview,
  getCoverageGaps,
  getDocumentUsage,
  getTopQueries,
  type AnalyticsOverview,
  type CoverageGap,
  type DocumentUsage,
  type TopQuery,
} from "@/lib/api";

const card: CSSProperties = {
  padding: "18px 20px", borderRadius: 18, background: "var(--card-bg)",
  border: "1px solid var(--card-border)", backdropFilter: "blur(18px) saturate(140%)",
  boxShadow: "0 8px 24px var(--cardShadow)",
};
const label: CSSProperties = {
  fontSize: 11.5, fontWeight: 700, letterSpacing: ".05em", textTransform: "uppercase",
  color: "var(--muted)",
};

export default function AnalyticsPage() {
  return (
    <PageShell>
      <AnalyticsInner />
    </PageShell>
  );
}

function AnalyticsInner() {
  const [overview, setOverview] = useState<AnalyticsOverview | null>(null);
  const [usage, setUsage] = useState<DocumentUsage[] | null>(null);
  const [top, setTop] = useState<TopQuery[] | null>(null);
  const [gaps, setGaps] = useState<CoverageGap[] | null>(null);
  const [sortKey, setSortKey] = useState<keyof DocumentUsage>("total_retrievals");

  useEffect(() => {
    getAnalyticsOverview().then(setOverview).catch(() => {});
    getDocumentUsage().then(setUsage).catch(() => {});
    getTopQueries(10).then(setTop).catch(() => {});
    getCoverageGaps().then(setGaps).catch(() => {});
  }, []);

  const sortedUsage = usage
    ? [...usage].sort((a, b) => {
        const av = a[sortKey] ?? 0;
        const bv = b[sortKey] ?? 0;
        return typeof av === "number" && typeof bv === "number" ? bv - av : String(bv).localeCompare(String(av));
      })
    : null;

  const maxDay = overview ? Math.max(1, ...overview.queries_this_week.map((d) => d.count)) : 1;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 22 }}>
      {/* Metric cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))", gap: 14 }}>
        <Metric title="Documents" value={overview?.total_documents} />
        <Metric title="Queries" value={overview?.total_queries} />
        <Metric title="Avg confidence" value={overview ? `${Math.round(overview.avg_confidence * 100)}%` : undefined} />
        <Metric title="Most active" value={overview ? (overview.most_queried_document?.name ?? "—") : undefined} small />
      </div>

      {/* Query volume chart */}
      <div style={card}>
        <div style={label}>Queries · last 7 days</div>
        {!overview ? (
          <Skeleton height={120} />
        ) : (
          <div style={{ display: "flex", alignItems: "flex-end", gap: 10, height: 130, marginTop: 14 }}>
            {overview.queries_this_week.map((d) => (
              <div key={d.date} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
                <div
                  title={`${d.count} queries`}
                  style={{ width: "100%", maxWidth: 40, height: `${(d.count / maxDay) * 100}px`, minHeight: 3, borderRadius: 8, background: "linear-gradient(180deg,var(--accent),var(--accent2))" }}
                />
                <span style={{ fontSize: 10.5, color: "var(--muted)" }}>{d.date.slice(5)}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div style={{ display: "flex", gap: 22, flexWrap: "wrap", alignItems: "flex-start" }}>
        {/* Document usage table */}
        <div style={{ ...card, flex: "1 1 460px", minWidth: 320 }}>
          <div style={label}>Document usage</div>
          {!sortedUsage ? (
            <Skeleton height={120} />
          ) : sortedUsage.length === 0 ? (
            <Empty />
          ) : (
            <div style={{ overflowX: "auto", marginTop: 12 }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <thead>
                  <tr style={{ color: "var(--muted)", textAlign: "left" }}>
                    <Th onClick={() => setSortKey("name")}>Name</Th>
                    <Th onClick={() => setSortKey("total_retrievals")}>Retrievals</Th>
                    <Th onClick={() => setSortKey("avg_similarity")}>Avg score</Th>
                  </tr>
                </thead>
                <tbody>
                  {sortedUsage.map((u) => (
                    <tr key={u.document_id} style={{ borderTop: "1px solid var(--card-border)", color: "var(--text)" }}>
                      <td style={{ padding: "8px 6px" }}>{u.name}</td>
                      <td style={{ padding: "8px 6px" }}>{u.total_retrievals}</td>
                      <td style={{ padding: "8px 6px" }}>{Math.round(u.avg_similarity * 100)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Coverage gaps */}
        <div style={{ ...card, flex: "1 1 300px", minWidth: 260 }}>
          <div style={label}>Coverage gaps</div>
          {!gaps ? (
            <Skeleton height={120} />
          ) : gaps.length === 0 ? (
            <div style={{ marginTop: 10, fontSize: 13, color: "var(--muted)" }}>No under-explored documents.</div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 12 }}>
              {gaps.map((g) => (
                <div key={g.document_id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
                  <span style={{ fontSize: 13, color: "var(--text)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{g.name}</span>
                  <span style={{ flex: "none", padding: "3px 9px", borderRadius: 8, fontSize: 11.5, fontWeight: 700, color: "#e0a53a", background: "rgba(224,165,58,.12)", border: "1px solid rgba(224,165,58,.35)" }}>
                    {g.unexplored_pct}% unexplored
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Top queries */}
      <div style={card}>
        <div style={label}>Top queries</div>
        {!top ? (
          <Skeleton height={80} />
        ) : top.length === 0 ? (
          <Empty />
        ) : (
          <ol style={{ margin: "12px 0 0", paddingLeft: 20, color: "var(--text)", fontSize: 13.5, lineHeight: 1.9 }}>
            {top.map((q, i) => (
              <li key={i}>{q.query} <span style={{ color: "var(--muted)" }}>· {q.count}×</span></li>
            ))}
          </ol>
        )}
      </div>
    </div>
  );
}

function Metric({ title, value, small }: { title: string; value?: number | string; small?: boolean }) {
  return (
    <div style={card}>
      <div style={label}>{title}</div>
      {value === undefined ? (
        <Skeleton height={30} />
      ) : (
        <div style={{ marginTop: 8, fontSize: small ? 16 : 28, fontWeight: 800, color: "var(--text)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {value}
        </div>
      )}
    </div>
  );
}

function Th({ children, onClick }: { children: React.ReactNode; onClick: () => void }) {
  return (
    <th onClick={onClick} style={{ padding: "6px", cursor: "pointer", fontWeight: 700, userSelect: "none" }}>
      {children} ↕
    </th>
  );
}

function Skeleton({ height }: { height: number }) {
  return <div style={{ height, marginTop: 10, borderRadius: 10, background: "var(--seg-bg)", animation: "pulse 1.2s ease-in-out infinite" }} />;
}

function Empty() {
  return <div style={{ marginTop: 10, fontSize: 13, color: "var(--muted)" }}>No data yet.</div>;
}
