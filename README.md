# agente-btc-mexc · agente de IA financiero (BTC/USDT en MEXC, modo Paper)

**Autor:** Juan Pablo Escalera Boites · Ciencia de Datos Aplicada a la Economía · Prof. Rubén Miguel Rodríguez Rangel · Universidad Iberoamericana León · otoño 2026.

Proyecto final de la práctica *Deep Learning para Finanzas con Agente de IA*. El agente observa velas diarias públicas de MEXC,
consulta el modelo predictivo de la práctica, propone una acción (con un LLM local), pasa controles de riesgo deterministas,
ejecuta en un simulador propio (Paper) y registra todo. **Nunca manda órdenes reales**: no existe esa ruta en el código.

El modelo viene de la práctica que hice en equipo con Luis Enrique López Salazar (Avances 1–5, capítulos 7–11): regresión lineal
sobre los 20 rendimientos diarios más recientes, elegida en el Avance 2 (corrida en Colab con Tesla T4) por encima de MLP y LSTM; en el
Avance 5 se le añadieron dos indicadores (distancia a la SMA20 y volatilidad de 20 días) y quedó como versión final **v2** (22 variables), con la
regla de señal elegida con VA (comprar si el rendimiento estimado supera 0.10 %, si no efectivo) y el filtro de la SMA20 como control de riesgo.
El agente es individual.

## Tecnologías

| Capa | Qué uso | Para qué |
|---|---|---|
| UI | **Vue 3 + TypeScript + Vite** | panel: activo, fecha de datos, pronóstico, variables, acción propuesta, estado de riesgo, posición y patrimonio; iniciar / pausar / detener |
| Backend | **Python 3.11+ · FastAPI · Uvicorn · pydantic** | API documentada (`/docs`), carga el modelo y el escalador, valida entradas, coordina el ciclo |
| Datos de mercado | **MEXC API pública** `GET /api/v3/klines` (httpx, reintentos con espera creciente) | velas diarias BTC/USDT; se descarta la vela abierta; se valida orden, continuidad, precios y antigüedad |
| Modelo | **numpy** en producción; **scikit-learn** solo para exportar | regresión lineal con StandardScaler de X y de y, versionada: `v1` (20 rezagos, Avance 2) y **`v2`** (20 rezagos + dist_sma20 + vol20, Avance 5), en `backend/modelo/<v>/modelo.json` con contrato de variables, huella de datos y métricas |
| LLM local | **Ollama** (modelo pequeño, en la misma máquina) | propone comprar / mantener / vender en JSON con esquema; nunca ve claves ni cambia límites |
| Riesgo y Paper | Python puro (`riesgo.py`, `paper.py`) | límites deterministas: dato atrasado, acción imposible, pérdida diaria, filtro SMA20, exposición, saldo; simulador con 50,000 USDT, costo 0 %, cantidad con 6 decimales, nominal mínimo 1 USDT, sin apalancamiento ni cortos |
| Persistencia | **SQLite** (`registro.py`) | estado y cuenta, un renglón por vela procesada (clave única: no se repite ni tras reinicio), órdenes, errores y eventos de control |
| Ciclo | `ciclo.py` + hilo programador | velas → variables → modelo → propuesta validada (pydantic) → riesgo → Paper → registro; revisa cada 5 min si cerró una vela nueva; iniciar / pausar / detener / liquidar |
| Seguridad | API key en cabecera `X-API-Key`, `.env` fuera del repo, CORS solo al panel | la UI pide la clave al usuario; nada en variables `VITE_*` |
| Pruebas | **pytest** (backend, sin red) · **vue-tsc** (tipos del panel) | contrato de variables, modelo, validación de velas, autenticación, API |

## Arquitectura

```
Vue 3 + TS (panel)  ──X-API-Key──▶  FastAPI (backend)
                                       ├─ mexc.py       velas públicas de MEXC, validadas (§15 paso 1)
                                       ├─ variables.py  20 rezagos + dist_sma20 + vol20 con la definición del entrenamiento (paso 2)
                                       ├─ modelo.py     modelo v2 (numpy) → rendimiento estimado
                                       ├─ ciclo.py      el ciclo: propuesta (regla; Ollama en el escalón 3) validada con pydantic (pasos 3–4)
                                       ├─ llm.py        Ollama local → propuesta JSON                                  [pendiente, escalón 3]
                                       ├─ riesgo.py     límites deterministas (paso 5)
                                       ├─ paper.py      simulador: saldo, posición, patrimonio, precisión del par (paso 6)
                                       └─ registro.py   SQLite: estado, ciclos (uno por vela), órdenes, errores, eventos (paso 7)
```

## Prenderlo (Windows): doble clic en `arrancar.bat`

Hace todo solo: crea el entorno de Python e instala dependencias la primera vez, exporta el modelo si falta, genera `backend/.env`
con una clave nueva, instala y compila el panel, arranca el backend en http://localhost:8765 y abre el navegador ya con la clave
puesta (la clave viaja una sola vez en el fragmento `#clave=…` de la URL, que nunca sale del navegador; el panel la guarda en la
pestaña y la borra de la barra). Para apagarlo, cierra la ventana negra. Necesita Python 3.11+ y Node 20+ instalados.

## Instalar y correr a mano (o en Linux / mac)

