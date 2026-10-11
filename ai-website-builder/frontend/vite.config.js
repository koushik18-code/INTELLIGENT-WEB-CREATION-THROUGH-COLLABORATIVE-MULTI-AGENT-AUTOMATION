import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Frontend calls same-origin '/api/...'; Vite forwards to FastAPI.
      // No CORS handling needed in dev, and the same relative paths work
      // unchanged if this is later served behind a single reverse proxy.
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
