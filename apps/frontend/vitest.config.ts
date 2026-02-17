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
        // Single global threshold (average of all metrics)
        // Current: Stmts 88.33%, Branch 78.93%, Funcs 87.32%, Lines 89.04%
        global: 80,
      },
    },
  },
})
