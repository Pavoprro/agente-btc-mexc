"""Controles deterministas de riesgo: la propuesta nunca manda; cada regla se prueba sola."""
from app.riesgo import Situacion, evaluar

LIMITES = dict(max_antiguedad_h=36, perdida_diaria_max=0.05, exposicion_max=1.0, filtro_sma20=True, nominal_minimo=1.0)


def sit(**kw):
    base = dict(propuesta="comprar", invertido=False, efectivo=50_000.0, patrimonio=50_000.0, patrimonio_anterior=50_000.0, antiguedad_h=2.0, dist_sma20=0.01)
    return Situacion(**{**base, **kw})


def test_compra_permitida():
    v = evaluar(sit(), **LIMITES)
    assert v.accion == "comprar" and v.fraccion == 1.0 and not v.bloqueos


def test_dato_atrasado_no_opera():
    v = evaluar(sit(antiguedad_h=40), **LIMITES)
    assert v.accion == "mantener" and v.bloqueos == ["dato_atrasado"]
    assert evaluar(sit(propuesta="vender", invertido=True, antiguedad_h=40), **LIMITES).accion == "mantener"


def test_acciones_imposibles_se_traducen_en_mantener():
    assert evaluar(sit(propuesta="comprar", invertido=True), **LIMITES).bloqueos == ["ya_invertido"]
    assert evaluar(sit(propuesta="vender", invertido=False), **LIMITES).bloqueos == ["sin_posicion"]
    assert evaluar(sit(propuesta="apalancar"), **LIMITES).bloqueos == ["propuesta_invalida"]


def test_perdida_diaria_bloquea_compras_pero_no_ventas():
    v = evaluar(sit(patrimonio=47_000.0, patrimonio_anterior=50_000.0), **LIMITES)
    assert v.accion == "mantener" and v.bloqueos == ["perdida_diaria"]
    assert evaluar(sit(propuesta="vender", invertido=True, patrimonio=47_000.0), **LIMITES).accion == "vender"
    assert evaluar(sit(patrimonio=48_000.0, patrimonio_anterior=50_000.0), **LIMITES).accion == "comprar"   # −4 %: dentro del límite


def test_filtro_sma20():
    assert evaluar(sit(dist_sma20=-0.02), **LIMITES).bloqueos == ["filtro_sma20"]
    assert evaluar(sit(dist_sma20=None), **LIMITES).bloqueos == ["filtro_sma20"]
    assert evaluar(sit(dist_sma20=-0.02), **{**LIMITES, "filtro_sma20": False}).accion == "comprar"


def test_exposicion_y_saldo():
    v = evaluar(sit(), **{**LIMITES, "exposicion_max": 0.5})
    assert v.accion == "comprar" and v.fraccion == 0.5
    assert evaluar(sit(efectivo=0.5), **LIMITES).bloqueos == ["saldo_insuficiente"]


def test_mantener_siempre_es_valida():
    assert evaluar(sit(propuesta="mantener"), **LIMITES).accion == "mantener"
    assert evaluar(sit(propuesta="mantener", invertido=True), **LIMITES).accion == "mantener"
