"use client";

import { useState } from "react";

export type Toast = { kind: "ok" | "err"; text: string };

/** Simple auto-dismissing toast: showToast(...) replaces any current toast
 * and clears it after 4s. */
export function useToast() {
  const [toast, setToast] = useState<Toast | null>(null);

  function showToast(kind: Toast["kind"], text: string) {
    setToast({ kind, text });
    window.setTimeout(() => setToast(null), 4000);
  }

  return { toast, showToast };
}
