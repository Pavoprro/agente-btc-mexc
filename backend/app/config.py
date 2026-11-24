"""Configuración del backend. Todo sale de variables de entorno (o de un archivo .env en backend/, que NO se sube al repo).
Los límites de riesgo viven aquí y solo aquí: el LLM nunca los ve ni los cambia, y el panel solo los muestra."""
import os
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

AQUI = os.path.dirname(os.path.abspath(__file__))


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=os.path.join(AQUI, "..", ".env"), env_file_encoding="utf-8", extra="ignore")

    # Acceso a la API privada (obligatoria; sin clave el backend no arranca)
    api_key: str = Field(min_length=16, description="Clave secreta que la UI manda en la cabecera X-API-Key")

    # Mercado (datos públicos de MEXC; no hay clave de trading ni ruta de órdenes reales)
    simbolo: str = "BTCUSDT"
    intervalo: str = "1d"
    mexc_url: str = "https://api.mexc.com/api/v3/klines"
    velas_a_pedir: int = 60                   # más que los 21 cierres que necesita el modelo, por si hay huecos
    max_antiguedad_h: float = 36.0            # una vela diaria cerrada no puede tener más de esto (24 h + margen)
    reintentos: int = 3
    espera_base_s: float = 0.5                # 0.5 s, 1 s, 2 s (espera creciente)

    # Modelo y regla de señal (Avance 5: versión final B = 20 rezagos + dist_sma20 + vol20; estrategia C con δ = 0.10 %)
    modelo_version: str = "v2"
    umbral: float = 0.001                     # comprar si el estimado > 0.10 % (elegido con VA en el Avance 5)

    # Paper y riesgo (§15): definidos ANTES de la prueba, no los toca el LLM
    capital_inicial: float = 50_000.0
    costo: float = 0.0                        # 0.0 % por compra o venta (§15); la práctica usaba 0.10 %
    exposicion_max: float = 1.0               # fracción máxima del efectivo que entra en una compra
    perdida_diaria_max: float = 0.05          # 5 %: si el patrimonio cae más que esto en un día, se bloquean compras nuevas
    filtro_sma20: bool = True                 # estrategia D del Avance 5: comprar solo con el cierre por encima de su SMA20
    precision_cantidad: int = 6               # BTCUSDT spot en MEXC: 6 decimales de cantidad
    nominal_minimo: float = 1.0               # 1 USDT por orden
    ruta_db: str = os.path.join(AQUI, "..", "datos", "agente.db")

    # Ciclo programado: cada cuánto revisa si ya cerró una vela nueva (segundos). La vela es diaria; la revisión, frecuente y barata.
    revision_s: int = 300

    # LLM local (Ollama). Vacío = decide solo la regla (sirve para la comparación sin LLM del §16)
    ollama_url: str = "http://127.0.0.1:11434"
    llm_modelo: str = ""
    llm_timeout_s: float = 60.0


@lru_cache
def config() -> Config:
    return Config()
