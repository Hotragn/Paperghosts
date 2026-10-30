import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // in development the live routes come from `make api`
  server: { proxy: { '/api': 'http://localhost:8000' } },
})
