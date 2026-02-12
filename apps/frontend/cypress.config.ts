import { defineConfig } from 'cypress'

export default defineConfig({
  e2e: {
    baseUrl: 'http://localhost:4173', // Frontend (Vite Preview)
    specPattern: 'tests/e2e/**/*.cy.{js,jsx,ts,tsx}',
    excludeSpecPattern: 'tests/real/**/*.cy.{js,jsx,ts,tsx}', // Exclude real device tests from default runs
    supportFile: 'tests/e2e/support/e2e.ts',
    fixturesFolder: false, // No fixtures needed (backend provides mocks)
    screenshotsFolder: 'tests/e2e/screenshots',
    videosFolder: 'tests/e2e/videos',
    video: false, // Disable video recording (speeds up tests)

    env: {
      // API URL set via CYPRESS_API_URL env var by run-e2e-tests.ps1
      // Default: http://localhost:7778/api (test port)
      apiUrl: 'http://localhost:7778/api'
    },

    setupNodeEvents() {
      // Future: Code Coverage Plugin
    },

    viewportWidth: 1280,
    viewportHeight: 720,
    defaultCommandTimeout: 5000,  // Reduced from 10s (Phase 1 optimization)
    requestTimeout: 8000,           // Keep higher for network calls
    responseTimeout: 8000,
  },
})
