import { dec1, int, pct, secs } from '../format'
import type {
  AnalysisResponse,
  SampleInfo,
  SectorStat,
  SourceLabel,
  Summary,
} from '../types'
import { SampleBadge, SmallSampleWarning, SourceTag } from './shared'

interface ExecutiveSummaryProps {
  analysis: AnalysisResponse
  onExpandFilter?: (field: 'week' | 'coverage' | 'exactDistance') => void
}

const EXPANDABLE_FILTERS = [
  { field: 'week', label: 'semana' },
  { field: 'coverage', label: 'cobertura' },
  { field: 'exactDistance', label: 'distancia exacta' },
] as const

export function ExecutiveSummary({ analysis, onExpandFilter }: ExecutiveSummaryProps) {
  const expandable =
    analysis.sample.plays > 0 && analysis.sample.plays < 30
      ? EXPANDABLE_FILTERS.find(({ field }) =>
          analysis.activeFilters.some((filter) => filter.field === field),
        )
      : undefined

  return (
    <section
      className="rounded-xl border border-emerald-700 bg-slate-900 p-5 shadow-lg shadow-black/10"
      aria-labelledby="executive-summary-title"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-400">
            Lectura principal
          </p>
          <h2 id="executive-summary-title" className="mt-1 text-xl font-bold text-slate-100">
            Resumen ejecutivo
          </h2>
        </div>
        <SampleBadge n={analysis.sample.plays} quality={analysis.sample.quality} />
      </div>

      <p className="mt-4 max-w-5xl text-base leading-7 text-slate-100">{analysis.summary.text}</p>
      <p className="mt-3 text-sm text-slate-300">
        {int(analysis.sample.plays)} jugadas en {int(analysis.sample.games)} partidos · Calidad de muestra:{' '}
        <span className="font-semibold text-slate-100">{analysis.sample.quality}</span>
      </p>

      <div className="mt-4">
        <SmallSampleWarning
          n={analysis.sample.plays}
          quality={analysis.sample.quality}
          message={analysis.sample.warning}
        />
      </div>

      {expandable && onExpandFilter ? (
        <button
          className="mt-4 rounded-md border border-emerald-400 bg-emerald-950 px-3 py-2 text-sm font-semibold text-emerald-100 hover:bg-emerald-900"
          type="button"
          onClick={() => onExpandFilter(expandable.field)}
        >
          Ampliar: quitar filtro de {expandable.label}
        </button>
      ) : null}
    </section>
  )
}

interface MetricDefinition {
  key: keyof Summary
  label: string
  source: SourceLabel
  format: (value: number | null | undefined) => string
  sample: (analysis: AnalysisResponse) => SampleInfo
  note?: string
}

const METRICS: MetricDefinition[] = [
  {
    key: 'blitzRate',
    label: 'Blitz aproximado',
    source: 'inferida',
    format: pct,
    sample: ({ summary }) => summary.pressureSample,
  },
  {
    key: 'averageRushers',
    label: 'Rushers promedio',
    source: 'PFF',
    format: dec1,
    sample: ({ summary }) => summary.pressureSample,
  },
  {
    key: 'pffPressureRate',
    label: 'Evento defensivo PFF',
    source: 'PFF',
    format: pct,
    sample: ({ summary }) => summary.pressureSample,
    note: 'Definición operativa de PocketIQ: Evento defensivo PFF (hit, hurry o sack).',
  },
  {
    key: 'averageThreatTime',
    label: 'Tiempo promedio hasta amenaza',
    source: 'inferida',
    format: secs,
    sample: ({ summary }) => summary.threatTimeSample,
    note: 'Tiempo hasta amenaza por proximidad.',
  },
  {
    key: 'hurryRate',
    label: 'Hurry rate',
    source: 'PFF',
    format: pct,
    sample: ({ summary }) => summary.pressureSample,
  },
  {
    key: 'hitRate',
    label: 'Hit rate',
    source: 'PFF',
    format: pct,
    sample: ({ summary }) => summary.pressureSample,
  },
  {
    key: 'sackRate',
    label: 'Sack rate',
    source: 'observada',
    format: pct,
    sample: ({ sample }) => ({ n: sample.plays, quality: sample.quality }),
    note: 'Calculada con passResult = “S”.',
  },
  {
    key: 'averageTimeToThrow',
    label: 'Tiempo promedio de lanzamiento',
    source: 'observada',
    format: secs,
    sample: ({ summary }) => summary.timeToThrowSample,
  },
]

