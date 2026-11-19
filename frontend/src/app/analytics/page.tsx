"use client";

import { useEffect, useState } from "react";
import AuthenticatedPageLayout from "@/components/layout/AuthenticatedPageLayout";
import { SortIcon } from "@/components/ui/Icons";
import {
  getAnalyticsOverview,
  getCoverageGaps,
  getDocumentUsage,
  getTopQueries,
  type AnalyticsOverview,
  type CoverageGap,
  type DocumentUsage,
  type TopQuery,
} from "@/api/backendClient";

export default function AnalyticsPage() {
  return (
    <AuthenticatedPageLayout>
      <AnalyticsInner />
    </AuthenticatedPageLayout>
  );
}

function AnalyticsInner() {
  const [overview, setOverview] = useState<AnalyticsOverview | null>(null);
  const [usage, setUsage] = useState<DocumentUsage[] | null>(null);
  const [top, setTop] = useState<TopQuery[] | null>(null);
  const [gaps, setGaps] = useState<CoverageGap[] | null>(null);
  const [sortKey, setSortKey] = useState<keyof DocumentUsage>("total_retrievals");
  // Display state only: which requests failed, so a section can say so instead
  // of showing a loading placeholder forever.
  const [failed, setFailed] = useState<Record<string, boolean>>({});
  const fail = (key: string) => () => setFailed((f) => ({ ...f, [key]: true }));

  useEffect(() => {
    getAnalyticsOverview().then(setOverview).catch(fail("overview"));
    getDocumentUsage().then(setUsage).catch(fail("usage"));
    getTopQueries(10).then(setTop).catch(fail("top"));
    getCoverageGaps().then(setGaps).catch(fail("gaps"));
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
    <>
      <h1 className="h-page" style={{ marginBottom: "var(--space-5)" }}>Analytics</h1>
      <div className="stack" style={{ gap: "var(--space-4)" }}>
        {/* Metric cards */}
        <div className="stat-grid">
          <Metric title="Documents" value={overview?.total_documents} failed={failed.overview} />
          <Metric title="Queries" value={overview?.total_queries} failed={failed.overview} />
          <Metric title="Avg confidence" value={overview ? `${Math.round(overview.avg_confidence * 100)}%` : undefined} failed={failed.overview} />
          <Metric title="Most active" value={overview ? (overview.most_queried_document?.name ?? "—") : undefined} small failed={failed.overview} />
        </div>

        {/* Query volume chart */}
        <div className="card">
          <div className="section-label">Queries, last 7 days</div>
          {failed.overview && !overview ? (
            <Problem />
          ) : !overview ? (
            <Skeleton height={120} />
          ) : (
            <div
              role="img"
              aria-label={`Queries per day, last 7 days: ${overview.queries_this_week.map((d) => `${d.date.slice(5)} ${d.count}`).join(", ")}`}
              style={{ display: "flex", alignItems: "flex-end", gap: "var(--space-3)", height: 140, marginTop: "var(--space-4)" }}
            >
              {overview.queries_this_week.map((d) => (
                <div key={d.date} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: "var(--space-2)" }}>
                  <div
                    title={`${d.count} queries`}
                    style={{ width: "100%", maxWidth: 40, height: `${(d.count / maxDay) * 100}px`, minHeight: 3, borderRadius: "var(--radius-sm)", background: d.count > 0 ? "var(--accent)" : "var(--border-strong)" }}
                  />
                  <span className="meta tabular-nums">{d.date.slice(5)}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="pair-grid">
          {/* Document usage table */}
          <div className="card">
            <div className="section-label">Document usage</div>
            {failed.usage && !sortedUsage ? (
              <Problem />
            ) : !sortedUsage ? (
              <Skeleton height={120} />
            ) : sortedUsage.length === 0 ? (
              <Empty />
            ) : (
              <div style={{ overflowX: "auto", marginTop: "var(--space-3)" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "var(--fs-sm)" }}>
                  <thead>
                    <tr style={{ color: "var(--text-2)", textAlign: "left" }}>
                      <Th active={sortKey === "name"} onClick={() => setSortKey("name")}>Name</Th>
                      <Th active={sortKey === "total_retrievals"} onClick={() => setSortKey("total_retrievals")}>Retrievals</Th>
                      <Th active={sortKey === "avg_similarity"} onClick={() => setSortKey("avg_similarity")}>Avg score</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {sortedUsage.map((u) => (
                      <tr key={u.document_id} style={{ borderTop: "1px solid var(--border)", color: "var(--text)" }}>
                        <td style={{ padding: "var(--space-2) var(--space-2)" }}>{u.name}</td>
                        <td className="tabular-nums" style={{ padding: "var(--space-2) var(--space-2)" }}>{u.total_retrievals}</td>
                        <td className="tabular-nums" style={{ padding: "var(--space-2) var(--space-2)" }}>{Math.round(u.avg_similarity * 100)}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Coverage gaps */}
          <div className="card">
            <div className="section-label">Coverage gaps</div>
            {failed.gaps && !gaps ? (
              <Problem />
            ) : !gaps ? (
              <Skeleton height={120} />
            ) : gaps.length === 0 ? (
              <div className="meta" style={{ marginTop: "var(--space-3)", fontSize: "var(--fs-sm)" }}>No under-explored documents.</div>
            ) : (
              <div className="stack" style={{ gap: "var(--space-2)", marginTop: "var(--space-3)" }}>
                {gaps.map((g) => (
                  <div key={g.document_id} className="row" style={{ justifyContent: "space-between" }}>
                    <span style={{ fontSize: "var(--fs-sm)", color: "var(--text)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{g.name}</span>
                    <span className="chip chip-warn tabular-nums" style={{ flex: "none" }}>
                      {g.unexplored_pct}% unexplored
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Top queries */}
        <div className="card">
          <div className="section-label">Top queries</div>
          {failed.top && !top ? (
            <Problem />
          ) : !top ? (
            <Skeleton height={80} />
          ) : top.length === 0 ? (
            <Empty />
          ) : (
            <ol style={{ margin: "var(--space-3) 0 0", paddingLeft: "var(--space-5)", color: "var(--text)", fontSize: "var(--fs-sm)", lineHeight: 1.9 }}>
              {top.map((q, i) => (
                <li key={i}>{q.query} <span className="meta" style={{ fontSize: "var(--fs-sm)" }}>· {q.count}×</span></li>
              ))}
            </ol>
          )}
        </div>
      </div>
    </>
  );
}

function Metric({ title, value, small, failed }: { title: string; value?: number | string; small?: boolean; failed?: boolean }) {
  return (
    <div className="card card-compact">
      <div className="section-label">{title}</div>
      {value === undefined ? (
        failed ? <div className="meta" style={{ marginTop: "var(--space-2)" }}>Unavailable</div> : <Skeleton height={32} />
      ) : (
        <div className="tabular-nums" style={{ marginTop: "var(--space-2)", fontSize: small ? "var(--fs-md)" : "var(--fs-xl)", fontWeight: "var(--fw-semibold)", color: "var(--text)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {value}
        </div>
      )}
    </div>
  );
}

function Th({ children, onClick, active }: { children: React.ReactNode; onClick: () => void; active: boolean }) {
  return (
    <th scope="col" aria-sort={active ? "descending" : "none"} style={{ padding: "var(--space-1) var(--space-1)", fontWeight: "var(--fw-medium)" }}>
      <button type="button" className="btn btn-ghost btn-sm" onClick={onClick} style={{ color: active ? "var(--text)" : "inherit", padding: "0 var(--space-2)" }}>
        {children} <SortIcon size={14} />
      </button>
    </th>
  );
}

function Skeleton({ height }: { height: number }) {
  return <div className="skeleton" style={{ height, marginTop: "var(--space-3)" }} />;
}

function Empty() {
  return <div className="meta" style={{ marginTop: "var(--space-3)", fontSize: "var(--fs-sm)" }}>No data yet.</div>;
}

function Problem() {
  return <div className="alert alert-danger" role="alert" style={{ marginTop: "var(--space-3)" }}>Couldn&rsquo;t load this section. Reload the page to try again.</div>;
}
