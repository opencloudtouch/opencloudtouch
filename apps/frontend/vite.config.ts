import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  define: {
    __OCT_EXT_RESOLVER__: JSON.stringify(false),
  },
  build: {
    outDir: '../../.out/dist',
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks(id: string) {
          if (id.includes('node_modules/react-dom') || id.includes('node_modules/react/')) {
            return 'react-vendor';
          }
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
