import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright E2E configuration for the CSPM frontend.
 *
 * Assumes the Next.js dev server is already running on http://localhost:3000
 * and the FastAPI backend is running on http://localhost:8000.
 * The Next.js rewrites proxy `/api/*` to the backend automatically.
 */
export default defineConfig({
  testDir: "./e2e",
  /* Maximum time one test can run */
  timeout: 30_000,
  /* Expect timeout for assertions */
  expect: {
    timeout: 10_000,
  },
  /* Run tests sequentially in CI to avoid port contention; parallel locally */
  fullyParallel: true,
  /* Retry once on failure to catch transient issues */
  retries: 1,
  /* Reporter: list for local, html for CI artifacts */
  reporter: process.env.CI ? "html" : "list",
  /* Shared settings for all projects */
  use: {
    baseURL: "http://localhost:3000",
    /* Collect trace on first retry for easier debugging */
    trace: "on-first-retry",
    /* Take screenshot only when a test fails */
    screenshot: "only-on-failure",
    /* Default viewport */
    viewport: { width: 1280, height: 720 },
    /* Increase action timeout slightly for slower dev servers */
    actionTimeout: 10_000,
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  /* Uncomment below to start the dev server automatically before tests.
   * Kept commented because the task requires assuming servers are already running.
   *
   * webServer: [
   *   {
   *     command: "cd ../backend && uvicorn app.main:app --port 8000",
   *     port: 8000,
   *     reuseExistingServer: true,
   *     timeout: 30_000,
   *   },
   *   {
   *     command: "pnpm dev",
   *     port: 3000,
   *     reuseExistingServer: true,
   *     timeout: 30_000,
   *   },
   * ],
   */
});
