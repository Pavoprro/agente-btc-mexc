"""El contrato de variables y los modelos reproducen EXACTAMENTE la práctica (Avances 1–3 para v1, Avance 5 para v2)."""
import numpy as np
import pytest

from app.variables import INDICADORES, LAGS, indicadores, rezagos, variables


def test_rezagos_reproducen_las_ventanas_del_avance1(precios, ventanas):
    cierres = precios.set_index("fecha").close
    muestra = ventanas.sample(200, random_state=42)
    for _, fila in muestra.iterrows():
        hasta = cierres.loc[:fila.fecha_emision]
        if len(hasta) < 21:
            continue
        rez = rezagos(hasta.tail(21).to_numpy())
        assert np.allclose([rez[k] for k in LAGS], fila[LAGS].to_numpy(dtype=float), atol=1e-12), f"difiere en {fila.fecha_emision.date()}"


def test_indicadores_con_la_definicion_del_avance5(precios):
    """dist_sma20 = cierre / media de 20 cierres − 1; vol20 = desviación muestral de 20 rendimientos. Solo historia hasta t."""
    cierres = precios.set_index("fecha").close
    for fin in (100, 1000, 2500, len(cierres) - 1):
        hasta = cierres.iloc[: fin + 1]
        ind = indicadores(hasta.tail(21).to_numpy())
        esperado_d = hasta.iloc[-1] / hasta.iloc[-20:].mean() - 1
        esperado_v = (hasta / hasta.shift(1) - 1).iloc[-20:].std(ddof=1)
        assert abs(ind["dist_sma20"] - esperado_d) < 1e-12 and abs(ind["vol20"] - esperado_v) < 1e-12
        assert indicadores(hasta.tail(60).to_numpy()) == ind          # con más historia da lo mismo: solo usa los últimos 21
    v = variables(cierres.tail(21).to_numpy())
    assert list(v) == LAGS + INDICADORES


def _con_indicadores(precios, ventanas):
    c = precios.set_index("fecha").close
    sma = c.rolling(20).mean()
    r = c / c.shift(1) - 1
    d = ventanas.copy()
    d["dist_sma20"] = (c / sma - 1).reindex(d.fecha_emision).to_numpy()
    d["vol20"] = r.rolling(20).std(ddof=1).reindex(d.fecha_emision).to_numpy()
    return d


def test_modelo_v2_reproduce_rmse_de_va_del_avance5(modelo, precios, ventanas):
    va = _con_indicadores(precios, ventanas)
    va = va[va.conjunto == "VA"]
    est = np.array([modelo.estimar(dict(zip(modelo.entradas, fila))) for fila in va[modelo.entradas].to_numpy()])
    rmse = float(np.sqrt(np.mean((est - va.y.to_numpy()) ** 2)))
    assert abs(rmse - 0.024243) < 1e-5, rmse
    assert abs(rmse - modelo.ficha["metricas"]["RMSE_VA"]) < 1e-9
    assert modelo.entradas == LAGS + INDICADORES and modelo.version == "v2"


def test_modelo_v1_reproduce_rmse_de_va_del_avance1(modelo_v1, ventanas):
    va = ventanas[ventanas.conjunto == "VA"]
    est = np.array([modelo_v1.estimar(dict(zip(LAGS, fila))) for fila in va[LAGS].to_numpy()])
    rmse = float(np.sqrt(np.mean((est - va.y.to_numpy()) ** 2)))
    assert abs(rmse - 0.024277) < 1e-5, rmse


def test_los_modelos_no_tocan_te(modelo, modelo_v1, ventanas):
    te = ventanas[ventanas.conjunto == "TE"]
    for m in (modelo, modelo_v1):
        assert str(te.fecha_objetivo.min().date()) > m.ficha["entrenamiento"]["ultima_fecha_objetivo"]


def test_variables_exigen_21_cierres():
    with pytest.raises(ValueError):
        rezagos(list(range(1, 21)))
    with pytest.raises(ValueError):
        indicadores(list(range(1, 21)))


def test_el_modelo_rechaza_variables_incompletas(modelo):
    with pytest.raises(ValueError):
        modelo.estimar({k: 0.0 for k in LAGS})             # faltan los indicadores
