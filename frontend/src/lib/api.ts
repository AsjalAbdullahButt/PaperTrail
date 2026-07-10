// API client for the PaperTrail backend (auth, documents, query, history).
//
// Access tokens live in memory only (never localStorage) — set via
// setAccessToken() by the auth store. Refresh tokens are an httpOnly cookie the
// browser sends automatically to /api/auth/* (credentials: "include"); JS never
// sees them. A same-origin, non-secret "session hint" cookie is mirrored so the
// Next.js middleware can drive redirect UX cross-origin.

const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://localhost:8000";

/** Resolves a possibly-relative URL (e.g. an avatar path returned by the API)
 * against the API origin, so it can be dropped straight into an <img src>. */
export function resolveApiUrl(url: string): string {
  return /^https?:\/\//i.test(url) ? url : `${API_URL}${url}`;
}

export const AUTH_EVENT = "papertrail-auth";
export const SESSION_HINT_COOKIE = "pt_session";

/* --------------------------- in-memory token ---------------------------- */
let accessToken: string | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
  if (typeof document !== "undefined") {
    if (token) {
      // Non-secret hint (no token value) so middleware can gate routes on
      // :3000 even though the real refresh cookie lives on the API origin.
      document.cookie = `${SESSION_HINT_COOKIE}=1; path=/; samesite=lax`;
    } else {
      document.cookie = `${SESSION_HINT_COOKIE}=; path=/; max-age=0; samesite=lax`;
    }
  }
  if (typeof window !== "undefined") window.dispatchEvent(new Event(AUTH_EVENT));
}

export function getAccessToken(): string | null {
  return accessToken;
}

export function isAuthenticated(): boolean {
  return accessToken !== null;
}

/* ------------------------------- types ---------------------------------- */
export type QueryMode = "rag" | "direct" | "multihop";

export type Source = {
  n: number;
  title: string;
  snippet: string;
  score: number; // relevance percentage 0-100 (meter)
  document_id: string;
  chunk_id: string;
  chunk_index: number;
  page_number: number;
  section_heading: string | null;
  similarity_score: number;
  importance_score: number;
  relevance_pct: number;
};

export type UnsupportedSentence = { sentence: string; source_chunk_id: string | null };

export type QueryResponse = {
  answer: string;
  mode: QueryMode;
  sources: Source[];
  confidence_score: number;
  followup_questions: string[];
  unsupported_sentences: UnsupportedSentence[];
  query_id: string | null;
};

export type Highlight = { text: string; score: number; chunk_index: number };
export type OutlineEntry = { heading: string; level: number; chunk_index: number };

export type UploadResult = {
  id: string;
  filename: string;
  file_type: string;
  page_count: number | null;
  word_count: number;
  chunks_created: number;
  highlights: Highlight[];
  outline: OutlineEntry[];
};

export type DocumentStatus = {
  id: string;
  filename: string;
  processed: boolean;
  processed_at: string | null;
  chunk_count: number;
};

export type DocumentInfo = {
  id: string;
  filename: string;
  file_type: string;
  page_count: number | null;
  word_count: number;
  version_number: number;
  created_at: string;
  chunk_count: number | null;
  tags: string[];
  is_duplicate: boolean;
  duplicate_of_name: string | null;
};

export type Collection = {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  document_count: number | null;
};

export type CoverageCell = {
  chunk_id: string;
  chunk_index: number;
  retrieved_count: number;
};

export type QueryHistoryItem = {
  id: string;
  question: string;
  answer: string;
  mode: string;
  confidence_score: number | null;
  bookmarked: boolean;
  bookmark_note: string | null;
  created_at: string;
};

export type QueryHistoryPage = {
  items: QueryHistoryItem[];
  total: number;
  limit: number;
  offset: number;
};

export type ChatHistoryItem = {
  id: string;
  question: string;
  answer: string;
  mode: string;
  created_at: string;
};

export type ChatHistoryPage = {
  items: ChatHistoryItem[];
  total: number;
  limit: number;
  offset: number;
};

export type MindMapNode = {
  id: string;
  label: string;
  type: "query" | "chunk";
  document?: string | null;
  importance?: number | null;
};
export type MindMapEdge = { source: string; target: string; weight: number };
export type MindMapData = { nodes: MindMapNode[]; edges: MindMapEdge[] };

export type TimelineEvent = { date: string; event: string; chunk_index: number };

export type User = {
  id: string;
  email: string;
  display_name: string | null;
  bio: string | null;
  avatar_url: string | null;
  created_at: string;
};

