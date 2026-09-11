import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The app calls /api/...; the dev (and preview) server forwards it to FastAPI, so the
// backend needs no CORS setup. Point API_URL elsewhere if the backend isn't on :8000.
const apiProxy = {
  '/api': {
    target: process.env.API_URL ?? 'http://localhost:8000',
    changeOrigin: true,
    rewrite: (path: string) => path.replace(/^\/api/, ''),
  },
}

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { proxy: apiProxy },
  preview: { proxy: apiProxy },
})
