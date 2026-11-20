import {
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { int, pct, secs } from '../format'
import type {
  AnalysisResponse,
  CategoryBucket,
  DiagnosisStat,
  DownDistanceBucket,
  RusherBucket,
  SourceLabel,
} from '../types'
import { DiagnosisDisclaimer, DoubleTeamNote, NullValue, SourceTag } from './shared'

const DIAGNOSES: ReadonlyArray<{ label: string; source: SourceLabel }> = [
  { label: 'Derrota individual', source: 'PFF' },
  { label: 'Posible rusher libre', source: 'inferida' },
  { label: 'Doble equipo', source: 'PFF' },
  { label: 'Chip o ayuda', source: 'PFF' },
  { label: 'Posible intercambio o stunt', source: 'inferida' },
  {
    label: 'Posible presión prolongada por movimiento o retención del QB',
    source: 'inferida',
  },
  { label: 'No determinado con los datos disponibles', source: 'inferida' },
]

interface ChartDatum {
  name: string
  plays: number
  valueLabel: string
}

interface DistributionChartProps {
  title: string
  description: string
  data: ChartDatum[]
  source: SourceLabel
  emptyMessage: string
}

function DistributionChart({
  title,
  description,
  data,
  source,
  emptyMessage,
}: DistributionChartProps) {
  const chartHeight = Math.max(220, data.length * 48 + 70)

  return (
    <article className="rounded-xl border border-slate-700 bg-slate-900 p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="font-semibold text-slate-100">{title}</h3>
          <p className="mt-1 text-sm text-slate-300">{description}</p>
        </div>
        <SourceTag source={source} />
      </div>

      {data.length > 0 ? (
        <div className="mt-4 w-full" style={{ height: chartHeight }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              accessibilityLayer
              data={data}
              layout="vertical"
              margin={{ top: 4, right: 100, bottom: 18, left: 8 }}
            >
              <CartesianGrid horizontal={false} stroke="#334155" strokeDasharray="3 3" />
              <XAxis
                allowDecimals={false}
                axisLine={{ stroke: '#64748b' }}
                tick={{ fill: '#cbd5e1', fontSize: 12 }}
                tickLine={false}
                type="number"
              />
              <YAxis
                axisLine={false}
                dataKey="name"
                tick={{ fill: '#e2e8f0', fontSize: 12 }}
                tickLine={false}
                type="category"
                width={132}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#0f172a',
                  border: '1px solid #64748b',
                  borderRadius: '0.5rem',
                  color: '#f8fafc',
                }}
                formatter={(_value, _name, item) => [item.payload.valueLabel, 'Jugadas']}
              />
              <Bar dataKey="plays" fill="#fb923c" name="Jugadas" radius={[0, 4, 4, 0]}>
                <LabelList
                  dataKey="valueLabel"
                  fill="#f8fafc"
                  fontSize={12}
                  fontWeight={600}
                  position="right"
                />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <p className="mt-4 rounded-md border border-slate-700 bg-slate-950 px-3 py-4 text-sm text-slate-300">
          {emptyMessage}
        </p>
      )}
    </article>
  )
}

function rusherData(buckets: RusherBucket[]): ChartDatum[] {
  return [...buckets]
    .sort((a, b) => a.rushers - b.rushers)
    .map((bucket) => ({
      name: `${int(bucket.rushers)} rushers`,
      plays: bucket.plays,
      valueLabel: `${int(bucket.plays)} (${pct(bucket.share)})`,
    }))
}

function categoryData(buckets: CategoryBucket[]): ChartDatum[] {
  return [...buckets]
    .sort((a, b) => b.plays - a.plays || a.value.localeCompare(b.value, 'es'))
    .map((bucket) => ({
      name: bucket.value,
      plays: bucket.plays,
      valueLabel: `${int(bucket.plays)} (${pct(bucket.share)})`,
    }))
}

