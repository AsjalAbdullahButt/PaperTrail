"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { listCollections, listDocuments, listQueries } from "@/lib/api";

type Item = { id: string; label: string; group: string; action: () => void };

/** Fuzzy-ish command palette over documents, collections, and recent queries.
 *  Arrow keys navigate, Enter selects, Escape closes. */
export default function CommandPalette({
  open,
  onClose,
  onPickQuery,
}: {
  open: boolean;
  onClose: () => void;
  onPickQuery: (q: string) => void;
}) {
  const router = useRouter();
  const [items, setItems] = useState<Item[]>([]);
  const [q, setQ] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    setQ("");
    setActive(0);
    inputRef.current?.focus();
    (async () => {
      const [docs, colls, hist] = await Promise.all([
        listDocuments(50, 0).catch(() => []),
        listCollections().catch(() => []),
        listQueries(20, 0).then((p) => p.items).catch(() => []),
      ]);
      const next: Item[] = [
        ...docs.map((d) => ({ id: `doc-${d.id}`, label: d.filename, group: "Documents", action: () => router.push("/library") })),
        ...colls.map((c) => ({ id: `col-${c.id}`, label: c.name, group: "Collections", action: () => router.push("/library") })),
        ...hist.map((h) => ({ id: `q-${h.id}`, label: h.question, group: "Recent queries", action: () => onPickQuery(h.question) })),
      ];
      setItems(next);
    })();
  }, [open, router, onPickQuery]);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    const list = needle
      ? items.filter((it) => it.label.toLowerCase().includes(needle))
      : items;
    return list.slice(0, 40);
  }, [q, items]);

  useEffect(() => { setActive(0); }, [q]);

  if (!open) return null;

  function choose(it: Item) {
    it.action();
    onClose();
  }

  return (
    <div
      onClick={onClose}
      style={{ position: "fixed", inset: 0, zIndex: 90, background: "rgba(0,0,0,.45)", display: "flex", alignItems: "flex-start", justifyContent: "center", paddingTop: "12vh" }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(filtered.length - 1, a + 1)); }
          else if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(0, a - 1)); }
          else if (e.key === "Enter" && filtered[active]) { e.preventDefault(); choose(filtered[active]); }
          else if (e.key === "Escape") { onClose(); }
        }}
        style={{ width: "min(560px, 92vw)", maxHeight: "70vh", overflow: "hidden", display: "flex", flexDirection: "column", borderRadius: 18, background: "var(--card-bg)", border: "1px solid var(--card-border)", backdropFilter: "blur(24px) saturate(150%)", boxShadow: "0 24px 60px var(--cardShadow)" }}
      >
        <input
          ref={inputRef}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search documents, collections, queries…"
          style={{ padding: "16px 18px", background: "transparent", border: "none", borderBottom: "1px solid var(--card-border)", color: "var(--text)", fontFamily: "inherit", fontSize: 16, outline: "none" }}
        />
        <div style={{ overflowY: "auto" }}>
          {filtered.length === 0 && (
            <div style={{ padding: 18, color: "var(--muted)", fontSize: 14 }}>No matches.</div>
          )}
          {filtered.map((it, i) => (
            <button
              key={it.id}
              onMouseEnter={() => setActive(i)}
              onClick={() => choose(it)}
              style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%", textAlign: "left", padding: "11px 18px", border: "none", cursor: "pointer", fontFamily: "inherit", fontSize: 14, color: "var(--text)", background: i === active ? "var(--seg-bg)" : "transparent" }}
            >
              <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{it.label}</span>
              <span style={{ flex: "none", marginLeft: 12, fontSize: 11, color: "var(--muted)" }}>{it.group}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
