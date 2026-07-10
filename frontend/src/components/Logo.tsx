/** The PaperTrail brand mark: a document with a highlighted excerpt and a
 * traced checkmark, echoing the citation-preview glyph used on source cards
 * elsewhere in the app. Used in every top nav and the marketing header.
 *
 * Keep this in sync with app/icon.svg (the browser-tab favicon) by eye —
 * that file can't share this component since favicons have no access to our
 * CSS custom properties and are rendered outside React entirely. */
export default function Logo({ size = 30 }: { size?: number }) {
  return (
    <div
      aria-hidden
      style={{
        width: size,
        height: size,
        flex: "none",
        borderRadius: size * 0.3,
        background: "linear-gradient(135deg,var(--accent),var(--accent2))",
        boxShadow: "0 4px 14px var(--accentGlow)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <svg width={size * 0.58} height={size * 0.58} viewBox="0 0 24 24" fill="none">
        <path
          d="M6 2.5h7L18 7.5v14a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V3.5a1 1 0 0 1 1-1Z"
          fill="#fff"
          fillOpacity=".95"
        />
        <path
          d="M13 2.5V7a1 1 0 0 0 1 1h4"
          stroke="var(--accent)"
          strokeWidth="1.3"
          fill="none"
          opacity=".6"
        />
        <rect x="6.8" y="11" width="6.6" height="1.4" rx=".7" fill="var(--accent2)" opacity=".65" />
        <rect x="6.8" y="13.8" width="8.6" height="1.4" rx=".7" fill="var(--accent2)" opacity=".4" />
        <path
          d="M6.8 18.3l2.1 2.1 4.3-4.6"
          stroke="var(--accent)"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
          fill="none"
        />
      </svg>
    </div>
  );
}
