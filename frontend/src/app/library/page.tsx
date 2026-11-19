"use client";

import { useCallback, useEffect, useState, type CSSProperties } from "react";
import dynamic from "next/dynamic";
import toast from "react-hot-toast";
import AuthenticatedPageLayout from "@/components/layout/AuthenticatedPageLayout";
import DropdownSelect from "@/components/ui/DropdownSelect";
import {
  addToCollection,
  addTags,
  createCollection,
  deleteCollection,
  getDocumentCoverage,
  listCollections,
  listDocumentsFiltered,
  listQueries,
  removeTag,
  type Collection,
  type CoverageCell,
  type DocumentInfo,
  type QueryHistoryItem,
} from "@/api/backendClient";

// Loaded only when a document's timeline is opened.
const DocumentTimeline = dynamic(() => import("@/components/documents/DocumentTimeline"));

const TYPE_ICON: Record<string, string> = {
  pdf: "PDF", docx: "DOC", pptx: "PPT", txt: "TXT", md: "MD", xlsx: "XLS", csv: "CSV",
};

const card: CSSProperties = {
  padding: "16px 18px", borderRadius: "var(--radius-md)", background: "var(--surface)",
  border: "1px solid var(--border)",
};
const label: CSSProperties = {
  fontSize: "var(--fs-xs)", fontWeight: "var(--fw-semibold)", letterSpacing: ".05em", textTransform: "uppercase",
  color: "var(--muted)",
};

export default function LibraryPage() {
  return (
    <AuthenticatedPageLayout>
      <LibraryInner />
    </AuthenticatedPageLayout>
  );
}

function LibraryInner() {
  const [collections, setCollections] = useState<Collection[]>([]);
  const [docs, setDocs] = useState<DocumentInfo[]>([]);
  const [view, setView] = useState<{ kind: "all" | "collection" | "bookmarks"; id?: string }>({ kind: "all" });
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [tagFilter, setTagFilter] = useState("");
  const [bookmarks, setBookmarks] = useState<QueryHistoryItem[]>([]);
  const [newCollection, setNewCollection] = useState("");

  const refreshCollections = useCallback(async () => {
    try { setCollections(await listCollections()); } catch { /* ignore */ }
  }, []);

  const refreshDocs = useCallback(async () => {
    if (view.kind === "bookmarks") {
      const page = await listQueries(100, 0);
      setBookmarks(page.items.filter((q) => q.bookmarked));
      return;
    }
    const params: { collection_id?: string; search?: string; type?: string; tag?: string } = {};
    if (view.kind === "collection") params.collection_id = view.id;
    if (search) params.search = search;
    if (typeFilter) params.type = typeFilter;
    if (tagFilter) params.tag = tagFilter;
    setDocs(await listDocumentsFiltered(params));
  }, [view, search, typeFilter, tagFilter]);

  // Network-driven data fetches, not state derivable during render — the
  // setState calls inside these run after an `await`, not synchronously, but
  // the lint rule can't see through that async boundary.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { refreshCollections(); }, [refreshCollections]);
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { refreshDocs(); }, [refreshDocs]);

  const duplicates = docs.filter((d) => d.is_duplicate);

  async function handleCreateCollection() {
    const name = newCollection.trim();
    if (!name) return;
    try {
      await createCollection(name);
      setNewCollection("");
      refreshCollections();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not create collection.");
    }
  }

  return (
    <div style={{ display: "flex", gap: 22, alignItems: "flex-start", flexWrap: "wrap" }}>
      {/* Sidebar */}
      <aside style={{ flex: "0 0 240px", minWidth: "min(200px, 100%)", display: "flex", flexDirection: "column", gap: 8 }}>
        <SidebarItem active={view.kind === "all"} label="All Documents" onClick={() => setView({ kind: "all" })} />
        <SidebarItem active={view.kind === "bookmarks"} label="★ Bookmarks" onClick={() => setView({ kind: "bookmarks" })} />
        <div style={{ ...label, marginTop: 14, padding: "0 4px" }}>Collections</div>
        {collections.map((c) => (
          <div key={c.id} style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <SidebarItem
              active={view.kind === "collection" && view.id === c.id}
              label={`${c.name} (${c.document_count ?? 0})`}
              onClick={() => setView({ kind: "collection", id: c.id })}
            />
            <button
              onClick={async () => { await deleteCollection(c.id); if (view.id === c.id) setView({ kind: "all" }); refreshCollections(); }}
              aria-label={`Delete ${c.name}`}
              style={{ border: "none", background: "none", color: "var(--muted)", cursor: "pointer", fontSize: "var(--fs-sm)" }}
            >✕</button>
          </div>
        ))}
        <div style={{ display: "flex", gap: 6, marginTop: 6 }}>
          <input
            value={newCollection}
            onChange={(e) => setNewCollection(e.target.value)}
            placeholder="New collection"
            style={{ flex: 1, minWidth: 0, padding: "8px 10px", borderRadius: "var(--radius-sm)", background: "var(--raised)", border: "1px solid var(--border)", color: "var(--text)", fontFamily: "inherit", fontSize: "var(--fs-sm)", outline: "none" }}
          />
          <button onClick={handleCreateCollection} style={{ border: "1px solid var(--border)", background: "var(--raised)", color: "var(--text)", borderRadius: "var(--radius-sm)", padding: "0 12px", cursor: "pointer", fontWeight: "var(--fw-semibold)" }}>+</button>
        </div>
      </aside>

      {/* Main */}
      <main style={{ flex: "1 1 520px", minWidth: "min(300px, 100%)" }}>
        {duplicates.length > 0 && view.kind !== "bookmarks" && (
          <div style={{ ...card, marginBottom: 16, borderColor: "var(--warn-line)", background: "var(--warn-soft)", color: "var(--warn)", fontSize: "var(--fs-sm)" }}>
            ⚠ {duplicates.length} document{duplicates.length === 1 ? "" : "s"} look like duplicates of existing uploads.
          </div>
        )}

        {view.kind === "bookmarks" ? (
          <BookmarksList items={bookmarks} />
        ) : (
          <>
            {/* Filters */}
            <div style={{ display: "flex", gap: 10, marginBottom: 16, flexWrap: "wrap" }}>
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search by name…"
                style={{ flex: "1 1 200px", padding: "10px 12px", borderRadius: "var(--radius-md)", background: "var(--surface)", border: "1px solid var(--border)", color: "var(--text)", fontFamily: "inherit", fontSize: "var(--fs-sm)", outline: "none" }}
              />
              <DropdownSelect
                value={typeFilter}
                onChange={setTypeFilter}
                placeholder="All types"
                ariaLabel="Filter by file type"
                options={["pdf", "docx", "txt", "md", "xlsx", "csv"].map((t) => ({ value: t, label: t.toUpperCase() }))}
              />
              <input
                value={tagFilter}
                onChange={(e) => setTagFilter(e.target.value)}
                placeholder="tag"
                style={{ ...selectStyle, width: 120 }}
              />
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 14 }}>
              {docs.map((d) => (
                <DocumentCard key={d.id} doc={d} collections={collections} onChanged={refreshDocs} />
              ))}
              {docs.length === 0 && (
                <div style={{ ...card, color: "var(--muted)", fontSize: "var(--fs-sm)" }}>No documents match.</div>
              )}
            </div>
          </>
        )}
      </main>
    </div>
  );
}

