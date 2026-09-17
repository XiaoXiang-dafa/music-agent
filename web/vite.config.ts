import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 开发时把 /api 代理到本地 Flask(5050)，避免跨域。
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:5050',
        changeOrigin: true,
      },
    },
  },
})
