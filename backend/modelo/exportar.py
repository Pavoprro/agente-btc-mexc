"""Exporta el modelo de la práctica (regresión lineal con 20 rezagos, elegido en el Avance 2 en T4 y validado en el Avance 3)
a un archivo JSON versionado que el backend carga sin scikit-learn.

Correr DESDE backend/:   python modelo/exportar.py
Qué hace:
  1. Lee las ventanas del Avance 1 (datos_entrenamiento/ventanas_btcusdt_1d.csv) y las particiones TR / VA / TE.
  2. Ajusta los escaladores (StandardScaler de X y de y) SOLO con TR y la regresión lineal sobre lo escalado, igual que el cuaderno.
  3. Comprueba que el RMSE en VA reproduce el de la práctica (0.024277, outputs/metricas_referencia_avance1.csv). Si no cuadra, no exporta.
  4. Escribe modelo/v1/modelo.json con coeficientes, intercepto, medias y desviaciones, contrato de variables, huella de los datos y métricas.
"""
import hashlib, json, os, sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler

AQUI = os.path.dirname(os.path.abspath(__file__))
DATOS = os.path.join(AQUI, "datos_entrenamiento")
VERSION = "v1"
VENTANA = 20
LAGS = [f"r_lag{i}" for i in range(VENTANA)]
TOLERANCIA = 1e-5


def huella(ruta):
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def main():
    ventanas = pd.read_csv(os.path.join(DATOS, "ventanas_btcusdt_1d.csv"), parse_dates=["fecha_emision", "fecha_objetivo"])
    part = pd.read_csv(os.path.join(DATOS, "particiones_avance1.csv")).set_index("conjunto")
    ref = pd.read_csv(os.path.join(DATOS, "metricas_referencia_avance1.csv"))
    regla = json.load(open(os.path.join(DATOS, "regla_seleccionada.json"), encoding="utf-8"))

    tr = ventanas[ventanas.conjunto == "TR"]
    va = ventanas[ventanas.conjunto == "VA"]
    assert len(tr) == part.loc["TR", "ejemplos"] and len(va) == part.loc["VA", "ejemplos"], "las particiones no cuadran con el Avance 1"
    assert tr.fecha_objetivo.max() < va.fecha_objetivo.min(), "TR invade VA"

    esc_x = StandardScaler().fit(tr[LAGS].to_numpy())
    esc_y = StandardScaler().fit(tr[["y"]].to_numpy())
    modelo = LinearRegression().fit(esc_x.transform(tr[LAGS].to_numpy()), esc_y.transform(tr[["y"]].to_numpy()).ravel())

    def estimar(df):
        return esc_y.inverse_transform(modelo.predict(esc_x.transform(df[LAGS].to_numpy())).reshape(-1, 1)).ravel()

    rmse_va = float(np.sqrt(np.mean((estimar(va) - va.y.to_numpy()) ** 2)))
    rmse_tr = float(np.sqrt(np.mean((estimar(tr) - tr.y.to_numpy()) ** 2)))
    esperado = float(ref[(ref.modelo == "Regresión lineal (20 rezagos)") & (ref.conjunto == "VA")].RMSE.iloc[0])
    if abs(rmse_va - esperado) > TOLERANCIA:
        sys.exit(f"El RMSE de VA ({rmse_va:.6f}) no reproduce el de la práctica ({esperado:.6f}). No se exporta.")

    # Inferencia equivalente sin scikit-learn: y = my + sy * (b + w · (x - mx) / sx)
    w = modelo.coef_.astype(float)
    salida = {
        "version": VERSION,
        "nombre": "Regresión lineal (20 rezagos)",
        "activo": "BTCUSDT", "plataforma": "MEXC", "intervalo": "1d",
        "contrato": {
            "entradas": LAGS,
            "definicion": "r_lag{k} = close(t-k) / close(t-k-1) - 1, rendimiento simple diario; t = fecha de la última vela CERRADA (emisión). "
                          "r_lag0 es el rendimiento del propio día t; r_lag19 el de hace 19 días. Hacen falta 21 cierres consecutivos.",
            "objetivo": "y = close(t+1) / close(t) - 1 (rendimiento del día siguiente a la emisión)",
            "escalado": "StandardScaler en X y en y ajustados solo con TR; la salida se desescala",
            "formula": "estimado = y_media + y_desv * (intercepto + sum_k coef[k] * (r_lag[k] - x_media[k]) / x_desv[k])",
        },
        "parametros": {
            "coef": w.tolist(), "intercepto": float(modelo.intercept_),
            "x_media": esc_x.mean_.tolist(), "x_desv": esc_x.scale_.tolist(),
            "y_media": float(esc_y.mean_[0]), "y_desv": float(esc_y.scale_[0]),
        },
        "entrenamiento": {
            "conjunto": "TR", "ejemplos": int(len(tr)),
            "primera_fecha_objetivo": str(tr.fecha_objetivo.min().date()), "ultima_fecha_objetivo": str(tr.fecha_objetivo.max().date()),
            "archivo": "datos_entrenamiento/ventanas_btcusdt_1d.csv", "sha256": huella(os.path.join(DATOS, "ventanas_btcusdt_1d.csv")),
            "seleccion": "Avance 2, corrida en Colab con Tesla T4 (13-nov-2026): la lineal ganó a MLP y LSTM por RMSE en VA",
        },
        "metricas": {"RMSE_TR": rmse_tr, "RMSE_VA": rmse_va, "RMSE_VA_practica": esperado, "RMSE_cero_VA": float(ref[(ref.modelo == "Cero") & (ref.conjunto == "VA")].RMSE.iloc[0])},
        "regla_avance3": {"umbral": regla["umbral"], "texto": regla["regla"], "rendimiento_neto_VA_%": regla["rendimiento_neto_VA_%"]},
        "exportado_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        "librerias_al_exportar": {"numpy": np.__version__, "pandas": pd.__version__, "scikit-learn": __import__("sklearn").__version__},
    }
    destino = os.path.join(AQUI, VERSION, "modelo.json")
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    with open(destino, "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, indent=1)

    # Comprobación de la fórmula sin sklearn sobre VA
    x = va[LAGS].to_numpy()
    manual = salida["parametros"]["y_media"] + salida["parametros"]["y_desv"] * (salida["parametros"]["intercepto"] + ((x - esc_x.mean_) / esc_x.scale_) @ w)
    assert np.allclose(manual, estimar(va), atol=1e-12), "la fórmula manual no coincide con sklearn"
    print(f"Modelo {VERSION} exportado a {destino}")
    print(f"RMSE TR {rmse_tr:.6f} · RMSE VA {rmse_va:.6f} (práctica {esperado:.6f}) · {len(tr)} ejemplos de TR · sha256 {salida['entrenamiento']['sha256'][:12]}…")


if __name__ == "__main__":
    main()
