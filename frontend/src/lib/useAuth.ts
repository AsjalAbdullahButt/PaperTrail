"use client";

import { useSyncExternalStore } from "react";
import { AUTH_EVENT, isAuthenticated } from "./api";

function subscribe(callback: () => void): () => void {
  window.addEventListener(AUTH_EVENT, callback);
  window.addEventListener("storage", callback); // cross-tab sign-in/out
  return () => {
    window.removeEventListener(AUTH_EVENT, callback);
    window.removeEventListener("storage", callback);
  };
}

/**
 * Auth state as an external store (localStorage). Returns `null` during SSR /
 * hydration (unknown) and a boolean on the client, so we never flash the wrong
 * screen or trigger a hydration mismatch.
 */
export function useAuthState(): boolean | null {
  return useSyncExternalStore(
    subscribe,
    () => isAuthenticated(),
    () => null,
  );
}
