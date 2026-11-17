<script setup lang="ts">
// Tira de 20 barras (r_lag19 … r_lag0) más la barra rayada del estimado. SVG puro, sin librerías.
import { computed } from 'vue'

const props = defineProps<{ variables: Record<string, number>; estimado: number; umbral: number }>()

const ANCHO = 1000
const ALTO = 220
const MARGEN = { arriba: 26, abajo: 50, izq: 8, der: 8 }

const barras = computed(() => {
  const dias = Array.from({ length: 20 }, (_, i) => ({ etiqueta: i === 19 ? 'hoy' : `−${19 - i}`, valor: props.variables[`r_lag${19 - i}`] ?? 0, estimado: false }))
  return [...dias, { etiqueta: 'mañana', valor: props.estimado, estimado: true }]
})

const escala = computed(() => {
  const maximo = Math.max(0.01, ...barras.value.map((b) => Math.abs(b.valor)))
  const alto = ALTO - MARGEN.arriba - MARGEN.abajo
  const cero = MARGEN.arriba + alto / 2
  return { y: (v: number) => cero - (v / maximo) * (alto / 2), cero, maximo }
})

const paso = (ANCHO - MARGEN.izq - MARGEN.der) / barras.value.length
const anchoBarra = paso * 0.58
const x = (i: number) => MARGEN.izq + i * paso + (paso - anchoBarra) / 2

const pct = (v: number) => `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(100 * v).toFixed(2)} %`
const yUmbral = computed(() => escala.value.y(props.umbral))
</script>

<template>
  <svg :viewBox="`0 0 ${ANCHO} ${ALTO}`" class="tira-svg" role="img" aria-label="Rendimiento diario de los últimos 20 días y estimado de mañana">
    <defs>
      <pattern id="rayas" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
        <rect width="3" height="6" fill="currentColor" />
      </pattern>
    </defs>
    <line :x1="MARGEN.izq" :x2="ANCHO - MARGEN.der" :y1="escala.cero" :y2="escala.cero" class="eje" />
    <line :x1="x(20) - paso * 0.3" :x2="x(20) + anchoBarra + paso * 0.3" :y1="yUmbral" :y2="yUmbral" class="umbral">
      <title>umbral de la regla: {{ pct(umbral) }}</title>
    </line>
    <g v-for="(b, i) in barras" :key="i" :class="['barra', b.valor >= 0 ? 'sube' : 'baja', { estimado: b.estimado, hoy: b.etiqueta === 'hoy' }]">
      <rect
        :x="x(i)"
        :y="Math.min(escala.y(b.valor), escala.cero)"
        :width="anchoBarra"
        :height="Math.max(1.5, Math.abs(escala.y(b.valor) - escala.cero))"
        rx="2"
        :fill="b.estimado ? 'url(#rayas)' : 'currentColor'"
      >
        <title>{{ b.etiqueta }}: {{ pct(b.valor) }}</title>
      </rect>
      <text :x="x(i) + anchoBarra / 2" :y="b.valor >= 0 ? escala.y(b.valor) - 6 : escala.y(b.valor) + 14" text-anchor="middle" class="valor">{{ pct(b.valor) }}</text>
      <text :x="x(i) + anchoBarra / 2" :y="ALTO - 10" text-anchor="middle" class="dia">{{ b.etiqueta }}</text>
    </g>
  </svg>
</template>
