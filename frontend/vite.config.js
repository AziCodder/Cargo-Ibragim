import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true, // слушать на 0.0.0.0 — доступ с localhost и по сети
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8800',
        changeOrigin: true,
      },
      '/uploads': {
        target: 'http://127.0.0.1:8800',
        changeOrigin: true,
      },
    },
  },
})
