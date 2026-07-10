"use client";

import { useEffect, useRef, useState, type CSSProperties } from "react";
import { createPortal } from "react-dom";
import { useFloatingRect } from "@/hooks/useFloatingRect";

export type SelectOption = { value: string; label: string };

function ChevronDownIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M6 9l6 6 6-6" />
    </svg>
  );
}

/** A themed dropdown that fully replaces the native <select>.
 *
 * Native <select> popups render as an OS-level widget outside the page's own
 * paint tree, so our dark-theme CSS variables and even the `color-scheme`
 * property don't reliably reach them on every browser/OS — they can render
 * with light-mode chrome regardless of the app's theme. Building the popup
 * out of our own DOM (portaled to <body>, positioned via the anchor's rect)
 * guarantees it always matches the app. */
export default function Select({
  value,
  onChange,
  options,
  placeholder,
  style,
  ariaLabel,
}: {
  value: string;
  onChange: (value: string) => void;
  options: SelectOption[];
  placeholder?: string;
  style?: CSSProperties;
  ariaLabel?: string;
}) {
  const [open, setOpen] = useState(false);
  const anchorRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const rect = useFloatingRect(anchorRef, open);

  useEffect(() => {
    if (!open) return;
    function onDocClick(e: MouseEvent) {
      const target = e.target as Node;
      if (anchorRef.current?.contains(target)) return;
      if (menuRef.current?.contains(target)) return;
      setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const selected = options.find((o) => o.value === value);

  function pick(v: string) {
    onChange(v);
    setOpen(false);
  }

  const optionStyle = (active: boolean): CSSProperties => ({
    display: "block",
    width: "100%",
    padding: "9px 12px",
    borderRadius: 9,
    border: "none",
    background: active ? "var(--chip-bg)" : "none",
    color: active ? "var(--accent)" : "var(--text)",
    fontFamily: "inherit",
    fontSize: 13.5,
    fontWeight: active ? 700 : 500,
    textAlign: "left",
    cursor: "pointer",
  });

  return (
    <>
      <button
        type="button"
        ref={anchorRef}
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={ariaLabel}
        style={{
          display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8,
          fontFamily: "inherit", cursor: "pointer", textAlign: "left",
          color: "var(--text)", background: "var(--card-bg)",
          border: `1px solid ${open ? "var(--accent)" : "var(--card-border)"}`,
          borderRadius: 12, padding: "10px 12px", fontSize: 14,
          ...style,
        }}
      >
        <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {selected ? selected.label : placeholder}
        </span>
        <span style={{ display: "inline-flex", flex: "none", opacity: 0.7, transform: open ? "rotate(180deg)" : "none", transition: "transform .15s ease" }}>
          <ChevronDownIcon />
        </span>
      </button>
      {open && rect && typeof document !== "undefined" && createPortal(
        <div
          ref={menuRef}
          role="listbox"
          style={{
            position: "fixed", top: rect.bottom + 6, left: rect.left, width: Math.max(rect.width, 160),
            maxHeight: 280, overflowY: "auto", padding: 6, borderRadius: 12,
            background: "var(--menu-bg)", border: "1px solid var(--card-border)",
            boxShadow: "0 18px 40px var(--cardShadow)", zIndex: 1000,
            animation: "rise .12s ease both",
          }}
        >
          {placeholder && (
            <button type="button" role="option" aria-selected={value === ""} onClick={() => pick("")} style={optionStyle(value === "")}>
              {placeholder}
            </button>
          )}
          {options.map((o) => (
            <button key={o.value} type="button" role="option" aria-selected={o.value === value} onClick={() => pick(o.value)} style={optionStyle(o.value === value)}>
              {o.label}
            </button>
          ))}
        </div>,
        document.body
      )}
    </>
  );
}