function SidebarItem({ active, label: text, onClick }: { active: boolean; label: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      style={{
        flex: 1, textAlign: "left", padding: "10px 12px", borderRadius: "var(--radius-md)", cursor: "pointer",
        fontFamily: "inherit", fontSize: "var(--fs-sm)", fontWeight: active ? "var(--fw-semibold)" : "var(--fw-medium)", minHeight: 44,
        color: active ? "var(--on-accent)" : "var(--text)",
        background: active ? "var(--accent)" : "var(--raised)",
        border: "1px solid var(--border)",
      }}
    >
      {text}
    </button>
  );
}

function DocumentCard({ doc, collections, onChanged }: { doc: DocumentInfo; collections: Collection[]; onChanged: () => void }) {
  const [coverage, setCoverage] = useState<CoverageCell[] | null>(null);
  const [showTimeline, setShowTimeline] = useState(false);
  const [newTag, setNewTag] = useState("");

  async function toggleCoverage() {
    if (coverage) { setCoverage(null); return; }
    setCoverage(await getDocumentCoverage(doc.id));
  }
  async function handleAddTag() {
    const tag = newTag.trim().toLowerCase();
    if (!tag) return;
    try { await addTags(doc.id, [tag]); setNewTag(""); onChanged(); } catch { /* invalid tag */ }
  }

  return (
    <div style={card}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <div style={{ width: 34, height: 34, borderRadius: "var(--radius-sm)", background: "var(--accent)", color: "var(--on-accent)", fontWeight: "var(--fw-semibold)", fontSize: "var(--fs-xs)", display: "flex", alignItems: "center", justifyContent: "center", flex: "none" }}>
          {TYPE_ICON[doc.file_type] || "DOC"}
        </div>
        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{ fontSize: "var(--fs-sm)", fontWeight: "var(--fw-semibold)", color: "var(--text)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{doc.filename}</div>
          <div style={{ fontSize: "var(--fs-xs)", color: "var(--muted)" }}>
            {doc.page_count ? `${doc.page_count}p · ` : ""}{doc.chunk_count ?? 0} chunks · v{doc.version_number}
          </div>
        </div>
      </div>

      {doc.is_duplicate && (
        <div style={{ marginTop: 8, fontSize: "var(--fs-xs)", color: "var(--warn)" }}>
          ⚠ Duplicate of {doc.duplicate_of_name}
        </div>
      )}

      <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 10 }}>
        {doc.tags.map((tag) => (
          <span key={tag} style={{ display: "inline-flex", alignItems: "center", gap: 5, padding: "3px 8px", borderRadius: "var(--radius-sm)", fontSize: "var(--fs-xs)", color: "var(--accent)", background: "var(--accent-soft)", border: "1px solid var(--accent-line)" }}>
            {tag}
            <button onClick={async () => { await removeTag(doc.id, tag); onChanged(); }} aria-label={`Remove ${tag}`} style={{ border: "none", background: "none", color: "inherit", cursor: "pointer", padding: 0, fontSize: "var(--fs-xs)" }}>✕</button>
          </span>
        ))}
      </div>

      <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 10 }}>
        <input value={newTag} onChange={(e) => setNewTag(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") handleAddTag(); }} placeholder="add tag" style={{ flex: "1 1 100px", minWidth: 0, padding: "6px 9px", borderRadius: "var(--radius-sm)", background: "var(--raised)", border: "1px solid var(--border)", color: "var(--text)", fontFamily: "inherit", fontSize: "var(--fs-xs)", outline: "none" }} />
        <DropdownSelect
          value=""
          onChange={async (v) => { if (v) await addToCollection(v, [doc.id]); }}
          placeholder="+ collection"
          ariaLabel={`Add ${doc.filename} to a collection`}
          options={collections.map((c) => ({ value: c.id, label: c.name }))}
          style={{ flex: "1 1 110px", minWidth: 0, fontSize: "var(--fs-xs)", padding: "6px 8px" }}
        />
        <button onClick={toggleCoverage} style={{ flex: "0 0 auto", border: "1px solid var(--border)", background: "var(--raised)", color: "var(--text)", borderRadius: "var(--radius-sm)", padding: "0 10px", height: 30, cursor: "pointer", fontSize: "var(--fs-xs)" }}>
          {coverage ? "Hide" : "Coverage"}
        </button>
        <button onClick={() => setShowTimeline((v) => !v)} style={{ flex: "0 0 auto", border: "1px solid var(--border)", background: "var(--raised)", color: "var(--text)", borderRadius: "var(--radius-sm)", padding: "0 10px", height: 30, cursor: "pointer", fontSize: "var(--fs-xs)" }}>
          Timeline
        </button>
      </div>

      {coverage && <CoverageHeatmap cells={coverage} />}
      {showTimeline && <DocumentTimeline documentId={doc.id} />}
    </div>
  );
}

