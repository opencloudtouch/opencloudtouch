import { defineConfig } from 'cypress'

export default defineConfig({
  allowCypressEnv: false,

  // Public configuration values accessible in tests via Cypress.expose()
  expose: {
    apiUrl: 'http://localhost:7778/api'
  },

  e2e: {
    baseUrl: 'http://localhost:4173', // Frontend (Vite Preview)
    specPattern: 'tests/e2e/**/*.cy.{js,jsx,ts,tsx}',
    excludeSpecPattern: 'tests/real/**/*.cy.{js,jsx,ts,tsx}', // Exclude real device tests from default runs
    supportFile: 'tests/e2e/support/e2e.ts',
    fixturesFolder: false, // No fixtures needed (backend provides mocks)
    screenshotsFolder: 'tests/e2e/screenshots',
    videosFolder: 'tests/e2e/videos',
    video: false, // Disable video recording (speeds up tests)

    setupNodeEvents(on, config) {
      // a11y violation report store (in-process, resets per test run)
      let a11yViolations: unknown[] = [];

      on('task', {
        'a11y:clear'() {
          a11yViolations = [];
          return null;
        },
        'a11y:log'(entry: unknown) {
          a11yViolations.push(entry);
          return null;
        },
        'a11y:report'() {
          const total = a11yViolations.length;
          if (total > 0) {
            console.log(`[a11y] ${total} violation entries logged across all pages.`);
          }
          return total;
        },
      });

      return config;
    },

    viewportWidth: 1280,
    viewportHeight: 720,
    defaultCommandTimeout: 5000,  // Reduced from 10s (Phase 1 optimization)
    requestTimeout: 8000,           // Keep higher for network calls
    responseTimeout: 8000,
  },
})