function downDistanceData(buckets: DownDistanceBucket[]): ChartDatum[] {
  return [...buckets]
    .sort((a, b) => a.down - b.down || a.distanceBand.localeCompare(b.distanceBand, 'es'))
    .map((bucket) => ({
      name: `Down ${int(bucket.down)} · ${bucket.distanceBand}`,
      plays: bucket.plays,
      valueLabel: `${int(bucket.plays)} · evento PFF ${pct(bucket.pffPressureRate)}`,
    }))
}

export function TrendsCharts({ analysis }: { analysis: AnalysisResponse }) {
  if (analysis.sample.plays === 0) {
    return (
      <section className="rounded-xl border border-slate-700 bg-slate-900 p-5" role="status">
        <h2 className="text-lg font-bold text-slate-100">Tendencias defensivas</h2>
        <p className="mt-2 text-slate-300">No hay jugadas para los filtros seleccionados.</p>
      </section>
    )
  }

  const blitzPlays =
    analysis.rusherDistributionMeta?.blitzPlays ??
    analysis.rusherDistribution.reduce(
      (total, bucket) => total + (bucket.rushers >= 5 ? bucket.plays : 0),
      0,
    )
  const blitzShare = blitzPlays / analysis.sample.plays

  return (
    <section aria-labelledby="defensive-trends-title">
      <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 id="defensive-trends-title" className="text-lg font-bold text-slate-100">
            Tendencias defensivas
          </h2>
          <p className="mt-1 text-sm text-slate-400">
            Distribuciones calculadas sobre las {int(analysis.sample.plays)} jugadas filtradas.
          </p>
        </div>
        <div className="rounded-md border border-orange-400 bg-orange-950/50 px-3 py-2 text-sm text-orange-100">
          <span className="font-semibold">Blitz aproximado:</span>{' '}
          {int(blitzPlays)} jugadas ({pct(blitzShare)})
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <DistributionChart
          title="Distribución de rushers"
          description="Número y porcentaje de jugadas para cada cantidad de rushers."
          data={rusherData(analysis.rusherDistribution)}
          source="PFF"
          emptyMessage="No hay conteos de rushers disponibles en esta muestra."
        />
        <DistributionChart
          title="Cobertura ejecutada (PFF)"
          description="Número y porcentaje de jugadas por cobertura ejecutada (PFF)."
          data={categoryData(analysis.coverageDistribution)}
          source="PFF"
          emptyMessage="No hay cobertura ejecutada (PFF) disponible en esta muestra."
        />
        <DistributionChart
          title="Personal defensivo"
          description="Número y porcentaje de jugadas por personal defensivo."
          data={categoryData(analysis.personnelDistribution)}
          source="observada"
          emptyMessage="No hay personal defensivo disponible en esta muestra."
        />
        <DistributionChart
          title="Down y Banda_Distancia"
          description="Jugadas y tasa de Evento defensivo PFF (hit, hurry o sack), definición operativa de PocketIQ."
          data={downDistanceData(analysis.downDistanceDistribution)}
          source="PFF"
          emptyMessage="No hay combinaciones de down y Banda_Distancia disponibles en esta muestra."
        />
      </div>
    </section>
  )
}

function completeDiagnoses(diagnoses: DiagnosisStat[]): DiagnosisStat[] {
  const byLabel = new Map(diagnoses.map((diagnosis) => [diagnosis.label, diagnosis]))

  return DIAGNOSES.map(({ label, source }) =>
    byLabel.get(label) ?? {
      label,
      source,
      plays: 0,
      share: 0,
      hurries: 0,
      hits: 0,
      sacks: 0,
      averageThreatTime: null,
      threatTimeN: 0,
    },
  )
}

function visibleDiagnosisLabel(diagnosis: DiagnosisStat): string {
  if (diagnosis.source === 'inferida' && !/posible|heurística/i.test(diagnosis.label)) {
    return `Heurística: ${diagnosis.label}`
  }
  return diagnosis.label
}

