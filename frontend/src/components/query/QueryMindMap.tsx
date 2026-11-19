"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import { getMindMap, type MindMapData, type MindMapNode } from "@/api/backendClient";

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
        const dist2 = dx * dx + dy * dy || 0.01;
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

function truncateLabel(label: string, max = 20): string {
  return label.length > max ? `${label.slice(0, max)}…` : label;
}

// Display sizing only. The layout above is untouched: it still runs in the
// fixed W x H space. This crops the drawing to where the nodes (and their
// labels) actually are, so a map of two nodes is small and a map of many fills
// more of the card instead of every map being stretched to the card width.
const VIEW_PAD = 24;
const MIN_VIEW_W = 280;
const MIN_VIEW_H = 96;
const MAX_UPSCALE = 1.25; // never draw larger than 1.25x its natural size

function viewBoxFor(nodes: Positioned[]): { x: number; y: number; w: number; h: number } {
  let minX = Infinity;
  let maxX = -Infinity;
  let minY = Infinity;
  let maxY = -Infinity;
  for (const nd of nodes) {
    if (nd.type === "query") {
      // The question label is centred above the node and is not truncated.
      const half = Math.min(nd.label.length * 6.2, W) / 2;
      minX = Math.min(minX, nd.x - Math.max(half, 16));
      maxX = Math.max(maxX, nd.x + Math.max(half, 16));
      minY = Math.min(minY, nd.y - 34);
      maxY = Math.max(maxY, nd.y + 16);
    } else {
      // Chunk labels start to the right of the dot and are truncated to 20 chars.
      minX = Math.min(minX, nd.x - 9);
      maxX = Math.max(maxX, nd.x + 13 + truncateLabel(nd.label).length * 5.4);
      minY = Math.min(minY, nd.y - 9);
      maxY = Math.max(maxY, nd.y + 9);
    }
  }
  let w = maxX - minX + VIEW_PAD * 2;
  let h = maxY - minY + VIEW_PAD * 2;
  let x = minX - VIEW_PAD;
  let y = minY - VIEW_PAD;
  if (w < MIN_VIEW_W) { x -= (MIN_VIEW_W - w) / 2; w = MIN_VIEW_W; }
  if (h < MIN_VIEW_H) { y -= (MIN_VIEW_H - h) / 2; h = MIN_VIEW_H; }
  return { x, y, w, h };
}

function LegendItem({ swatch, label }: { swatch: ReactNode; label: string }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: "var(--space-1)" }}>
      {swatch}
      {label}
    </span>
  );
}

function Legend() {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)", fontSize: "var(--fs-xs)", color: "var(--text-2)", flexWrap: "wrap" }}>
      <LegendItem
        swatch={<span style={{ width: 12, height: 12, borderRadius: "50%", display: "inline-block", background: "var(--accent)" }} />}
        label="Your question"
      />
      <LegendItem
        swatch={<span style={{ width: 8, height: 8, borderRadius: "50%", display: "inline-block", background: "var(--accent)" }} />}
        label="High-importance source"
      />
      <LegendItem
        swatch={<span style={{ width: 8, height: 8, borderRadius: "50%", display: "inline-block", background: "var(--muted)" }} />}
        label="Other source"
      />
    </div>
  );
}

