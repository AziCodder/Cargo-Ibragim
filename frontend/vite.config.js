import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: true, // слушать на 0.0.0.0 — доступ с localhost и по сети
    proxy: {
      '/api': 'http://localhost:8800',
      '/uploads': 'http://localhost:8800',
    },
  },
})
