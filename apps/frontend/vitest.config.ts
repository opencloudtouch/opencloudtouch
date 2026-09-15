import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  define: {
    __TUNEIN_SUPPORTED__: JSON.stringify(true),
  },
  resolve: {
    alias: {
      // Mock html2canvas in test environment (not installed as runtime dep yet)
      'html2canvas': path.resolve(__dirname, 'src/__mocks__/html2canvas.ts'),
    },
  },
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
      reportsDirectory: '../../.out/coverage/frontend',
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
        // Per-metric thresholds (the v8 provider does not support a "global" key —
        // it silently ignored the prior single-key config, so this gate was inert).
        statements: 80,
        branches: 80,
        functions: 80,
        lines: 80,
      },
    },
  },
})