export default function QueryMindMap({ queryId }: { queryId: string }) {
  const [data, setData] = useState<MindMapData | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [selected, setSelected] = useState<MindMapNode | null>(null);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [loadedFor, setLoadedFor] = useState(queryId);

  // Reset during render when queryId changes, instead of a synchronous
  // setState at the top of the fetch effect below.
  if (queryId !== loadedFor) {
    setLoadedFor(queryId);
    setData(null);
    setLoadError(false);
    setSelected(null);
  }

  useEffect(() => {
    let active = true;
    getMindMap(queryId)
      .then((d) => { if (active) setData(d); })
      .catch(() => { if (active) setLoadError(true); });
    return () => { active = false; };
  }, [queryId]);

  const positioned = useMemo(() => (data ? layout(data) : null), [data]);

  if (loadError) {
    return (
      <div className="card" style={{ marginTop: "var(--space-5)" }}>
        <div className="section-label">Concept map</div>
        <div className="empty">Couldn&rsquo;t load the concept map for this answer.</div>
      </div>
    );
  }

  if (data && (!positioned || data.nodes.length <= 1)) {
    return (
      <div className="card" style={{ marginTop: "var(--space-5)" }}>
        <div className="section-label">Concept map</div>
        <div className="empty">
          Not enough content to map yet — ask a question that draws on more of your documents.
        </div>
      </div>
    );
  }

  if (!data || !positioned) {
    return (
      <div className="card" style={{ marginTop: "var(--space-5)" }}>
        <div className="section-label">Concept map</div>
        <div className="empty">Loading concept map…</div>
      </div>
    );
  }

  const vb = viewBoxFor(positioned.nodes);

  const nodeColor = (nd: MindMapNode) => {
    if (nd.type === "query") return "var(--accent)";
    const imp = nd.importance ?? 0;
    return imp > 0.5 ? "var(--accent)" : "var(--muted)";
  };

  return (
    <div className="card" style={{ marginTop: "var(--space-5)" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "var(--space-3)", marginBottom: "var(--space-3)" }}>
        <div className="section-label">Concept map</div>
        <Legend />
      </div>
      <svg
        viewBox={`${vb.x} ${vb.y} ${vb.w} ${vb.h}`}
        width="100%"
        role="img"
        aria-label="Query concept map"
        style={{ display: "block", margin: "0 auto", maxWidth: Math.round(vb.w * MAX_UPSCALE), animation: "rise var(--dur-base) var(--ease) both" }}
      >
        {data.edges.map((e, i) => {
          const a = positioned.byId[e.source];
          const b = positioned.byId[e.target];
          if (!a || !b) return null;
          return (
            <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y}
              stroke="var(--border)" strokeWidth={1 + e.weight * 3} opacity={0.5 + e.weight * 0.4} />
          );
        })}
        {positioned.nodes.map((nd) => {
          const r = nd.type === "query" ? 16 : 9;
          const isHovered = hoveredId === nd.id;
          const tooltip =
            nd.type === "query"
              ? nd.label
              : `${nd.document || "Source"}${typeof nd.importance === "number" ? ` · importance ${Math.round(nd.importance * 100)}%` : ""}\n${nd.label}`;
          return (
            <g
              key={nd.id}
              onClick={() => setSelected(nd)}
              onMouseEnter={() => setHoveredId(nd.id)}
              onMouseLeave={() => setHoveredId((h) => (h === nd.id ? null : h))}
              style={{ cursor: "pointer" }}
            >
              <title>{tooltip}</title>
              <circle cx={nd.x} cy={nd.y} r={r} fill={nodeColor(nd)} stroke="var(--surface)" strokeWidth={2} />
              {nd.type === "query" ? (
                <text x={nd.x} y={nd.y - 22} textAnchor="middle" fontSize={11} fill="var(--text)" fontWeight={600}>
                  {nd.label}
                </text>
              ) : (
                <text
                  x={nd.x + r + 4}
                  y={nd.y + 3}
                  fontSize={9}
                  fill="var(--text)"
                  opacity={isHovered ? 1 : 0.5}
                  style={{ transition: "opacity var(--dur-fast) var(--ease)" }}
                >
                  {truncateLabel(nd.label)}
                </text>
              )}
            </g>
          );
        })}
      </svg>
      {selected && selected.type === "chunk" && (
        <div className="card card-compact" style={{ marginTop: "var(--space-3)", background: "var(--raised)", fontSize: "var(--fs-xs)", color: "var(--text-2)" }}>
          <strong style={{ color: "var(--text)" }}>{selected.document || "Source"}</strong>
          {typeof selected.importance === "number" ? ` · importance ${Math.round(selected.importance * 100)}%` : ""}
          <div style={{ marginTop: 4 }}>{selected.label}</div>
        </div>
      )}
    </div>
  );
}
