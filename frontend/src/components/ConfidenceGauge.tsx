"use client";

// SVG semicircular arc gauge for a 0..1 confidence score (no chart library).

const R = 46;
const CX = 60;
const CY = 56;

function polar(angleDeg: number): [number, number] {
  const a = (angleDeg * Math.PI) / 180;
  return [CX + R * Math.cos(a), CY + R * Math.sin(a)];
}

function arcPath(fromDeg: number, toDeg: number): string {
  const [x1, y1] = polar(fromDeg);
  const [x2, y2] = polar(toDeg);
  const large = toDeg - fromDeg > 180 ? 1 : 0;
  return `M ${x1} ${y1} A ${R} ${R} 0 ${large} 1 ${x2} ${y2}`;
}

export default function ConfidenceGauge({ value }: { value: number }) {
  const v = Math.max(0, Math.min(1, value));
  // Semicircle from 180deg (left) to 360deg (right).
  const end = 180 + v * 180;
  const pct = Math.round(v * 100);
  const label = v >= 0.75 ? "High confidence" : v >= 0.5 ? "Moderate" : "Low confidence";

  return (
    <div style={{ display: "inline-flex", flexDirection: "column", alignItems: "center", gap: 2 }}>
      <svg viewBox="0 0 120 70" width="120" height="70" role="img" aria-label={`Confidence ${pct} percent`}>
        <defs>
          <linearGradient id="conf-grad" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="var(--accent)" />
            <stop offset="100%" stopColor="var(--accent2)" />
          </linearGradient>
        </defs>
        <path d={arcPath(180, 360)} fill="none" stroke="var(--seg-bg)" strokeWidth={9} strokeLinecap="round" />
        {v > 0 && (
          <path d={arcPath(180, end)} fill="none" stroke="url(#conf-grad)" strokeWidth={9} strokeLinecap="round" />
        )}
        <text x={CX} y={CY - 6} textAnchor="middle" fontSize={18} fontWeight={800} fill="var(--text)">
          {pct}%
        </text>
      </svg>
      <span style={{ fontSize: 12, fontWeight: 600, color: "var(--muted)" }}>{label}</span>
    </div>
  );
}
