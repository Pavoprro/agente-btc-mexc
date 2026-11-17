"""El contrato de variables y el modelo reproducen EXACTAMENTE la práctica (Avances 1–3)."""
import numpy as np

from app.variables import LAGS, rezagos


def test_rezagos_reproducen_las_ventanas_del_avance1(precios, ventanas):
    cierres = precios.set_index("fecha").close
    muestra = ventanas.sample(200, random_state=42)
    for _, fila in muestra.iterrows():
        hasta = cierres.loc[:fila.fecha_emision]
        if len(hasta) < 21:
            continue
        rez = rezagos(hasta.tail(21).to_numpy())
        assert np.allclose([rez[k] for k in LAGS], fila[LAGS].to_numpy(dtype=float), atol=1e-12), f"difiere en {fila.fecha_emision.date()}"


def test_modelo_reproduce_rmse_de_va(modelo, ventanas):
    va = ventanas[ventanas.conjunto == "VA"]
    est = np.array([modelo.estimar(dict(zip(LAGS, fila))) for fila in va[LAGS].to_numpy()])
    rmse = float(np.sqrt(np.mean((est - va.y.to_numpy()) ** 2)))
    assert abs(rmse - 0.024277) < 1e-5, rmse
    assert abs(rmse - modelo.ficha["metricas"]["RMSE_VA"]) < 1e-9


def test_el_modelo_no_toca_te(modelo, ventanas):
    te = ventanas[ventanas.conjunto == "TE"]
    assert str(te.fecha_objetivo.min().date()) > modelo.ficha["entrenamiento"]["ultima_fecha_objetivo"]


def test_rezagos_exigen_21_cierres():
    import pytest
    with pytest.raises(ValueError):
        rezagos(list(range(1, 21)))
