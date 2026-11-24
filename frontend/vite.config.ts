import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// En desarrollo (npm run dev), /api/* se reenvía al backend FastAPI (puerto 8765).
// En producción, el backend sirve dist/ y /api/* es suyo, así que la misma ruta funciona en los dos casos.
// La clave NO va aquí ni en variables VITE: la UI se la pide al usuario y la manda en la cabecera X-API-Key.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { '/api': { target: 'http://127.0.0.1:8765', changeOrigin: true } },
  },
})
