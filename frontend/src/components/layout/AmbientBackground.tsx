"use client";

export default function AmbientBackground({ parallax }: { parallax: { x: number; y: number } }) {
  return (
    <div
      style={{
        position: "absolute", inset: 0, overflow: "hidden", pointerEvents: "none", zIndex: 0,
        transform: `translate3d(${parallax.x * 18}px, ${parallax.y * 18}px, 0)`,
        transition: "transform .25s ease-out", willChange: "transform",
      }}
    >
      <div style={{ position: "absolute", top: -140, left: -120, width: 560, height: 560, borderRadius: "50%", background: "var(--blob1)", filter: "blur(90px)", opacity: "var(--blobOp)" as unknown as number, animation: "floatA 18s ease-in-out infinite" }} />
      <div style={{ position: "absolute", bottom: -180, right: -120, width: 620, height: 620, borderRadius: "50%", background: "var(--blob2)", filter: "blur(100px)", opacity: "var(--blobOp)" as unknown as number, animation: "floatB 22s ease-in-out infinite" }} />
      <div style={{ position: "absolute", top: "32%", left: "44%", width: 420, height: 420, borderRadius: "50%", background: "var(--blob3)", filter: "blur(110px)", opacity: "var(--blobOp3)" as unknown as number, animation: "floatC 26s ease-in-out infinite" }} />
    </div>
  );
}
