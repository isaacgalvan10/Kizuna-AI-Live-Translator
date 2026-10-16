import { defineConfig } from 'vitest/config'
import react, { reactCompilerPreset } from '@vitejs/plugin-react'
import babel from '@rolldown/plugin-babel'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    babel({ presets: [reactCompilerPreset()] }),
    tailwindcss(),
  ],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
  },
  server: {
    watch: {
      usePolling: true,
    },
    host: true, // needed for the Docker Container port mapping to work
    strictPort: true,
    port: 5173, 
    allowedHosts: [
      '.ngrok-free.dev'
    ],
  proxy: {
      '/api': {
        target: 'http://backend:8000', // Points to the Docker Service Name
        changeOrigin: true,
        secure: false,
        // Optional: Rewrite path if your backend doesn't use /api prefix
        // rewrite: (path) => path.replace(/^\/api/, ''), 
      },
      '/db-test': {
        target: 'http://backend:8000',
        changeOrigin: true,
        secure: false,
      }
    }
  }
})