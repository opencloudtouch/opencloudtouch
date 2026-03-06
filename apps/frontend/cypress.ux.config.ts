/**
 * Cypress UX Screenshot Configuration
 *
 * Dedicated config for visual documentation tests.
 * All API calls are intercepted — no backend required.
 *
 * Run:   npm run screenshots          (headless, for automation)
 *        npm run screenshots:headed   (headed, for hover-state capture)
 *        npm run screenshots:open     (interactive Cypress UI)
 *
 * Output: tests/e2e/screenshots/ux/
 */
import { defineConfig } from "cypress";

export default defineConfig({
  e2e: {
    baseUrl: "http://localhost:4173", // Vite preview
    specPattern: "tests/e2e/ux/**/*.cy.{js,ts}",
    supportFile: "tests/e2e/support/e2e.ts",
    fixturesFolder: false, // Inline fixtures in tests
    screenshotsFolder: "tests/e2e/screenshots/ux",
    videosFolder: "tests/e2e/videos/ux",
    video: false, // Screenshots only
    screenshotOnRunFailure: true, // Also capture failures

    env: {
      // UX tests intercept all API calls — no backend needed
      isUxScreenshotRun: true,
    },

    setupNodeEvents(on) {
      // Fix Chrome headless GPU tile-repeat artifact (bottom 15% repeating)
      // Caused by height:100vh + overflow:hidden triggering GPU compositing bug
      on("before:browser:launch", (browser, launchOptions) => {
        if (browser.family === "chromium") {
          launchOptions.args.push("--disable-gpu");
          launchOptions.args.push("--disable-software-rasterizer");
          launchOptions.args.push("--force-device-scale-factor=1");
          launchOptions.args.push("--disable-gpu-compositing");
          launchOptions.args.push("--no-sandbox");
        }
        return launchOptions;
      });

      // After screenshot: log path to console for easy access
      on("after:screenshot", (details) => {
        console.log(`📸 Screenshot: ${details.path}`);
      });
    },

    // Desktop viewport (primary)
    viewportWidth: 1280,
    viewportHeight: 800,

    // Prevent scroll position artifacts in screenshots
    scrollBehavior: false,

    defaultCommandTimeout: 10000,
    requestTimeout: 10000,
    responseTimeout: 10000,

    // Never fail on uncaught app errors during screenshot runs
    // (some components have non-critical console warnings)
    numTestsKeptInMemory: 0,
  },
});
