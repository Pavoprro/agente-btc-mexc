"""Backend del agente (escalón 1: datos de MEXC validados + modelo versionado + pronóstico, detrás de una API key).
Arrancar:  uvicorn app.main:crear_app --factory --port 8765     (API en /api/*, docs en /docs)
Si existe frontend/dist (npm run build), el mismo proceso sirve el panel en http://localhost:8765/."""
import os
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import __version__
from .auth import exigir_clave
from .config import Config, config
from .mexc import ErrorDatos, velas_cerradas
from .modelo import Modelo
from .variables import rezagos

AQUI = os.path.dirname(os.path.abspath(__file__))
PANEL = os.path.normpath(os.path.join(AQUI, "..", "..", "frontend", "dist"))


def crear_app(cfg: Config | None = None, modelo: Modelo | None = None, obtener_velas=None) -> FastAPI:
    cfg = cfg or config()
    modelo = modelo or Modelo(cfg.modelo_version)
    obtener_velas = obtener_velas or (lambda: velas_cerradas(cfg))

    app = FastAPI(title="Agente BTC/USDT · MEXC Paper", version=__version__,
                  description="Backend del agente de IA financiero (práctica DL para Finanzas). Solo lectura de MEXC; ejecución en Paper.")
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                       allow_methods=["*"], allow_headers=["*"])
    api = APIRouter(prefix="/api")

    @api.get("/salud", tags=["público"])
    def salud():
        return {"estado": "ok", "backend": __version__, "activo": cfg.simbolo, "intervalo": cfg.intervalo,
                "modelo": modelo.resumen(), "llm": {"modelo": cfg.llm_modelo or None, "url": cfg.ollama_url},
                "paper": {"capital_inicial": cfg.capital_inicial, "costo": cfg.costo, "exposicion_max": cfg.exposicion_max,
                          "perdida_diaria_max": cfg.perdida_diaria_max, "max_antiguedad_h": cfg.max_antiguedad_h,
                          "ordenes_reales": "deshabilitadas (no existe la ruta)"},
                "hora_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}

    @api.get("/pronostico", tags=["privado"], dependencies=[Depends(exigir_clave)])
    def pronostico():
        t0 = time.perf_counter()
        try:
            velas = obtener_velas()
        except ErrorDatos as e:
            raise HTTPException(status_code=503, detail=f"sin dato válido: {e}")
        ultima = velas[-1]
        rez = rezagos([v.close for v in velas])
        estimado = modelo.estimar(rez)
        return {"activo": cfg.simbolo, "fecha_vela": ultima.fecha, "cierre": ultima.close, "apertura": ultima.open,
                "maximo": ultima.high, "minimo": ultima.low, "volumen": ultima.volumen,
                "vela_cerrada_utc": datetime.fromtimestamp(ultima.cierre_ms / 1000, tz=timezone.utc).isoformat(timespec="seconds"),
                "estimado": estimado, "estimado_%": round(100 * estimado, 4),
                "senal_regla": "comprar" if estimado > cfg.umbral else "efectivo", "umbral": cfg.umbral,
                "variables": rez, "modelo": {"version": modelo.version, "nombre": modelo.nombre},
                "latencia_ms": round(1000 * (time.perf_counter() - t0), 1)}

    app.include_router(api)
    if os.path.isdir(PANEL):
        app.mount("/", StaticFiles(directory=PANEL, html=True), name="panel")
    return app
