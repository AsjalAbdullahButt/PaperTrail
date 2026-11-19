"use client";

import { useEffect, type ReactNode } from "react";
import { CloseIcon } from "@/components/ui/Icons";

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
          animation: "rise var(--dur-base) var(--ease) both",
        }}
      />
      <aside
        role="dialog"
        aria-modal="true"
        aria-label={title}
        style={{
          position: "relative",
          width: "min(440px, 100vw)",
          height: "100%",
          overflowY: "auto",
          padding: "var(--space-5) var(--space-5) var(--space-7)",
          background: "var(--surface)",
          borderLeft: "1px solid var(--border)",
          boxShadow: "var(--shadow-overlay)",
          animation: "slideIn var(--dur-base) var(--ease) both",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: "var(--space-4)",
          }}
        >
          <h2 className="h-section">{title}</h2>
          <button type="button" className="btn btn-ghost btn-icon" onClick={onClose} aria-label="Close panel" title="Close panel">
            <CloseIcon />
          </button>
        </div>
        {children}
      </aside>
    </div>
  );
}
