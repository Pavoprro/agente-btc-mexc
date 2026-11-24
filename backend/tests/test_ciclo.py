"""El ciclo completo (§15) con velas reales de la serie auditada, sin red: decisión, Paper, SQLite, idempotencia, control humano,
reinicio del backend, replay de ≥ 20 velas, respaldo cuando la propuesta externa falla."""
import os

import pytest

from app.ciclo import Agente, Propuesta
from app.mexc import ErrorDatos
from app.registro import Registro
from tests.conftest import velas_validas


def agente_en(cfg, modelo, precios, hasta, registro=None, **kw):
    velas, ahora = velas_validas(precios, 60, hasta)
    reg = registro or Registro(":memory:", cfg.capital_inicial)
    return Agente(cfg, modelo, reg, lambda: velas, reloj=lambda: ahora, **kw), velas


def test_un_ciclo_decide_ejecuta_y_registra(cfg, modelo, precios):
    ag, velas = agente_en(cfg, modelo, precios, hasta=len(precios) - 1)
    assert ag.ciclo()["omitido"]                                   # detenido: no procesa
    ag.iniciar()
    r = ag.ciclo()
    c = r["ciclo"]
    assert not r["duplicado"] and c["fecha_vela"] == velas[-1].fecha and c["modelo"] == "v2" and len(c["variables"]) == 22
    assert c["propuesta"] in ("comprar", "mantener", "vender") and c["accion"] in ("comprar", "mantener", "vender")
    assert abs(c["patrimonio"] - cfg.capital_inicial) < 1e-6        # se ejecuta y valora al mismo cierre: el patrimonio no cambia el día de la compra
    assert ag.reg.conteos()["ciclos"] == 1 and ag.reg.ciclo_existe(c["fecha_vela"])["accion"] == c["accion"]


def test_la_misma_vela_no_se_procesa_dos_veces(cfg, modelo, precios):
    ag, _ = agente_en(cfg, modelo, precios, hasta=len(precios) - 1)
    ag.iniciar()
    primero = ag.ciclo()
    segundo = ag.ciclo()
    assert segundo["duplicado"] and segundo["ciclo"]["fecha_vela"] == primero["ciclo"]["fecha_vela"]
    assert ag.reg.conteos()["ciclos"] == 1 and ag.reg.conteos()["ordenes"] <= 1


def test_pausar_detener_e_iniciar(cfg, modelo, precios):
    ag, _ = agente_en(cfg, modelo, precios, hasta=len(precios) - 1)
    ag.iniciar(); assert ag.reg.modo() == "activo"
    ag.pausar(); assert ag.reg.modo() == "pausado" and ag.ciclo()["omitido"]
    ag.detener(); assert ag.reg.modo() == "detenido" and ag.ciclo()["omitido"]
    assert not ag.ciclo(forzar=True)["omitido"]                   # el operador puede forzar un ciclo aunque esté detenido
    tipos = [e["tipo"] for e in ag.reg.eventos()]
    assert tipos[-3:] == ["activo", "pausado", "detenido"]


def test_reinicio_del_backend_restaura_la_cuenta_y_no_duplica(cfg, modelo, precios, tmp_path):
    ruta = os.path.join(tmp_path, "agente.db")
    reg1 = Registro(ruta, cfg.capital_inicial)
    ag1, velas = agente_en(cfg, modelo, precios, hasta=len(precios) - 1, registro=reg1)
    ag1.iniciar()
    r1 = ag1.ciclo()
    cuenta_antes = ag1.paper.cuenta.__dict__.copy()
    reg1.cerrar()
    reg2 = Registro(ruta, cfg.capital_inicial)                     # "reinicio": nuevo proceso, misma base
    ag2, _ = agente_en(cfg, modelo, precios, hasta=len(precios) - 1, registro=reg2)
    assert ag2.paper.cuenta.__dict__ == cuenta_antes and reg2.modo() == "activo"
    r2 = ag2.ciclo()
    assert r2["duplicado"] and reg2.conteos()["ciclos"] == 1
    assert [e["tipo"] for e in reg2.eventos()].count("arranque") == 2