export function MetricCards({ analysis }: { analysis: AnalysisResponse }) {
  return (
    <section aria-labelledby="key-metrics-title">
      <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 id="key-metrics-title" className="text-lg font-bold text-slate-100">
            Métricas clave
          </h2>
          <p className="text-sm text-slate-400">Cada tarjeta identifica su fuente y muestra evaluable.</p>
        </div>
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {METRICS.map((metric) => {
          const value = analysis.summary[metric.key]
          const sample = metric.sample(analysis)
          const numericValue = typeof value === 'number' ? value : null

          return (
            <article
              key={metric.key}
              className="flex min-h-48 flex-col rounded-xl border border-slate-700 bg-slate-900 p-4"
            >
              <div className="flex items-start justify-between gap-2">
                <h3 className="font-semibold text-slate-200">{metric.label}</h3>
                <SourceTag source={metric.source} />
              </div>
              <p className="mt-4 text-3xl font-bold tabular-nums text-white">
                {metric.format(numericValue)}
              </p>
              {metric.note ? <p className="mt-2 text-xs leading-5 text-slate-300">{metric.note}</p> : null}

              {metric.key === 'sackRate' && analysis.summary.sackDiscrepancy ? (
                <div className="mt-3 border-t border-slate-700 pt-3 text-xs text-slate-200">
                  <div className="flex flex-wrap items-center gap-2">
                    <span>Tasa de sack PFF: {pct(analysis.summary.pffSackRate)}</span>
                    <SourceTag source="PFF" />
                  </div>
                  <p className="mt-2 font-semibold text-amber-200">
                    Jugadas discrepantes: {int(analysis.summary.sackDiscrepancy.discrepantPlays)}
                  </p>
                </div>
              ) : null}

              <div className="mt-auto pt-4">
                <SampleBadge n={sample.n} quality={sample.quality} label="Muestra evaluable" />
                <div className="mt-2">
                  <SmallSampleWarning n={sample.n} quality={sample.quality} />
                </div>
              </div>
            </article>
          )
        })}
      </div>
    </section>
  )
}

const SECTOR_GEOMETRY = [
  '20,35 205,35 395,340 280,340',
  '205,35 390,35 470,340 395,340',
  '390,35 610,35 530,340 470,340',
  '610,35 795,35 605,340 530,340',
  '795,35 980,35 720,340 605,340',
]

const SECTOR_LABEL_LINES: Record<string, string[]> = {
  Izquierda: ['Izquierda'],
  'Interior izquierda': ['Interior', 'izquierda'],
  Centro: ['Centro'],
  'Interior derecha': ['Interior', 'derecha'],
  Derecha: ['Derecha'],
}

function sectorFill(stat: SectorStat): string {
  if (stat.plays === 0) return 'rgba(251, 146, 60, 0.08)'
  const opacity = Math.min(0.82, 0.18 + stat.share * 1.6)
  return `rgba(249, 115, 22, ${opacity})`
}

function SectorText({ stat, index }: { stat: SectorStat; index: number }) {
  const x = 110 + index * 195
  const lines = SECTOR_LABEL_LINES[stat.sector] ?? [stat.sector]

  return (
    <g className="pointer-events-none fill-slate-100 text-[17px] font-semibold" textAnchor="middle">
      <text x={x} y={75}>
        {lines.map((line, lineIndex) => (
          <tspan key={line} x={x} dy={lineIndex === 0 ? 0 : 20}>
            {line}
          </tspan>
        ))}
      </text>
      <text x={x} y={130} className="fill-white text-[24px] font-bold">
        {pct(stat.share)}
      </text>
      <text x={x} y={163} className="fill-slate-100 text-[14px] font-medium">
        n = {int(stat.plays)}
      </text>
      <text x={x} y={190} className="fill-orange-100 text-[13px] font-medium">
        Tiempo: {secs(stat.averageThreatTime)}
      </text>
      <text x={x} y={218} className="fill-slate-100 text-[13px] font-medium">
        Hurries: {int(stat.hurries)}
      </text>
      <text x={x} y={242} className="fill-slate-100 text-[13px] font-medium">
        Hits: {int(stat.hits)}
      </text>
      <text x={x} y={266} className="fill-slate-100 text-[13px] font-medium">
        Sacks: {int(stat.sacks)}
      </text>
      <text x={x} y={294} className="fill-slate-200 text-[12px] font-medium">
        Calidad: {stat.quality}
      </text>
    </g>
  )
}

