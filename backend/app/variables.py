"""Las variables del modelo con la MISMA definición del entrenamiento (contrato en modelo/v1/modelo.json):
r_lag{k} = close(t-k) / close(t-k-1) - 1, para k = 0..19, con t = última vela cerrada. Hacen falta 21 cierres consecutivos."""
import numpy as np

VENTANA = 20
LAGS = [f"r_lag{i}" for i in range(VENTANA)]


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


def vector(rez: dict[str, float]) -> np.ndarray:
    faltan = [k for k in LAGS if k not in rez]
    if faltan:
        raise ValueError(f"faltan variables: {faltan}")
    x = np.array([rez[k] for k in LAGS], dtype=float)
    if not np.isfinite(x).all():
        raise ValueError("hay variables no finitas")
    return x
