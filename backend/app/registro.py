"""Persistencia en SQLite (§15 paso 6 y 7): estado de la cuenta y del agente, un renglón por vela procesada (clave única →
no se procesa dos veces la misma vela, ni tras un reinicio), órdenes Paper, patrimonio diario, errores y eventos de control.
Todo lo que el panel muestra sale de aquí."""
import json, os, sqlite3
from datetime import datetime, timezone

from .paper import Cuenta

ESQUEMA = """
CREATE TABLE IF NOT EXISTS estado (
  id INTEGER PRIMARY KEY CHECK (id = 1), modo TEXT NOT NULL, capital_inicial REAL NOT NULL, efectivo REAL NOT NULL, unidades REAL NOT NULL,
  costos_acum REAL NOT NULL, compra_base REAL NOT NULL, operaciones_cerradas INTEGER NOT NULL, operaciones_ganadoras INTEGER NOT NULL,
  ultima_vela TEXT, actualizado_utc TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ciclos (
  fecha_vela TEXT PRIMARY KEY, cierre REAL NOT NULL, vela_cerrada_utc TEXT NOT NULL, estimado REAL NOT NULL, variables TEXT NOT NULL,
  propuesta TEXT NOT NULL, fuente TEXT NOT NULL, justificacion TEXT NOT NULL, accion TEXT NOT NULL, motivo TEXT NOT NULL, bloqueos TEXT NOT NULL,
  precio_ejecucion REAL, cantidad REAL, costo REAL, efectivo REAL NOT NULL, unidades REAL NOT NULL, patrimonio REAL NOT NULL,
  latencia_ms REAL NOT NULL, modelo TEXT NOT NULL, llm TEXT, creado_utc TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ordenes (
  id INTEGER PRIMARY KEY AUTOINCREMENT, fecha_vela TEXT NOT NULL, lado TEXT NOT NULL, precio REAL NOT NULL, cantidad REAL NOT NULL,
  monto REAL NOT NULL, costo REAL NOT NULL, ganancia_operacion REAL, origen TEXT NOT NULL, creado_utc TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS errores (
  id INTEGER PRIMARY KEY AUTOINCREMENT, creado_utc TEXT NOT NULL, fecha_vela TEXT, tipo TEXT NOT NULL, detalle TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS eventos (
  id INTEGER PRIMARY KEY AUTOINCREMENT, creado_utc TEXT NOT NULL, tipo TEXT NOT NULL, detalle TEXT NOT NULL);
"""
MODOS = ("detenido", "activo", "pausado")


