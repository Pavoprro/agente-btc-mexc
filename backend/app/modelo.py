"""Carga el modelo versionado (modelo/<version>/modelo.json) y pronostica con numpy, sin scikit-learn."""
import json, os

import numpy as np

from .variables import LAGS, vector

AQUI = os.path.dirname(os.path.abspath(__file__))


class Modelo:
    def __init__(self, version: str = "v1", ruta: str | None = None):
        ruta = ruta or os.path.join(AQUI, "..", "modelo", version, "modelo.json")
        with open(ruta, encoding="utf-8") as f:
            self.ficha = json.load(f)
        p = self.ficha["parametros"]
        if self.ficha["contrato"]["entradas"] != LAGS:
            raise ValueError("el contrato de variables del modelo no coincide con app/variables.py")
        self.coef = np.array(p["coef"], dtype=float)
        self.intercepto = float(p["intercepto"])
        self.x_media = np.array(p["x_media"], dtype=float)
        self.x_desv = np.array(p["x_desv"], dtype=float)
        self.y_media, self.y_desv = float(p["y_media"]), float(p["y_desv"])
        self.version = self.ficha["version"]
        self.nombre = self.ficha["nombre"]

    def estimar(self, rez: dict[str, float]) -> float:
        x = vector(rez)
        z = (x - self.x_media) / self.x_desv
        return float(self.y_media + self.y_desv * (self.intercepto + z @ self.coef))

    def resumen(self) -> dict:
        return {"version": self.version, "nombre": self.nombre, "entradas": len(LAGS),
                "RMSE_VA": self.ficha["metricas"]["RMSE_VA"], "RMSE_cero_VA": self.ficha["metricas"]["RMSE_cero_VA"],
                "entrenado_hasta": self.ficha["entrenamiento"]["ultima_fecha_objetivo"], "sha256_datos": self.ficha["entrenamiento"]["sha256"][:12],
                "seleccion": self.ficha["entrenamiento"]["seleccion"]}
