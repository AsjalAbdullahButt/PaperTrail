"use client";

import { useRef, useState, type ChangeEvent } from "react";
import { ApiError, uploadDocument, type UploadResult } from "@/lib/api";

export function useDocumentUpload(opts: {
  onUnauthorized: () => void;
  onUploaded: () => void; // bump the document-manager refresh key
  showToast: (kind: "ok" | "err", text: string) => void;
}) {
  const [uploading, setUploading] = useState(false);
  const [lastUpload, setLastUpload] = useState<UploadResult | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  async function handleFile(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = ""; // allow re-uploading the same file
    if (!file) return;
    setUploading(true);
    try {
      const res = await uploadDocument(file);
      setLastUpload(res);
      opts.showToast("ok", `Uploaded ${res.filename} · ${res.chunks_created} chunks`);
      opts.onUploaded();
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) return opts.onUnauthorized();
      opts.showToast("err", err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  return { uploading, lastUpload, setLastUpload, fileRef, handleFile };
}
