import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, login: vi.fn(), register: vi.fn() };
});

import AuthScreen from "@/components/AuthScreen";
import { ApiError, login, register } from "@/lib/api";

describe("AuthScreen", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows an error message when login fails", async () => {
    vi.mocked(login).mockRejectedValueOnce(
      new ApiError("Invalid email or password.", 401)
    );
    render(<AuthScreen />);
    await userEvent.type(screen.getByLabelText(/email/i), "a@b.io");
    await userEvent.type(screen.getByLabelText(/password/i), "password123");
    await userEvent.click(screen.getByRole("button", { name: /^sign in$/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /invalid email or password/i
    );
  });

  it("calls onAuthed after a successful register", async () => {
    vi.mocked(register).mockResolvedValueOnce(undefined);
    const onAuthed = vi.fn();
    render(<AuthScreen onAuthed={onAuthed} />);

    // Switch to register mode.
    await userEvent.click(screen.getByRole("button", { name: /create one/i }));
    await userEvent.type(screen.getByLabelText(/email/i), "new@user.io");
    await userEvent.type(screen.getByLabelText(/password/i), "password123");
    await userEvent.click(screen.getByRole("button", { name: /create account/i }));

    expect(register).toHaveBeenCalledWith("new@user.io", "password123");
    expect(onAuthed).toHaveBeenCalled();
  });

  it("toggles between sign-in and register", async () => {
    render(<AuthScreen />);
    expect(screen.getByRole("heading", { name: /welcome back/i })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /create one/i }));
    expect(
      screen.getByRole("heading", { name: /create your account/i })
    ).toBeInTheDocument();
  });
});
