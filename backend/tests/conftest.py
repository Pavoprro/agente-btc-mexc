import os, sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("API_KEY", "clave-de-prueba-0123456789")

from app.config import Config  # noqa: E402
from app.modelo import Modelo  # noqa: E402

DATOS = os.path.join(os.path.dirname(__file__), "..", "modelo", "datos_entrenamiento")
DIA_MS = 86_400_000


@pytest.fixture(scope="session")
def cfg():
    return Config(api_key="clave-de-prueba-0123456789", reintentos=2, espera_base_s=0.0)


@pytest.fixture(scope="session")
def modelo():
    return Modelo("v1")


@pytest.fixture(scope="session")
def precios():
    import pandas as pd
    return pd.read_csv(os.path.join(DATOS, "btcusdt_1d_auditado.csv"), parse_dates=["fecha"])


@pytest.fixture(scope="session")
def ventanas():
    import pandas as pd
    return pd.read_csv(os.path.join(DATOS, "ventanas_btcusdt_1d.csv"), parse_dates=["fecha_emision", "fecha_objetivo"])


def velas_crudas(precios, n=60, incluir_abierta=True):
    """Arma una respuesta de MEXC con las últimas n velas de la serie auditada (más una abierta, como manda MEXC)."""
    p = precios.tail(n)
    filas = []
    for _, r in p.iterrows():
        a = int(r.fecha.tz_localize("UTC").timestamp() * 1000)
        filas.append([a, str(r.open), str(r.high), str(r.low), str(r.close), str(r.volume), a + DIA_MS - 1, str(r.quote_volume)])
    if incluir_abierta:
        a = filas[-1][0] + DIA_MS
        filas.append([a, filas[-1][4], filas[-1][4], filas[-1][4], filas[-1][4], "0", a + DIA_MS - 1, "0"])
    return filas
