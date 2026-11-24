"""El ciclo del agente (§15): velas cerradas validadas → variables como en el entrenamiento → pronóstico del modelo →
propuesta (regla, o LLM en el escalón 3) validada → controles deterministas de riesgo → ejecución en Paper → registro.
Un ciclo por vela: si la vela ya se procesó (también tras un reinicio) no se vuelve a ejecutar nada.

Precio de ejecución: el cierre de la última vela cerrada. En MEXC la vela diaria siguiente abre exactamente en ese
precio (BTC cotiza 24/7; comprobado en el Avance 4 en el 100 % de los días de VA), así que es la "apertura de t+1" del §9.
Valoración del patrimonio: ese mismo cierre."""
import threading
import time
from typing import Callable, Literal

from pydantic import BaseModel, Field, ValidationError

from .config import Config
from .mexc import ErrorDatos, Vela
from .modelo import Modelo
from .paper import ErrorPaper, Paper
from .registro import Registro
from .riesgo import Situacion, Veredicto, evaluar
from .variables import variables


class Propuesta(BaseModel):
    """Lo que la regla o el LLM proponen. Esquema cerrado: cualquier otra cosa se rechaza."""
    accion: Literal["comprar", "mantener", "vender"]
    simbolo: str = Field(min_length=3, max_length=20)
    fecha_vela: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    justificacion: str = Field(min_length=3, max_length=400)
    fuente: str = "regla"


