// Cliente de la API del backend. La clave vive en sessionStorage mientras la pestaña está abierta; nunca en el código.

export interface Salud {
  estado: string
  backend: string
  activo: string
  intervalo: string
  modelo: {
    version: string
    nombre: string
    entradas: number
    variables: string[]
    RMSE_VA: number
    RMSE_cero_VA: number
    RMSE_TE: number | null
    RMSE_cero_TE: number | null
    entrenado_hasta: string
    sha256_datos: string
    seleccion: string
  }
  llm: { modelo: string | null; url: string }
  agente: { modo: Modo; ciclos: number; ordenes: number; errores: number; eventos: number }
  paper: {
    capital_inicial: number
    costo: number
    exposicion_max: number
    perdida_diaria_max: number
    max_antiguedad_h: number
    filtro_sma20: boolean
    umbral: number
    ordenes_reales: string
  }
  hora_utc: string
}

export interface Pronostico {
  activo: string
  fecha_vela: string
  cierre: number
  apertura: number
  maximo: number
  minimo: number
  volumen: number
  vela_cerrada_utc: string
  estimado: number
  'estimado_%': number
  senal_regla: 'comprar' | 'efectivo'
  umbral: number
  filtro_sma20_ok: boolean
  variables: Record<string, number>
  modelo: { version: string; nombre: string }
  latencia_ms: number
}

export type Modo = 'detenido' | 'activo' | 'pausado'
export type Accion = 'comprar' | 'mantener' | 'vender'

export interface Cuenta {
  efectivo: number
  unidades: number
  costos_acum: number
  compra_base: number
  operaciones_cerradas: number
  operaciones_ganadoras: number
  patrimonio: number
  exposicion: number
  precio_valoracion: number | null
  'rendimiento_neto_%': number
  capital_inicial: number
  'win_rate_%': number | null
}

export interface Ciclo {
  fecha_vela: string
  cierre: number
  vela_cerrada_utc: string
  estimado: number
  variables: Record<string, number>
  propuesta: Accion
  fuente: string
  justificacion: string
  accion: Accion
  motivo: string
  bloqueos: string[]
  precio_ejecucion: number | null
  cantidad: number | null
  costo: number | null
  efectivo: number
  unidades: number
  patrimonio: number
  latencia_ms: number
  modelo: string
  llm: string | null
  creado_utc?: string
}

export interface Orden {
  lado: 'comprar' | 'vender'
  precio: number
  cantidad: number
  monto: number
  costo: number
  efectivo_despues?: number
  unidades_despues?: number
  ganancia_operacion: number | null
  fecha_vela?: string
  origen?: string
  creado_utc?: string
}

export interface Estado {
  modo: Modo
  cuenta: Cuenta
  ultimo_ciclo: Ciclo | null
  conteos: { ciclos: number; ordenes: number; errores: number; eventos: number }
  limites: {
    exposicion_max: number
    perdida_diaria_max: number
    max_antiguedad_h: number
    filtro_sma20: boolean
    umbral: number
    costo: number
    nominal_minimo: number
  }
  revision_s: number
}

export interface ResultadoCiclo {
  omitido?: boolean
  duplicado?: boolean
  motivo?: string
  modo?: Modo
  ciclo?: Ciclo
  orden?: Orden | null
}

export interface Bitacora {
  ciclos: Ciclo[]
  ordenes: Orden[]
  errores: { creado_utc: string; fecha_vela: string | null; tipo: string; detalle: string }[]
  eventos: { creado_utc: string; tipo: string; detalle: string }[]
}

export class ErrorApi extends Error {
  status: number
  constructor(status: number, mensaje: string) {
    super(mensaje)
    this.status = status
  }
}

const BASE = '/api'

/** La clave puede llegar una sola vez en el fragmento de la URL (#clave=…), que nunca viaja al servidor:
 *  así arrancar.bat abre el panel ya autenticado en la misma máquina. Se guarda y se borra de la barra. */
export function claveInicial(): string {
  const m = location.hash.match(/clave=([^&]+)/)
  if (m && m[1]) {
    const clave = decodeURIComponent(m[1])
    guardarClave(clave)
    history.replaceState(null, '', location.pathname)
    return clave
  }
  try {
    return sessionStorage.getItem('clave') ?? ''
  } catch {
    return ''
  }
}

export function guardarClave(clave: string) {
  try {
    sessionStorage.setItem('clave', clave)
  } catch {
    /* sin sessionStorage: la clave solo vive en memoria */
  }
}

export function olvidarClave() {
  try {
    sessionStorage.removeItem('clave')
  } catch {
    /* nada */
  }
}

async function pedir<T>(ruta: string, clave?: string, metodo: 'GET' | 'POST' = 'GET'): Promise<T> {
  const cabeceras: Record<string, string> = { Accept: 'application/json' }
  if (clave) cabeceras['X-API-Key'] = clave
  let r: Response
  try {
    r = await fetch(BASE + ruta, { method: metodo, headers: cabeceras })
  } catch {
    throw new ErrorApi(0, 'No hay conexión con el backend. Arranca arrancar.bat o uvicorn en el puerto 8765.')
  }
  const cuerpo = await r.json().catch(() => ({}))
  if (!r.ok) throw new ErrorApi(r.status, cuerpo.detail ?? r.statusText)
  return cuerpo as T
}

export const api = {
  salud: () => pedir<Salud>('/salud'),
  pronostico: (clave: string) => pedir<Pronostico>('/pronostico', clave),
  estado: (clave: string) => pedir<Estado>('/estado', clave),
  bitacora: (clave: string, n = 40) => pedir<Bitacora>(`/bitacora?n=${n}`, clave),
  ciclo: (clave: string, forzar = false) => pedir<ResultadoCiclo>(`/ciclo?forzar=${forzar}`, clave, 'POST'),
  iniciar: (clave: string) => pedir<Estado>('/agente/iniciar', clave, 'POST'),
  pausar: (clave: string) => pedir<Estado>('/agente/pausar', clave, 'POST'),
  detener: (clave: string) => pedir<Estado>('/agente/detener', clave, 'POST'),
  liquidar: (clave: string) => pedir<Estado & { liquidado: boolean; motivo?: string; orden?: Orden }>('/agente/liquidar', clave, 'POST'),
}
