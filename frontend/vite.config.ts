import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

// En desarrollo, /api/* se reenvía al backend FastAPI (puerto 8765). La clave NO va aquí ni en variables VITE:
// la UI se la pide al usuario al abrir y la manda en la cabecera X-API-Key.
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8765', changeOrigin: true, rewrite: (p) => p.replace(/^\/api/, '') },
    },
  },
})
