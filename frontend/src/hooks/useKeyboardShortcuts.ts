"use client";

import { useEffect } from "react";

export type ShortcutHandlers = {
  focusQuery?: () => void; // "/"
  escape?: () => void; // Escape
  commandPalette?: () => void; // Ctrl/Cmd+K
  upload?: () => void; // Ctrl/Cmd+U
  history?: () => void; // Ctrl/Cmd+H
  shortcutsHelp?: () => void; // Ctrl/Cmd+/
};

function isTyping(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null;
  if (!el) return false;
  const tag = el.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || el.isContentEditable;
}

/** Global keyboard shortcuts. Shortcuts that would interfere with typing are
 *  suppressed while an input/textarea is focused (except Escape). */
export function useKeyboardShortcuts(handlers: ShortcutHandlers) {
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const mod = e.ctrlKey || e.metaKey;

      if (e.key === "Escape") {
        handlers.escape?.();
        return;
      }
      if (mod && (e.key === "k" || e.key === "K")) {
        e.preventDefault();
        handlers.commandPalette?.();
        return;
      }
      if (mod && (e.key === "u" || e.key === "U")) {
        e.preventDefault();
        handlers.upload?.();
        return;
      }
      if (mod && (e.key === "h" || e.key === "H")) {
        e.preventDefault();
        handlers.history?.();
        return;
      }
      if (mod && e.key === "/") {
        e.preventDefault();
        handlers.shortcutsHelp?.();
        return;
      }
      if (e.key === "/" && !mod && !isTyping(e.target)) {
        e.preventDefault();
        handlers.focusQuery?.();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [handlers]);
}
