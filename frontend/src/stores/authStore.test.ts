import { beforeEach, describe, expect, it, vi } from "vitest";
import { useAuthStore } from "./authStore";
import * as api from "@/lib/api";

vi.mock("@/lib/api", () => ({
  login: vi.fn(),
  register: vi.fn(),
  getMe: vi.fn(),
  logout: vi.fn(),
  refresh: vi.fn(),
  refreshOnce: vi.fn(),
}));

function tokenWithExp(secondsFromNow: number): string {
  const nowSec = Math.floor(Date.now() / 1000);
  const payload = btoa(
    JSON.stringify({ exp: nowSec + secondsFromNow })
  ).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
  return `x.${payload}.y`;
}

describe("authStore", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
    useAuthStore.setState({
      user: null,
      accessToken: null,
      isAuthenticated: false,
      ready: false,
    });
  });

  it("login success sets user/auth state", async () => {
    vi.mocked(api.login).mockResolvedValueOnce(tokenWithExp(3600));
    vi.mocked(api.getMe).mockResolvedValueOnce({
      id: "u1",
      email: "u@x.com",
      display_name: null,
      bio: null,
      avatar_url: null,
      created_at: "2026-01-01T00:00:00Z",
    });

    await useAuthStore.getState().login("u@x.com", "pass");
    const s = useAuthStore.getState();
    expect(s.isAuthenticated).toBe(true);
    expect(s.accessToken).toBeTruthy();
    expect(s.user?.id).toBe("u1");
    expect(s.ready).toBe(true);
  });

  it("login failure leaves auth state unauthenticated", async () => {
    vi.mocked(api.login).mockRejectedValueOnce(new Error("bad creds"));
    await expect(useAuthStore.getState().login("u@x.com", "bad")).rejects.toThrow();
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
    expect(useAuthStore.getState().accessToken).toBeNull();
  });

  it("register success sets user/auth state", async () => {
    vi.mocked(api.register).mockResolvedValueOnce(tokenWithExp(3600));
    vi.mocked(api.getMe).mockResolvedValueOnce({
      id: "u2",
      email: "new@x.com",
      display_name: "New",
      bio: null,
      avatar_url: null,
      created_at: "2026-01-01T00:00:00Z",
    });

    await useAuthStore.getState().register("new@x.com", "pass1234", "New");
    expect(useAuthStore.getState().isAuthenticated).toBe(true);
    expect(useAuthStore.getState().user?.id).toBe("u2");
  });

  it("refreshToken clears auth state when refresh fails", async () => {
    useAuthStore.setState({
      user: { id: "u1", email: "u@x.com", display_name: null, bio: null, avatar_url: null, created_at: "x" },
      accessToken: tokenWithExp(3600),
      isAuthenticated: true,
      ready: true,
    });
    vi.mocked(api.refreshOnce).mockResolvedValueOnce(null);

    const ok = await useAuthStore.getState().refreshToken();
    expect(ok).toBe(false);
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
    expect(useAuthStore.getState().user).toBeNull();
  });

  it("restoreSession marks ready even when profile fetch fails", async () => {
    vi.mocked(api.refreshOnce).mockResolvedValueOnce(tokenWithExp(3600));
    vi.mocked(api.getMe).mockRejectedValueOnce(new Error("profile down"));

    await useAuthStore.getState().restoreSession();
    const s = useAuthStore.getState();
    expect(s.ready).toBe(true);
    expect(s.isAuthenticated).toBe(true);
  });

  it("logout clears session state", async () => {
    useAuthStore.setState({
      user: { id: "u1", email: "u@x.com", display_name: null, bio: null, avatar_url: null, created_at: "x" },
      accessToken: tokenWithExp(3600),
      isAuthenticated: true,
      ready: true,
    });
    vi.mocked(api.logout).mockResolvedValueOnce();

    await useAuthStore.getState().logout();
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
    expect(useAuthStore.getState().accessToken).toBeNull();
    expect(useAuthStore.getState().user).toBeNull();
  });
});
