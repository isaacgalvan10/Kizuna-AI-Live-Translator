import { defineConfig } from 'vitest/config'
import react, { reactCompilerPreset } from '@vitejs/plugin-react'
import babel from '@rolldown/plugin-babel'
import tailwindcss from '@tailwindcss/vite'

// Where the dev server forwards /api and /ws. Docker Compose sets this to the
// backend's service name (http://backend:8000); when Vite runs directly on the
// host, localhost is correct.
const backendTarget = process.env.VITE_BACKEND_PROXY_TARGET || 'http://localhost:8000'

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
    // Tests derive WebSocket URLs from window.location, so pin the jsdom URL to
    // what the dev server actually serves on.
    environmentOptions: { jsdom: { url: 'http://localhost:5173' } },
  },
  server: {
    watch: {
      usePolling: true,
    },
    host: true, // needed for the Docker Container port mapping to work
    strictPort: true,
    port: 5173,
    allowedHosts: [
      // Both spellings ngrok's free tier hands out for random subdomains.
      '.ngrok-free.app',
      '.ngrok-free.dev'
    ],
    proxy: {
      // Keeping every request on one origin is what lets phones on the LAN use
      // the app: they load it from http://<your-ip>:5173, and this server-side
      // proxy reaches the backend. No CORS, no hardcoded hostnames.
      '/api': {
        target: backendTarget,
        changeOrigin: true,
        secure: false,
      },
      '/ws': {
        target: backendTarget,
        ws: true, // WebSocket upgrade (listener feed, operator feed state, audio stream)
        changeOrigin: true,
        secure: false,
      },
    },
  },
})
