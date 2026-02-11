import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          // Vendor chunk: React and React DOM (changes rarely)
          'react-vendor': ['react', 'react-dom'],
          // Router chunk (if using React Router in future)
          // 'router': ['react-router-dom'],
        },
      },
    },
    // Optimize chunk size (warn if chunk > 500KB)
    chunkSizeWarningLimit: 500,
    // Source maps for debugging (production)
    sourcemap: true,
  },
  server: {
    port: 5175,
    host: true,
    proxy: {
      '/api': {
        target: 'http://localhost:7777',
        changeOrigin: true,
      }
    }
  },
  preview: {
    port: 4173,
    proxy: {
      '/api': {
        target: process.env.VITE_API_TARGET || 'http://localhost:7778',
        changeOrigin: true,
      }
    }
  }
})
