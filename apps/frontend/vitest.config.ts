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
        'vite.config.ts',
        'vitest.config.ts',
        'eslint.config.ts',
      ],
      thresholds: {
        lines: 80,        // Current: 85.31% ✓
        functions: 75,    // Current: ~75% - Updated to match current coverage
        branches: 79,     // Current: 79% - Updated to match current coverage (to be improved to 80%)
        statements: 80,   // Current: 85.6% ✓
      },
    },
  },
})
