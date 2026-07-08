"use client";

import { useEffect, useMemo, useState } from "react";
import { getMindMap, type MindMapData, type MindMapNode } from "@/lib/api";

const W = 640;
const H = 420;

type Positioned = MindMapNode & { x: number; y: number };

/** Simple force-directed layout (repulsion + springs), ~200 iterations, run
 *  once deterministically. No d3 — ~40 lines of vanilla physics. */
function layout(data: MindMapData): { nodes: Positioned[]; byId: Record<string, Positioned> } {
  const cx = W / 2;
  const cy = H / 2;
  const n = data.nodes.length;
  // Seed on a circle (query node centered).
  const nodes: Positioned[] = data.nodes.map((node, i) => {
    if (node.type === "query") return { ...node, x: cx, y: cy };
    const angle = (2 * Math.PI * i) / Math.max(1, n - 1);
    return { ...node, x: cx + Math.cos(angle) * 150, y: cy + Math.sin(angle) * 130 };
  });
  const byId: Record<string, Positioned> = {};
  nodes.forEach((nd) => (byId[nd.id] = nd));

  const K_REP = 9000; // repulsion
  const K_SPR = 0.02; // spring
  const REST = 120; // spring rest length
  for (let iter = 0; iter < 200; iter++) {
    // Repulsion between every pair.
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const a = nodes[i];
        const b = nodes[j];
        let dx = a.x - b.x;
        let dy = a.y - b.y;
        let dist2 = dx * dx + dy * dy || 0.01;
        const force = K_REP / dist2;
        const dist = Math.sqrt(dist2);
        dx /= dist;
        dy /= dist;
        if (a.type !== "query") { a.x += dx * force * 0.02; a.y += dy * force * 0.02; }
        if (b.type !== "query") { b.x -= dx * force * 0.02; b.y -= dy * force * 0.02; }
      }
    }
    // Springs along edges.
    for (const e of data.edges) {
      const a = byId[e.source];
      const b = byId[e.target];
      if (!a || !b) continue;
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 0.01;
      const f = K_SPR * (dist - REST);
      const fx = (dx / dist) * f;
      const fy = (dy / dist) * f;
      if (a.type !== "query") { a.x += fx; a.y += fy; }
      if (b.type !== "query") { b.x -= fx; b.y -= fy; }
    }
    // Keep inside the viewport.
    for (const nd of nodes) {
      nd.x = Math.max(30, Math.min(W - 30, nd.x));
      nd.y = Math.max(30, Math.min(H - 30, nd.y));
    }
  }
  return { nodes, byId };
}

export default function MindMap({ queryId }: { queryId: string }) {
  const [data, setData] = useState<MindMapData | null>(null);
  const [selected, setSelected] = useState<MindMapNode | null>(null);

  useEffect(() => {
    let active = true;
    getMindMap(queryId).then((d) => { if (active) setData(d); }).catch(() => {});
    return () => { active = false; };
  }, [queryId]);

  const positioned = useMemo(() => (data ? layout(data) : null), [data]);

  if (!data || !positioned || data.nodes.length <= 1) return null;

  const nodeColor = (nd: MindMapNode) => {
    if (nd.type === "query") return "url(#mm-grad)";
    const imp = nd.importance ?? 0;
    return imp > 0.5 ? "var(--accent)" : "var(--muted)";
  };

  return (
    <div style={{ marginTop: 22, padding: "18px 20px", borderRadius: 20, background: "var(--card-bg)", border: "1px solid var(--card-border)", backdropFilter: "blur(18px) saturate(140%)", boxShadow: "0 12px 34px var(--cardShadow)" }}>
      <div style={{ fontSize: 11.5, fontWeight: 700, letterSpacing: ".05em", textTransform: "uppercase", color: "var(--muted)", marginBottom: 10 }}>
        Concept map
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Query concept map" style={{ maxWidth: "100%", animation: "rise .5s ease both" }}>
        <defs>
          <linearGradient id="mm-grad" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="var(--accent)" />
            <stop offset="100%" stopColor="var(--accent2)" />
          </linearGradient>
        </defs>
        {data.edges.map((e, i) => {
          const a = positioned.byId[e.source];
          const b = positioned.byId[e.target];
          if (!a || !b) return null;
          return (
            <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y}
              stroke="var(--card-border)" strokeWidth={1 + e.weight * 3} opacity={0.5 + e.weight * 0.4} />
          );
        })}
        {positioned.nodes.map((nd) => {
          const r = nd.type === "query" ? 16 : 9;
          return (
            <g key={nd.id} onClick={() => setSelected(nd)} style={{ cursor: nd.type === "chunk" ? "pointer" : "default" }}>
              <circle cx={nd.x} cy={nd.y} r={r} fill={nodeColor(nd)} stroke="var(--card-bg)" strokeWidth={2} />
              {nd.type === "query" && (
                <text x={nd.x} y={nd.y - 22} textAnchor="middle" fontSize={11} fill="var(--text)" fontWeight={700}>
                  {nd.label}
                </text>
              )}
            </g>
          );
        })}
      </svg>
      {selected && selected.type === "chunk" && (
        <div style={{ marginTop: 10, padding: "10px 13px", borderRadius: 12, background: "var(--seg-bg)", border: "1px solid var(--card-border)", fontSize: 12.5, color: "var(--muted)" }}>
          <strong style={{ color: "var(--text)" }}>{selected.document || "Source"}</strong>
          {typeof selected.importance === "number" ? ` · importance ${Math.round(selected.importance * 100)}%` : ""}
          <div style={{ marginTop: 4 }}>{selected.label}</div>
        </div>
      )}
    </div>
  );
}
