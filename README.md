# agente-btc-mexc · agente de IA financiero (BTC/USDT en MEXC, modo Paper)

**Autor:** Juan Pablo Escalera Boites · Ciencia de Datos Aplicada a la Economía · Prof. Rubén Miguel Rodríguez Rangel · Universidad Iberoamericana León · otoño 2026.

Proyecto final de la práctica *Deep Learning para Finanzas con Agente de IA*. El agente observa velas diarias públicas de MEXC,
consulta el modelo predictivo de la práctica, propone una acción (con un LLM local), pasa controles de riesgo deterministas,
ejecuta en un simulador propio (Paper) y registra todo. **Nunca manda órdenes reales**: no existe esa ruta en el código.

El modelo viene de la práctica que hice en equipo con Luis Enrique López Salazar (Avances 1–5, capítulos 7–11): regresión lineal
sobre los 20 rendimientos diarios más recientes, elegida en el Avance 2 (corrida en Colab con Tesla T4) por encima de MLP y LSTM, y la
regla de decisión del Avance 3 (comprar si el rendimiento estimado supera 0.05 %, si no efectivo). El agente es individual.

## Tecnologías

| Capa | Qué uso | Para qué |
|---|---|---|
| UI | **Vue 3 + TypeScript + Vite** | panel: activo, fecha de datos, pronóstico, variables, acción propuesta, estado de riesgo, posición y patrimonio; iniciar / pausar / detener |
| Backend | **Python 3.11+ · FastAPI · Uvicorn · pydantic** | API documentada (`/docs`), carga el modelo y el escalador, valida entradas, coordina el ciclo |
| Datos de mercado | **MEXC API pública** `GET /api/v3/klines` (httpx, reintentos con espera creciente) | velas diarias BTC/USDT; se descarta la vela abierta; se valida orden, continuidad, precios y antigüedad |
| Modelo | **numpy** en producción; **scikit-learn** solo para exportar | regresión lineal (20 rezagos) con StandardScaler de X y de y, versionada en `backend/modelo/v1/modelo.json` |
| LLM local | **Ollama** (modelo pequeño, en la misma máquina) | propone comprar / mantener / vender en JSON con esquema; nunca ve claves ni cambia límites |
| Riesgo y Paper | Python puro | límites de exposición, pérdida diaria y antigüedad del dato; simulador con saldo, precisión del par y costo 0 % |
| Persistencia | **SQLite** | velas procesadas, decisiones, órdenes Paper, patrimonio y errores; reinicio sin duplicar |
| Seguridad | API key en cabecera `X-API-Key`, `.env` fuera del repo, CORS solo al panel | la UI pide la clave al usuario; nada en variables `VITE_*` |
| Pruebas | **pytest** (backend, sin red) · **vue-tsc** (tipos del panel) | contrato de variables, modelo, validación de velas, autenticación, API |

## Arquitectura

```
Vue 3 + TS (panel)  ──X-API-Key──▶  FastAPI (backend)
                                       ├─ mexc.py       velas públicas de MEXC, validadas (§15 paso 1)
                                       ├─ variables.py  20 rezagos con la definición del entrenamiento (paso 2)
                                       ├─ modelo.py     modelo v1 (numpy) → rendimiento estimado
                                       ├─ llm.py        Ollama local → propuesta JSON validada (pasos 3–4)   [pendiente]
                                       ├─ riesgo.py     límites deterministas (paso 5)                       [pendiente]
                                       ├─ paper.py      simulador: saldo, posición, patrimonio (paso 6)      [pendiente]
                                       └─ registro.py   SQLite: bitácora y estado (paso 7)                   [pendiente]
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
Probar a mano:
```bash
curl localhost:8765/api/salud
curl -H "X-API-Key: <tu clave>" localhost:8765/api/pronostico
```

## Estado (bitácora en `docs/BITACORA.md`)

**Escalón 1 · listo (17-nov-2026):** repo, modelo versionado, datos de MEXC validados, pronóstico detrás de API key, panel que lo muestra, 16 pruebas.
Consulta en vivo del 17-nov-2026: vela cerrada del 16-nov (cierre 64,875.64 USDT), estimado +0.091 % → señal *comprar*, 0.8 s.

| Escalón | Qué | Estado |
|---|---|---|
| 1 | MEXC validado + modelo versionado + `/pronostico` con API key + panel | listo |
| 2 | Paper (50,000 USDT, 0 %), riesgo determinista, SQLite, ciclo diario idempotente, iniciar / pausar / detener / liquidar | pendiente |
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
- Paper: 50,000 USDT iniciales, costo 0.0 % por operación (§15), sin apalancamiento ni cortos, deslizamiento 0 (documentado).
- Decisión al cierre de la vela *t*, ejecución a la apertura de *t+1*, valoración al cierre.
- El LLM solo elige entre las acciones posibles; las reglas de riesgo y la configuración no se tocan desde el LLM ni desde la UI.
