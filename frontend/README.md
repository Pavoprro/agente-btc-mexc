# frontend · React + TypeScript + Vite

Panel del agente. En desarrollo, `/api/*` se reenvía al backend (`vite.config.ts`), así que primero arranca el backend en el puerto 8765.
Compilado (`dist/`), lo sirve el propio backend en http://localhost:8765 (eso hace `arrancar.bat`).

```bash
npm install
npm run dev        # http://localhost:5173
npm run build      # revisa tipos (tsc -b) y genera dist/
```

Qué muestra: última vela cerrada y pronóstico (dos cifras grandes), la ficha del agente (modo, patrimonio, efectivo, posición, operaciones,
último ciclo con propuesta → acción de riesgo → motivo) con los botones **Iniciar / Pausar / Detener / Correr un ciclo ahora / Liquidar posición**,
la tira SVG de los 20 rendimientos que ve el modelo más el estimado de mañana (`src/components/TiraDias.tsx`, sin librerías), la bitácora
(una línea por vela procesada, de la base SQLite del backend) y las fichas del modelo y de Paper y riesgo. Mientras hay sesión, el estado y la
bitácora se refrescan solos cada minuto.

La clave de la API se escribe en la propia pantalla y se guarda solo en `sessionStorage` de esa pestaña. No hay secretos en el código ni en
variables `VITE_*`. Los límites de riesgo se muestran, no se editan: viven en `backend/.env`.
