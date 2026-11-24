// Tira de 20 barras (r_lag19 … r_lag0) más la barra rayada del estimado. SVG puro, sin librerías.

const ANCHO = 1000
const ALTO = 220
const MARGEN = { arriba: 26, abajo: 50, izq: 8, der: 8 }

const pct = (v: number) => `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(100 * v).toFixed(2)} %`

export default function TiraDias({ variables, estimado, umbral }: { variables: Record<string, number>; estimado: number; umbral: number }) {
  const dias = Array.from({ length: 20 }, (_, i) => ({ etiqueta: i === 19 ? 'hoy' : `−${19 - i}`, valor: variables[`r_lag${19 - i}`] ?? 0, estimado: false }))
  const barras = [...dias, { etiqueta: 'mañana', valor: estimado, estimado: true }]
  const maximo = Math.max(0.01, ...barras.map((b) => Math.abs(b.valor)))
  const alto = ALTO - MARGEN.arriba - MARGEN.abajo
  const cero = MARGEN.arriba + alto / 2
  const y = (v: number) => cero - (v / maximo) * (alto / 2)
  const paso = (ANCHO - MARGEN.izq - MARGEN.der) / barras.length
  const anchoBarra = paso * 0.58
  const x = (i: number) => MARGEN.izq + i * paso + (paso - anchoBarra) / 2
  const yUmbral = y(umbral)

  return (
    <svg viewBox={`0 0 ${ANCHO} ${ALTO}`} className="tira-svg" role="img" aria-label="Rendimiento diario de los últimos 20 días y estimado de mañana">
      <defs>
        <pattern id="rayas" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <rect width="3" height="6" fill="currentColor" />
        </pattern>
      </defs>
      <line x1={MARGEN.izq} x2={ANCHO - MARGEN.der} y1={cero} y2={cero} className="eje" />
      <line x1={x(20) - paso * 0.3} x2={x(20) + anchoBarra + paso * 0.3} y1={yUmbral} y2={yUmbral} className="umbral">
        <title>umbral de la regla: {pct(umbral)}</title>
      </line>
      {barras.map((b, i) => (
        <g key={b.etiqueta} className={['barra', b.valor >= 0 ? 'sube' : 'baja', b.estimado ? 'estimado' : '', b.etiqueta === 'hoy' ? 'hoy' : ''].join(' ')}>
          <rect
            x={x(i)}
            y={Math.min(y(b.valor), cero)}
            width={anchoBarra}
            height={Math.max(1.5, Math.abs(y(b.valor) - cero))}
            rx="2"
            fill={b.estimado ? 'url(#rayas)' : 'currentColor'}
          >
            <title>
              {b.etiqueta}: {pct(b.valor)}
            </title>
          </rect>
          <text x={x(i) + anchoBarra / 2} y={b.valor >= 0 ? y(b.valor) - 6 : y(b.valor) + 14} textAnchor="middle" className="valor">
            {pct(b.valor)}
          </text>
          <text x={x(i) + anchoBarra / 2} y={ALTO - 10} textAnchor="middle" className="dia">
            {b.etiqueta}
          </text>
        </g>
      ))}
    </svg>
  )
}
