"""La API: /salud pública, /pronostico solo con clave, 503 cuando no hay dato válido."""
import pytest
from fastapi.testclient import TestClient

from app.main import crear_app
from app.mexc import DIA_MS, ErrorDatos, validar
from tests.conftest import velas_crudas

CLAVE = {"X-API-Key": "clave-de-prueba-0123456789"}


@pytest.fixture
def cliente(cfg, modelo, precios):
    filas = velas_crudas(precios, 60)
    velas = validar(filas, "BTCUSDT", "1d", filas[-1][0] + DIA_MS // 2, 36)
    return TestClient(crear_app(cfg, modelo, obtener_velas=lambda: velas)), velas


def test_salud_es_publica(cliente):
    c, _ = cliente
    r = c.get("/salud")
    assert r.status_code == 200 and r.json()["modelo"]["version"] == "v1"
    assert "deshabilitadas" in r.json()["paper"]["ordenes_reales"]


def test_pronostico_sin_clave_401(cliente):
    c, _ = cliente
    assert c.get("/pronostico").status_code == 401
    assert c.get("/pronostico", headers={"X-API-Key": "incorrecta"}).status_code == 401


def test_pronostico_con_clave(cliente, modelo, ventanas):
    c, velas = cliente
    r = c.get("/pronostico", headers=CLAVE)
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["fecha_vela"] == velas[-1].fecha and cuerpo["senal_regla"] in ("comprar", "efectivo")
    # el mismo estimado que la práctica para esa fecha de emisión
    fila = ventanas[ventanas.fecha_emision == velas[-1].fecha]
    if len(fila):
        from app.variables import LAGS
        assert abs(cuerpo["estimado"] - modelo.estimar(dict(zip(LAGS, fila[LAGS].iloc[0])))) < 1e-12


def test_pronostico_503_sin_dato(cfg, modelo):
    def falla():
        raise ErrorDatos("MEXC sin respuesta válida tras 3 intentos")
    c = TestClient(crear_app(cfg, modelo, obtener_velas=falla))
    r = c.get("/pronostico", headers=CLAVE)
    assert r.status_code == 503 and "3 intentos" in r.json()["detail"]