export type DayCount = { date: string; count: number };
export type AnalyticsOverview = {
  total_documents: number;
  total_queries: number;
  total_chunks: number;
  avg_confidence: number;
  most_queried_document: { name: string; query_count: number } | null;
  queries_this_week: DayCount[];
};
export type TopQuery = { query: string; count: number };
export type DocumentUsage = {
  document_id: string;
  name: string;
  total_retrievals: number;
  avg_similarity: number;
  last_queried: string | null;
};
export type CoverageGap = {
  document_id: string;
  name: string;
  total_chunks: number;
  unexplored_chunks: number;
  unexplored_pct: number;
};

/** Thrown for non-2xx responses; carries the HTTP status for callers. */
export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/* ----------------------------- internals -------------------------------- */
function authHeaders(extra: Record<string, string> = {}): Record<string, string> {
  return accessToken ? { ...extra, Authorization: `Bearer ${accessToken}` } : extra;
}

async function parseError(res: Response): Promise<string> {
  try {
    const data = await res.json();
    // Field-level validation errors (422) carry the actionable reason in
    // error.details[0].msg — prefer it over the generic "Request validation
    // failed." wrapper in error.message. Pydantic prefixes custom
    // field_validator messages with "Value error, "; strip that, it's an
    // implementation detail that means nothing to a user.
    const details = data?.error?.details;
    if (Array.isArray(details) && typeof details[0]?.msg === "string") {
      return details[0].msg.replace(/^Value error,\s*/, "");
    }
    if (typeof data?.error?.message === "string") return data.error.message;
    if (typeof data?.detail === "string") return data.detail;
    if (Array.isArray(data?.detail) && data.detail[0]?.msg) return data.detail[0].msg;
  } catch {
    /* ignore */
  }
  return `Request failed (${res.status})`;
}

async function handle<T>(res: Response): Promise<T> {
  if (res.status === 503 && typeof window !== "undefined") {
    const { default: toast } = await import("react-hot-toast");
    toast.error("Service temporarily unavailable — please try again in a moment.");
  }
  if (!res.ok) throw new ApiError(await parseError(res), res.status);
  return res.json() as Promise<T>;
}

/* --------------------------- low-level fetch ----------------------------- */
// One in-flight refresh shared by every concurrent caller (401 retries here,
// and restoreSession()/refreshToken() in the auth store), so any burst of
// concurrent callers triggers exactly one /api/auth/refresh round trip. This
// matters because refresh tokens are single-use: two independent calls to
// refresh() at once would send the same cookie twice, and the backend would
// treat the second as replay/theft and revoke the whole session.
let refreshInFlight: Promise<string | null> | null = null;

export function refreshOnce(): Promise<string | null> {
  if (!refreshInFlight) {
    refreshInFlight = refresh().finally(() => {
      refreshInFlight = null;
    });
  }
  return refreshInFlight;
}

export type ApiFetchInit = RequestInit & {
  /** Skip the silent refresh-and-retry. Used by the auth routes themselves,
   * where a 401 is a real answer (bad credentials / no session), not an
   * expired access token. */
  skipAuthRetry?: boolean;
};

/** The low-level fetch every API call routes through: attaches the in-memory
 * access token, and on a 401 silently refreshes once and retries the request
 * once with the new token. If the refresh also fails, the original 401
 * propagates so the caller / auth store can log the user out. */
export async function apiFetch(path: string, init: ApiFetchInit = {}): Promise<Response> {
  const { skipAuthRetry, headers, ...rest } = init;
  const doFetch = () =>
    fetch(`${API_URL}${path}`, {
      ...rest,
      // Recomputed per attempt so the retry picks up the refreshed token.
      headers: authHeaders((headers as Record<string, string>) ?? {}),
    });

  let res = await doFetch();
  if (res.status === 401 && !skipAuthRetry) {
    const token = await refreshOnce();
    if (token !== null) res = await doFetch(); // exactly one retry
  }
  return res;
}

/** Download the current user's data export ZIP (triggers a browser download). */
export async function exportMyData(): Promise<void> {
  const res = await apiFetch("/api/export/my-data");
  if (!res.ok) throw new ApiError(await parseError(res), res.status);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "papertrail-export.zip";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

/* -------------------------------- auth ---------------------------------- */
type TokenResponse = { access_token: string };

export async function register(
  email: string,
  password: string,
  displayName?: string,
): Promise<string> {
  const res = await apiFetch("/api/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include", // accept the httpOnly refresh cookie
    body: JSON.stringify({ email, password, display_name: displayName || null }),
    skipAuthRetry: true,
  });
  const data = await handle<TokenResponse>(res);
  setAccessToken(data.access_token);
  return data.access_token;
}

export async function login(email: string, password: string): Promise<string> {
  const res = await apiFetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ email, password }),
    skipAuthRetry: true,
  });
  const data = await handle<TokenResponse>(res);
  setAccessToken(data.access_token);
  return data.access_token;
}

