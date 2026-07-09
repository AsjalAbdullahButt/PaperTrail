import { beforeEach, describe, expect, it, vi } from "vitest";

const { redirectMock, nextMock } = vi.hoisted(() => ({
  redirectMock: vi.fn((url: URL) => ({ type: "redirect", href: url.pathname })),
  nextMock: vi.fn(() => ({ type: "next" })),
}));

vi.mock("next/server", () => ({
  NextResponse: {
    redirect: redirectMock,
    next: nextMock,
  },
}));

import { middleware } from "./middleware";

function req(pathname: string, hasSession: boolean) {
  return {
    url: `http://localhost${pathname}`,
    nextUrl: { pathname },
    cookies: {
      get: (name: string) => (name === "pt_session" && hasSession ? { value: "1" } : undefined),
    },
  };
}

describe("middleware", () => {
  beforeEach(() => {
    redirectMock.mockClear();
    nextMock.mockClear();
  });

  it("redirects authenticated users away from auth pages", () => {
    const out = middleware(req("/login", true) as never);
    expect(out).toEqual({ type: "redirect", href: "/" });
  });

  it("keeps authenticated users on protected pages", () => {
    const out = middleware(req("/library", true) as never);
    expect(out).toEqual({ type: "next" });
  });

  it("keeps unauthenticated users on auth pages", () => {
    const out = middleware(req("/register", false) as never);
    expect(out).toEqual({ type: "next" });
  });

  it("redirects unauthenticated users from protected pages to login", () => {
    const out = middleware(req("/analytics", false) as never);
    expect(out).toEqual({ type: "redirect", href: "/login" });
  });
});
