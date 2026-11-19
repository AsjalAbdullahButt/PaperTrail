"use client";

import type { Toast } from "@/hooks/useToast";
import { CheckIcon, WarningIcon } from "@/components/ui/Icons";

export default function ToastViewport({ toast }: { toast: Toast | null }) {
  return (
    <div aria-live="polite" role="status" style={{ position: "fixed", bottom: "var(--space-5)", right: "var(--space-5)", left: "var(--space-4)", display: "flex", justifyContent: "flex-end", pointerEvents: "none", zIndex: 70 }}>
      {toast && (
        <div
          className="menu row"
          style={{
            gap: "var(--space-2)",
            padding: "var(--space-3) var(--space-4)",
            fontSize: "var(--fs-sm)",
            fontWeight: "var(--fw-medium)",
            color: "var(--text)",
            borderColor: toast.kind === "ok" ? "var(--accent-line)" : "var(--danger-line)",
            pointerEvents: "auto",
            animation: "rise var(--dur-base) var(--ease) both",
          }}
        >
          <span style={{ display: "inline-flex", color: toast.kind === "ok" ? "var(--accent)" : "var(--danger)" }}>
            {toast.kind === "ok" ? <CheckIcon /> : <WarningIcon />}
          </span>
          {toast.text}
        </div>
      )}
    </div>
  );
}
