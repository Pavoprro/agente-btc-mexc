<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api, claveGuardada, guardarClave, ErrorApi, type Pronostico, type Salud } from './api'

const salud = ref<Salud | null>(null)
const errorSalud = ref('')
const clave = ref(claveGuardada())
const pron = ref<Pronostico | null>(null)
const cargando = ref(false)
const error = ref('')
const ultimaConsulta = ref('')

const pct = (x: number, d = 2) => `${x >= 0 ? '+' : ''}${(100 * x).toFixed(d)} %`
const usdt = (x: number) => x.toLocaleString('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

const rezagos = computed(() => {
  if (!pron.value) return []
  return Object.entries(pron.value.variables).map(([k, v]) => ({ k: k.replace('r_lag', 't−'), v }))
})

async function cargarSalud() {
  try {
    salud.value = await api.salud()
    errorSalud.value = ''
  } catch (e) {
    errorSalud.value = e instanceof ErrorApi ? e.message : String(e)
  }
}

async function consultar() {
  if (!clave.value) {
    error.value = 'escribe la clave de la API'
    return
  }
  guardarClave(clave.value)
  cargando.value = true
  error.value = ''
  try {
    pron.value = await api.pronostico(clave.value)
    ultimaConsulta.value = new Date().toLocaleTimeString('es-MX')
  } catch (e) {
    pron.value = null
    error.value = e instanceof ErrorApi ? `${e.status || 'red'} · ${e.message}` : String(e)
  } finally {
    cargando.value = false
  }
}

onMounted(cargarSalud)
</script>

<template>
  <header>
    <h1>Agente BTC/USDT · MEXC · Paper</h1>
    <p class="sub">Escalón 1 · datos de MEXC validados → modelo versionado → pronóstico. Sin órdenes reales.</p>
  </header>

  <main>
    <section class="tarjeta">
      <h2>Backend</h2>
      <p v-if="errorSalud" class="error">{{ errorSalud }}</p>
      <dl v-else-if="salud">
        <dt>Activo</dt><dd>{{ salud.activo }} · velas {{ salud.intervalo }}</dd>
        <dt>Modelo</dt><dd>{{ salud.modelo.nombre }} ({{ salud.modelo.version }}) · RMSE VA {{ salud.modelo.RMSE_VA.toFixed(6) }} vs cero {{ salud.modelo.RMSE_cero_VA.toFixed(6) }}</dd>
        <dt>Entrenado hasta</dt><dd>{{ salud.modelo.entrenado_hasta }} · datos sha256 {{ salud.modelo.sha256_datos }}…</dd>
        <dt>LLM local</dt><dd>{{ salud.llm.modelo ?? 'apagado (solo regla del Avance 3)' }}</dd>
        <dt>Paper</dt><dd>{{ usdt(salud.paper.capital_inicial) }} USDT · costo {{ (100 * salud.paper.costo).toFixed(2) }} % · órdenes reales {{ salud.paper.ordenes_reales }}</dd>
        <dt>Hora</dt><dd>{{ salud.hora_utc }} · backend {{ salud.backend }}</dd>
      </dl>
      <p v-else>Consultando…</p>
      <button class="secundario" @click="cargarSalud">Actualizar</button>
    </section>

    <section class="tarjeta">
      <h2>Pronóstico</h2>
      <form @submit.prevent="consultar" class="fila">
        <label>
          Clave de la API
          <input v-model="clave" type="password" autocomplete="off" placeholder="X-API-Key" />
        </label>
        <button type="submit" :disabled="cargando">{{ cargando ? 'Consultando…' : 'Consultar MEXC' }}</button>
      </form>
      <p v-if="error" class="error">{{ error }}</p>

      <div v-if="pron" class="resultado">
        <div class="grande" :class="pron.senal_regla">
          <span class="etiqueta">Rendimiento estimado para la siguiente vela</span>
          <strong>{{ pct(pron.estimado, 3) }}</strong>
          <span class="senal">señal de la regla: <b>{{ pron.senal_regla }}</b> (umbral {{ pct(pron.umbral, 2) }})</span>
        </div>
        <dl>
          <dt>Última vela cerrada</dt><dd>{{ pron.fecha_vela }} · cierre {{ usdt(pron.cierre) }} USDT · cerró {{ pron.vela_cerrada_utc }}</dd>
          <dt>Modelo</dt><dd>{{ pron.modelo.nombre }} · {{ pron.modelo.version }}</dd>
          <dt>Latencia</dt><dd>{{ pron.latencia_ms }} ms · consultado a las {{ ultimaConsulta }}</dd>
        </dl>
        <h3>Las 20 variables (rendimiento diario, del más reciente al más viejo)</h3>
        <ul class="rezagos">
          <li v-for="r in rezagos" :key="r.k" :class="r.v >= 0 ? 'pos' : 'neg'">
            <span>{{ r.k }}</span><b>{{ pct(r.v) }}</b>
          </li>
        </ul>
      </div>
    </section>
  </main>

  <footer>
    Juan Pablo Escalera Boites · Ciencia de Datos Aplicada a la Economía · Ibero León · 2026. El pronóstico no es una recomendación.
  </footer>
</template>
