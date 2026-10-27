"use client";

import type { Toast } from "@/hooks/useToast";

export default function ToastViewport({ toast }: { toast: Toast | null }) {
  return (
    <div aria-live="polite" role="status" style={{ position: "fixed", bottom: 22, right: 22, zIndex: 70 }}>
      {toast && (
        <div
          style={{
            padding: "12px 16px",
            borderRadius: 12,
            fontSize: 13.5,
            fontWeight: 600,
            color: "var(--text)",
            background: "var(--card-bg)",
            border: `1px solid ${toast.kind === "ok" ? "var(--chip-border)" : "rgba(255,120,120,.4)"}`,
            backdropFilter: "blur(18px) saturate(150%)",
            WebkitBackdropFilter: "blur(18px) saturate(150%)",
            boxShadow: "0 10px 30px var(--cardShadow)",
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
