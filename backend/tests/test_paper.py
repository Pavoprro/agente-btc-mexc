"""Motor Paper: saldo, costo, precisión del par, sin apalancamiento ni cortos, saldo insuficiente."""
import pytest

from app.paper import ErrorPaper, Paper


def test_compra_y_venta_con_costo_cero():
    p = Paper(50_000, 0.0)
    o = p.comprar(70_000.0)
    assert o.lado == "comprar" and o.cantidad == 0.714285 and o.costo == 0           # 50,000 / 70,000 = 0.7142857… → 6 decimales hacia abajo
    assert abs(p.cuenta.efectivo - (50_000 - 0.714285 * 70_000)) < 1e-6 and p.invertido
    assert abs(p.patrimonio(70_000) - 50_000) < 1e-6
    v = p.vender(77_000.0)
    assert v.lado == "vender" and v.cantidad == 0.714285 and not p.invertido
    assert abs(p.cuenta.efectivo - (50_000 + 0.714285 * 7_000)) < 1e-6 and v.ganancia_operacion > 0
    r = p.resumen(77_000)
    assert r["operaciones_cerradas"] == 1 and r["win_rate_%"] == 100.0 and r["rendimiento_neto_%"] > 9.9


def test_el_costo_se_descuenta_antes_de_calcular_las_unidades():
    p = Paper(100_000, 0.001)
    o = p.comprar(68_809.89)
    assert o.monto + o.costo <= 100_000 + 1e-9 and p.cuenta.efectivo >= 0
    assert abs(o.cantidad - 1.451828) < 1e-6                                           # la transición manual del Avance 4
    assert abs(o.costo - o.monto * 0.001) < 1e-9


def test_exposicion_parcial():
    p = Paper(50_000)
    o = p.comprar(50_000.0, fraccion=0.5)
    assert o.cantidad == 0.5 and abs(p.cuenta.efectivo - 25_000) < 1e-6 and abs(p.exposicion(50_000) - 0.5) < 1e-9


def test_sin_apalancamiento_ni_cortos():
    p = Paper(50_000)
    with pytest.raises(ErrorPaper, match="corto"):
        p.vender(70_000)
    p.comprar(70_000)
    with pytest.raises(ErrorPaper, match="apalancamiento"):
        p.comprar(70_000)


def test_saldo_insuficiente():
    p = Paper(50_000)
    p.comprar(70_000)
    assert p.cuenta.efectivo < 1                                                        # queda el residuo del redondeo
    p.vender(70_000)
    p.cuenta.efectivo = 0.5                                                             # simulamos una cuenta casi vacía
    with pytest.raises(ErrorPaper, match="saldo insuficiente"):
        p.comprar(70_000)


def test_precio_invalido():
    p = Paper(50_000)
    for malo in (0, -1, float("nan"), float("inf")):
        with pytest.raises(ErrorPaper):
            p.comprar(malo)
