import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/playwright",
  use: { baseURL: "http://localhost:4173" },
  webServer: {
    // shortcut: builds on every run, so the preview always serves the current source; upgrade to a cached build if slow
    command: "npm run build && npm run preview -- --port 4173 --strictPort",
    url: "http://localhost:4173",
    reuseExistingServer: !process.env.CI,
  },
});
