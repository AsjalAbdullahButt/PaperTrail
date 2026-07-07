import { defineConfig, devices } from "@playwright/test";

/**
 * E2E config. Requires the backend running at http://localhost:8000
 * (with MySQL) and starts the built frontend automatically.
 *
 * Run:  npm run build && npx playwright install chromium && npm run test:e2e
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  fullyParallel: false,
  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "npm run start",
    url: "http://localhost:3000",
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
});
