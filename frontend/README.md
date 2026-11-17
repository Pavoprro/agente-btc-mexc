# frontend · Vue 3 + TypeScript + Vite

Panel del agente. En desarrollo, `/api/*` se reenvía al backend (`vite.config.ts`), así que primero arranca el backend en el puerto 8765.

```bash
npm install
npm run dev        # http://localhost:5173
npm run build      # revisa tipos (vue-tsc) y genera dist/
```

La clave de la API se escribe en la propia pantalla y se guarda solo en `sessionStorage` de esa pestaña. No hay secretos en el código ni en variables `VITE_*`.
