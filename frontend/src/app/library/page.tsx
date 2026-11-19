"use client";

import { useCallback, useEffect, useState } from "react";
import dynamic from "next/dynamic";
import toast from "react-hot-toast";
import AuthenticatedPageLayout from "@/components/layout/AuthenticatedPageLayout";
import DropdownSelect from "@/components/ui/DropdownSelect";
import { CloseIcon, PlusIcon, StarIcon, WarningIcon } from "@/components/ui/Icons";
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
  // Display state for the list: first load in flight, and a failed load.
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

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

  const loadDocs = useCallback(() => {
    setLoadError(false);
    refreshDocs()
      .catch(() => setLoadError(true))
      .finally(() => setLoading(false));
  }, [refreshDocs]);

  // Network-driven data fetches, not state derivable during render — the
  // setState calls inside these run after an `await`, not synchronously, but
  // the lint rule can't see through that async boundary.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { refreshCollections(); }, [refreshCollections]);
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { loadDocs(); }, [loadDocs]);

  const duplicates = docs.filter((d) => d.is_duplicate);
  const filtered = Boolean(search || typeFilter || tagFilter) || view.kind === "collection";

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
    <>
      <h1 className="h-page" style={{ marginBottom: "var(--space-5)" }}>Library</h1>
      <div className="split">
        {/* Sidebar */}
        <aside className="split-side" aria-label="Library views">
          <SidebarItem active={view.kind === "all"} onClick={() => setView({ kind: "all" })}>All documents</SidebarItem>
          <SidebarItem active={view.kind === "bookmarks"} onClick={() => setView({ kind: "bookmarks" })}>
            <StarIcon /> Bookmarks
          </SidebarItem>
          <div className="section-label" style={{ margin: "var(--space-5) var(--space-1) var(--space-1)" }}>Collections</div>
          {collections.map((c) => (
            <div key={c.id} className="row" style={{ gap: "var(--space-1)" }}>
              <SidebarItem
                active={view.kind === "collection" && view.id === c.id}
                onClick={() => setView({ kind: "collection", id: c.id })}
              >
                {`${c.name} (${c.document_count ?? 0})`}
              </SidebarItem>
              <button
                type="button"
                className="btn btn-ghost btn-icon btn-sm"
                onClick={async () => { await deleteCollection(c.id); if (view.id === c.id) setView({ kind: "all" }); refreshCollections(); }}
                aria-label={`Delete ${c.name}`}
                title={`Delete ${c.name}`}
              >
                <CloseIcon size={14} />
              </button>
            </div>
          ))}
          <div className="row" style={{ marginTop: "var(--space-2)" }}>
            <input
              className="input input-sm"
              value={newCollection}
              onChange={(e) => setNewCollection(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") handleCreateCollection(); }}
              placeholder="New collection"
              aria-label="New collection name"
            />
            <button type="button" className="btn btn-icon btn-sm" onClick={handleCreateCollection} aria-label="Create collection" title="Create collection">
              <PlusIcon />
            </button>
          </div>
        </aside>

        {/* Main */}
        <section style={{ minWidth: 0 }}>
          {duplicates.length > 0 && view.kind !== "bookmarks" && (
            <div className="alert alert-warn" style={{ marginBottom: "var(--space-4)" }}>
              <WarningIcon style={{ marginTop: 2 }} />
              <span>{duplicates.length} document{duplicates.length === 1 ? "" : "s"} look like duplicates of existing uploads.</span>
            </div>
          )}

          {view.kind === "bookmarks" ? (
            <BookmarksList items={bookmarks} />
          ) : (
            <>
              {/* Filters */}
              <div className="toolbar" style={{ marginBottom: "var(--space-4)" }}>
                <input
                  className="input"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search by name…"
                  aria-label="Search documents by name"
                  style={{ flex: "1 1 200px", width: "auto" }}
                />
                <DropdownSelect
                  value={typeFilter}
                  onChange={setTypeFilter}
                  placeholder="All types"
                  ariaLabel="Filter by file type"
                  options={["pdf", "docx", "txt", "md", "xlsx", "csv"].map((t) => ({ value: t, label: t.toUpperCase() }))}
                />
                <input
                  className="input"
                  value={tagFilter}
                  onChange={(e) => setTagFilter(e.target.value)}
                  placeholder="Tag"
                  aria-label="Filter by tag"
                  style={{ width: 120 }}
                />
              </div>

              {loadError ? (
                <div className="alert alert-danger" role="alert" style={{ justifyContent: "space-between", alignItems: "center" }}>
                  <span>Couldn&rsquo;t load your documents.</span>
                  <button type="button" className="btn btn-sm" onClick={loadDocs}>Try again</button>
                </div>
              ) : loading ? (
                <div className="doc-grid" aria-busy="true">
                  {[0, 1, 2].map((i) => (
                    <div key={i} className="card skeleton" style={{ height: 140, animationDelay: `${i * 0.1}s` }} />
                  ))}
                </div>
              ) : docs.length === 0 ? (
                <div className="card empty">
                  <div className="empty-title">{filtered ? "No documents match" : "No documents yet"}</div>
                  {filtered ? "Try a different search or filter." : "Upload a document from the home page to get started."}
                </div>
              ) : (
                <div className="doc-grid">
                  {docs.map((d) => (
                    <DocumentCard key={d.id} doc={d} collections={collections} onChanged={loadDocs} />
                  ))}
                </div>
              )}
            </>
          )}
        </section>
      </div>
    </>
  );
}

