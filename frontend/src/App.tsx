import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { api, claveInicial, guardarClave, olvidarClave, ErrorApi, type Bitacora, type Estado, type Pronostico, type Salud } from './api'
import TiraDias from './components/TiraDias'

const pct = (x: number, d = 2) => `${x > 0 ? '+' : x < 0 ? '−' : ''}${Math.abs(100 * x).toFixed(d)} %`
const num = (x: number, d = 2) => x.toLocaleString('es-MX', { minimumFractionDigits: d, maximumFractionDigits: d })
const fechaLarga = (iso: string) =>
  new Date(iso + 'T00:00:00Z').toLocaleDateString('es-MX', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' })
const hora = (iso: string) => new Date(iso).toLocaleString('es-MX', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })
const MODO_TEXTO = { activo: 'Activo: revisa cada 5 minutos si cerró una vela', pausado: 'Pausado: conserva la posición, no procesa velas', detenido: 'Detenido' }
const ACCION_TEXTO = { comprar: 'Comprar', mantener: 'Mantener', vender: 'Vender' }

function explicarError(e: unknown): string {
  if (e instanceof ErrorApi && e.status === 401) return 'Clave rechazada. Es la API_KEY del archivo backend/.env.'
  if (e instanceof ErrorApi && e.status === 503) return `MEXC no dio un dato válido, así que el agente no decide: ${e.message.replace('sin dato válido: ', '')}`
  return e instanceof ErrorApi ? e.message : String(e)
}

