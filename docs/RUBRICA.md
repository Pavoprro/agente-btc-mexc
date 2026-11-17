# Rúbrica del proyecto final (§16 del protocolo) y dónde queda cada cosa

| Criterio | Subcriterio (puntos) | Dónde | Estado |
|---|---|---|---|
| Integración y modelo | Modelo y escalador versionados (5) | `backend/modelo/v1/modelo.json`, `modelo/exportar.py`, prueba `test_modelo_reproduce_rmse_de_va` | listo |
| | Ollama realmente local (5) | `app/llm.py` (registro de modelo, versión, hardware y tiempo) | pendiente |
| | UI TypeScript funcional (5) | `frontend/` (Vue 3 + TS + Vite) | parcial (escalón 1) |
| API privada y secretos | Autenticación y rechazo de acceso inválido (5) | `app/auth.py`, pruebas `test_pronostico_sin_clave_401` | listo |
| | Secretos solo en servidor (5) | `.env` ignorado, `.env.example`, clave pedida en la UI, sin `VITE_*` | listo |
| Datos MEXC y Paper | Datos válidos y fechados (5) | `app/mexc.py` (vela cerrada, orden, huecos, antigüedad), pruebas `test_mexc.py` | listo |
| | Simulador con saldo, costos y precisión (5) | `app/paper.py` | pendiente |
| | Bloqueo de operaciones reales (5) | no existe ruta de órdenes; sin clave de MEXC | listo (se documenta) |
| Ciclo del agente | Observación, herramientas y propuesta estructurada (5) | `app/llm.py` + esquema JSON | pendiente |
| | Validación de acciones (5) | pydantic sobre la propuesta; acciones imposibles rechazadas | pendiente |
| | Ciclo programado con evidencia (5) | `POST /ciclo` + programador diario + bitácora | pendiente |
| Riesgo y control humano | Límites deterministas (5) | `app/riesgo.py` con `config.py` | pendiente |
| | Iniciar, pausar y detener efectivos (5) | rutas + botones del panel | pendiente |
| Errores y persistencia | Nueve escenarios (5) | pruebas automatizadas, una por escenario | pendiente (2 de 9 ya: API sin respuesta, dato atrasado) |
| | Recuperación sin duplicados (5) | SQLite con clave única por vela | pendiente |
| | Bitácora trazable (5) | tablas de decisiones, órdenes y errores | pendiente |
| Evaluación | Comparación sin LLM / con LLM / pasiva (5) | `comparar.py` | pendiente |
| | Métricas e interpretación (5) | informe | pendiente |
| Entrega reproducible | README y configuración sin secretos (5) | `README.md`, `.env.example` | listo |
| | Demostración y evidencia completa (5) | `docs/`, capturas, bases exportadas | pendiente |

Los nueve errores del §15: API sin respuesta o con límite · dato atrasado · Ollama detenido · JSON inválido · clave incorrecta ·
saldo insuficiente · evento duplicado · reinicio del backend · botón de detención.
