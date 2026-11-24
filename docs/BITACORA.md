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

## 2026-11-24 · escalón 2 (backend)
- La práctica quedó completa (Avance 5, cap. 11): la versión final es **v2** = 20 rezagos + dist_sma20 + vol20 (RMSE VA 0.024243 frente a 0.024277 de v1;
  en TE 0.022435, no supera al cero 0.022378). `modelo/exportar.py` exporta v1 y v2 y verifica VA y TE contra la práctica; `app/variables.py` calcula los
  indicadores con la definición del Avance 5 (prueba contra la serie auditada, diferencia < 1e-12). Regla de señal: comprar si el estimado > 0.10 % (C del Avance 5).
- `app/paper.py`: simulador con 50,000 USDT, costo 0 %, cantidad con 6 decimales hacia abajo, nominal mínimo 1 USDT; sin apalancamiento ni cortos; ganancia por operación y Win Rate.
- `app/riesgo.py`: seis controles deterministas en orden (dato atrasado, acción imposible, pérdida diaria 5 %, filtro SMA20 del Avance 5, exposición, saldo). La propuesta nunca manda.
- `app/registro.py`: SQLite con estado, ciclos (clave única por vela), órdenes, errores y eventos. Una transacción por ciclo.
- `app/ciclo.py`: `Agente` (iniciar / pausar / detener / liquidar, `ciclo()` idempotente, propuesta validada con pydantic y respaldo a la regla si la externa falla)
  y `Programador` (hilo que revisa cada 5 min si cerró una vela). Precio de ejecución = cierre de la vela cerrada (= apertura de la siguiente en MEXC).
- API: `/api/estado`, `POST /api/ciclo`, `POST /api/agente/{iniciar,pausar,detener,liquidar}`, `/api/bitacora`; todo privado salvo `/api/salud`.
- 42 pruebas sin red: Paper (6), riesgo (7), ciclo (8: replay de 25 velas idempotente, reinicio con la misma base restaura la cuenta y no duplica,
  saldo insuficiente, dato atrasado, MEXC caída, propuesta inválida y LLM caído con respaldo, liquidar), API (5), variables y modelos (7), MEXC (9).
- Ciclo en vivo (24-nov, 14:21 León): vela del 2026-11-23, cierre 61,279.98, estimado −0.27 %, dist_sma20 −10.7 % → mantener en efectivo, 556 ms; repetir → duplicado; sin clave → 401.
- De los nueve errores del §15 ya quedan demostrados en pruebas: API sin respuesta, dato atrasado, JSON inválido (propuesta), clave incorrecta, saldo insuficiente, evento duplicado, reinicio del backend, botón de detención. Falta Ollama detenido (escalón 3), que ya tiene su ruta de respaldo.

## 2026-11-24 · escalón 2 (panel)
- Panel migrado de Vue a **React 19 + TypeScript** (la rúbrica dice "UI React y TypeScript"; la recomendación de Vue fue verbal) con el mismo diseño: `App.tsx`, `components/TiraDias.tsx`, `api.ts` con todos los endpoints, `tsc -b` en el build.
- Nueva ficha "El agente en Paper": modo (activo / pausado / detenido), patrimonio, efectivo, posición, operaciones y Win Rate, último ciclo (propuesta → acción de riesgo → motivo), botones Iniciar / Pausar / Detener / Correr un ciclo ahora / Liquidar posición (con confirmación). Estado y bitácora se refrescan cada minuto.
- Nueva sección de bitácora: una línea por vela procesada (cierre, estimado, propuesta y fuente, acción, motivo, posición, patrimonio) y los últimos errores.
- Revisado en 1280 px y en ancho de celular con el backend sirviendo `dist/`.

## Siguiente
- Escalón 3: Ollama local (`app/llm.py`) con esquema JSON, registro de modelo, hardware y tiempo, y clave en el gateway.
