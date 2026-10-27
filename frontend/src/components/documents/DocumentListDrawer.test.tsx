import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";

vi.mock("../ui/RightSideDrawer", () => ({
  default: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

vi.mock("@/api/backendClient", () => ({
  listDocuments: vi.fn(),
  deleteDocument: vi.fn(),
}));

import { listDocuments } from "@/api/backendClient";
import DocumentListDrawer from "./DocumentListDrawer";

const baseProps = {
  open: true,
  onClose: vi.fn(),
  refreshKey: 0,
  onChanged: vi.fn(),
  onUnauthorized: vi.fn(),
};

describe("DocumentListDrawer", () => {
  it("shows loading then empty state", async () => {
    vi.mocked(listDocuments).mockResolvedValueOnce([]);
    render(<DocumentListDrawer {...baseProps} />);
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
        summary: null,
      },
    ]);
    render(<DocumentListDrawer {...baseProps} />);
    expect(await screen.findByText("report.txt")).toBeInTheDocument();
    expect(screen.getByText(/txt · 3 chunks/i)).toBeInTheDocument();
  });

  it("shows a one-line summary under the filename when present", async () => {
    vi.mocked(listDocuments).mockResolvedValueOnce([
      {
        id: "d2",
        filename: "with-summary.pdf",
        file_type: "pdf",
        page_count: 5,
        word_count: 500,
        version_number: 1,
        created_at: "2026-01-01T00:00:00Z",
        chunk_count: 4,
        tags: [],
        is_duplicate: false,
        duplicate_of_name: null,
        summary: "A concise executive summary of the document.",
      },
    ]);
    render(<DocumentListDrawer {...baseProps} />);
    expect(
      await screen.findByText("A concise executive summary of the document.")
    ).toBeInTheDocument();
  });

  it("shows error state when load fails", async () => {
    vi.mocked(listDocuments).mockRejectedValueOnce(new Error("boom"));
    render(<DocumentListDrawer {...baseProps} />);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("boom");
  });
});
