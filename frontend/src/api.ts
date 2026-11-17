// Cliente de la API del backend. La clave vive en sessionStorage mientras la pestaña está abierta; nunca en el código.

export interface Salud {
  estado: string
  backend: string
  activo: string
  intervalo: string
  modelo: { version: string; nombre: string; entradas: number; RMSE_VA: number; RMSE_cero_VA: number; entrenado_hasta: string; sha256_datos: string; seleccion: string }
  llm: { modelo: string | null; url: string }
  paper: { capital_inicial: number; costo: number; exposicion_max: number; perdida_diaria_max: number; max_antiguedad_h: number; ordenes_reales: string }
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
  variables: Record<string, number>
  modelo: { version: string; nombre: string }
  latencia_ms: number
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
  if (m) {
    const clave = decodeURIComponent(m[1]!)
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

async function pedir<T>(ruta: string, clave?: string, init: RequestInit = {}): Promise<T> {
  const cabeceras: Record<string, string> = { Accept: 'application/json' }
  if (clave) cabeceras['X-API-Key'] = clave
  let r: Response
  try {
    r = await fetch(BASE + ruta, { ...init, headers: cabeceras })
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
}
