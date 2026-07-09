import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("@/lib/api", () => ({
  getMindMap: vi.fn(),
}));

import { getMindMap } from "@/lib/api";
import MindMap from "./MindMap";

describe("MindMap", () => {
  it("shows a real empty state instead of vanishing when there's not enough content", async () => {
    vi.mocked(getMindMap).mockResolvedValueOnce({
      nodes: [{ id: "q1", label: "Question", type: "query" }],
      edges: [],
    });
    render(<MindMap queryId="q1" />);
    expect(await screen.findByText(/not enough content to map yet/i)).toBeInTheDocument();
  });

  it("shows an error state when the fetch fails", async () => {
    vi.mocked(getMindMap).mockRejectedValueOnce(new Error("network down"));
    render(<MindMap queryId="q1" />);
    expect(await screen.findByText(/couldn.t load the concept map/i)).toBeInTheDocument();
  });

  it("renders a labeled legend and per-node hover tooltips when there's enough data", async () => {
    vi.mocked(getMindMap).mockResolvedValueOnce({
      nodes: [
        { id: "q1", label: "Question", type: "query" },
        { id: "c1", label: "Chunk about revenue projections", type: "chunk", document: "report.pdf", importance: 0.8 },
        { id: "c2", label: "Another chunk", type: "chunk", document: "notes.txt", importance: 0.1 },
      ],
      edges: [
        { source: "q1", target: "c1", weight: 0.9 },
        { source: "q1", target: "c2", weight: 0.3 },
      ],
    });
    const { container } = render(<MindMap queryId="q1" />);
    expect(await screen.findByText("Your question")).toBeInTheDocument();
    expect(screen.getByText("High-importance source")).toBeInTheDocument();
    expect(screen.getByText("Other source")).toBeInTheDocument();
    // Every node gets a <title> hover tooltip, not just query nodes.
    expect(container.querySelectorAll("title")).toHaveLength(3);
    // Chunk nodes now render a visible (if low-opacity) truncated label.
    expect(container.textContent).toContain("Chunk about revenue");
  });
});
