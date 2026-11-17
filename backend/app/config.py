"""Configuración del backend. Todo sale de variables de entorno (o de un archivo .env en backend/, que NO se sube al repo).
Los límites de riesgo viven aquí y solo aquí: el LLM nunca los ve ni los cambia."""
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

    # Modelo
    modelo_version: str = "v1"
    umbral: float = 0.0005                    # regla del Avance 3: comprar si el estimado > 0.05 %

    # Paper y riesgo (§15): definidos ANTES de la prueba, no los toca el LLM
    capital_inicial: float = 50_000.0
    costo: float = 0.0                        # 0.0 % por compra o venta (§15); la práctica usaba 0.10 %
    exposicion_max: float = 1.0               # fracción máxima del patrimonio en BTC
    perdida_diaria_max: float = 0.05          # 5 %: si un día cae más, se bloquean órdenes nuevas
    ruta_db: str = os.path.join(AQUI, "..", "datos", "agente.db")

    # LLM local (Ollama). Vacío = decide solo la regla del Avance 3 (sirve para la comparación sin LLM del §16)
    ollama_url: str = "http://127.0.0.1:11434"
    llm_modelo: str = ""
    llm_timeout_s: float = 60.0


@lru_cache
def config() -> Config:
    return Config()
