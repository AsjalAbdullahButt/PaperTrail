"use client";

import { useEffect, useRef, useState, type CSSProperties } from "react";
import { createPortal } from "react-dom";
import { useFloatingRect } from "@/hooks/useFloatingRect";
import { ChevronDownIcon } from "@/components/ui/Icons";

export type SelectOption = { value: string; label: string };

/** A themed dropdown that fully replaces the native <select>.
 *
 * Native <select> popups render as an OS-level widget outside the page's own
 * paint tree, so our dark-theme CSS variables and even the `color-scheme`
 * property don't reliably reach them on every browser/OS — they can render
 * with light-mode chrome regardless of the app's theme. Building the popup
 * out of our own DOM (portaled to <body>, positioned via the anchor's rect)
 * guarantees it always matches the app. */
export default function DropdownSelect({
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

  return (
    <>
      <button
        type="button"
        ref={anchorRef}
        className="btn btn-select"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={ariaLabel}
        style={style}
      >
        <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {selected ? selected.label : placeholder}
        </span>
        <span style={{ display: "inline-flex", flex: "none", color: "var(--muted)", transform: open ? "rotate(180deg)" : "none" }}>
          <ChevronDownIcon size={14} />
        </span>
      </button>
      {open && rect && typeof document !== "undefined" && createPortal(
        <div
          ref={menuRef}
          role="listbox"
          className="menu"
          style={{
            position: "fixed", top: rect.bottom + 6, left: `min(${rect.left}px, calc(100vw - ${Math.max(rect.width, 160) + 8}px))`, width: Math.max(rect.width, 160),
            maxHeight: 280, overflowY: "auto", zIndex: 1000,
            animation: "rise var(--dur-fast) var(--ease) both",
          }}
        >
          {placeholder && (
            <button type="button" role="option" className="menu-item" aria-selected={value === ""} onClick={() => pick("")}>
              {placeholder}
            </button>
          )}
          {options.map((o) => (
            <button key={o.value} type="button" role="option" className="menu-item" aria-selected={o.value === value} onClick={() => pick(o.value)}>
              {o.label}
            </button>
          ))}
        </div>,
        document.body
      )}
    </>
  );
}
