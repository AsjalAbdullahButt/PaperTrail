"use client";

import { useEffect, type ReactNode } from "react";

type Props = {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
};

/** Accessible right-side drawer: backdrop click + Escape close it. */
export default function RightSideDrawer({ open, onClose, title, children }: Props) {
  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 60,
        display: "flex",
        justifyContent: "flex-end",
      }}
    >
      {/* Backdrop */}
      <div
        onClick={onClose}
        aria-hidden
        style={{
          position: "absolute",
          inset: 0,
          background: "var(--scrim)",
          animation: "rise .2s ease both",
        }}
      />
      <aside
        role="dialog"
        aria-modal="true"
        aria-label={title}
        style={{
          position: "relative",
          width: "min(440px, 92vw)",
          height: "100%",
          overflowY: "auto",
          padding: "22px 22px 40px",
          background: "var(--surface)",
          borderLeft: "1px solid var(--border)",
          boxShadow: "var(--shadow-overlay)",
          animation: "slideIn .25s cubic-bezier(.4,0,.2,1) both",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: 18,
          }}
        >
          <h2 style={{ margin: 0, fontSize: "var(--fs-md)", fontWeight: "var(--fw-semibold)", color: "var(--text)", letterSpacing: "-.01em" }}>
            {title}
          </h2>
          <button
            onClick={onClose}
            aria-label="Close panel"
            style={{
              width: 32,
              height: 32,
              borderRadius: "var(--radius-sm)",
              border: "1px solid var(--border)",
              background: "var(--raised)",
              color: "var(--text)",
              fontSize: "var(--fs-lg)",
              lineHeight: 1,
              cursor: "pointer",
              flex: "none",
            }}
          >
            ×
          </button>
        </div>
        {children}
      </aside>
    </div>
  );
}