def ahora_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Registro:
    def __init__(self, ruta: str, capital_inicial: float):
        if ruta != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(ruta)), exist_ok=True)
        self.con = sqlite3.connect(ruta, check_same_thread=False)
        self.con.row_factory = sqlite3.Row
        self.con.executescript(ESQUEMA)
        if self.con.execute("SELECT 1 FROM estado WHERE id = 1").fetchone() is None:
            self.con.execute("INSERT INTO estado VALUES (1, 'detenido', ?, ?, 0, 0, 0, 0, 0, NULL, ?)", (capital_inicial, capital_inicial, ahora_utc()))
            self.con.commit()

    # ---- estado del agente y de la cuenta ----
    def estado(self) -> dict:
        return dict(self.con.execute("SELECT * FROM estado WHERE id = 1").fetchone())

    def cuenta(self) -> Cuenta:
        e = self.estado()
        return Cuenta(e["efectivo"], e["unidades"], e["costos_acum"], e["compra_base"], e["operaciones_cerradas"], e["operaciones_ganadoras"])

    def guardar_cuenta(self, c: Cuenta, ultima_vela: str | None = None):
        self.con.execute("UPDATE estado SET efectivo=?, unidades=?, costos_acum=?, compra_base=?, operaciones_cerradas=?, operaciones_ganadoras=?, "
                         "ultima_vela=COALESCE(?, ultima_vela), actualizado_utc=? WHERE id = 1",
                         (c.efectivo, c.unidades, c.costos_acum, c.compra_base, c.operaciones_cerradas, c.operaciones_ganadoras, ultima_vela, ahora_utc()))
        self.con.commit()

    def modo(self) -> str:
        return self.estado()["modo"]

    def cambiar_modo(self, modo: str, detalle: str = ""):
        if modo not in MODOS:
            raise ValueError(f"modo desconocido: {modo}")
        self.con.execute("UPDATE estado SET modo=?, actualizado_utc=? WHERE id = 1", (modo, ahora_utc()))
        self.evento(modo, detalle)

    def evento(self, tipo: str, detalle: str = ""):
        self.con.execute("INSERT INTO eventos (creado_utc, tipo, detalle) VALUES (?, ?, ?)", (ahora_utc(), tipo, detalle))
        self.con.commit()

    def error(self, tipo: str, detalle: str, fecha_vela: str | None = None):
        self.con.execute("INSERT INTO errores (creado_utc, fecha_vela, tipo, detalle) VALUES (?, ?, ?, ?)", (ahora_utc(), fecha_vela, tipo, detalle[:2000]))
        self.con.commit()

    # ---- ciclos (idempotentes por vela) ----
    def ciclo_existe(self, fecha_vela: str) -> dict | None:
        fila = self.con.execute("SELECT * FROM ciclos WHERE fecha_vela = ?", (fecha_vela,)).fetchone()
        return self._ciclo(fila) if fila else None

    def guardar_ciclo(self, c: dict, orden: dict | None, cuenta: Cuenta):
        """Una transacción: ciclo + orden (si hubo) + cuenta. Si la vela ya existe, no escribe nada y devuelve False."""
        try:
            with self.con:
                self.con.execute(
                    "INSERT INTO ciclos VALUES (:fecha_vela, :cierre, :vela_cerrada_utc, :estimado, :variables, :propuesta, :fuente, :justificacion, :accion, :motivo, "
                    ":bloqueos, :precio_ejecucion, :cantidad, :costo, :efectivo, :unidades, :patrimonio, :latencia_ms, :modelo, :llm, :creado_utc)",
                    {**c, "variables": json.dumps(c["variables"]), "bloqueos": json.dumps(c["bloqueos"]), "creado_utc": ahora_utc()})
                if orden:
                    self.con.execute("INSERT INTO ordenes (fecha_vela, lado, precio, cantidad, monto, costo, ganancia_operacion, origen, creado_utc) VALUES (?,?,?,?,?,?,?,?,?)",
                                     (c["fecha_vela"], orden["lado"], orden["precio"], orden["cantidad"], orden["monto"], orden["costo"], orden.get("ganancia_operacion"), "ciclo", ahora_utc()))
                self.con.execute("UPDATE estado SET efectivo=?, unidades=?, costos_acum=?, compra_base=?, operaciones_cerradas=?, operaciones_ganadoras=?, ultima_vela=?, actualizado_utc=? WHERE id = 1",
                                 (cuenta.efectivo, cuenta.unidades, cuenta.costos_acum, cuenta.compra_base, cuenta.operaciones_cerradas, cuenta.operaciones_ganadoras, c["fecha_vela"], ahora_utc()))
            return True
        except sqlite3.IntegrityError:
            return False

    def guardar_orden(self, fecha_vela: str, orden: dict, origen: str, cuenta: Cuenta):
        with self.con:
            self.con.execute("INSERT INTO ordenes (fecha_vela, lado, precio, cantidad, monto, costo, ganancia_operacion, origen, creado_utc) VALUES (?,?,?,?,?,?,?,?,?)",
                             (fecha_vela, orden["lado"], orden["precio"], orden["cantidad"], orden["monto"], orden["costo"], orden.get("ganancia_operacion"), origen, ahora_utc()))
            self.con.execute("UPDATE estado SET efectivo=?, unidades=?, costos_acum=?, compra_base=?, operaciones_cerradas=?, operaciones_ganadoras=?, actualizado_utc=? WHERE id = 1",
                             (cuenta.efectivo, cuenta.unidades, cuenta.costos_acum, cuenta.compra_base, cuenta.operaciones_cerradas, cuenta.operaciones_ganadoras, ahora_utc()))

    @staticmethod
    def _ciclo(fila) -> dict:
        d = dict(fila)
        d["variables"], d["bloqueos"] = json.loads(d["variables"]), json.loads(d["bloqueos"])
        return d

    def ciclos(self, n: int = 60) -> list[dict]:
        filas = self.con.execute("SELECT * FROM ciclos ORDER BY fecha_vela DESC LIMIT ?", (n,)).fetchall()
        return [self._ciclo(f) for f in reversed(filas)]

    def ultimo_ciclo(self) -> dict | None:
        fila = self.con.execute("SELECT * FROM ciclos ORDER BY fecha_vela DESC LIMIT 1").fetchone()
        return self._ciclo(fila) if fila else None

    def ordenes(self, n: int = 100) -> list[dict]:
        return [dict(f) for f in self.con.execute("SELECT * FROM ordenes ORDER BY id DESC LIMIT ?", (n,)).fetchall()][::-1]

    def errores(self, n: int = 50) -> list[dict]:
        return [dict(f) for f in self.con.execute("SELECT * FROM errores ORDER BY id DESC LIMIT ?", (n,)).fetchall()][::-1]

    def eventos(self, n: int = 50) -> list[dict]:
        return [dict(f) for f in self.con.execute("SELECT * FROM eventos ORDER BY id DESC LIMIT ?", (n,)).fetchall()][::-1]

    def conteos(self) -> dict:
        q = lambda t: self.con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        return {"ciclos": q("ciclos"), "ordenes": q("ordenes"), "errores": q("errores"), "eventos": q("eventos")}

    def cerrar(self):
        self.con.close()
