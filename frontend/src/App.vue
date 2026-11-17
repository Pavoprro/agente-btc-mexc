<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api, claveInicial, guardarClave, olvidarClave, ErrorApi, type Pronostico, type Salud } from './api'
import TiraDias from './components/TiraDias.vue'

const salud = ref<Salud | null>(null)
const sinBackend = ref('')
const clave = ref('')
const autenticado = ref(false)
const pron = ref<Pronostico | null>(null)
const cargando = ref(false)
const error = ref('')
const consultadoA = ref('')

const pct = (x: number, d = 2) => `${x > 0 ? '+' : x < 0 ? '−' : ''}${Math.abs(100 * x).toFixed(d)} %`
const num = (x: number, d = 2) => x.toLocaleString('es-MX', { minimumFractionDigits: d, maximumFractionDigits: d })
const fechaLarga = (iso: string) =>
  new Date(iso + 'T00:00:00Z').toLocaleDateString('es-MX', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' })

const rendimientoHoy = computed(() => (pron.value ? pron.value.variables.r_lag0 ?? 0 : 0))
const rango = computed(() => (pron.value ? (pron.value.maximo - pron.value.minimo) / pron.value.apertura : 0))

async function cargarSalud() {
  try {
    salud.value = await api.salud()
    sinBackend.value = ''
  } catch (e) {
    sinBackend.value = e instanceof ErrorApi ? e.message : String(e)
  }
}

async function consultar() {
  if (!clave.value.trim()) {
    error.value = 'Escribe la clave de la API para consultar.'
    return
  }
  guardarClave(clave.value)
  cargando.value = true
  error.value = ''
  try {
    pron.value = await api.pronostico(clave.value)
    autenticado.value = true
    consultadoA.value = new Date().toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' })
  } catch (e) {
    pron.value = null
    if (e instanceof ErrorApi && e.status === 401) {
      autenticado.value = false
      error.value = 'Clave rechazada. Es la API_KEY del archivo backend/.env.'
    } else if (e instanceof ErrorApi && e.status === 503) {
      error.value = `MEXC no dio un dato válido, así que no se pronostica: ${e.message.replace('sin dato válido: ', '')}`
    } else {
      error.value = e instanceof ErrorApi ? e.message : String(e)
    }
  } finally {
    cargando.value = false
  }
}

function salir() {
  olvidarClave()
  clave.value = ''
  autenticado.value = false
  pron.value = null
}

onMounted(async () => {
  await cargarSalud()
  clave.value = claveInicial()
  if (clave.value && !sinBackend.value) consultar()
})
</script>

<template>
  <div class="pantalla">
    <header class="barra">
      <div class="marca">
        <span class="punto" :class="sinBackend ? 'rojo' : 'verde'" aria-hidden="true"></span>
        <strong>Agente BTC/USDT</strong>
        <span class="suave">MEXC · velas diarias · Paper</span>
      </div>
      <form v-if="!autenticado" class="acceso" @submit.prevent="consultar">
        <input v-model="clave" type="password" autocomplete="off" placeholder="Clave de la API" aria-label="Clave de la API" />
        <button type="submit" :disabled="cargando">{{ cargando ? 'Entrando…' : 'Entrar' }}</button>
      </form>
      <div v-else class="acceso">
        <span class="suave">sesión abierta</span>
        <button type="button" class="fantasma" @click="salir">Salir</button>
      </div>
    </header>

    <p v-if="sinBackend" class="aviso rojo-texto">{{ sinBackend }}</p>
    <p v-else-if="error" class="aviso rojo-texto">{{ error }}</p>

    <section class="hero" :class="{ vacio: !pron }">
      <article class="numero">
        <p class="ceja">Última vela cerrada <span v-if="pron">· {{ fechaLarga(pron.fecha_vela) }}</span></p>
        <p class="cifra">
          <template v-if="pron">{{ num(pron.cierre) }}<small>USDT</small></template>
          <template v-else>—</template>
        </p>
        <p v-if="pron" class="pie">
          <span :class="rendimientoHoy >= 0 ? 'sube' : 'baja'">{{ pct(rendimientoHoy) }}</span> en el día ·
          abrió {{ num(pron.apertura, 0) }} · rango {{ pct(rango) }} · cerró {{ pron.vela_cerrada_utc.slice(11, 16) }} UTC
        </p>
        <p v-else class="pie">Entra con la clave para consultar MEXC.</p>
      </article>

      <article class="numero">
        <p class="ceja">Pronóstico del modelo para la siguiente vela</p>
        <p class="cifra" :class="pron ? (pron.estimado >= 0 ? 'sube' : 'baja') : ''">
          <template v-if="pron">{{ pct(pron.estimado, 3) }}</template>
          <template v-else>—</template>
        </p>
        <p v-if="pron" class="pie">
          <span class="senal" :class="pron.senal_regla">{{ pron.senal_regla === 'comprar' ? 'Comprar' : 'Quedarse en efectivo' }}</span>
          regla del Avance 3: comprar si supera {{ pct(pron.umbral) }} · {{ pron.latencia_ms }} ms · {{ consultadoA }}
        </p>
        <p v-else class="pie">{{ salud ? salud.modelo.nombre + ' · ' + salud.modelo.version : '' }}</p>
      </article>
    </section>

    <section class="tira">
      <div class="tira-cabeza">
        <h2>Los 20 días que ve el modelo</h2>
        <p class="suave">rendimiento diario de cierre a cierre, del más viejo al más reciente. La barra rayada es el estimado de mañana y la rayita ámbar, el umbral de la regla ({{ pron ? pct(pron.umbral) : '+0.05 %' }}).</p>
      </div>
      <div v-if="pron" class="tira-lienzo"><TiraDias :variables="pron.variables" :estimado="pron.estimado" :umbral="pron.umbral" /></div>
      <div v-else class="tira-vacia" aria-hidden="true"><span v-for="i in 21" :key="i"></span></div>
    </section>

    <section class="fichas">
      <article class="ficha">
        <h2>Modelo</h2>
        <dl v-if="salud">
          <div><dt>Qué es</dt><dd>{{ salud.modelo.nombre }} · {{ salud.modelo.version }}</dd></div>
          <div><dt>Error en validación</dt><dd><code>{{ salud.modelo.RMSE_VA.toFixed(6) }}</code> RMSE, contra <code>{{ salud.modelo.RMSE_cero_VA.toFixed(6) }}</code> del pronóstico cero</dd></div>
          <div><dt>Entrenado hasta</dt><dd>{{ salud.modelo.entrenado_hasta }}</dd></div>
          <div><dt>Cómo se eligió</dt><dd>{{ salud.modelo.seleccion }}</dd></div>
          <div><dt>Huella de los datos</dt><dd><code>{{ salud.modelo.sha256_datos }}…</code></dd></div>
        </dl>
      </article>
      <article class="ficha">
        <h2>Paper y riesgo</h2>
        <dl v-if="salud">
          <div><dt>Capital</dt><dd>{{ num(salud.paper.capital_inicial, 0) }} USDT · costo {{ (100 * salud.paper.costo).toFixed(2) }} % por operación</dd></div>
          <div><dt>Exposición máxima</dt><dd>{{ (100 * salud.paper.exposicion_max).toFixed(0) }} % del patrimonio, sin apalancamiento ni cortos</dd></div>
          <div><dt>Pérdida diaria máxima</dt><dd>{{ (100 * salud.paper.perdida_diaria_max).toFixed(0) }} %: al pasarla se bloquean órdenes nuevas</dd></div>
          <div><dt>Dato más viejo aceptado</dt><dd>{{ salud.paper.max_antiguedad_h }} h desde el cierre de la vela</dd></div>
          <div><dt>Órdenes reales</dt><dd>{{ salud.paper.ordenes_reales }}</dd></div>
          <div><dt>LLM local</dt><dd>{{ salud.llm.modelo ?? 'apagado: decide la regla del Avance 3' }}</dd></div>
        </dl>
      </article>
    </section>

    <footer>
      Juan Pablo Escalera Boites · Ciencia de Datos Aplicada a la Economía · Ibero León · 2026 · backend {{ salud?.backend ?? '—' }} · escalón 1.
      Es un simulador: el pronóstico no es una recomendación.
    </footer>
  </div>
</template>