function SidebarItem({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`btn btn-ghost side-item${active ? " is-active" : ""}`}
      aria-current={active ? "true" : undefined}
    >
      {children}
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
    <div className="card card-compact">
      <div className="row" style={{ gap: "var(--space-3)" }}>
        <div aria-hidden style={{ width: 36, height: 36, borderRadius: "var(--radius-sm)", background: "var(--raised)", border: "1px solid var(--border)", color: "var(--text-2)", fontWeight: "var(--fw-medium)", fontSize: "var(--fs-xs)", display: "flex", alignItems: "center", justifyContent: "center", flex: "none" }}>
          {TYPE_ICON[doc.file_type] || "DOC"}
        </div>
        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{ fontSize: "var(--fs-sm)", fontWeight: "var(--fw-semibold)", color: "var(--text)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{doc.filename}</div>
          <div className="meta">
            {doc.page_count ? `${doc.page_count}p · ` : ""}{doc.chunk_count ?? 0} chunks · v{doc.version_number}
          </div>
        </div>
      </div>

      {doc.is_duplicate && (
        <div className="row" style={{ marginTop: "var(--space-2)", gap: "var(--space-1)", fontSize: "var(--fs-xs)", color: "var(--warn)" }}>
          <WarningIcon size={14} /> Duplicate of {doc.duplicate_of_name}
        </div>
      )}

      {doc.tags.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-1)", marginTop: "var(--space-3)" }}>
          {doc.tags.map((tag) => (
            <span key={tag} className="chip chip-accent" style={{ paddingRight: 2 }}>
              {tag}
              <button type="button" className="btn btn-ghost btn-icon" onClick={async () => { await removeTag(doc.id, tag); onChanged(); }} aria-label={`Remove ${tag}`} title={`Remove ${tag}`} style={{ width: 20, minHeight: 20, height: 20, color: "inherit" }}>
                <CloseIcon size={12} />
              </button>
            </span>
          ))}
        </div>
      )}

      <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-2)", marginTop: "var(--space-3)" }}>
        <input className="input input-sm" value={newTag} onChange={(e) => setNewTag(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") handleAddTag(); }} placeholder="Add tag" aria-label={`Add a tag to ${doc.filename}`} style={{ flex: "1 1 100px", width: "auto", minWidth: 0 }} />
        <DropdownSelect
          value=""
          onChange={async (v) => { if (v) await addToCollection(v, [doc.id]); }}
          placeholder="Add to collection"
          ariaLabel={`Add ${doc.filename} to a collection`}
          options={collections.map((c) => ({ value: c.id, label: c.name }))}
          style={{ flex: "1 1 130px", minWidth: 0, minHeight: 32, padding: "0 var(--space-3)", fontSize: "var(--fs-sm)" }}
        />
      </div>
      <div className="row" style={{ marginTop: "var(--space-2)" }}>
        <button type="button" className="btn btn-sm" onClick={toggleCoverage}>
          {coverage ? "Hide" : "Coverage"}
        </button>
        <button type="button" className="btn btn-sm" onClick={() => setShowTimeline((v) => !v)}>
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
    <div style={{ marginTop: "var(--space-3)" }}>
      <div className="section-label" style={{ marginBottom: "var(--space-2)" }}>Coverage</div>
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
  if (items.length === 0) return <div className="card empty"><div className="empty-title">No bookmarked queries yet</div></div>;
  return (
    <div className="stack" style={{ gap: "var(--space-3)" }}>
      {items.map((q) => (
        <div key={q.id} className="card card-compact">
          <div style={{ fontSize: "var(--fs-sm)", fontWeight: "var(--fw-semibold)", color: "var(--text)" }}>{q.question}</div>
          <div style={{ fontSize: "var(--fs-sm)", color: "var(--text-2)", marginTop: "var(--space-2)", lineHeight: 1.5 }}>{q.answer.slice(0, 220)}{q.answer.length > 220 ? "…" : ""}</div>
          {q.bookmark_note && <div className="meta" style={{ color: "var(--accent)", marginTop: "var(--space-2)" }}>Note: {q.bookmark_note}</div>}
        </div>
      ))}
    </div>
  );
}
