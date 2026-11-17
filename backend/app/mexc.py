"""Velas diarias públicas de MEXC (GET /api/v3/klines, sin cuenta ni clave) con validación.
Nunca hay ruta de órdenes: este módulo solo LEE."""
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

DIA_MS = 86_400_000


class ErrorDatos(Exception):
    """Dato inválido o no disponible: el agente NO decide con esto."""


@dataclass(frozen=True)
class Vela:
    apertura_ms: int
    open: float
    high: float
    low: float
    close: float
    volumen: float
    cierre_ms: int

    @property
    def fecha(self) -> str:
        return datetime.fromtimestamp(self.apertura_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


def _parsear(fila) -> Vela:
    # MEXC v3: [open_time, open, high, low, close, volume, close_time, quote_volume]
    if not isinstance(fila, (list, tuple)) or len(fila) < 7:
        raise ErrorDatos(f"vela con formato inesperado: {fila!r}")
    try:
        v = Vela(int(fila[0]), float(fila[1]), float(fila[2]), float(fila[3]), float(fila[4]), float(fila[5]), int(fila[6]))
    except (TypeError, ValueError) as e:
        raise ErrorDatos(f"vela con valores no numéricos: {fila!r} ({e})")
    return v


def descargar(url: str, simbolo: str, intervalo: str, limite: int, reintentos: int = 3, espera_base_s: float = 0.5,
              cliente: httpx.Client | None = None) -> list:
    """Pide las últimas `limite` velas. Reintenta ante caídas, 429 o 5xx con espera creciente (0.5, 1, 2 s).
    Si agota los intentos levanta ErrorDatos: el ciclo se pausa, no se inventa nada."""
    propio = cliente is None
    cliente = cliente or httpx.Client(timeout=10.0)
    ultimo = None
    try:
        for intento in range(reintentos):
            try:
                r = cliente.get(url, params={"symbol": simbolo, "interval": intervalo, "limit": limite})
                if r.status_code == 429 or r.status_code >= 500:
                    ultimo = f"MEXC respondió {r.status_code}"
                else:
                    r.raise_for_status()
                    cuerpo = r.json()
                    if not isinstance(cuerpo, list):
                        raise ErrorDatos(f"MEXC devolvió algo que no es una lista de velas: {str(cuerpo)[:200]}")
                    return cuerpo
            except httpx.HTTPError as e:
                ultimo = f"{type(e).__name__}: {e}"
            if intento < reintentos - 1:
                time.sleep(espera_base_s * (2 ** intento))
        raise ErrorDatos(f"MEXC sin respuesta válida tras {reintentos} intentos ({ultimo})")
    finally:
        if propio:
            cliente.close()


def validar(crudo: list, simbolo: str, intervalo: str, ahora_ms: int, max_antiguedad_h: float, minimo: int = 21) -> list[Vela]:
    """Convierte y valida (§15 paso 1): descarta la vela aún abierta, exige orden, continuidad diaria, precios coherentes
    y que la última vela cerrada no esté atrasada. Devuelve solo velas CERRADAS, en orden."""
    if intervalo != "1d":
        raise ErrorDatos(f"este agente trabaja con velas diarias, no {intervalo}")
    if not simbolo.isalnum():
        raise ErrorDatos(f"símbolo inválido: {simbolo!r}")
    velas = [_parsear(f) for f in crudo]
    cerradas = [v for v in velas if v.cierre_ms <= ahora_ms]
    if len(cerradas) < minimo:
        raise ErrorDatos(f"solo hay {len(cerradas)} velas cerradas; el modelo necesita {minimo} cierres consecutivos")
    for a, b in zip(cerradas, cerradas[1:]):
        if b.apertura_ms <= a.apertura_ms:
            raise ErrorDatos(f"velas en desorden o repetidas en {a.fecha} → {b.fecha}")
        if b.apertura_ms - a.apertura_ms != DIA_MS:
            raise ErrorDatos(f"hueco en la serie entre {a.fecha} y {b.fecha}: no se pronostica con una ventana rota")
    for v in cerradas:
        if not (0 < v.low <= min(v.open, v.close) <= max(v.open, v.close) <= v.high) or v.volumen < 0:
            raise ErrorDatos(f"precios imposibles en la vela {v.fecha}: O {v.open} H {v.high} L {v.low} C {v.close}")
        if v.cierre_ms - v.apertura_ms != DIA_MS - 1 and v.cierre_ms - v.apertura_ms != DIA_MS:
            raise ErrorDatos(f"la vela {v.fecha} no dura un día")
    ultima = cerradas[-1]
    antiguedad_h = (ahora_ms - ultima.cierre_ms) / 3_600_000
    if antiguedad_h > max_antiguedad_h:
        raise ErrorDatos(f"dato atrasado: la última vela cerrada ({ultima.fecha}) tiene {antiguedad_h:.1f} h; el máximo es {max_antiguedad_h:.0f} h")
    return cerradas


def velas_cerradas(cfg, cliente: httpx.Client | None = None, ahora_ms: int | None = None) -> list[Vela]:
    ahora_ms = ahora_ms if ahora_ms is not None else int(time.time() * 1000)
    crudo = descargar(cfg.mexc_url, cfg.simbolo, cfg.intervalo, cfg.velas_a_pedir, cfg.reintentos, cfg.espera_base_s, cliente)
    return validar(crudo, cfg.simbolo, cfg.intervalo, ahora_ms, cfg.max_antiguedad_h)
