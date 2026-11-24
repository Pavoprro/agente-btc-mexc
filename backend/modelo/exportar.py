"""Exporta el modelo de la práctica a un archivo JSON versionado que el backend carga sin scikit-learn.
  v1: regresión lineal con 20 rezagos (elegida en el Avance 2 en T4, validada en el Avance 3).
  v2: la misma regresión con 20 rezagos + dist_sma20 + vol20 (versión final elegida con VA en el Avance 5). Es la que usa el agente.

Correr DESDE backend/:   python modelo/exportar.py          (exporta v1 y v2)
Qué hace para cada versión:
  1. Lee las ventanas y los precios del Avance 1 (datos_entrenamiento/) y las particiones TR / VA / TE; calcula los indicadores
     con la definición del Avance 5 y los une por fecha de emisión.
  2. Ajusta los escaladores (StandardScaler de X y de y) SOLO con TR y la regresión lineal sobre lo escalado, igual que los cuadernos.
  3. Comprueba que el RMSE en VA reproduce el de la práctica (v1: 0.024277 del Avance 1; v2: el de version_final_avance5.json). Si no cuadra, no exporta.
  4. Evalúa TE una vez (ya evaluado en el Avance 5; aquí solo se verifica que coincide) y escribe modelo/<version>/modelo.json con
     coeficientes, intercepto, medias y desviaciones, contrato de variables, huella de los datos y métricas.
"""
import hashlib, json, os, sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler

AQUI = os.path.dirname(os.path.abspath(__file__))
DATOS = os.path.join(AQUI, "datos_entrenamiento")
VENTANA = 20
LAGS = [f"r_lag{i}" for i in range(VENTANA)]
INDICADORES = ["dist_sma20", "vol20"]
TOLERANCIA = 1e-5
DEFINICION_LAGS = ("r_lag{k} = close(t-k) / close(t-k-1) - 1, rendimiento simple diario; t = fecha de la última vela CERRADA (emisión). "
                   "r_lag0 es el rendimiento del propio día t; r_lag19 el de hace 19 días. Hacen falta 21 cierres consecutivos.")
DEFINICION_IND = ("dist_sma20 = close(t) / SMA20(t) - 1, SMA20 = promedio simple de los 20 cierres t-19 … t. "
                  "vol20 = desviación estándar muestral (ddof = 1) de los 20 rendimientos r_t-19 … r_t, sin anualizar. Solo historia hasta t.")


def huella(ruta):
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def cargar():
    ventanas = pd.read_csv(os.path.join(DATOS, "ventanas_btcusdt_1d.csv"), parse_dates=["fecha_emision", "fecha_objetivo"])
    precios = pd.read_csv(os.path.join(DATOS, "btcusdt_1d_auditado.csv"), parse_dates=["fecha"]).set_index("fecha").sort_index()
    sma = precios.close.rolling(VENTANA, min_periods=VENTANA).mean()
    r = precios.close / precios.close.shift(1) - 1
    ind = pd.DataFrame({"dist_sma20": precios.close / sma - 1, "vol20": r.rolling(VENTANA, min_periods=VENTANA).std(ddof=1)})
    ventanas = ventanas.merge(ind, left_on="fecha_emision", right_index=True, how="left", validate="1:1")
    assert ventanas[INDICADORES].notna().all().all(), "hay filas sin indicador válido"
    assert np.allclose(ventanas.vol20, ventanas[LAGS].std(axis=1, ddof=1), atol=1e-12), "vol20 no coincide con los 20 rendimientos de la fila"
    part = pd.read_csv(os.path.join(DATOS, "particiones_avance1.csv")).set_index("conjunto")
    tr, va, te = (ventanas[ventanas.conjunto == k] for k in ("TR", "VA", "TE"))
    assert len(tr) == part.loc["TR", "ejemplos"] and len(va) == part.loc["VA", "ejemplos"] and len(te) == part.loc["TE", "ejemplos"], "las particiones no cuadran con el Avance 1"
    assert tr.fecha_objetivo.max() < va.fecha_objetivo.min() < te.fecha_objetivo.min(), "las particiones se traslapan"
    return tr, va, te