def test_replay_de_mas_de_20_velas_es_idempotente(cfg, modelo, precios):
    """Se recorren 25 velas consecutivas (cada una con su ventana de 60), como el agente las iría viendo día con día."""
    reg = Registro(":memory:", cfg.capital_inicial)
    n = len(precios)
    resultados = []
    for hasta in range(n - 25, n):
        velas, ahora = velas_validas(precios, 60, hasta)
        ag = Agente(cfg, modelo, reg, lambda v=velas: v, reloj=lambda a=ahora: a)
        if reg.modo() != "activo":
            ag.iniciar()
        resultados.append(ag.ciclo())
        assert ag.ciclo()["duplicado"]
    assert reg.conteos()["ciclos"] == 25 and not any(r["duplicado"] for r in resultados)
    ciclos = reg.ciclos(100)
    assert [c["fecha_vela"] for c in ciclos] == sorted(c["fecha_vela"] for c in ciclos)
    for a, b in zip(ciclos, ciclos[1:]):                           # el patrimonio se encadena: efectivo + unidades × cierre
        assert abs(b["patrimonio"] - (b["efectivo"] + b["unidades"] * b["cierre"])) < 1e-6
        if a["unidades"] > 0 and b["accion"] == "mantener":
            assert abs(b["patrimonio"] - (a["efectivo"] + a["unidades"] * b["cierre"])) < 1e-6
    assert reg.conteos()["ordenes"] == sum(c["accion"] != "mantener" for c in ciclos)
    assert reg.conteos()["errores"] == 0


def test_saldo_insuficiente_queda_registrado(cfg, modelo, precios):
    ag, _ = agente_en(cfg.model_copy(update={"filtro_sma20": False}), modelo, precios, hasta=len(precios) - 1)   # sin el filtro, para aislar el saldo
    ag.paper.cuenta.efectivo = 0.5
    ag.reg.guardar_cuenta(ag.paper.cuenta)
    ag.iniciar()
    ag.proponer = lambda ctx: Propuesta(accion="comprar", simbolo="BTCUSDT", fecha_vela=ctx["fecha_vela"], justificacion="prueba", fuente="prueba")
    r = ag.ciclo()
    assert r["ciclo"]["accion"] == "mantener" and "saldo_insuficiente" in r["ciclo"]["bloqueos"] and r["orden"] is None


def test_dato_atrasado_no_opera_y_queda_en_errores(cfg, modelo, precios):
    velas, ahora = velas_validas(precios, 60, len(precios) - 1)
    reg = Registro(":memory:", cfg.capital_inicial)
    ag = Agente(cfg, modelo, reg, lambda: velas, reloj=lambda: ahora + 3 * 86_400)      # tres días después
    ag.iniciar()
    r = ag.ciclo()
    assert r["ciclo"]["accion"] == "mantener" and r["ciclo"]["bloqueos"] == ["dato_atrasado"]

    def caida():
        raise ErrorDatos("MEXC sin respuesta válida tras 3 intentos")
    ag2 = Agente(cfg, modelo, Registro(":memory:", cfg.capital_inicial), caida)
    ag2.iniciar()
    with pytest.raises(ErrorDatos):
        ag2.ciclo()
    assert ag2.reg.errores()[-1]["tipo"] == "datos"


def test_propuesta_externa_invalida_cae_a_la_regla(cfg, modelo, precios):
    ag, velas = agente_en(cfg, modelo, precios, hasta=len(precios) - 1, proponer=lambda ctx: {"accion": "apalancar", "simbolo": "BTCUSDT", "fecha_vela": ctx["fecha_vela"], "justificacion": "x"})
    ag.iniciar()
    r = ag.ciclo()
    assert r["ciclo"]["fuente"] == "regla (respaldo)" and ag.reg.errores()[-1]["tipo"] == "propuesta_invalida"

    def ollama_caido(ctx):
        raise ConnectionError("Ollama no responde en 127.0.0.1:11434")
    ag2, _ = agente_en(cfg, modelo, precios, hasta=len(precios) - 1, proponer=ollama_caido)
    ag2.iniciar()
    r2 = ag2.ciclo()
    assert r2["ciclo"]["fuente"] == "regla (respaldo)" and ag2.reg.errores()[-1]["tipo"] == "llm"


def test_liquidar_vende_toda_la_posicion(cfg, modelo, precios):
    ag, velas = agente_en(cfg, modelo, precios, hasta=len(precios) - 1)
    ag.iniciar()
    ag.paper.comprar(velas[-1].close)                                # dejamos una posición abierta
    ag.reg.guardar_cuenta(ag.paper.cuenta)
    r = ag.liquidar()
    assert r["liquidado"] and not ag.paper.invertido and ag.reg.ordenes()[-1]["origen"] == "liquidar"
    assert not ag.liquidar()["liquidado"]
