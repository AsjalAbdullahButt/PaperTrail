"use client";

// Zustand auth store. The access token lives in memory (this store) only —
// never localStorage. On mount, restoreSession() silently exchanges the
// httpOnly refresh cookie for a fresh access token so a page reload keeps the
// user signed in without re-entering credentials.

import { create } from "zustand";
import * as api from "@/lib/api";

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

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  accessToken: null,
  isAuthenticated: false,
  ready: false,

  async login(email, password) {
    const token = await api.login(email, password);
    const user = await api.getMe();
    set({ accessToken: token, user, isAuthenticated: true, ready: true });
  },

  async register(email, password, displayName) {
    const token = await api.register(email, password, displayName);
    const user = await api.getMe();
    set({ accessToken: token, user, isAuthenticated: true, ready: true });
  },

  async logout() {
    await api.logout();
    set({ accessToken: null, user: null, isAuthenticated: false, ready: true });
  },

  async refreshToken() {
    const token = await api.refresh();
    if (!token) {
      set({ accessToken: null, user: null, isAuthenticated: false, ready: true });
      return false;
    }
    set({ accessToken: token, isAuthenticated: true, ready: true });
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
}));