/** Exchange the httpOnly refresh cookie for a new access token. Returns null
 *  (without throwing) when there is no valid session to restore. */
export async function refresh(): Promise<string | null> {
  try {
    const res = await apiFetch("/api/auth/refresh", {
      method: "POST",
      credentials: "include",
      skipAuthRetry: true, // a failed refresh must not recurse into itself
    });
    if (!res.ok) {
      setAccessToken(null);
      return null;
    }
    const data = (await res.json()) as TokenResponse;
    setAccessToken(data.access_token);
    return data.access_token;
  } catch {
    setAccessToken(null);
    return null;
  }
}

export async function logout(): Promise<void> {
  try {
    await apiFetch("/api/auth/logout", {
      method: "POST",
      credentials: "include",
      skipAuthRetry: true,
    });
  } catch {
    /* best-effort; clear client state regardless */
  }
  setAccessToken(null);
}

export async function getMe(): Promise<User> {
  const res = await apiFetch("/api/auth/me");
  return handle<User>(res);
}

export async function updateProfile(profile: {
  display_name?: string | null;
  bio?: string | null;
  avatar_url?: string | null;
}): Promise<User> {
  const res = await apiFetch("/api/auth/me", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(profile),
  });
  return handle<User>(res);
}

export async function uploadAvatar(file: File): Promise<User> {
  const form = new FormData();
  form.append("file", file);
  const res = await apiFetch("/api/auth/me/avatar", { method: "POST", body: form });
  return handle<User>(res);
}

export async function deleteAvatar(): Promise<User> {
  const res = await apiFetch("/api/auth/me/avatar", { method: "DELETE" });
  return handle<User>(res);
}

export async function changePassword(
  currentPassword: string,
  newPassword: string,
): Promise<void> {
  const res = await apiFetch("/api/auth/change-password", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  });
  await handle<{ detail: string }>(res);
}

export async function deleteAccount(): Promise<void> {
  const res = await apiFetch("/api/auth/me", { method: "DELETE" });
  await handle<{ detail: string }>(res);
  setAccessToken(null);
}

export async function forgotPassword(email: string): Promise<void> {
  const res = await apiFetch("/api/auth/forgot-password", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ email }),
    skipAuthRetry: true,
  });
  await handle<{ detail: string }>(res);
}

export async function resetPassword(token: string, newPassword: string): Promise<void> {
  const res = await apiFetch("/api/auth/reset-password", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ token, new_password: newPassword }),
    skipAuthRetry: true,
  });
  await handle<{ detail: string }>(res);
}

/* ------------------------------- query ---------------------------------- */
export async function askQuery(
  question: string,
  mode: QueryMode,
  opts: { document_ids?: string[]; collection_id?: string } = {},
): Promise<QueryResponse> {
  const res = await apiFetch("/api/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      mode,
      document_ids: opts.document_ids ?? [],
      collection_id: opts.collection_id ?? null,
    }),
  });
  return handle<QueryResponse>(res);
}

/* ------------------------------ documents ------------------------------- */
export async function uploadDocument(file: File): Promise<UploadResult> {
  const form = new FormData();
  form.append("file", file);
  const res = await apiFetch("/api/documents/upload", {
    method: "POST",
    body: form,
  });
  return handle<UploadResult>(res);
}

export async function getDocumentStatus(id: string): Promise<DocumentStatus> {
  const res = await apiFetch(`/api/documents/${id}/status`);
  return handle<DocumentStatus>(res);
}

export async function listDocuments(limit = 50, offset = 0): Promise<DocumentInfo[]> {
  const res = await apiFetch(`/api/documents?limit=${limit}&offset=${offset}`);
  return handle<DocumentInfo[]>(res);
}

export async function deleteDocument(id: string): Promise<void> {
  const res = await apiFetch(`/api/documents/${id}`, { method: "DELETE" });
  await handle<{ id: string; deleted: boolean }>(res);
}

export async function listDocumentsFiltered(params: {
  tag?: string;
  collection_id?: string;
  type?: string;
  search?: string;
} = {}): Promise<DocumentInfo[]> {
  const qs = new URLSearchParams();
  if (params.tag) qs.set("tag", params.tag);
  if (params.collection_id) qs.set("collection_id", params.collection_id);
  if (params.type) qs.set("type", params.type);
  if (params.search) qs.set("search", params.search);
  const res = await apiFetch(`/api/documents?${qs.toString()}`);
  return handle<DocumentInfo[]>(res);
}

