"""Validación de velas (§15 paso 1) y reintentos ante MEXC caída, sin red: se simula la respuesta."""
import httpx
import pytest

from app.mexc import DIA_MS, ErrorDatos, descargar, validar
from tests.conftest import velas_crudas


def ahora_tras(filas):
    return filas[-1][0] + DIA_MS // 2        # a media vela abierta


def test_descarta_la_vela_abierta(precios):
    filas = velas_crudas(precios, 30)
    velas = validar(filas, "BTCUSDT", "1d", ahora_tras(filas), 36)
    assert len(velas) == 30 and velas[-1].close == float(filas[-2][4])


def test_detecta_hueco(precios):
    filas = velas_crudas(precios, 30)
    del filas[10]
    with pytest.raises(ErrorDatos, match="hueco"):
        validar(filas, "BTCUSDT", "1d", ahora_tras(filas), 36)


def test_detecta_desorden(precios):
    filas = velas_crudas(precios, 30)
    filas[5], filas[6] = filas[6], filas[5]
    with pytest.raises(ErrorDatos, match="desorden|hueco"):
        validar(filas, "BTCUSDT", "1d", ahora_tras(filas), 36)


def test_detecta_dato_atrasado(precios):
    filas = velas_crudas(precios, 30)
    with pytest.raises(ErrorDatos, match="atrasado"):
        validar(filas, "BTCUSDT", "1d", filas[-1][0] + 3 * DIA_MS, 36)


def test_detecta_precios_imposibles(precios):
    filas = velas_crudas(precios, 30)
    filas[3][2] = "1"          # high por debajo del resto
    with pytest.raises(ErrorDatos, match="imposibles"):
        validar(filas, "BTCUSDT", "1d", ahora_tras(filas), 36)


def test_pocas_velas(precios):
    filas = velas_crudas(precios, 15)
    with pytest.raises(ErrorDatos, match="necesita 21"):
        validar(filas, "BTCUSDT", "1d", ahora_tras(filas), 36)


def test_reintenta_y_luego_falla_si_mexc_no_responde():
    llamadas = []

    def respuesta(req):
        llamadas.append(req.url)
        return httpx.Response(429, json={"msg": "limite"})

    cliente = httpx.Client(transport=httpx.MockTransport(respuesta))
    with pytest.raises(ErrorDatos, match="3 intentos"):
        descargar("https://x/klines", "BTCUSDT", "1d", 30, reintentos=3, espera_base_s=0.0, cliente=cliente)
    assert len(llamadas) == 3


def test_reintento_exitoso(precios):
    filas = velas_crudas(precios, 30)
    estado = {"n": 0}

    def respuesta(req):
        estado["n"] += 1
        return httpx.Response(503) if estado["n"] == 1 else httpx.Response(200, json=filas)

    cliente = httpx.Client(transport=httpx.MockTransport(respuesta))
    assert descargar("https://x/klines", "BTCUSDT", "1d", 30, reintentos=3, espera_base_s=0.0, cliente=cliente) == filas
    assert estado["n"] == 2
