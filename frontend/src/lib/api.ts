// Thin API client for the PaperTrail backend.

const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://localhost:8000";

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

async function parseError(res: Response): Promise<string> {
  try {
    const data = await res.json();
    if (typeof data?.detail === "string") return data.detail;
    if (Array.isArray(data?.detail) && data.detail[0]?.msg) return data.detail[0].msg;
  } catch {
    /* ignore */
  }
  return `Request failed (${res.status})`;
}

export async function askQuery(
  question: string,
  mode: "rag" | "direct"
): Promise<QueryResponse> {
  const res = await fetch(`${API_URL}/api/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, mode }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function uploadDocument(file: File): Promise<UploadResult> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_URL}/api/documents/upload`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}
