import { defineConfig } from "@playwright/test";

const port = Number(process.env.E2E_PORT || 4173);

export default defineConfig({
  testDir: "tests/e2e",
  testMatch: "**/*.spec.mjs",
  reporter: "list",
  use: { baseURL: `http://127.0.0.1:${port}`, trace: "off" },
  webServer: {
    command: `node tests/e2e/static-server.mjs`,
    env: { PORT: String(port) },
    url: `http://127.0.0.1:${port}/demo.html`,
    reuseExistingServer: !process.env.CI
  }
});
