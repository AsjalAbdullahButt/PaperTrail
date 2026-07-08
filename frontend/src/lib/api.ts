// API client for the PaperTrail backend (auth, documents, query, history).
//
// Access tokens live in memory only (never localStorage) — set via
// setAccessToken() by the auth store. Refresh tokens are an httpOnly cookie the
// browser sends automatically to /api/auth/* (credentials: "include"); JS never
// sees them. A same-origin, non-secret "session hint" cookie is mirrored so the
// Next.js middleware can drive redirect UX cross-origin.

const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://localhost:8000";

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
export type Source = {
  n: number;
  title: string;
  snippet: string;
  score: number; // percentage 0-100
  document_id: string;
  chunk_index: number;
};

export type QueryResponse = {
  answer: string;
  mode: "rag" | "direct";
  sources: Source[];
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
  created_at: string;
  chunk_count: number | null;
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

export type User = {
  id: string;
  email: string;
  display_name: string | null;
  created_at: string;
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
    if (typeof data?.error?.message === "string") return data.error.message;
    if (typeof data?.detail === "string") return data.detail;
    if (Array.isArray(data?.detail) && data.detail[0]?.msg) return data.detail[0].msg;
  } catch {
    /* ignore */
  }
  return `Request failed (${res.status})`;
}

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) throw new ApiError(await parseError(res), res.status);
  return res.json() as Promise<T>;
}

/* -------------------------------- auth ---------------------------------- */
type TokenResponse = { access_token: string };

export async function register(
  email: string,
  password: string,
  displayName?: string,
): Promise<string> {
  const res = await fetch(`${API_URL}/api/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include", // accept the httpOnly refresh cookie
    body: JSON.stringify({ email, password, display_name: displayName || null }),
  });
  const data = await handle<TokenResponse>(res);
  setAccessToken(data.access_token);
  return data.access_token;
}

export async function login(email: string, password: string): Promise<string> {
  const res = await fetch(`${API_URL}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ email, password }),
  });
  const data = await handle<TokenResponse>(res);
  setAccessToken(data.access_token);
  return data.access_token;
}

/** Exchange the httpOnly refresh cookie for a new access token. Returns null
 *  (without throwing) when there is no valid session to restore. */
export async function refresh(): Promise<string | null> {
  try {
    const res = await fetch(`${API_URL}/api/auth/refresh`, {
      method: "POST",
      credentials: "include",
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
    await fetch(`${API_URL}/api/auth/logout`, {
      method: "POST",
      credentials: "include",
    });
  } catch {
    /* best-effort; clear client state regardless */
  }
  setAccessToken(null);
}

export async function getMe(): Promise<User> {
  const res = await fetch(`${API_URL}/api/auth/me`, { headers: authHeaders() });
  return handle<User>(res);
}

/* ------------------------------- query ---------------------------------- */
export async function askQuery(
  question: string,
  mode: "rag" | "direct",
): Promise<QueryResponse> {
  const res = await fetch(`${API_URL}/api/query`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ question, mode }),
  });
  return handle<QueryResponse>(res);
}

/* ------------------------------ documents ------------------------------- */
export async function uploadDocument(file: File): Promise<UploadResult> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_URL}/api/documents/upload`, {
    method: "POST",
    headers: authHeaders(),
    body: form,
  });
  return handle<UploadResult>(res);
}

export async function getDocumentStatus(id: string): Promise<DocumentStatus> {
  const res = await fetch(`${API_URL}/api/documents/${id}/status`, {
    headers: authHeaders(),
  });
  return handle<DocumentStatus>(res);
}

export async function listDocuments(limit = 50, offset = 0): Promise<DocumentInfo[]> {
  const res = await fetch(`${API_URL}/api/documents?limit=${limit}&offset=${offset}`, {
    headers: authHeaders(),
  });
  return handle<DocumentInfo[]>(res);
}

export async function deleteDocument(id: string): Promise<void> {
  const res = await fetch(`${API_URL}/api/documents/${id}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  await handle<{ id: string; deleted: boolean }>(res);
}

/* ----------------------------- chat history ----------------------------- */
export async function getChatHistory(limit = 20, offset = 0): Promise<ChatHistoryPage> {
  const res = await fetch(`${API_URL}/api/chat-history?limit=${limit}&offset=${offset}`, {
    headers: authHeaders(),
  });
  return handle<ChatHistoryPage>(res);
}
