# Bitácora del proyecto

## 2026-11-17 · escalón 1
- Repo creado. Estructura: `backend/` (FastAPI) y `frontend/` (Vue 3 + TS + Vite).
- `backend/modelo/exportar.py` reajusta la regresión lineal de 20 rezagos con los datos del Avance 1 (TR: 2,069 ejemplos,
  2018-09-13 → 2024-06-03) y exporta `modelo/v1/modelo.json` (coeficientes, intercepto, medias y desviaciones de X y de y, contrato
  de variables, sha256 de los datos). Reproduce el RMSE de VA de la práctica: 0.024277 (cero: 0.024354).
- `app/mexc.py`: velas públicas de MEXC con 3 intentos (0.5 s, 1 s, 2 s). Se descarta la vela abierta; se rechazan huecos,
  desorden, precios imposibles y dato atrasado (> 36 h). Si no hay dato válido, `/pronostico` responde 503 y no se decide.
- `app/variables.py` reproduce las ventanas del Avance 1 (prueba con 200 fechas al azar, diferencia < 1e-12).
- `/pronostico` exige `X-API-Key` (401 si falta o es incorrecta). `/salud` es pública y no revela secretos.
- Panel: muestra backend, modelo, última vela cerrada, estimado, señal de la regla y las 20 variables. Pide la clave al usuario.
- 16 pruebas en pytest, sin red. Consulta en vivo: vela del 2026-11-16, cierre 64,875.64, estimado +0.0908 %, señal comprar, 797 ms.

## 2026-11-17 · panel y arranque
- La API queda bajo `/api/*` y el backend sirve `frontend/dist` en `/`: un solo proceso para todo.
- `arrancar.bat`: prepara entorno, modelo, `.env` con clave generada, panel compilado, arranca y abre el navegador con la clave en el fragmento de la URL.
- Panel rediseñado: dos cifras grandes (última vela cerrada y pronóstico), tira SVG de los 20 rendimientos que ve el modelo más la barra rayada del estimado y la marca del umbral, fichas de modelo y de Paper/riesgo. IBM Plex Sans + Mono. Sin librerías de gráficas.
- Se revisó en 1280 px y en ancho de celular; los errores 401 y 503 se muestran con texto que dice qué hacer.

## Siguiente
- Escalón 2: Paper + riesgo + SQLite + ciclo diario + iniciar / pausar / detener / liquidar en backend y panel.