def exportar(version, entradas, nombre, esperado_va, seleccion, tr, va, te, extra):
    esc_x = StandardScaler().fit(tr[entradas].to_numpy())
    esc_y = StandardScaler().fit(tr[["y"]].to_numpy())
    modelo = LinearRegression().fit(esc_x.transform(tr[entradas].to_numpy()), esc_y.transform(tr[["y"]].to_numpy()).ravel())

    def estimar(df):
        return esc_y.inverse_transform(modelo.predict(esc_x.transform(df[entradas].to_numpy())).reshape(-1, 1)).ravel()

    rmse = {k: float(np.sqrt(np.mean((estimar(d) - d.y.to_numpy()) ** 2))) for k, d in (("TR", tr), ("VA", va), ("TE", te))}
    cero = {k: float(np.sqrt(np.mean(d.y.to_numpy() ** 2))) for k, d in (("VA", va), ("TE", te))}
    if abs(rmse["VA"] - esperado_va) > TOLERANCIA:
        sys.exit(f"[{version}] El RMSE de VA ({rmse['VA']:.6f}) no reproduce el de la práctica ({esperado_va:.6f}). No se exporta.")

    w = modelo.coef_.astype(float)
    salida = {
        "version": version, "nombre": nombre, "activo": "BTCUSDT", "plataforma": "MEXC", "intervalo": "1d",
        "contrato": {"entradas": entradas, "definicion": DEFINICION_LAGS + ("" if len(entradas) == VENTANA else " " + DEFINICION_IND),
                     "objetivo": "y = close(t+1) / close(t) - 1 (rendimiento del día siguiente a la emisión)",
                     "escalado": "StandardScaler en X y en y ajustados solo con TR; la salida se desescala",
                     "formula": "estimado = y_media + y_desv * (intercepto + sum_k coef[k] * (x[k] - x_media[k]) / x_desv[k])"},
        "parametros": {"coef": w.tolist(), "intercepto": float(modelo.intercept_), "x_media": esc_x.mean_.tolist(), "x_desv": esc_x.scale_.tolist(),
                       "y_media": float(esc_y.mean_[0]), "y_desv": float(esc_y.scale_[0])},
        "entrenamiento": {"conjunto": "TR", "ejemplos": int(len(tr)), "primera_fecha_objetivo": str(tr.fecha_objetivo.min().date()),
                          "ultima_fecha_objetivo": str(tr.fecha_objetivo.max().date()), "archivo": "datos_entrenamiento/ventanas_btcusdt_1d.csv",
                          "sha256": huella(os.path.join(DATOS, "ventanas_btcusdt_1d.csv")), "seleccion": seleccion},
        "metricas": {"RMSE_TR": rmse["TR"], "RMSE_VA": rmse["VA"], "RMSE_VA_practica": esperado_va, "RMSE_cero_VA": cero["VA"],
                     "RMSE_TE": rmse["TE"], "RMSE_cero_TE": cero["TE"], "nota_TE": "TE se evaluó una sola vez en el Avance 5; aquí solo se verifica que coincide"},
        **extra,
        "exportado_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        "librerias_al_exportar": {"numpy": np.__version__, "pandas": pd.__version__, "scikit-learn": __import__("sklearn").__version__},
    }
    destino = os.path.join(AQUI, version, "modelo.json")
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    with open(destino, "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, indent=1)
    x = va[entradas].to_numpy()
    manual = salida["parametros"]["y_media"] + salida["parametros"]["y_desv"] * (salida["parametros"]["intercepto"] + ((x - esc_x.mean_) / esc_x.scale_) @ w)
    assert np.allclose(manual, estimar(va), atol=1e-12), "la fórmula manual no coincide con sklearn"
    print(f"Modelo {version} exportado a {destino}: RMSE TR {rmse['TR']:.6f} · VA {rmse['VA']:.6f} (práctica {esperado_va:.6f}) · TE {rmse['TE']:.6f} (cero {cero['TE']:.6f}) · {len(tr)} ejemplos de TR")
    return salida


def main():
    tr, va, te = cargar()
    ref = pd.read_csv(os.path.join(DATOS, "metricas_referencia_avance1.csv"))
    regla = json.load(open(os.path.join(DATOS, "regla_seleccionada.json"), encoding="utf-8"))
    final5 = json.load(open(os.path.join(DATOS, "version_final_avance5.json"), encoding="utf-8"))
    reglas5 = json.load(open(os.path.join(DATOS, "reglas_finales_avance5.json"), encoding="utf-8"))
    esperado_v1 = float(ref[(ref.modelo == "Regresión lineal (20 rezagos)") & (ref.conjunto == "VA")].RMSE.iloc[0])
    exportar("v1", LAGS, "Regresión lineal (20 rezagos)", esperado_v1,
             "Avance 2, corrida en Colab con Tesla T4 (13-nov-2026): la lineal ganó a MLP y LSTM por RMSE en VA", tr, va, te,
             {"regla_avance3": {"umbral": regla["umbral"], "texto": regla["regla"], "rendimiento_neto_VA_%": regla["rendimiento_neto_VA_%"]}})
    assert final5["final"].startswith("B") and final5["variables"] == LAGS + INDICADORES, "el Avance 5 no eligió la versión B"
    v2 = exportar("v2", LAGS + INDICADORES, "Regresión lineal (20 rezagos + dist_sma20 + vol20)", float(final5["RMSE_VA"]["B: rezagos + 2 indicadores"]),
                  "Avance 5 (24-nov-2026): versión final elegida con VA (menor RMSE) sobre la lineal del Avance 2; la lineal se eligió en T4 en el Avance 2", tr, va, te,
                  {"reglas_avance5": {"C": reglas5["C"], "D": reglas5["D"], "nota": "C = comprar si estimado > umbral; D = además cierre > SMA20 (dist_sma20 > 0). Elegidas con VA."}})
    assert abs(v2["metricas"]["RMSE_TE"] - final5.get("RMSE_TE", v2["metricas"]["RMSE_TE"])) < TOLERANCIA


if __name__ == "__main__":
    main()
