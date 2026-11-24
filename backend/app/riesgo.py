"""Controles deterministas de riesgo (§15 paso 5). Reciben una propuesta (de la regla o del LLM) y el estado de la cuenta y
devuelven la acción FINAL con su motivo. La propuesta nunca sustituye estas reglas; los límites salen de config.py y de nada más.

Reglas, en este orden:
 1. Dato atrasado (más de max_antiguedad_h desde el cierre de la vela): no se opera. Acción final: mantener.
 2. Acción imposible: comprar con posición abierta o vender sin posición → mantener (no se intenta nada).
 3. Pérdida diaria: si el patrimonio cayó más de perdida_diaria_max frente al patrimonio del ciclo anterior, se bloquean compras
    nuevas ese día (vender sigue permitido).
 4. Filtro de tendencia del Avance 5 (estrategia D): comprar solo si el cierre está por encima de su SMA20 (dist_sma20 > 0).
    Es una regla del motor de riesgo, no del modelo ni del LLM.
 5. Exposición: una compra usa como máximo exposicion_max del efectivo.
 6. Saldo: si el efectivo no cubre el nominal mínimo del par, la compra se bloquea (el Paper lo volvería a rechazar)."""
from dataclasses import dataclass, field

ACCIONES = ("comprar", "mantener", "vender")


@dataclass(frozen=True)
class Situacion:
    propuesta: str
    invertido: bool
    efectivo: float
    patrimonio: float
    patrimonio_anterior: float | None      # del ciclo anterior (None si es el primero)
    antiguedad_h: float                    # horas desde el cierre de la vela hasta ahora
    dist_sma20: float | None               # None = no disponible


@dataclass
class Veredicto:
    accion: str
    motivo: str
    bloqueos: list[str] = field(default_factory=list)
    fraccion: float = 1.0                  # fracción del efectivo que puede usar una compra

    @property
    def cambio(self) -> bool:
        return self.accion != "mantener"


def evaluar(s: Situacion, max_antiguedad_h: float, perdida_diaria_max: float, exposicion_max: float, filtro_sma20: bool,
            nominal_minimo: float = 1.0) -> Veredicto:
    if s.propuesta not in ACCIONES:
        return Veredicto("mantener", f"propuesta desconocida {s.propuesta!r}: se mantiene", ["propuesta_invalida"])
    bloqueos: list[str] = []
    if s.antiguedad_h > max_antiguedad_h:
        return Veredicto("mantener", f"dato atrasado ({s.antiguedad_h:.1f} h > {max_antiguedad_h:.0f} h): no se opera", ["dato_atrasado"])
    accion = s.propuesta
    if accion == "comprar" and s.invertido:
        return Veredicto("mantener", "ya hay posición abierta: comprar se traduce en mantener (sin apalancamiento)", ["ya_invertido"])
    if accion == "vender" and not s.invertido:
        return Veredicto("mantener", "no hay posición: vender se traduce en permanecer en efectivo (sin cortos)", ["sin_posicion"])
    if accion == "comprar":
        if s.patrimonio_anterior and s.patrimonio < s.patrimonio_anterior * (1 - perdida_diaria_max):
            caida = 100 * (1 - s.patrimonio / s.patrimonio_anterior)
            return Veredicto("mantener", f"pérdida diaria de {caida:.2f} % supera el límite de {100 * perdida_diaria_max:.0f} %: compras bloqueadas hoy", ["perdida_diaria"])
        if filtro_sma20 and (s.dist_sma20 is None or s.dist_sma20 <= 0):
            return Veredicto("mantener", "cierre por debajo de la SMA20 (filtro del Avance 5): no se compra" if s.dist_sma20 is not None else "sin SMA20 disponible: no se compra",
                             ["filtro_sma20"])
        if s.efectivo * exposicion_max < nominal_minimo:
            return Veredicto("mantener", f"saldo insuficiente: {s.efectivo:,.2f} USDT no cubre el nominal mínimo de {nominal_minimo} USDT", ["saldo_insuficiente"])
        return Veredicto("comprar", f"compra permitida con hasta {100 * exposicion_max:.0f} % del efectivo", bloqueos, exposicion_max)
    if accion == "vender":
        return Veredicto("vender", "venta permitida: se cierra toda la posición", bloqueos)
    return Veredicto("mantener", "se mantiene la posición" if s.invertido else "se permanece en efectivo", bloqueos)
