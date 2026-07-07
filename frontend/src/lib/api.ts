// API client for the PaperTrail backend (auth, documents, query, history).

const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://localhost:8000";

const TOKEN_KEY = "papertrail_token";

/* ------------------------------- types ---------------------------------- */
export type Source = {
  n: number;
  title: string;
  snippet: string;
  score: number; // percentage 0-100
  document_id: number;
  chunk_index: number;
};

export type QueryResponse = {
  answer: string;
  mode: "rag" | "direct";
  sources: Source[];
};

export type UploadResult = {
  id: number;
  filename: string;
  chunks_created: number;
};

export type DocumentInfo = {
  id: number;
  filename: string;
  file_type: string;
  page_count: number | null;
  created_at: string;
  chunk_count: number | null;
};

export type ChatHistoryItem = {
  id: number;
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

/** Thrown for non-2xx responses; carries the HTTP status for callers. */
export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/* --------------------------- token storage ------------------------------ */
export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

function setToken(token: string): void {
  if (typeof window !== "undefined") window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  if (typeof window !== "undefined") window.localStorage.removeItem(TOKEN_KEY);
}

export function isAuthenticated(): boolean {
  return getToken() !== null;
}

/* ----------------------------- internals -------------------------------- */
function authHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const token = getToken();
  return token ? { ...extra, Authorization: `Bearer ${token}` } : extra;
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
  if (res.status === 401) {
    // Token invalid/expired: drop it so the UI can send the user to sign-in.
    clearToken();
  }
  if (!res.ok) throw new ApiError(await parseError(res), res.status);
  return res.json() as Promise<T>;
}

/* -------------------------------- auth ---------------------------------- */
export async function register(email: string, password: string): Promise<void> {
  const res = await fetch(`${API_URL}/api/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  const data = await handle<{ access_token: string }>(res);
  setToken(data.access_token);
}

export async function login(email: string, password: string): Promise<void> {
  const res = await fetch(`${API_URL}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  const data = await handle<{ access_token: string }>(res);
  setToken(data.access_token);
}

export function logout(): void {
  clearToken();
}

/* ------------------------------- query ---------------------------------- */
export async function askQuery(
  question: string,
  mode: "rag" | "direct"
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

export async function listDocuments(
  limit = 50,
  offset = 0
): Promise<DocumentInfo[]> {
  const res = await fetch(
    `${API_URL}/api/documents?limit=${limit}&offset=${offset}`,
    { headers: authHeaders() }
  );
  return handle<DocumentInfo[]>(res);
}

export async function deleteDocument(id: number): Promise<void> {
  const res = await fetch(`${API_URL}/api/documents/${id}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  await handle<{ id: number; deleted: boolean }>(res);
}

/* ----------------------------- chat history ----------------------------- */
export async function getChatHistory(
  limit = 20,
  offset = 0
): Promise<ChatHistoryPage> {
  const res = await fetch(
    `${API_URL}/api/chat-history?limit=${limit}&offset=${offset}`,
    { headers: authHeaders() }
  );
  return handle<ChatHistoryPage>(res);
}
