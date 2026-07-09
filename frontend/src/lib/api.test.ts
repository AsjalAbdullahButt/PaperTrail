// apiFetch: silent refresh-and-retry on 401, with a single shared in-flight
// refresh so concurrent expired-token requests trigger exactly one
// /api/auth/refresh round trip.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiFetch, setAccessToken } from "./api";

function fakeRes(status: number, body: unknown = {}): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

const isRefresh = (url: unknown) => String(url).endsWith("/api/auth/refresh");

function refreshCallCount(mock: ReturnType<typeof vi.fn>): number {
  return mock.mock.calls.filter(([url]) => isRefresh(url)).length;
}

describe("apiFetch", () => {
  beforeEach(() => {
    setAccessToken("stale-token");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    setAccessToken(null);
  });

  it("refreshes once and retries on 401, returning the retried result", async () => {
    const mockFetch = vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      if (isRefresh(url)) return fakeRes(200, { access_token: "fresh-token" });
      const auth = (init?.headers as Record<string, string>)?.Authorization;
      if (auth === "Bearer fresh-token") return fakeRes(200, { data: 42 });
      return fakeRes(401, { error: { message: "expired" } });
    });
    vi.stubGlobal("fetch", mockFetch);

    const res = await apiFetch("/api/documents");
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ data: 42 });
    expect(refreshCallCount(mockFetch)).toBe(1);
  });

  it("shares one refresh across 3 concurrent 401s", async () => {
    const mockFetch = vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      if (isRefresh(url)) {
        // Slow refresh so all three 401s are waiting on it together.
        await new Promise((r) => setTimeout(r, 20));
        return fakeRes(200, { access_token: "fresh-token" });
      }
      const auth = (init?.headers as Record<string, string>)?.Authorization;
      if (auth === "Bearer fresh-token") return fakeRes(200, { ok: true });
      return fakeRes(401, { error: { message: "expired" } });
    });
    vi.stubGlobal("fetch", mockFetch);

    const results = await Promise.all([
      apiFetch("/api/documents"),
      apiFetch("/api/collections"),
      apiFetch("/api/queries"),
    ]);
    expect(results.map((r) => r.status)).toEqual([200, 200, 200]);
    expect(refreshCallCount(mockFetch)).toBe(1);
  });

  it("propagates the 401 when the refresh itself fails", async () => {
    const mockFetch = vi.fn(async (url: RequestInfo | URL) => {
      if (isRefresh(url)) return fakeRes(401, {});
      return fakeRes(401, { error: { message: "expired" } });
    });
    vi.stubGlobal("fetch", mockFetch);

    const res = await apiFetch("/api/documents");
    expect(res.status).toBe(401);
    // One refresh attempt, no retry loop.
    expect(refreshCallCount(mockFetch)).toBe(1);
    expect(mockFetch).toHaveBeenCalledTimes(2);
  });

  it("does not attempt a refresh when skipAuthRetry is set", async () => {
    const mockFetch = vi.fn(async () => fakeRes(401, {}));
    vi.stubGlobal("fetch", mockFetch);

    const res = await apiFetch("/api/auth/login", {
      method: "POST",
      skipAuthRetry: true,
    });
    expect(res.status).toBe(401);
    expect(mockFetch).toHaveBeenCalledTimes(1);
    expect(refreshCallCount(mockFetch)).toBe(0);
  });

  it("retries with the refreshed token in the Authorization header", async () => {
    const seenAuth: (string | undefined)[] = [];
    const mockFetch = vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      if (isRefresh(url)) return fakeRes(200, { access_token: "fresh-token" });
      seenAuth.push((init?.headers as Record<string, string>)?.Authorization);
      return seenAuth.length === 1 ? fakeRes(401, {}) : fakeRes(200, {});
    });
    vi.stubGlobal("fetch", mockFetch);

    await apiFetch("/api/documents");
    expect(seenAuth).toEqual(["Bearer stale-token", "Bearer fresh-token"]);
  });
});
