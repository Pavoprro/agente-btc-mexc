"""Backend del agente (escalón 1: datos de MEXC validados + modelo versionado + pronóstico, detrás de una API key).
Arrancar:  uvicorn app.main:crear_app --factory --port 8765     (docs en /docs)"""
import time
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .auth import exigir_clave
from .config import Config, config
from .mexc import ErrorDatos, velas_cerradas
from .modelo import Modelo
from .variables import rezagos


def crear_app(cfg: Config | None = None, modelo: Modelo | None = None, obtener_velas=None) -> FastAPI:
    cfg = cfg or config()
    modelo = modelo or Modelo(cfg.modelo_version)
    obtener_velas = obtener_velas or (lambda: velas_cerradas(cfg))

    app = FastAPI(title="Agente BTC/USDT · MEXC Paper", version=__version__,
                  description="Backend del agente de IA financiero (práctica DL para Finanzas). Solo lectura de MEXC; ejecución en Paper.")
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                       allow_methods=["*"], allow_headers=["*"])

    @app.get("/salud", tags=["público"])
    def salud():
        return {"estado": "ok", "backend": __version__, "activo": cfg.simbolo, "intervalo": cfg.intervalo,
                "modelo": modelo.resumen(), "llm": {"modelo": cfg.llm_modelo or None, "url": cfg.ollama_url},
                "paper": {"capital_inicial": cfg.capital_inicial, "costo": cfg.costo, "ordenes_reales": "deshabilitadas (no existe la ruta)"},
                "hora_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}

    @app.get("/pronostico", tags=["privado"], dependencies=[Depends(exigir_clave)])
    def pronostico():
        t0 = time.perf_counter()
        try:
            velas = obtener_velas()
        except ErrorDatos as e:
            raise HTTPException(status_code=503, detail=f"sin dato válido: {e}")
        ultima = velas[-1]
        rez = rezagos([v.close for v in velas])
        estimado = modelo.estimar(rez)
        return {"activo": cfg.simbolo, "fecha_vela": ultima.fecha, "cierre": ultima.close,
                "vela_cerrada_utc": datetime.fromtimestamp(ultima.cierre_ms / 1000, tz=timezone.utc).isoformat(timespec="seconds"),
                "estimado": estimado, "estimado_%": round(100 * estimado, 4),
                "senal_regla": "comprar" if estimado > cfg.umbral else "efectivo", "umbral": cfg.umbral,
                "variables": rez, "modelo": {"version": modelo.version, "nombre": modelo.nombre},
                "latencia_ms": round(1000 * (time.perf_counter() - t0), 1)}

    return app
