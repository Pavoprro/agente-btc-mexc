import os, sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("API_KEY", "clave-de-prueba-0123456789")

from app.config import Config  # noqa: E402
from app.mexc import DIA_MS, validar  # noqa: E402
from app.modelo import Modelo  # noqa: E402
from app.registro import Registro  # noqa: E402

DATOS = os.path.join(os.path.dirname(__file__), "..", "modelo", "datos_entrenamiento")
CLAVE = {"X-API-Key": "clave-de-prueba-0123456789"}


@pytest.fixture(scope="session")
def cfg():
    return Config(api_key="clave-de-prueba-0123456789", reintentos=2, espera_base_s=0.0, ruta_db=":memory:")


@pytest.fixture(scope="session")
def modelo():
    return Modelo("v2")


@pytest.fixture(scope="session")
def modelo_v1():
    return Modelo("v1")


@pytest.fixture(scope="session")
def precios():
    import pandas as pd
    return pd.read_csv(os.path.join(DATOS, "btcusdt_1d_auditado.csv"), parse_dates=["fecha"])


@pytest.fixture(scope="session")
def ventanas():
    import pandas as pd
    return pd.read_csv(os.path.join(DATOS, "ventanas_btcusdt_1d.csv"), parse_dates=["fecha_emision", "fecha_objetivo"])


@pytest.fixture
def registro(cfg):
    return Registro(":memory:", cfg.capital_inicial)


def velas_crudas(precios, n=60, incluir_abierta=True, hasta=None):
    """Arma una respuesta de MEXC con n velas de la serie auditada que terminan en la fila `hasta` (por defecto la última),
    más una vela abierta, como manda MEXC."""
    p = precios if hasta is None else precios.iloc[: hasta + 1]
    p = p.tail(n)
    filas = []
    for _, r in p.iterrows():
        a = int(r.fecha.tz_localize("UTC").timestamp() * 1000)
        filas.append([a, str(r.open), str(r.high), str(r.low), str(r.close), str(r.volume), a + DIA_MS - 1, str(r.quote_volume)])
    if incluir_abierta:
        a = filas[-1][0] + DIA_MS
        filas.append([a, filas[-1][4], filas[-1][4], filas[-1][4], filas[-1][4], "0", a + DIA_MS - 1, "0"])
    return filas


def velas_validas(precios, n=60, hasta=None):
    """Velas cerradas ya validadas (ahora = media vela abierta) y el instante 'ahora' en segundos."""
    filas = velas_crudas(precios, n, True, hasta)
    ahora_ms = filas[-1][0] + DIA_MS // 2
    return validar(filas, "BTCUSDT", "1d", ahora_ms, 36), ahora_ms / 1000
