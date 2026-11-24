"""Backend del agente (escalón 2: datos de MEXC validados + modelo v2 + Paper + riesgo determinista + SQLite + ciclo programado +
iniciar / pausar / detener / liquidar), detrás de una API key.
Arrancar:  uvicorn app.main:crear_app --factory --port 8765     (API en /api/*, docs en /docs)
Si existe frontend/dist (npm run build), el mismo proceso sirve el panel en http://localhost:8765/."""
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import __version__
from .auth import exigir_clave
from .ciclo import Agente, Programador
from .config import Config, config
from .mexc import ErrorDatos, velas_cerradas
from .modelo import Modelo
from .registro import Registro
from .variables import variables

AQUI = os.path.dirname(os.path.abspath(__file__))
PANEL = os.path.normpath(os.path.join(AQUI, "..", "..", "frontend", "dist"))


def crear_app(cfg: Config | None = None, modelo: Modelo | None = None, obtener_velas=None, registro: Registro | None = None,
              programar: bool = True, proponer=None, reloj=None) -> FastAPI:
    cfg = cfg or config()
    modelo = modelo or Modelo(cfg.modelo_version)
    obtener_velas = obtener_velas or (lambda: velas_cerradas(cfg))
    registro = registro or Registro(cfg.ruta_db, cfg.capital_inicial)
    agente = Agente(cfg, modelo, registro, obtener_velas, proponer=proponer, reloj=reloj)
    programador = Programador(agente, cfg.revision_s) if programar else None

    @asynccontextmanager
    async def vida(app: FastAPI):
        if programador:
            programador.iniciar()
        yield
        if programador:
            programador.parar()

    app = FastAPI(title="Agente BTC/USDT · MEXC Paper", version=__version__, lifespan=vida,
                  description="Backend del agente de IA financiero (práctica DL para Finanzas). Solo lectura de MEXC; ejecución en Paper.")
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_methods=["*"], allow_headers=["*"])
    app.state.agente = agente
    api = APIRouter(prefix="/api")
    privado = [Depends(exigir_clave)]

    @api.get("/salud", tags=["público"])
    def salud():
        return {"estado": "ok", "backend": __version__, "activo": cfg.simbolo, "intervalo": cfg.intervalo,
                "modelo": modelo.resumen(), "llm": {"modelo": cfg.llm_modelo or None, "url": cfg.ollama_url},
                "agente": {"modo": registro.modo(), **registro.conteos()},
                "paper": {"capital_inicial": cfg.capital_inicial, "costo": cfg.costo, "exposicion_max": cfg.exposicion_max,
                          "perdida_diaria_max": cfg.perdida_diaria_max, "max_antiguedad_h": cfg.max_antiguedad_h, "filtro_sma20": cfg.filtro_sma20,
                          "umbral": cfg.umbral, "ordenes_reales": "deshabilitadas (no existe la ruta)"},
                "hora_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}

    @api.get("/pronostico", tags=["privado"], dependencies=privado)
    def pronostico():
        t0 = time.perf_counter()
        try:
            velas = obtener_velas()
        except ErrorDatos as e:
            raise HTTPException(status_code=503, detail=f"sin dato válido: {e}")
        ultima = velas[-1]
        vars_ = variables([v.close for v in velas])
        estimado = modelo.estimar(vars_)
        return {"activo": cfg.simbolo, "fecha_vela": ultima.fecha, "cierre": ultima.close, "apertura": ultima.open, "maximo": ultima.high, "minimo": ultima.low,
                "volumen": ultima.volumen, "vela_cerrada_utc": ultima.cerrada_utc, "estimado": estimado, "estimado_%": round(100 * estimado, 4),
                "senal_regla": "comprar" if estimado > cfg.umbral else "efectivo", "umbral": cfg.umbral, "filtro_sma20_ok": vars_["dist_sma20"] > 0,
                "variables": vars_, "modelo": {"version": modelo.version, "nombre": modelo.nombre}, "latencia_ms": round(1000 * (time.perf_counter() - t0), 1)}

    @api.get("/estado", tags=["privado"], dependencies=privado)
    def estado():
        return agente.estado()

    @api.post("/ciclo", tags=["privado"], dependencies=privado)
    def ciclo(forzar: bool = False):
        """Corre un ciclo ahora (el programador lo hace solo cada revision_s mientras el agente está activo). Idempotente por vela."""
        try:
            return agente.ciclo(forzar=forzar)
        except ErrorDatos as e:
            raise HTTPException(status_code=503, detail=f"sin dato válido: {e}")

    @api.post("/agente/iniciar", tags=["privado"], dependencies=privado)
    def iniciar():
        return agente.iniciar()

    @api.post("/agente/pausar", tags=["privado"], dependencies=privado)
    def pausar():
        return agente.pausar()

    @api.post("/agente/detener", tags=["privado"], dependencies=privado)
    def detener():
        return agente.detener()

    @api.post("/agente/liquidar", tags=["privado"], dependencies=privado)
    def liquidar():
        try:
            return agente.liquidar()
        except ErrorDatos as e:
            raise HTTPException(status_code=503, detail=f"sin dato válido para liquidar: {e}")

    @api.get("/bitacora", tags=["privado"], dependencies=privado)
    def bitacora(n: int = 60):
        n = max(1, min(n, 500))
        return {"ciclos": registro.ciclos(n), "ordenes": registro.ordenes(n), "errores": registro.errores(n), "eventos": registro.eventos(n)}

    app.include_router(api)
    if os.path.isdir(PANEL):
        app.mount("/", StaticFiles(directory=PANEL, html=True), name="panel")
    return app
