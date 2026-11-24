"""Las variables del modelo con la MISMA definición del entrenamiento (contrato en modelo/<version>/modelo.json).
- r_lag{k} = close(t-k) / close(t-k-1) - 1, para k = 0..19, con t = última vela cerrada (Avance 1).
- dist_sma20 = close(t) / SMA20(t) - 1, con SMA20 = promedio de los 20 cierres t-19 … t (Avance 5).
- vol20 = desviación estándar MUESTRAL (ddof = 1) de los 20 rendimientos r_t-19 … r_t, sin anualizar (Avance 5).
Hacen falta 21 cierres consecutivos. Todo se calcula solo con historia hasta t."""
import numpy as np

VENTANA = 20
LAGS = [f"r_lag{i}" for i in range(VENTANA)]
INDICADORES = ["dist_sma20", "vol20"]


def rendimientos(cierres) -> np.ndarray:
    c = np.asarray(cierres, dtype=float)
    if len(c) < 2 or (c <= 0).any():
        raise ValueError("hacen falta al menos 2 cierres positivos")
    return c[1:] / c[:-1] - 1


def rezagos(cierres) -> dict[str, float]:
    """Devuelve {r_lag0: ..., r_lag19: ...} a partir de los últimos 21 cierres (o más: usa los últimos)."""
    c = np.asarray(cierres, dtype=float)
    if len(c) < VENTANA + 1:
        raise ValueError(f"hacen falta {VENTANA + 1} cierres consecutivos y hay {len(c)}")
    r = rendimientos(c[-(VENTANA + 1):])          # 20 rendimientos: r[-1] es el de hoy (lag0)
    return {f"r_lag{k}": float(r[-1 - k]) for k in range(VENTANA)}


def indicadores(cierres) -> dict[str, float]:
    """dist_sma20 y vol20 de la última vela cerrada, con la definición del Avance 5."""
    c = np.asarray(cierres, dtype=float)
    if len(c) < VENTANA + 1:
        raise ValueError(f"hacen falta {VENTANA + 1} cierres consecutivos y hay {len(c)}")
    ult = c[-VENTANA:]
    r = rendimientos(c[-(VENTANA + 1):])
    return {"dist_sma20": float(ult[-1] / ult.mean() - 1), "vol20": float(np.std(r, ddof=1))}


def variables(cierres) -> dict[str, float]:
    """Las 22 variables del contrato v2 (20 rezagos + 2 indicadores)."""
    return {**rezagos(cierres), **indicadores(cierres)}


def vector(valores: dict[str, float], entradas: list[str]) -> np.ndarray:
    faltan = [k for k in entradas if k not in valores]
    if faltan:
        raise ValueError(f"faltan variables: {faltan}")
    x = np.array([valores[k] for k in entradas], dtype=float)
    if not np.isfinite(x).all():
        raise ValueError("hay variables no finitas")
    return x
