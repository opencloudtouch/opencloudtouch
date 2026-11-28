/**
 * Cypress config for the local real-hardware UI test (never in CI, never in test:all or test:e2e).
 *
 * Runs against a running OCT with a real speaker. Everything comes from the environment:
 *   CYPRESS_OCT_URL        base URL of the running OCT (it serves the UI and the API)
 *   CYPRESS_HW_DEVICE_ID   device id of the test speaker
 *   CYPRESS_HW_PRESET      preset number (1-6) to start
 * Without them the spec skips.
 *
 * Run: npm run test:hw
 */
import { defineConfig } from "cypress";
import base from "./cypress.config";

const env = process.env;

export default defineConfig({
  ...base,
  expose: {
    octUrl: env.CYPRESS_OCT_URL ?? "",
    deviceId: env.CYPRESS_HW_DEVICE_ID ?? "",
    preset: env.CYPRESS_HW_PRESET ?? "",
  },
  e2e: {
    ...base.e2e,
    baseUrl: env.CYPRESS_OCT_URL || null,
    specPattern: "tests/hardware/**/*.cy.ts",
    excludeSpecPattern: [],
    // A retry would start the speaker again: a hardware run happens once.
    retries: 0,
  },
});
