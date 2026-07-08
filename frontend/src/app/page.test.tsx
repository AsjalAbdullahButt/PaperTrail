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
    uploadDocument: vi.fn(),
  };
});

import Home from "@/app/page";
import { uploadDocument } from "@/lib/api";

describe("Home (authenticated)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("toggles the answer mode and reflects it via aria-pressed", async () => {
    render(<Home />);
    const rag = screen.getByRole("button", { name: /rag mode/i });
    const direct = screen.getByRole("button", { name: /direct mode/i });
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
});
