"""Motor Paper: simulador propio con saldo, posición, costo y precisión del par. Es el ÚNICO sitio donde se "ejecuta" algo,
y solo mueve números en memoria (el registro los guarda en SQLite). No existe ninguna ruta hacia MEXC desde aquí.

Convenciones (§15): 50,000 USDT iniciales, costo 0.0 % por operación, sin apalancamiento ni ventas en corto.
Precisión del par BTCUSDT en MEXC spot: cantidad con 6 decimales (se redondea hacia ABAJO, nunca se compra de más),
precio con 2 decimales, nominal mínimo 1 USDT. Si el efectivo no alcanza para el nominal mínimo, la orden se rechaza
con ErrorPaper("saldo insuficiente")."""
import math
from dataclasses import asdict, dataclass


class ErrorPaper(Exception):
    """La orden no se puede ejecutar en el simulador (saldo insuficiente, sin posición, precio inválido…)."""


@dataclass
class Cuenta:
    efectivo: float
    unidades: float = 0.0
    costos_acum: float = 0.0
    compra_base: float = 0.0        # efectivo que se invirtió en la posición abierta (para la ganancia por operación)
    operaciones_cerradas: int = 0
    operaciones_ganadoras: int = 0


@dataclass(frozen=True)
class Orden:
    lado: str                       # "comprar" | "vender"
    precio: float
    cantidad: float
    monto: float                    # cantidad × precio
    costo: float
    efectivo_despues: float
    unidades_despues: float
    ganancia_operacion: float | None = None   # solo en ventas: efectivo tras vender − efectivo invertido


class Paper:
    def __init__(self, capital_inicial: float, costo: float = 0.0, precision_cantidad: int = 6, precision_precio: int = 2,
                 nominal_minimo: float = 1.0, cuenta: Cuenta | None = None):
        if capital_inicial <= 0 or not 0 <= costo < 1:
            raise ValueError("capital o costo inválidos")
        self.capital_inicial, self.costo = float(capital_inicial), float(costo)
        self.precision_cantidad, self.precision_precio, self.nominal_minimo = precision_cantidad, precision_precio, nominal_minimo
        self.cuenta = cuenta or Cuenta(efectivo=float(capital_inicial))

    # ---- lectura ----
    def patrimonio(self, precio: float) -> float:
        return self.cuenta.efectivo + self.cuenta.unidades * precio

    @property
    def invertido(self) -> bool:
        return self.cuenta.unidades > 0

    def exposicion(self, precio: float) -> float:
        p = self.patrimonio(precio)
        return (self.cuenta.unidades * precio / p) if p > 0 else 0.0

    def resumen(self, precio: float) -> dict:
        c = self.cuenta
        return {**asdict(c), "patrimonio": self.patrimonio(precio), "exposicion": self.exposicion(precio), "precio_valoracion": precio,
                "rendimiento_neto_%": 100 * (self.patrimonio(precio) / self.capital_inicial - 1), "capital_inicial": self.capital_inicial,
                "win_rate_%": (100 * c.operaciones_ganadoras / c.operaciones_cerradas) if c.operaciones_cerradas else None}

    # ---- ejecución (solo en memoria) ----
    def _precio(self, precio: float) -> float:
        if not (isinstance(precio, (int, float)) and math.isfinite(precio) and precio > 0):
            raise ErrorPaper(f"precio inválido: {precio!r}")
        return round(float(precio), self.precision_precio)

    def comprar(self, precio: float, fraccion: float = 1.0) -> Orden:
        """Compra con `fraccion` del efectivo (0 < fraccion ≤ 1), descontando el costo antes de calcular las unidades."""
        precio = self._precio(precio)
        if not 0 < fraccion <= 1:
            raise ErrorPaper(f"fracción inválida: {fraccion}")
        if self.invertido:
            raise ErrorPaper("ya hay posición abierta: no se compra de más (sin apalancamiento)")
        disponible = self.cuenta.efectivo * fraccion
        bruto = disponible / (1 + self.costo)                       # monto que se puede negociar pagando el costo con el mismo efectivo
        cantidad = math.floor(bruto / precio * 10 ** self.precision_cantidad) / 10 ** self.precision_cantidad
        monto = cantidad * precio
        if cantidad <= 0 or monto < self.nominal_minimo:
            raise ErrorPaper(f"saldo insuficiente: con {disponible:,.2f} USDT no se cubre el nominal mínimo de {self.nominal_minimo} USDT a {precio:,.2f}")
        costo = monto * self.costo
        if monto + costo > self.cuenta.efectivo + 1e-9:
            raise ErrorPaper("la orden excede el efectivo disponible")
        c = self.cuenta
        c.compra_base = monto + costo
        c.efectivo, c.unidades, c.costos_acum = c.efectivo - monto - costo, cantidad, c.costos_acum + costo
        return Orden("comprar", precio, cantidad, monto, costo, c.efectivo, c.unidades)

    def vender(self, precio: float) -> Orden:
        """Vende toda la posición. Sin posición no hay nada que vender (ni cortos)."""
        precio = self._precio(precio)
        if not self.invertido:
            raise ErrorPaper("no hay posición que vender (no se permiten ventas en corto)")
        c = self.cuenta
        cantidad, monto = c.unidades, c.unidades * precio
        costo = monto * self.costo
        neto = monto - costo
        ganancia = neto - c.compra_base
        c.efectivo, c.unidades, c.costos_acum, c.compra_base = c.efectivo + neto, 0.0, c.costos_acum + costo, 0.0
        c.operaciones_cerradas += 1
        c.operaciones_ganadoras += int(ganancia > 0)
        return Orden("vender", precio, cantidad, monto, costo, c.efectivo, c.unidades, ganancia)
