"""La API: /salud pública; todo lo demás solo con clave; 503 cuando no hay dato válido; control humano y bitácora."""
import pytest
from fastapi.testclient import TestClient

from app.main import crear_app
from app.mexc import ErrorDatos
from app.registro import Registro
from tests.conftest import CLAVE, velas_validas


@pytest.fixture
def cliente(cfg, modelo, precios):
    velas, ahora = velas_validas(precios, 60)
    app = crear_app(cfg, modelo, obtener_velas=lambda: velas, registro=Registro(":memory:", cfg.capital_inicial), programar=False, reloj=lambda: ahora)
    return TestClient(app), velas


def test_salud_es_publica(cliente):
    c, _ = cliente
    r = c.get("/api/salud")
    assert r.status_code == 200 and r.json()["modelo"]["version"] == "v2" and r.json()["agente"]["modo"] == "detenido"
    assert "deshabilitadas" in r.json()["paper"]["ordenes_reales"]


def test_todo_lo_privado_exige_clave(cliente):
    c, _ = cliente
    for metodo, ruta in [("get", "/api/pronostico"), ("get", "/api/estado"), ("get", "/api/bitacora"), ("post", "/api/ciclo"),
                         ("post", "/api/agente/iniciar"), ("post", "/api/agente/pausar"), ("post", "/api/agente/detener"), ("post", "/api/agente/liquidar")]:
        assert getattr(c, metodo)(ruta).status_code == 401, ruta
        assert getattr(c, metodo)(ruta, headers={"X-API-Key": "incorrecta"}).status_code == 401, ruta


def test_pronostico_con_clave(cliente, modelo):
    c, velas = cliente
    r = c.get("/api/pronostico", headers=CLAVE)
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["fecha_vela"] == velas[-1].fecha and cuerpo["senal_regla"] in ("comprar", "efectivo") and len(cuerpo["variables"]) == 22
    assert cuerpo["modelo"]["version"] == "v2" and isinstance(cuerpo["filtro_sma20_ok"], bool)


def test_ciclo_y_control_por_api(cliente):
    c, velas = cliente
    assert c.post("/api/ciclo", headers=CLAVE).json()["omitido"]                # detenido
    assert c.post("/api/agente/iniciar", headers=CLAVE).json()["modo"] == "activo"
    r = c.post("/api/ciclo", headers=CLAVE).json()
    assert not r["duplicado"] and r["ciclo"]["fecha_vela"] == velas[-1].fecha
    assert c.post("/api/ciclo", headers=CLAVE).json()["duplicado"]
    e = c.get("/api/estado", headers=CLAVE).json()
    assert e["modo"] == "activo" and e["conteos"]["ciclos"] == 1 and e["cuenta"]["capital_inicial"] == 50_000
    assert c.post("/api/agente/pausar", headers=CLAVE).json()["modo"] == "pausado"
    assert c.post("/api/agente/detener", headers=CLAVE).json()["modo"] == "detenido"
    b = c.get("/api/bitacora", headers=CLAVE).json()
    assert len(b["ciclos"]) == 1 and [x["tipo"] for x in b["eventos"]][-3:] == ["activo", "pausado", "detenido"]
    liq = c.post("/api/agente/liquidar", headers=CLAVE).json()
    assert "liquidado" in liq


def test_503_sin_dato(cfg, modelo):
    def falla():
        raise ErrorDatos("MEXC sin respuesta válida tras 3 intentos")
    c = TestClient(crear_app(cfg, modelo, obtener_velas=falla, registro=Registro(":memory:", cfg.capital_inicial), programar=False))
    assert c.get("/api/pronostico", headers=CLAVE).status_code == 503
    c.post("/api/agente/iniciar", headers=CLAVE)
    r = c.post("/api/ciclo", headers=CLAVE)
    assert r.status_code == 503 and "3 intentos" in r.json()["detail"]
    assert c.get("/api/bitacora", headers=CLAVE).json()["errores"][-1]["tipo"] == "datos"