export function PressureMapSVG({ analysis }: { analysis: AnalysisResponse }) {
  const sectors = analysis.pressureMap.slice(0, 5)

  return (
    <section
      className="rounded-xl border border-emerald-700 bg-slate-900 p-4 sm:p-5"
      aria-labelledby="pressure-map-title"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 id="pressure-map-title" className="text-lg font-bold text-slate-100">
            Mapa de presión
          </h2>
          <p className="mt-1 text-sm text-slate-300">
            Participación y tiempo hasta amenaza por proximidad por Sector.
          </p>
        </div>
        <SourceTag source="inferida" />
      </div>

      <div className="mt-4 overflow-x-auto rounded-lg border border-emerald-800 bg-emerald-950/70">
        <svg
          className="min-w-[760px]"
          viewBox="0 0 1000 410"
          role="img"
          aria-labelledby="pressure-map-svg-title pressure-map-svg-description"
        >
          <title id="pressure-map-svg-title">Mapa de presión de cinco sectores</title>
          <desc id="pressure-map-svg-description">
            Cinco sectores desde la izquierda hasta la derecha de la ofensiva, con participación, muestra,
            tiempo promedio hasta amenaza, hurries, hits, sacks y calidad.
          </desc>
          <rect width="1000" height="410" fill="#064e3b" />
          {[85, 165, 245, 325].map((y) => (
            <line key={y} x1="15" x2="985" y1={y} y2={y} stroke="#34d399" strokeOpacity="0.2" />
          ))}
          {sectors.map((stat, index) => (
            <g key={stat.sector}>
              <polygon
                points={SECTOR_GEOMETRY[index]}
                fill={sectorFill(stat)}
                stroke="#fdba74"
                strokeOpacity={stat.plays === 0 ? 0.35 : 0.75}
                strokeWidth="2"
              />
              <SectorText stat={stat} index={index} />
            </g>
          ))}
          <circle cx="500" cy="365" r="25" fill="#f8fafc" stroke="#0f172a" strokeWidth="3" />
          <text x="500" y="371" textAnchor="middle" className="fill-slate-950 text-[16px] font-bold">
            QB
          </text>
          <text x="500" y="402" textAnchor="middle" className="fill-emerald-100 text-[12px]">
            Perspectiva de la ofensiva
          </text>
        </svg>
      </div>

      <div className="mt-4 space-y-2 text-sm text-slate-300">
        <p>
          Los sectores representan la posición del rusher respecto del QB en el primer cuadro de amenaza por proximidad.
        </p>
        <p className="flex flex-wrap items-center gap-2">
          <SourceTag source="inferida" />
          <span>
            Los Sectores son una clasificación geométrica de PocketIQ y no una etiqueta oficial de PFF.
          </span>
        </p>
        <p>La intensidad naranja complementa los valores; los Sectores sin jugadas usan la intensidad mínima.</p>
      </div>
      <div className="mt-4">
        <SampleBadge n={analysis.sample.plays} quality={analysis.sample.quality} label="Muestra del análisis" />
        <div className="mt-2">
          <SmallSampleWarning
            n={analysis.sample.plays}
            quality={analysis.sample.quality}
            message={analysis.sample.warning}
          />
        </div>
      </div>
    </section>
  )
}

export function CoreAnalysisPanels({
  analysis,
  onExpandFilter,
}: {
  analysis: AnalysisResponse
  onExpandFilter?: ExecutiveSummaryProps['onExpandFilter']
}) {
  return (
    <div className="space-y-5">
      <ExecutiveSummary analysis={analysis} onExpandFilter={onExpandFilter} />
      <MetricCards analysis={analysis} />
      <PressureMapSVG analysis={analysis} />
    </div>
  )
}