export function DiagnosisTable({ analysis }: { analysis: AnalysisResponse }) {
  if (analysis.sample.plays === 0) {
    return (
      <section className="rounded-xl border border-slate-700 bg-slate-900 p-5" role="status">
        <h2 className="text-lg font-bold text-slate-100">Diagnóstico de protección</h2>
        <p className="mt-2 text-slate-300">No hay jugadas para los filtros seleccionados.</p>
      </section>
    )
  }

  const diagnoses = completeDiagnoses(analysis.diagnoses)

  return (
    <section
      className="rounded-xl border border-slate-700 bg-slate-900 p-4 sm:p-5"
      aria-labelledby="diagnosis-table-title"
    >
      <div>
        <h2 id="diagnosis-table-title" className="text-lg font-bold text-slate-100">
          Diagnóstico de protección
        </h2>
        <p className="mt-1 text-sm text-slate-300">
          Los porcentajes pueden sumar más de 100 % porque una jugada puede tener varios diagnósticos.
        </p>
      </div>

      <div className="mt-4 overflow-x-auto">
        <table className="min-w-[940px] w-full border-separate border-spacing-0 text-left text-sm">
          <thead>
            <tr className="text-slate-300">
              <th className="border-b border-slate-600 px-3 py-2 font-semibold" scope="col">Diagnóstico</th>
              <th className="border-b border-slate-600 px-3 py-2 font-semibold" scope="col">Fuente</th>
              <th className="border-b border-slate-600 px-3 py-2 text-right font-semibold" scope="col">Jugadas</th>
              <th className="border-b border-slate-600 px-3 py-2 text-right font-semibold" scope="col">Porcentaje</th>
              <th className="border-b border-slate-600 px-3 py-2 text-right font-semibold" scope="col">Hurries</th>
              <th className="border-b border-slate-600 px-3 py-2 text-right font-semibold" scope="col">Hits</th>
              <th className="border-b border-slate-600 px-3 py-2 text-right font-semibold" scope="col">Sacks</th>
              <th className="border-b border-slate-600 px-3 py-2 text-right font-semibold" scope="col">Tiempo hasta amenaza</th>
            </tr>
          </thead>
          <tbody>
            {diagnoses.map((diagnosis) => (
              <tr className="align-top even:bg-slate-950/50" key={diagnosis.label}>
                <th className="border-b border-slate-800 px-3 py-3 font-semibold text-slate-100" scope="row">
                  <span>{visibleDiagnosisLabel(diagnosis)}</span>
                  {diagnosis.label === 'Doble equipo' ? (
                    <div className="mt-1 max-w-md font-normal">
                      <DoubleTeamNote />
                    </div>
                  ) : null}
                </th>
                <td className="border-b border-slate-800 px-3 py-3"><SourceTag source={diagnosis.source} /></td>
                <td className="border-b border-slate-800 px-3 py-3 text-right tabular-nums text-slate-100">{int(diagnosis.plays)}</td>
                <td className="border-b border-slate-800 px-3 py-3 text-right tabular-nums text-slate-100">{pct(diagnosis.share)}</td>
                <td className="border-b border-slate-800 px-3 py-3 text-right tabular-nums text-slate-100">{int(diagnosis.hurries)}</td>
                <td className="border-b border-slate-800 px-3 py-3 text-right tabular-nums text-slate-100">{int(diagnosis.hits)}</td>
                <td className="border-b border-slate-800 px-3 py-3 text-right tabular-nums text-slate-100">{int(diagnosis.sacks)}</td>
                <td className="border-b border-slate-800 px-3 py-3 text-right tabular-nums text-orange-200">
                  {diagnosis.averageThreatTime === null ? <NullValue /> : secs(diagnosis.averageThreatTime)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-4">
        <DiagnosisDisclaimer />
      </div>
    </section>
  )
}

export function DefensiveTrends({ analysis }: { analysis: AnalysisResponse }) {
  return (
    <div className="space-y-5">
      <TrendsCharts analysis={analysis} />
      <DiagnosisTable analysis={analysis} />
    </div>
  )
}