export default function App() {
  const [salud, setSalud] = useState<Salud | null>(null)
  const [sinBackend, setSinBackend] = useState('')
  const [clave, setClave] = useState('')
  const [autenticado, setAutenticado] = useState(false)
  const [pron, setPron] = useState<Pronostico | null>(null)
  const [estado, setEstado] = useState<Estado | null>(null)
  const [bitacora, setBitacora] = useState<Bitacora | null>(null)
  const [cargando, setCargando] = useState(false)
  const [ocupado, setOcupado] = useState('')
  const [error, setError] = useState('')
  const [aviso, setAviso] = useState('')
  const [consultadoA, setConsultadoA] = useState('')
  const claveRef = useRef('')
  claveRef.current = clave

  const cargarSalud = useCallback(async () => {
    try {
      setSalud(await api.salud())
      setSinBackend('')
    } catch (e) {
      setSinBackend(explicarError(e))
    }
  }, [])

  const refrescar = useCallback(async (k: string) => {
    const [e, b] = await Promise.all([api.estado(k), api.bitacora(k, 40)])
    setEstado(e)
    setBitacora(b)
  }, [])

  const entrar = useCallback(
    async (k: string) => {
      if (!k.trim()) {
        setError('Escribe la clave de la API para entrar.')
        return
      }
      guardarClave(k)
      setCargando(true)
      setError('')
      try {
        await refrescar(k)
        setAutenticado(true)
        setPron(await api.pronostico(k))
        setConsultadoA(new Date().toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' }))
      } catch (e) {
        if (e instanceof ErrorApi && e.status === 401) {
          setAutenticado(false)
          setPron(null)
        }
        setError(explicarError(e))
      } finally {
        setCargando(false)
      }
    },
    [refrescar],
  )

  async function accion(nombre: 'iniciar' | 'pausar' | 'detener' | 'liquidar' | 'ciclo') {
    const k = claveRef.current
    if (nombre === 'liquidar' && !confirm('¿Vender toda la posición al último cierre de MEXC?')) return
    setOcupado(nombre)
    setError('')
    setAviso('')
    try {
      if (nombre === 'ciclo') {
        const r = await api.ciclo(k, true)
        if (r.omitido) setAviso(r.motivo ?? 'Ciclo omitido.')
        else if (r.duplicado) setAviso(`La vela ${r.ciclo?.fecha_vela} ya se procesó: no se repite.`)
        else if (r.ciclo) setAviso(`Vela ${r.ciclo.fecha_vela}: ${ACCION_TEXTO[r.ciclo.accion]}. ${r.ciclo.motivo}.`)
      } else if (nombre === 'liquidar') {
        const r = await api.liquidar(k)
        setAviso(r.liquidado && r.orden ? `Posición vendida: ${r.orden.cantidad} BTC a ${num(r.orden.precio)} USDT.` : `Nada que liquidar: ${r.motivo ?? 'sin posición'}.`)
      } else {
        await api[nombre](k)
      }
      await Promise.all([refrescar(k), cargarSalud()])
    } catch (e) {
      setError(explicarError(e))
    } finally {
      setOcupado('')
    }
  }

  function salir() {
    olvidarClave()
    setClave('')
    setAutenticado(false)
    setPron(null)
    setEstado(null)
    setBitacora(null)
  }

  useEffect(() => {
    ;(async () => {
      await cargarSalud()
      const k = claveInicial()
      setClave(k)
      if (k) entrar(k)
    })()
  }, [cargarSalud, entrar])

  useEffect(() => {
    if (!autenticado) return
    const id = setInterval(() => {
      refrescar(claveRef.current).catch(() => {})
      cargarSalud()
    }, 60_000)
    return () => clearInterval(id)
  }, [autenticado, refrescar, cargarSalud])

  const rendimientoHoy = pron ? (pron.variables.r_lag0 ?? 0) : 0
  const rango = pron ? (pron.maximo - pron.minimo) / pron.apertura : 0
  const cuenta = estado?.cuenta
  const ultimo = estado?.ultimo_ciclo ?? null
  const modo = estado?.modo ?? salud?.agente.modo ?? 'detenido'

  return (
    <div className="pantalla">
      <header className="barra">
        <div className="marca">
          <span className={`punto ${sinBackend ? 'rojo' : 'verde'}`} aria-hidden="true"></span>
          <strong>Agente BTC/USDT</strong>
          <span className="suave">MEXC · velas diarias · Paper</span>
        </div>
        {!autenticado ? (
          <form
            className="acceso"
            onSubmit={(ev: FormEvent) => {
              ev.preventDefault()
              entrar(clave)
            }}
          >
            <input value={clave} onChange={(ev) => setClave(ev.target.value)} type="password" autoComplete="off" placeholder="Clave de la API" aria-label="Clave de la API" />
            <button type="submit" disabled={cargando}>
              {cargando ? 'Entrando…' : 'Entrar'}
            </button>
          </form>
        ) : (
          <div className="acceso">
            <span className="suave">sesión abierta</span>
            <button type="button" className="fantasma" onClick={salir}>
              Salir
            </button>
          </div>
        )}
      </header>

      {sinBackend ? <p className="aviso rojo-texto">{sinBackend}</p> : error ? <p className="aviso rojo-texto">{error}</p> : aviso ? <p className="aviso">{aviso}</p> : null}

      <section className={`hero${pron ? '' : ' vacio'}`}>
        <article className="numero">
          <p className="ceja">
            Última vela cerrada {pron && <span>· {fechaLarga(pron.fecha_vela)}</span>}
          </p>
          <p className="cifra">
            {pron ? (
              <>
                {num(pron.cierre)}
                <small>USDT</small>
              </>
            ) : (
              '—'
            )}
          </p>
          {pron ? (
            <p className="pie">
              <span className={rendimientoHoy >= 0 ? 'sube' : 'baja'}>{pct(rendimientoHoy)}</span> en el día · abrió {num(pron.apertura, 0)} · rango {pct(rango)} · cerró{' '}
              {pron.vela_cerrada_utc.slice(11, 16)} UTC
            </p>
          ) : (
            <p className="pie">Entra con la clave para consultar MEXC.</p>
          )}
        </article>

        <article className="numero">
          <p className="ceja">Pronóstico del modelo para la siguiente vela</p>
          <p className={`cifra ${pron ? (pron.estimado >= 0 ? 'sube' : 'baja') : ''}`}>{pron ? pct(pron.estimado, 3) : '—'}</p>
          {pron ? (
            <p className="pie">
              <span className={`senal ${pron.senal_regla}`}>{pron.senal_regla === 'comprar' ? 'Comprar' : 'Quedarse en efectivo'}</span>
              regla: comprar si supera {pct(pron.umbral)} · cierre {pron.filtro_sma20_ok ? 'por encima' : 'por debajo'} de la SMA20 · {pron.latencia_ms} ms · {consultadoA}
            </p>
          ) : (
            <p className="pie">{salud ? `${salud.modelo.nombre} · ${salud.modelo.version}` : ''}</p>
          )}
        </article>
      </section>

      <section className="agente">
        <div className="agente-cabeza">
          <div className="marca">
            <h2>El agente en Paper</h2>
            <span className={`modo ${modo}`}>
              <span className={`punto ${modo === 'activo' ? 'verde' : modo === 'pausado' ? 'ambar' : 'gris'}`} aria-hidden="true"></span>
              {MODO_TEXTO[modo]}
            </span>
          </div>
          {autenticado && (
            <div className="botones">
              <button type="button" onClick={() => accion('iniciar')} disabled={!!ocupado || modo === 'activo'}>
                Iniciar
              </button>
              <button type="button" className="fantasma" onClick={() => accion('pausar')} disabled={!!ocupado || modo !== 'activo'}>
                Pausar
              </button>
              <button type="button" className="fantasma" onClick={() => accion('detener')} disabled={!!ocupado || modo === 'detenido'}>
                Detener
              </button>
              <button type="button" className="fantasma" onClick={() => accion('ciclo')} disabled={!!ocupado}>
                {ocupado === 'ciclo' ? 'Consultando MEXC…' : 'Correr un ciclo ahora'}
              </button>
              <button type="button" className="peligro" onClick={() => accion('liquidar')} disabled={!!ocupado || !cuenta || cuenta.unidades <= 0}>
                Liquidar posición
              </button>
            </div>
          )}
        </div>
        {cuenta ? (
          <>
            <div className="cuenta">
              <div className="dato">
                <span className="etiqueta">Patrimonio</span>
                <span className="valor">{num(cuenta.patrimonio)}</span>
                <span className={`sub ${cuenta['rendimiento_neto_%'] >= 0 ? 'sube' : 'baja'}`}>{pct(cuenta['rendimiento_neto_%'] / 100)} neto</span>
              </div>
              <div className="dato">
                <span className="etiqueta">Efectivo</span>
                <span className="valor">{num(cuenta.efectivo)}</span>
                <span className="sub suave">USDT</span>
              </div>
              <div className="dato">
                <span className="etiqueta">Posición</span>
                <span className="valor">{cuenta.unidades.toFixed(6)}</span>
                <span className="sub suave">BTC · {pct(cuenta.exposicion, 0)} expuesto</span>
              </div>
              <div className="dato">
                <span className="etiqueta">Operaciones cerradas</span>
                <span className="valor">{cuenta.operaciones_cerradas}</span>
                <span className="sub suave">{cuenta['win_rate_%'] == null ? 'Win Rate no definido' : `Win Rate ${cuenta['win_rate_%'].toFixed(0)} %`}</span>
              </div>
            </div>
            <p className="ultimo">
              {ultimo ? (
                <>
                  Último ciclo: vela del <strong>{ultimo.fecha_vela}</strong>, cierre {num(ultimo.cierre)}, estimado{' '}
                  <span className={ultimo.estimado >= 0 ? 'sube' : 'baja'}>{pct(ultimo.estimado, 3)}</span> → propuesta <em>{ACCION_TEXTO[ultimo.propuesta].toLowerCase()}</em> ({ultimo.fuente}) →
                  riesgo: <strong>{ACCION_TEXTO[ultimo.accion]}</strong>. {ultimo.motivo}. {ultimo.latencia_ms} ms.
                </>
              ) : (
                'Todavía no se ha procesado ninguna vela. Inicia el agente o corre un ciclo ahora.'
              )}
            </p>
          </>
        ) : (
          <p className="ultimo">Entra con la clave para ver la cuenta y controlar el agente. Los límites de riesgo no se cambian desde aquí.</p>
        )}
      </section>

      <section className="tira">
        <div className="tira-cabeza">
          <h2>Los 20 días que ve el modelo</h2>
          <p className="suave">
            rendimiento diario de cierre a cierre, del más viejo al más reciente. La barra rayada es el estimado de mañana y la rayita ámbar, el umbral de la regla (
            {pron ? pct(pron.umbral) : salud ? pct(salud.paper.umbral) : '+0.10 %'}).
          </p>
        </div>
        {pron ? (
          <div className="tira-lienzo">
            <TiraDias variables={pron.variables} estimado={pron.estimado} umbral={pron.umbral} />
          </div>
        ) : (
          <div className="tira-vacia" aria-hidden="true">
            {Array.from({ length: 21 }, (_, i) => (
              <span key={i}></span>
            ))}
          </div>
        )}
      </section>

      {bitacora && bitacora.ciclos.length > 0 && (
        <section className="bitacora">
          <div className="tira-cabeza">
            <h2>Bitácora: una línea por vela procesada</h2>
            <p className="suave">
              {estado?.conteos.ciclos} ciclos · {estado?.conteos.ordenes} órdenes · {estado?.conteos.errores} errores registrados. Todo sale de la base SQLite del backend.
            </p>
          </div>
          <div className="bitacora-lienzo">
            <table>
              <thead>
                <tr>
                  <th>Vela</th>
                  <th>Cierre</th>
                  <th>Estimado</th>
                  <th>Propuesta</th>
                  <th>Acción</th>
                  <th>Motivo</th>
                  <th>Posición</th>
                  <th>Patrimonio</th>
                </tr>
              </thead>
              <tbody>
                {[...bitacora.ciclos].reverse().map((c) => (
                  <tr key={c.fecha_vela}>
                    <td>{c.fecha_vela}</td>
                    <td>{num(c.cierre)}</td>
                    <td className={c.estimado >= 0 ? 'sube' : 'baja'}>{pct(c.estimado, 3)}</td>
                    <td>
                      {ACCION_TEXTO[c.propuesta]} <span className="suave">({c.fuente})</span>
                    </td>
                    <td className={`accion ${c.accion}`}>{ACCION_TEXTO[c.accion]}</td>
                    <td className="motivo">{c.motivo}</td>
                    <td>{c.unidades.toFixed(6)}</td>
                    <td>{num(c.patrimonio)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {bitacora.errores.length > 0 && (
            <p className="ultimo">
              Últimos errores: {bitacora.errores.slice(-3).map((e) => `${hora(e.creado_utc)} · ${e.tipo}: ${e.detalle}`).join(' · ')}
            </p>
          )}
        </section>
      )}

      <section className="fichas">
        <article className="ficha">
          <h2>Modelo</h2>
          {salud && (
            <dl>
              <div>
                <dt>Qué es</dt>
                <dd>
                  {salud.modelo.nombre} · {salud.modelo.version} · {salud.modelo.entradas} variables
                </dd>
              </div>
              <div>
                <dt>Error en validación</dt>
                <dd>
                  <code>{salud.modelo.RMSE_VA.toFixed(6)}</code> RMSE, contra <code>{salud.modelo.RMSE_cero_VA.toFixed(6)}</code> del pronóstico cero
                </dd>
              </div>
              {salud.modelo.RMSE_TE != null && salud.modelo.RMSE_cero_TE != null && (
                <div>
                  <dt>Error en prueba (TE, una vez)</dt>
                  <dd>
                    <code>{salud.modelo.RMSE_TE.toFixed(6)}</code> contra <code>{salud.modelo.RMSE_cero_TE.toFixed(6)}</code> del cero: no lo supera
                  </dd>
                </div>
              )}
              <div>
                <dt>Entrenado hasta</dt>
                <dd>{salud.modelo.entrenado_hasta}</dd>
              </div>
              <div>
                <dt>Cómo se eligió</dt>
                <dd>{salud.modelo.seleccion}</dd>
              </div>
              <div>
                <dt>Huella de los datos</dt>
                <dd>
                  <code>{salud.modelo.sha256_datos}…</code>
                </dd>
              </div>
            </dl>
          )}
        </article>
        <article className="ficha">
          <h2>Paper y riesgo</h2>
          {salud && (
            <dl>
              <div>
                <dt>Capital</dt>
                <dd>
                  {num(salud.paper.capital_inicial, 0)} USDT · costo {(100 * salud.paper.costo).toFixed(2)} % por operación
                </dd>
              </div>
              <div>
                <dt>Exposición máxima</dt>
                <dd>{(100 * salud.paper.exposicion_max).toFixed(0)} % del efectivo en una compra, sin apalancamiento ni cortos</dd>
              </div>
              <div>
                <dt>Pérdida diaria máxima</dt>
                <dd>{(100 * salud.paper.perdida_diaria_max).toFixed(0)} %: al pasarla se bloquean compras ese día</dd>
              </div>
              <div>
                <dt>Filtro de tendencia</dt>
                <dd>{salud.paper.filtro_sma20 ? 'solo compra con el cierre por encima de su SMA20 (Avance 5)' : 'apagado'}</dd>
              </div>
              <div>
                <dt>Dato más viejo aceptado</dt>
                <dd>{salud.paper.max_antiguedad_h} h desde el cierre de la vela</dd>
              </div>
              <div>
                <dt>Órdenes reales</dt>
                <dd>{salud.paper.ordenes_reales}</dd>
              </div>
              <div>
                <dt>LLM local</dt>
                <dd>{salud.llm.modelo ?? 'apagado: decide la regla del Avance 5'}</dd>
              </div>
            </dl>
          )}
        </article>
      </section>

      <footer>
        Juan Pablo Escalera Boites · Ciencia de Datos Aplicada a la Economía · Ibero León · 2026 · backend {salud?.backend ?? '—'} · escalón 2. Es un simulador: el pronóstico no es una
        recomendación.
      </footer>
    </div>
  )
}
