# Rúbrica del proyecto final (§16 del protocolo) y dónde queda cada cosa

| Criterio | Subcriterio (puntos) | Dónde | Estado |
|---|---|---|---|
| Integración y modelo | Modelo y escalador versionados (5) | `backend/modelo/v1/` y `v2/modelo.json` (contrato de variables, huella, métricas VA y TE), `modelo/exportar.py`, pruebas `test_modelo_v2_reproduce_rmse_de_va_del_avance5` y `test_indicadores_con_la_definicion_del_avance5` | listo |
| | Ollama realmente local (5) | `app/llm.py` (registro de modelo, versión, hardware y tiempo) | pendiente |
| | UI TypeScript funcional (5) | `frontend/` (React 19 + TypeScript + Vite): activo, fecha de datos, pronóstico, variables, propuesta, motivo de riesgo, posición, patrimonio, iniciar / pausar / detener, bitácora | listo (falta mostrar la justificación del LLM, escalón 3) |
| API privada y secretos | Autenticación y rechazo de acceso inválido (5) | `app/auth.py`, pruebas `test_pronostico_sin_clave_401` | listo |
| | Secretos solo en servidor (5) | `.env` ignorado, `.env.example`, clave pedida en la UI, sin `VITE_*` | listo |
| Datos MEXC y Paper | Datos válidos y fechados (5) | `app/mexc.py` (vela cerrada, orden, huecos, antigüedad), pruebas `test_mexc.py` | listo |
| | Simulador con saldo, costos y precisión (5) | `app/paper.py` (50,000 USDT, costo 0 %, 6 decimales, nominal mínimo), pruebas `test_paper.py` | listo |
| | Bloqueo de operaciones reales (5) | no existe ruta de órdenes; sin clave de MEXC | listo (se documenta) |
| Ciclo del agente | Observación, herramientas y propuesta estructurada (5) | `app/ciclo.py` (`Propuesta` con esquema cerrado; contexto con vela, variables, estimado, cuenta) + `app/llm.py` | parcial (regla; Ollama en el escalón 3) |
| | Validación de acciones (5) | pydantic sobre la propuesta (`Propuesta`), símbolo y fecha verificados, acciones imposibles → mantener (`riesgo.py`); prueba `test_propuesta_externa_invalida_cae_a_la_regla` | listo |
| | Ciclo programado con evidencia (5) | `POST /api/ciclo`, hilo `Programador` (cada 5 min, una vez por vela), tabla `ciclos`; replay de 25 velas en `test_replay_de_mas_de_20_velas_es_idempotente` | listo (evidencia en vivo se acumula desde el 24-nov) |
| Riesgo y control humano | Límites deterministas (5) | `app/riesgo.py` (seis reglas) con límites solo en `config.py`; pruebas `test_riesgo.py` | listo |
| | Iniciar, pausar y detener efectivos (5) | rutas `/api/agente/*` (+ liquidar), estado en SQLite; prueba `test_pausar_detener_e_iniciar` | listo (API y panel) |
| Errores y persistencia | Nueve escenarios (5) | pruebas automatizadas: API sin respuesta, dato atrasado, JSON inválido, clave incorrecta, saldo insuficiente, evento duplicado, reinicio del backend, botón de detención | 8 de 9 (falta Ollama detenido; su respaldo ya está probado) |
| | Recuperación sin duplicados (5) | `registro.py`: clave única por vela, transacción por ciclo; prueba `test_reinicio_del_backend_restaura_la_cuenta_y_no_duplica` | listo |
| | Bitácora trazable (5) | tablas `ciclos`, `ordenes`, `errores`, `eventos`; `GET /api/bitacora` | listo |
| Evaluación | Comparación sin LLM / con LLM / pasiva (5) | `comparar.py` | pendiente |
| | Métricas e interpretación (5) | informe | pendiente |
| Entrega reproducible | README y configuración sin secretos (5) | `README.md`, `.env.example` | listo |
| | Demostración y evidencia completa (5) | `docs/`, capturas, bases exportadas | pendiente |

Los nueve errores del §15: API sin respuesta o con límite · dato atrasado · Ollama detenido · JSON inválido · clave incorrecta ·
saldo insuficiente · evento duplicado · reinicio del backend · botón de detención.