Backend (Python 3.11 o más nuevo):
```bash
cd backend
python -m venv .venv && source .venv/Scripts/activate     # en Windows con Git Bash; en Linux/mac: source .venv/bin/activate
pip install -r requirements.txt
python modelo/exportar.py          # regenera modelo/v1/modelo.json y comprueba que reproduce el RMSE de VA de la práctica (0.024277)
python -m pytest                   # 16 pruebas, sin red
cp .env.example .env               # poner API_KEY (mínimo 16 caracteres); el .env no se sube
uvicorn app.main:crear_app --factory --port 8765      # API en /api/*, docs en /docs; si existe frontend/dist sirve el panel en /
```
Panel:
```bash
cd frontend
npm install
npm run build                      # genera dist/, que el backend sirve en http://localhost:8765
npm run dev                        # o modo desarrollo en http://localhost:5173 (reenvía /api al backend)
```
Probar a mano (docs interactivas en http://localhost:8765/docs):
```bash
curl localhost:8765/api/salud                                                   # pública: modelo, límites, modo del agente
curl -H "X-API-Key: <tu clave>" localhost:8765/api/pronostico                   # última vela cerrada, 22 variables, estimado, señal
curl -X POST -H "X-API-Key: <tu clave>" localhost:8765/api/agente/iniciar       # también /pausar, /detener, /liquidar
curl -X POST -H "X-API-Key: <tu clave>" localhost:8765/api/ciclo                # corre un ciclo ahora (idempotente por vela)
curl -H "X-API-Key: <tu clave>" localhost:8765/api/estado                       # modo, cuenta, patrimonio, último ciclo, límites
curl -H "X-API-Key: <tu clave>" "localhost:8765/api/bitacora?n=30"              # ciclos, órdenes, errores, eventos
```
Con el agente *activo*, un hilo revisa cada 5 minutos si MEXC ya cerró una vela nueva (00:00 UTC) y corre el ciclo una sola vez por vela.
La base queda en `backend/datos/agente.db` (fuera del repo); al reiniciar el backend la cuenta se restaura de ahí.

## Estado (bitácora en `docs/BITACORA.md`)

**Escalón 1 · listo (17-nov-2026):** repo, modelo versionado, datos de MEXC validados, pronóstico detrás de API key, panel que lo muestra, 16 pruebas.
**Escalón 2 · listo (24-nov-2026):** modelo v2 del Avance 5, motor Paper, riesgo determinista, SQLite, ciclo programado e idempotente, iniciar / pausar / detener / liquidar por API; 42 pruebas (replay de 25 velas, reinicio sin duplicar, saldo insuficiente, dato atrasado, propuesta inválida con respaldo a la regla).
Ciclo en vivo del 24-nov-2026: vela cerrada del 23-nov (cierre 61,279.98 USDT), estimado −0.27 %, cierre 10.7 % por debajo de la SMA20 → *mantener* en efectivo, 0.6 s; el segundo intento sobre la misma vela respondió *duplicado*.

| Escalón | Qué | Estado |
|---|---|---|
| 1 | MEXC validado + modelo versionado + `/pronostico` con API key + panel | listo |
| 2 | Modelo v2 + Paper (50,000 USDT, 0 %) + riesgo determinista + SQLite + ciclo diario idempotente + iniciar / pausar / detener / liquidar (API) | listo (backend); panel con botones en curso |
| 3 | Ollama local con propuesta JSON validada y respaldo a la regla; gateway con clave | pendiente |
| 4 | Los nueve errores del §15 demostrados; replay de ≥ 20 ciclos; comparación sin LLM / con LLM / comprar y mantener (§16) | pendiente |
| 5 | Informe breve, evidencia y entrega (30-nov y 1-dic-2026) | pendiente |

## Lo que dice el protocolo y cómo lo cubro (`docs/RUBRICA.md`)

Modelo y escalador versionados · Ollama realmente local · UI con TypeScript · API privada con rechazo de claves inválidas · secretos solo
en el servidor · datos de MEXC válidos y fechados · simulador con saldo, costos y precisión · bloqueo de operaciones reales · ciclo
programado con evidencia · límites deterministas · iniciar, pausar y detener · nueve escenarios de error · recuperación sin duplicados ·
bitácora trazable · comparación con y sin LLM y contra comprar y mantener.

## Supuestos fijos
- Activo BTC/USDT, velas diarias (UTC), API pública de MEXC sin cuenta. Sin clave de MEXC de ningún tipo.
- Objetivo del modelo: rendimiento simple del día siguiente, `y = close(t+1) / close(t) − 1`. Entradas: `r_lag0 … r_lag19`.
- Paper: 50,000 USDT iniciales, costo 0.0 % por operación (§15), sin apalancamiento ni cortos, deslizamiento 0, cantidad con 6 decimales (redondeo hacia abajo), nominal mínimo 1 USDT.
- Decisión al cierre de la vela *t*, ejecución al precio de ese cierre (en MEXC es exactamente la apertura de *t+1*: BTC cotiza 24/7, comprobado en el Avance 4), valoración al mismo cierre.
- Límites de riesgo, en este orden: dato atrasado (> 36 h) → no se opera; comprar con posición o vender sin ella → mantener; pérdida diaria > 5 % → sin compras ese día; cierre bajo la SMA20 → sin compras (Avance 5); exposición máxima 100 % del efectivo; nominal mínimo.
- El LLM solo elige entre las acciones posibles; las reglas de riesgo y la configuración no se tocan desde el LLM ni desde la UI.
