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

// Calibration thresholds match backend/app/routers/query.py's _confidence():
// < 0.4 is capped low as an absolute "likely off-topic" gate, so labels
// follow the same cut points rather than the old relative 0.5/0.75 split.
const LOW_MAX = 0.4;
const HIGH_MIN = 0.7;

export default function ConfidenceGauge({ value }: { value: number }) {
  const v = Math.max(0, Math.min(1, value));
  // Semicircle from 180deg (left) to 360deg (right).
  const end = 180 + v * 180;
  const pct = Math.round(v * 100);
  const label = v > HIGH_MIN ? "High confidence" : v >= LOW_MAX ? "Moderate" : "Low confidence";
  const tooltip =
    v > HIGH_MIN
      ? "High — well-supported"
      : v >= LOW_MAX
      ? "Moderate — review sources"
      : "Low — answer may not be in documents";
  // Colour follows the word: accent for high, neutral for moderate, amber for
  // low. The label stays the main signal; no number or threshold changed.
  const tone = v > HIGH_MIN ? "var(--accent)" : v >= LOW_MAX ? "var(--text-2)" : "var(--warn)";

  return (
    <div
      title={tooltip}
      style={{ display: "inline-flex", flexDirection: "column", alignItems: "center", gap: "var(--space-1)" }}
    >
      <svg viewBox="0 0 120 70" width="120" height="70" role="img" aria-label={`Confidence ${pct} percent`}>
        <path d={arcPath(180, 360)} fill="none" stroke="var(--raised)" strokeWidth={9} strokeLinecap="round" />
        {v > 0 && (
          <path d={arcPath(180, end)} fill="none" stroke={tone} strokeWidth={9} strokeLinecap="round" />
        )}
        <text className="tabular-nums" x={CX} y={CY - 6} textAnchor="middle" fontSize={18} fontWeight={600} fill="var(--text)">
          {pct}%
        </text>
      </svg>
      <span style={{ fontSize: "var(--fs-sm)", fontWeight: "var(--fw-medium)", color: v >= LOW_MAX ? "var(--text-2)" : "var(--warn)" }}>{label}</span>
    </div>
  );
}
