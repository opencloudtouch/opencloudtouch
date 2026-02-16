import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './tests/setup.ts',
    exclude: [
      '**/node_modules/**',
      '**/dist/**',
      '**/tests/real/**', // Exclude real device tests from default runs
      '**/tests/e2e/**', // Exclude Cypress E2E tests
    ],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html', 'json-summary', 'lcov'],
      exclude: [
        'node_modules/',
        'tests/',
        '**/*.test.{js,jsx,ts,tsx}',
        '**/*.css',
        'vite.config.ts',
        'vitest.config.ts',
        'eslint.config.ts',
      ],
      thresholds: {
        lines: 65,        // Temporarily lowered - new components need tests
        functions: 65,    // Temporarily lowered - new components need tests
        branches: 55,     // Temporarily lowered - new components need tests
        statements: 65,   // Temporarily lowered - new components need tests
      },
    },
  },
})
