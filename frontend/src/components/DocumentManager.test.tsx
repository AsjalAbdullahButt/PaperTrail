import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";

vi.mock("./SlideOver", () => ({
  default: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

vi.mock("@/lib/api", () => ({
  listDocuments: vi.fn(),
  deleteDocument: vi.fn(),
}));

import { listDocuments } from "@/lib/api";
import DocumentManager from "./DocumentManager";

const baseProps = {
  open: true,
  onClose: vi.fn(),
  refreshKey: 0,
  onChanged: vi.fn(),
  onUnauthorized: vi.fn(),
};

describe("DocumentManager", () => {
  it("shows loading then empty state", async () => {
    vi.mocked(listDocuments).mockResolvedValueOnce([]);
    render(<DocumentManager {...baseProps} />);
    expect(screen.getByText(/loading documents/i)).toBeInTheDocument();
    expect(await screen.findByText(/no documents yet/i)).toBeInTheDocument();
  });

  it("shows populated list state", async () => {
    vi.mocked(listDocuments).mockResolvedValueOnce([
      {
        id: "d1",
        filename: "report.txt",
        file_type: "txt",
        page_count: null,
        word_count: 50,
        version_number: 1,
        created_at: "2026-01-01T00:00:00Z",
        chunk_count: 3,
        tags: [],
        is_duplicate: false,
        duplicate_of_name: null,
      },
    ]);
    render(<DocumentManager {...baseProps} />);
    expect(await screen.findByText("report.txt")).toBeInTheDocument();
    expect(screen.getByText(/txt · 3 chunks/i)).toBeInTheDocument();
  });

  it("shows error state when load fails", async () => {
    vi.mocked(listDocuments).mockRejectedValueOnce(new Error("boom"));
    render(<DocumentManager {...baseProps} />);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("boom");
  });
});