function CoverageHeatmap({ cells }: { cells: CoverageCell[] }) {
  const max = Math.max(1, ...cells.map((c) => c.retrieved_count));
  return (
    <div style={{ marginTop: 10 }}>
      <div style={{ ...label, marginBottom: 6 }}>Coverage</div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 2 }}>
        {cells.map((c) => {
          const intensity = c.retrieved_count / max;
          const bg = c.retrieved_count === 0
            ? "var(--raised)"
            : `color-mix(in srgb, var(--accent) ${Math.round((0.25 + 0.75 * intensity) * 100)}%, transparent)`;
          return (
            <div
              key={c.chunk_id}
              title={`chunk ${c.chunk_index + 1}: retrieved ${c.retrieved_count}×`}
              style={{ width: 12, height: 12, borderRadius: "var(--radius-full)", background: bg, border: "1px solid var(--border)" }}
            />
          );
        })}
      </div>
    </div>
  );
}

function BookmarksList({ items }: { items: QueryHistoryItem[] }) {
  if (items.length === 0) return <div style={{ ...card, color: "var(--muted)" }}>No bookmarked queries yet.</div>;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {items.map((q) => (
        <div key={q.id} style={card}>
          <div style={{ fontSize: "var(--fs-sm)", fontWeight: "var(--fw-semibold)", color: "var(--text)" }}>{q.question}</div>
          <div style={{ fontSize: "var(--fs-sm)", color: "var(--muted)", marginTop: 6, lineHeight: 1.5 }}>{q.answer.slice(0, 220)}{q.answer.length > 220 ? "…" : ""}</div>
          {q.bookmark_note && <div style={{ fontSize: "var(--fs-xs)", color: "var(--accent)", marginTop: 6 }}>Note: {q.bookmark_note}</div>}
        </div>
      ))}
    </div>
  );
}

const selectStyle: CSSProperties = {
  padding: "10px 12px", borderRadius: "var(--radius-md)", background: "var(--surface)",
  border: "1px solid var(--border)", color: "var(--text)", fontFamily: "inherit",
  fontSize: "var(--fs-sm)", outline: "none", cursor: "pointer",
};
