"use client";

import type { Toast } from "@/hooks/useToast";

export default function ToastViewport({ toast }: { toast: Toast | null }) {
  return (
    <div aria-live="polite" role="status" style={{ position: "fixed", bottom: 22, right: 22, zIndex: 70 }}>
      {toast && (
        <div
          style={{
            padding: "12px 16px",
            borderRadius: "var(--radius-md)",
            fontSize: "var(--fs-sm)",
            fontWeight: "var(--fw-medium)",
            color: "var(--text)",
            background: "var(--surface)",
            border: `1px solid ${toast.kind === "ok" ? "var(--accent-line)" : "var(--danger-line)"}`,
            boxShadow: "var(--shadow-overlay)",
            animation: "rise .3s ease both",
          }}
        >
          <span style={{ marginRight: 8 }} aria-hidden>
            {toast.kind === "ok" ? "✓" : "⚠"}
          </span>
          {toast.text}
        </div>
      )}
    </div>
  );
}
