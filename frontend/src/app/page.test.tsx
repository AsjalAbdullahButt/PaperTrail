import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// Force the authenticated view via the auth store, and stub the router.
type AuthSlice = {
  isAuthenticated: boolean;
  ready: boolean;
  restoreSession: () => void;
  logout: () => Promise<void>;
};
vi.mock("@/stores/authStore", () => ({
  useAuthStore: (selector: (s: AuthSlice) => unknown) =>
    selector({
      isAuthenticated: true,
      ready: true,
      restoreSession: () => {},
      logout: async () => {},
    }),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    askQuery: vi.fn(),
    askQueryStreaming: vi.fn(),
    uploadDocument: vi.fn(),
  };
});

import Home from "@/app/page";
import { askQueryStreaming, uploadDocument, type QueryStreamEvent } from "@/lib/api";

describe("Home (authenticated)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("toggles the answer mode and reflects it via aria-pressed", async () => {
    render(<Home />);
    const rag = screen.getByRole("button", { name: /^rag$/i });
    const direct = screen.getByRole("button", { name: /^direct$/i });
    expect(rag).toHaveAttribute("aria-pressed", "true");
    expect(direct).toHaveAttribute("aria-pressed", "false");

    await userEvent.click(direct);
    expect(direct).toHaveAttribute("aria-pressed", "true");
    expect(rag).toHaveAttribute("aria-pressed", "false");
  });

  it("toggles the theme (label reflects the next theme)", async () => {
    render(<Home />);
    // Starts dark -> control offers switching to light.
    const toggle = screen.getByRole("button", { name: /switch to light theme/i });
    await userEvent.click(toggle);
    expect(
      screen.getByRole("button", { name: /switch to dark theme/i })
    ).toBeInTheDocument();
  });

  it("shows an error toast when an upload fails", async () => {
    vi.mocked(uploadDocument).mockRejectedValueOnce(new Error("Upload failed: too big"));
    const { container } = render(<Home />);
    const fileInput = container.querySelector(
      'input[type="file"]'
    ) as HTMLInputElement;
    const file = new File(["hi"], "notes.txt", { type: "text/plain" });
    await userEvent.upload(fileInput, file);

    expect(await screen.findByText(/upload failed: too big/i)).toBeInTheDocument();
  });

  it("shows source cards before the answer finishes streaming in", async () => {
    async function* fakeStream(): AsyncGenerator<QueryStreamEvent> {
      yield {
        type: "sources",
        sources: [
          {
            n: 1,
            title: "facts.txt",
            snippet: "The fictional country Zubrowka has a capital city.",
            score: 90,
            document_id: "doc-1",
            chunk_id: "chunk-1",
            chunk_index: 0,
            page_number: 1,
            section_heading: null,
            similarity_score: 0.9,
            importance_score: 0.5,
            relevance_pct: 90,
          },
        ],
      };
      yield { type: "token", token: "Lutz " };
      yield { type: "token", token: "is the capital." };
      yield { type: "followups", followups: ["What else is in Zubrowka?"] };
      yield { type: "hallucination", unsupported_sentences: [] };
      yield { type: "done", query_id: "q-1", confidence_score: 0.87 };
    }
    vi.mocked(askQueryStreaming).mockReturnValueOnce(fakeStream());

    render(<Home />);
    await userEvent.type(
      screen.getByPlaceholderText(/ask anything/i),
      "What is the capital?"
    );
    await userEvent.click(screen.getByRole("button", { name: /^ask/i }));

    // Source card appears (title from the "sources" event).
    expect(await screen.findByText("facts.txt")).toBeInTheDocument();
    // Streaming completes and the full answer text renders.
    expect(await screen.findByText(/Lutz is the capital\./)).toBeInTheDocument();
    // Follow-up question surfaced only after the stream fully completes.
    expect(
      await screen.findByText("What else is in Zubrowka?")
    ).toBeInTheDocument();
  });

  it("threads prior turns into the next query, and 'New conversation' clears them", async () => {
    async function* fakeStream(answer: string): AsyncGenerator<QueryStreamEvent> {
      yield { type: "sources", sources: [] };
      yield { type: "token", token: answer };
      yield { type: "done", query_id: "q-1", confidence_score: 0.5 };
    }

    const calls: unknown[] = [];
    vi.mocked(askQueryStreaming).mockImplementation((_q, _mode, opts) => {
      calls.push(opts?.conversation_history ?? []);
      return fakeStream(`answer #${calls.length}`);
    });

    render(<Home />);
    const input = screen.getByPlaceholderText(/ask anything/i);
    const askButton = screen.getByRole("button", { name: /^ask/i });

    await userEvent.type(input, "first question");
    await userEvent.click(askButton);
    expect(await screen.findByText("answer #1")).toBeInTheDocument();
    expect(calls[0]).toEqual([]); // no prior turns yet

    await userEvent.clear(input);
    await userEvent.type(input, "second question");
    await userEvent.click(askButton);
    expect(await screen.findByText("answer #2")).toBeInTheDocument();
    // The prior exchange is now carried as context.
    expect(calls[1]).toEqual([
      { role: "user", content: "first question" },
      { role: "assistant", content: "answer #1" },
    ]);

    await userEvent.click(screen.getByRole("button", { name: /new conversation/i }));
    await userEvent.clear(input);
    await userEvent.type(input, "third question");
    await userEvent.click(askButton);
    expect(await screen.findByText("answer #3")).toBeInTheDocument();
    expect(calls[2]).toEqual([]); // cleared by "New conversation"
  });
});