export async function getDocumentCoverage(id: string): Promise<CoverageCell[]> {
  const res = await apiFetch(`/api/documents/${id}/coverage`);
  return handle<CoverageCell[]>(res);
}

export async function addTags(id: string, tags: string[]): Promise<{ tags: string[] }> {
  const res = await apiFetch(`/api/documents/${id}/tags`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tags }),
  });
  return handle<{ document_id: string; tags: string[] }>(res);
}

export async function removeTag(id: string, tag: string): Promise<{ tags: string[] }> {
  const res = await apiFetch(`/api/documents/${id}/tags/${encodeURIComponent(tag)}`, {
    method: "DELETE",
  });
  return handle<{ document_id: string; tags: string[] }>(res);
}

/* ----------------------------- collections ------------------------------ */
export async function listCollections(): Promise<Collection[]> {
  const res = await apiFetch("/api/collections");
  return handle<Collection[]>(res);
}

export async function createCollection(name: string, description?: string): Promise<Collection> {
  const res = await apiFetch("/api/collections", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, description: description ?? null }),
  });
  return handle<Collection>(res);
}

export async function addToCollection(collectionId: string, documentIds: string[]): Promise<Collection> {
  const res = await apiFetch(`/api/collections/${collectionId}/documents`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ document_ids: documentIds }),
  });
  return handle<Collection>(res);
}

export async function deleteCollection(id: string): Promise<void> {
  const res = await apiFetch(`/api/collections/${id}`, { method: "DELETE" });
  await handle<{ id: string; deleted: boolean }>(res);
}

/* -------------------------- query history ------------------------------- */
export async function listQueries(limit = 20, offset = 0): Promise<QueryHistoryPage> {
  const res = await apiFetch(`/api/queries?limit=${limit}&offset=${offset}`);
  return handle<QueryHistoryPage>(res);
}

export async function toggleBookmark(id: string, note?: string): Promise<QueryHistoryItem> {
  const res = await apiFetch(`/api/queries/${id}/bookmark`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ note: note ?? null }),
  });
  return handle<QueryHistoryItem>(res);
}

export async function getMindMap(queryId: string): Promise<MindMapData> {
  const res = await apiFetch(`/api/queries/${queryId}/mindmap`);
  return handle<MindMapData>(res);
}

export async function getDocumentTimeline(id: string): Promise<TimelineEvent[]> {
  const res = await apiFetch(`/api/documents/${id}/timeline`);
  return handle<TimelineEvent[]>(res);
}

export async function deleteQuery(id: string): Promise<void> {
  const res = await apiFetch(`/api/queries/${id}`, { method: "DELETE" });
  await handle<{ id: string; deleted: boolean }>(res);
}

export type ShareResult = { token: string; shared: boolean };
export type SharedQuery = {
  question: string;
  answer: string;
  mode: string;
  confidence_score: number | null;
  source_count: number;
  created_at: string;
};

/** Issues a fresh public share link for a query, invalidating any previous one. */
export async function shareQuery(id: string): Promise<ShareResult> {
  const res = await apiFetch(`/api/queries/${id}/share`, { method: "POST" });
  return handle<ShareResult>(res);
}

export async function unshareQuery(id: string): Promise<ShareResult> {
  const res = await apiFetch(`/api/queries/${id}/share`, { method: "DELETE" });
  return handle<ShareResult>(res);
}

/** Public, unauthenticated fetch of a shared query by token. */
export async function getSharedQuery(token: string): Promise<SharedQuery> {
  const res = await apiFetch(`/api/share/${encodeURIComponent(token)}`, { skipAuthRetry: true });
  return handle<SharedQuery>(res);
}

/* ------------------------------ analytics ------------------------------- */
export async function getAnalyticsOverview(): Promise<AnalyticsOverview> {
  const res = await apiFetch("/api/analytics/overview");
  return handle<AnalyticsOverview>(res);
}
export async function getTopQueries(limit = 10): Promise<TopQuery[]> {
  const res = await apiFetch(`/api/analytics/top-queries?limit=${limit}`);
  return handle<TopQuery[]>(res);
}
export async function getDocumentUsage(): Promise<DocumentUsage[]> {
  const res = await apiFetch("/api/analytics/document-usage");
  return handle<DocumentUsage[]>(res);
}
export async function getCoverageGaps(): Promise<CoverageGap[]> {
  const res = await apiFetch("/api/analytics/coverage-gaps");
  return handle<CoverageGap[]>(res);
}

/* ----------------------------- chat history ----------------------------- */
export async function getChatHistory(limit = 20, offset = 0): Promise<ChatHistoryPage> {
  const res = await apiFetch(`/api/chat-history?limit=${limit}&offset=${offset}`);
  return handle<ChatHistoryPage>(res);
}
