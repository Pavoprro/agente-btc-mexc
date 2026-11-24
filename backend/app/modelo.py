"""Carga el modelo versionado (modelo/<version>/modelo.json) y pronostica con numpy, sin scikit-learn.
v1 = 20 rezagos (Avance 2/3). v2 = 20 rezagos + dist_sma20 + vol20 (versión final del Avance 5). El contrato de
variables viene en el propio archivo y se valida contra app/variables.py al cargar."""
import json, os

import numpy as np

from .variables import INDICADORES, LAGS, vector

AQUI = os.path.dirname(os.path.abspath(__file__))
CONTRATOS_CONOCIDOS = {tuple(LAGS), tuple(LAGS + INDICADORES)}


class Modelo:
    def __init__(self, version: str = "v2", ruta: str | None = None):
        ruta = ruta or os.path.join(AQUI, "..", "modelo", version, "modelo.json")
        with open(ruta, encoding="utf-8") as f:
            self.ficha = json.load(f)
        p = self.ficha["parametros"]
        self.entradas: list[str] = list(self.ficha["contrato"]["entradas"])
        if tuple(self.entradas) not in CONTRATOS_CONOCIDOS:
            raise ValueError("el contrato de variables del modelo no coincide con app/variables.py")
        self.coef = np.array(p["coef"], dtype=float)
        if len(self.coef) != len(self.entradas):
            raise ValueError("el número de coeficientes no coincide con el contrato")
        self.intercepto = float(p["intercepto"])
        self.x_media = np.array(p["x_media"], dtype=float)
        self.x_desv = np.array(p["x_desv"], dtype=float)
        self.y_media, self.y_desv = float(p["y_media"]), float(p["y_desv"])
        self.version = self.ficha["version"]
        self.nombre = self.ficha["nombre"]

    def estimar(self, valores: dict[str, float]) -> float:
        x = vector(valores, self.entradas)
        z = (x - self.x_media) / self.x_desv
        return float(self.y_media + self.y_desv * (self.intercepto + z @ self.coef))

    def resumen(self) -> dict:
        m, e = self.ficha["metricas"], self.ficha["entrenamiento"]
        return {"version": self.version, "nombre": self.nombre, "entradas": len(self.entradas), "variables": self.entradas,
                "RMSE_VA": m["RMSE_VA"], "RMSE_cero_VA": m["RMSE_cero_VA"], "RMSE_TE": m.get("RMSE_TE"), "RMSE_cero_TE": m.get("RMSE_cero_TE"),
                "entrenado_hasta": e["ultima_fecha_objetivo"], "sha256_datos": e["sha256"][:12], "seleccion": e["seleccion"]}
