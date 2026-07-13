import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

// jsdom has no matchMedia; components use it for prefers-reduced-motion.
if (!window.matchMedia) {
  window.matchMedia = ((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia;
}

// Unmount React trees between tests so queries don't see prior renders.
afterEach(() => {
  cleanup();
});

// Deliberately does NOT import/reset Zustand stores (useAuthStore,
// useQueryStore) here: importing them in this shared setup file binds their
// internal `import * as api from "@/lib/api"` to the *real* api module before
// each test file's own hoisted vi.mock("@/lib/api", ...) takes effect,
// silently breaking every test file that mocks the API layer. Store resets
// belong in each test file instead (see authStore.test.ts's beforeEach and
// page.test.tsx's afterEach), where they run after that file's own mocks.
