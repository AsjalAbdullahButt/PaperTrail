"use client";

// Zustand auth store. The access token lives in memory (this store) only —
// never localStorage. On mount, restoreSession() silently exchanges the
// httpOnly refresh cookie for a fresh access token so a page reload keeps the
// user signed in without re-entering credentials.
//
// A proactive refresh timer fires ~60s before the access token's expiry (read
// from the JWT's exp claim — no signature check needed, it's UX timing only;
// the server remains the source of truth), so an active user never hits a 401
// mid-session. apiFetch's silent refresh-and-retry remains the backstop.

import { create } from "zustand";
import * as api from "@/lib/api";

/** Milliseconds-since-epoch expiry from a JWT's exp claim, or null if the
 * token can't be decoded. Decode only — never trusted for authorization. */
export function tokenExpiryMs(token: string): number | null {
  try {
    const payload = JSON.parse(
      atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")),
    );
    return typeof payload.exp === "number" ? payload.exp * 1000 : null;
  } catch {
    return null;
  }
}

const REFRESH_LEAD_MS = 60_000; // refresh this long before expiry
const MIN_DELAY_MS = 5_000; // never busy-loop on an already-stale token

let refreshTimer: ReturnType<typeof setTimeout> | null = null;

function clearRefreshTimer(): void {
  if (refreshTimer !== null) {
    clearTimeout(refreshTimer);
    refreshTimer = null;
  }
}

function scheduleProactiveRefresh(token: string, doRefresh: () => void): void {
  clearRefreshTimer();
  const expMs = tokenExpiryMs(token);
  if (expMs === null) return;
  const delay = Math.max(expMs - Date.now() - REFRESH_LEAD_MS, MIN_DELAY_MS);
  refreshTimer = setTimeout(doRefresh, delay);
}

type AuthState = {
  user: api.User | null;
  accessToken: string | null;
  isAuthenticated: boolean;
  /** null = not yet determined (during the initial refresh attempt). */
  ready: boolean;

  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, displayName?: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshToken: () => Promise<boolean>;
  restoreSession: () => Promise<void>;
};

export const useAuthStore = create<AuthState>((set, get) => {
  const rearm = (token: string) =>
    scheduleProactiveRefresh(token, () => void get().refreshToken());

  return {
    user: null,
    accessToken: null,
    isAuthenticated: false,
    ready: false,

    async login(email, password) {
      const token = await api.login(email, password);
      const user = await api.getMe();
      set({ accessToken: token, user, isAuthenticated: true, ready: true });
      rearm(token);
    },

    async register(email, password, displayName) {
      const token = await api.register(email, password, displayName);
      const user = await api.getMe();
      set({ accessToken: token, user, isAuthenticated: true, ready: true });
      rearm(token);
    },

    async logout() {
      clearRefreshTimer();
      await api.logout();
      set({ accessToken: null, user: null, isAuthenticated: false, ready: true });
    },

    async refreshToken() {
      const token = await api.refreshOnce();
      if (!token) {
        clearRefreshTimer();
        set({ accessToken: null, user: null, isAuthenticated: false, ready: true });
        return false;
      }
      set({ accessToken: token, isAuthenticated: true, ready: true });
      rearm(token);
      return true;
    },

    async restoreSession() {
      const ok = await get().refreshToken();
      if (ok) {
        try {
          set({ user: await api.getMe() });
        } catch {
          /* token was just set; profile fetch failure is non-fatal */
        }
      }
      set({ ready: true });
    },
  };
});