class Agente:
    def __init__(self, cfg: Config, modelo: Modelo, registro: Registro, obtener_velas: Callable[[], list[Vela]],
                 proponer: Callable[[dict], Propuesta] | None = None, reloj: Callable[[], float] | None = None):
        self.cfg, self.modelo, self.reg, self.obtener_velas = cfg, modelo, registro, obtener_velas
        self.proponer, self.reloj = proponer, (reloj or time.time)
        self.paper = Paper(cfg.capital_inicial, cfg.costo, cfg.precision_cantidad, 2, cfg.nominal_minimo, cuenta=registro.cuenta())
        self.cerrojo = threading.Lock()
        self.ultimo_precio: float | None = (registro.ultimo_ciclo() or {}).get("cierre")
        registro.evento("arranque", f"backend arriba; cuenta restaurada de SQLite (modo {registro.modo()}, {registro.conteos()['ciclos']} ciclos previos)")

    # ---- control humano ----
    def iniciar(self) -> dict:
        self.reg.cambiar_modo("activo", "iniciar: el ciclo corre solo cuando cierra una vela")
        return self.estado()

    def pausar(self) -> dict:
        self.reg.cambiar_modo("pausado", "pausar: se conserva la posición; no se procesan velas nuevas")
        return self.estado()

    def detener(self) -> dict:
        self.reg.cambiar_modo("detenido", "detener: botón de detención; el ciclo no corre hasta volver a iniciar")
        return self.estado()

    def liquidar(self) -> dict:
        """Vende toda la posición al último cierre válido de MEXC. Es una orden humana, no del ciclo."""
        with self.cerrojo:
            velas = self.obtener_velas()
            precio = velas[-1].close
            self.ultimo_precio = precio
            if not self.paper.invertido:
                self.reg.evento("liquidar", "sin posición: nada que liquidar")
                return {"liquidado": False, "motivo": "sin posición", **self.estado()}
            orden = self.paper.vender(precio)
            self.reg.guardar_orden(velas[-1].fecha, orden.__dict__, "liquidar", self.paper.cuenta)
            self.reg.evento("liquidar", f"posición vendida a {precio:,.2f}: {orden.cantidad} BTC → {orden.efectivo_despues:,.2f} USDT")
            return {"liquidado": True, "orden": orden.__dict__, **self.estado()}

    # ---- propuesta ----
    def regla(self, estimado: float, fecha_vela: str, invertido: bool) -> Propuesta:
        if estimado > self.cfg.umbral:
            accion, texto = ("mantener" if invertido else "comprar"), f"estimado {100 * estimado:+.3f} % > umbral {100 * self.cfg.umbral:.2f} %"
        else:
            accion, texto = ("vender" if invertido else "mantener"), f"estimado {100 * estimado:+.3f} % ≤ umbral {100 * self.cfg.umbral:.2f} %: efectivo"
        return Propuesta(accion=accion, simbolo=self.cfg.simbolo, fecha_vela=fecha_vela, justificacion=f"regla del Avance 5: {texto}", fuente="regla")

    def _propuesta(self, contexto: dict, respaldo: Propuesta) -> Propuesta:
        if self.proponer is None:
            return respaldo
        try:
            p = self.proponer(contexto)
            if not isinstance(p, Propuesta):
                p = Propuesta.model_validate(p)
            if p.simbolo != self.cfg.simbolo or p.fecha_vela != contexto["fecha_vela"]:
                raise ValueError(f"la propuesta no corresponde a {self.cfg.simbolo} {contexto['fecha_vela']}: {p.simbolo} {p.fecha_vela}")
            return p
        except (ValidationError, ValueError, TypeError) as e:
            self.reg.error("propuesta_invalida", f"{type(e).__name__}: {e}", contexto["fecha_vela"])
        except Exception as e:  # LLM caído, tiempo agotado…
            self.reg.error("llm", f"{type(e).__name__}: {e}", contexto["fecha_vela"])
        return Propuesta(**{**respaldo.model_dump(), "fuente": "regla (respaldo)", "justificacion": "LLM sin respuesta válida; " + respaldo.justificacion})

    # ---- el ciclo ----
    def ciclo(self, forzar: bool = False, velas: list[Vela] | None = None) -> dict:
        with self.cerrojo:
            modo = self.reg.modo()
            if modo != "activo" and not forzar:
                return {"omitido": True, "motivo": f"agente {modo}: no se procesan velas", "modo": modo}
            t0 = time.perf_counter()
            try:
                velas = velas or self.obtener_velas()
            except ErrorDatos as e:
                self.reg.error("datos", str(e))
                raise
            ultima = velas[-1]
            previo = self.reg.ciclo_existe(ultima.fecha)
            if previo:
                return {"duplicado": True, "motivo": f"la vela {ultima.fecha} ya se procesó; no se repite", "ciclo": previo}
            vars_ = variables([v.close for v in velas])
            estimado = self.modelo.estimar(vars_)
            precio = ultima.close
            self.ultimo_precio = precio
            contexto = {"activo": self.cfg.simbolo, "fecha_vela": ultima.fecha, "cierre": precio, "estimado": estimado, "umbral": self.cfg.umbral,
                        "variables": vars_, "invertido": self.paper.invertido, "efectivo": self.paper.cuenta.efectivo, "unidades": self.paper.cuenta.unidades}
            propuesta = self._propuesta(contexto, self.regla(estimado, ultima.fecha, self.paper.invertido))
            anterior = self.reg.ultimo_ciclo()
            s = Situacion(propuesta.accion, self.paper.invertido, self.paper.cuenta.efectivo, self.paper.patrimonio(precio),
                          anterior["patrimonio"] if anterior else None, (self.reloj() * 1000 - ultima.cierre_ms) / 3_600_000, vars_.get("dist_sma20"))
            v: Veredicto = evaluar(s, self.cfg.max_antiguedad_h, self.cfg.perdida_diaria_max, self.cfg.exposicion_max, self.cfg.filtro_sma20, self.cfg.nominal_minimo)
            orden = None
            if v.accion in ("comprar", "vender"):
                try:
                    o = self.paper.comprar(precio, v.fraccion) if v.accion == "comprar" else self.paper.vender(precio)
                    orden = o.__dict__
                except ErrorPaper as e:
                    self.reg.error("paper", str(e), ultima.fecha)
                    v = Veredicto("mantener", f"orden rechazada por el simulador: {e}", v.bloqueos + ["paper"])
            fila = {"fecha_vela": ultima.fecha, "cierre": precio, "vela_cerrada_utc": ultima.cerrada_utc, "estimado": estimado, "variables": vars_,
                    "propuesta": propuesta.accion, "fuente": propuesta.fuente, "justificacion": propuesta.justificacion,
                    "accion": v.accion, "motivo": v.motivo, "bloqueos": v.bloqueos,
                    "precio_ejecucion": orden["precio"] if orden else None, "cantidad": orden["cantidad"] if orden else None, "costo": orden["costo"] if orden else None,
                    "efectivo": self.paper.cuenta.efectivo, "unidades": self.paper.cuenta.unidades, "patrimonio": self.paper.patrimonio(precio),
                    "latencia_ms": round(1000 * (time.perf_counter() - t0), 1), "modelo": self.modelo.version, "llm": self.cfg.llm_modelo or None}
            if not self.reg.guardar_ciclo(fila, orden, self.paper.cuenta):
                return {"duplicado": True, "motivo": f"la vela {ultima.fecha} ya se procesó (carrera); no se repite", "ciclo": self.reg.ciclo_existe(ultima.fecha)}
            return {"duplicado": False, "omitido": False, "ciclo": fila, "orden": orden}

    # ---- lectura ----
    def estado(self) -> dict:
        precio = self.ultimo_precio or self.cfg.capital_inicial and None
        cuenta = self.paper.resumen(precio) if precio else {**self.paper.cuenta.__dict__, "patrimonio": self.paper.cuenta.efectivo, "exposicion": 0.0,
                                                               "precio_valoracion": None, "rendimiento_neto_%": 100 * (self.paper.cuenta.efectivo / self.cfg.capital_inicial - 1),
                                                               "capital_inicial": self.cfg.capital_inicial, "win_rate_%": None}
        return {"modo": self.reg.modo(), "cuenta": cuenta, "ultimo_ciclo": self.reg.ultimo_ciclo(), "conteos": self.reg.conteos(),
                "limites": {"exposicion_max": self.cfg.exposicion_max, "perdida_diaria_max": self.cfg.perdida_diaria_max, "max_antiguedad_h": self.cfg.max_antiguedad_h,
                            "filtro_sma20": self.cfg.filtro_sma20, "umbral": self.cfg.umbral, "costo": self.cfg.costo, "nominal_minimo": self.cfg.nominal_minimo},
                "revision_s": self.cfg.revision_s}


class Programador:
    """Hilo que, mientras el agente está activo, llama a ciclo() cada revision_s. El ciclo mismo decide si hay vela nueva."""

    def __init__(self, agente: Agente, revision_s: int):
        self.agente, self.revision_s, self._parar = agente, revision_s, threading.Event()
        self.hilo = threading.Thread(target=self._correr, name="programador", daemon=True)
        self.ultimo: dict | None = None

    def iniciar(self):
        self.hilo.start()

    def parar(self):
        self._parar.set()

    def _correr(self):
        while not self._parar.wait(self.revision_s):
            try:
                self.ultimo = self.agente.ciclo()
            except ErrorDatos:
                pass                                       # ya quedó en la tabla de errores; se reintenta en la siguiente revisión
            except Exception as e:                         # nunca tumbar el hilo
                self.agente.reg.error("programador", f"{type(e).__name__}: {e}")
