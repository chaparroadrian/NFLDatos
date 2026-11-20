import { useMemo, useState } from 'react'

import { dec1, int, pct, secs } from '../format'
import type {
  ProtectionAlternative,
  ProtectionDimension,
  ProtectionDimensionKey,
  SampleQuality,
} from '../types'
import { NullValue, SampleBadge } from './shared'

type SortKey =
  | 'value'
  | 'plays'
  | 'pffPressureRate'
  | 'sackRate'
  | 'averageThreatTime'
  | 'completionRate'
  | 'avgPrePenaltyYards'
  | 'avgPlayResult'
  | 'quality'

type SortDirection = 'asc' | 'desc'

interface SortState {
  key: SortKey
  direction: SortDirection
  interacted: boolean
}

interface ColumnDefinition {
  key: SortKey
  label: string
  numeric?: boolean
}

const DIMENSIONS: ReadonlyArray<{ key: ProtectionDimensionKey; label: string }> = [
  { key: 'offenseFormation', label: 'Formación ofensiva' },
  { key: 'passBlockers', label: 'Número de Bloqueadores' },
  { key: 'playAction', label: 'Play action' },
  { key: 'dropBackType', label: 'Tipo de dropback' },
  { key: 'blockType', label: 'Tipo de bloqueo' },
  { key: 'personnelO', label: 'Personal ofensivo' },
]

const COLUMNS: ReadonlyArray<ColumnDefinition> = [
  { key: 'value', label: 'Alternativa' },
  { key: 'plays', label: 'n', numeric: true },
  { key: 'pffPressureRate', label: 'Evento defensivo PFF', numeric: true },
  { key: 'sackRate', label: 'Sack observado', numeric: true },
  { key: 'averageThreatTime', label: 'Tiempo hasta amenaza', numeric: true },
  { key: 'completionRate', label: 'Pases completos', numeric: true },
  { key: 'avgPrePenaltyYards', label: 'Yardas antes de castigo', numeric: true },
  { key: 'avgPlayResult', label: 'Yardas de resultado', numeric: true },
  { key: 'quality', label: 'Calidad', numeric: true },
]

const QUALITY_ORDER: Record<SampleQuality, number> = {
  insuficiente: 0,
  pequeña: 1,
  moderada: 2,
  amplia: 3,
}

const INITIAL_SORT: SortState = {
  key: 'pffPressureRate',
  direction: 'asc',
  interacted: false,
}

function comparePresentValues(
  left: string | number,
  right: string | number,
  direction: SortDirection,
): number {
  const comparison =
    typeof left === 'number' && typeof right === 'number'
      ? left - right
      : String(left).localeCompare(String(right), 'es', { numeric: true, sensitivity: 'base' })

  return direction === 'asc' ? comparison : -comparison
}

function sortableValue(alternative: ProtectionAlternative, key: SortKey): string | number | null {
  if (key === 'quality') return QUALITY_ORDER[alternative.quality]
  return alternative[key]
}

/** Sorts table values while keeping missing metrics last in both directions. */
export function sortProtectionAlternatives(
  alternatives: ProtectionAlternative[],
  sort: SortState,
): ProtectionAlternative[] {
  return [...alternatives].sort((left, right) => {
    const leftValue = sortableValue(left, sort.key)
    const rightValue = sortableValue(right, sort.key)

    if (leftValue === null && rightValue === null) return left.value.localeCompare(right.value, 'es')
    if (leftValue === null) return 1
    if (rightValue === null) return -1

    const primary = comparePresentValues(leftValue, rightValue, sort.direction)
    if (primary !== 0) return primary

    if (!sort.interacted && sort.key === 'pffPressureRate' && left.plays !== right.plays) {
      return right.plays - left.plays
    }

    return left.value.localeCompare(right.value, 'es', { numeric: true, sensitivity: 'base' })
  })
}

function nextSortState(current: SortState, key: SortKey): SortState {
  if (current.interacted && current.key === key) {
    return { key, direction: current.direction === 'asc' ? 'desc' : 'asc', interacted: true }
  }
  return { key, direction: 'asc', interacted: true }
}

function formatMetric(alternative: ProtectionAlternative, key: SortKey) {
  const value = sortableValue(alternative, key)
  if (value === null) return <NullValue />

  switch (key) {
    case 'pffPressureRate':
    case 'sackRate':
    case 'completionRate':
      return pct(value as number)
    case 'averageThreatTime':
      return secs(value as number)
    case 'avgPrePenaltyYards':
    case 'avgPlayResult':
      return dec1(value as number)
    case 'plays':
      return int(value as number)
    default:
      return String(value)
  }
}

function AlternativeSampleWarning({ alternative }: { alternative: ProtectionAlternative }) {
  if (alternative.plays >= 30) return null

  const label = alternative.quality === 'insuficiente' ? 'Muestra insuficiente' : 'Muestra pequeña'

  return (
    <div
      className="mt-2 rounded border-2 border-dashed border-amber-400 bg-amber-950/60 px-2 py-1 text-xs font-semibold text-amber-100"
      role="note"
    >
      {label} (n = {alternative.plays}). Interpretar como resultado observado y revisar en video.
    </div>
  )
}

function SortHeader({
  column,
  sort,
  onSort,
}: {
  column: ColumnDefinition
  sort: SortState
  onSort: (key: SortKey) => void
}) {
  const active = sort.key === column.key
  const ariaSort = active ? (sort.direction === 'asc' ? 'ascending' : 'descending') : 'none'

  return (
    <th
      className={`whitespace-nowrap border-b border-sky-700 bg-slate-950 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-sky-100 ${column.numeric ? 'text-right' : 'text-left'}`}
      scope="col"
      aria-sort={ariaSort}
    >
      <button
        className={`inline-flex w-full items-center gap-1 rounded px-1 py-1 hover:bg-slate-800 ${column.numeric ? 'justify-end' : 'justify-start'}`}
        type="button"
        onClick={() => onSort(column.key)}
        aria-label={`Ordenar por ${column.label}, ${active && sort.direction === 'asc' ? 'actualmente ascendente' : active ? 'actualmente descendente' : 'sin orden activo'}`}
      >
        <span>{column.label}</span>
        <span aria-hidden="true" className={active ? 'text-sky-300' : 'text-slate-500'}>
          {active ? (sort.direction === 'asc' ? '▲' : '▼') : '↕'}
        </span>
      </button>
    </th>
  )
}

function DimensionTable({ dimension }: { dimension: ProtectionDimension }) {
  const [sort, setSort] = useState<SortState>(INITIAL_SORT)
  const alternatives = useMemo(
    () => sortProtectionAlternatives(dimension.alternatives, sort),
    [dimension.alternatives, sort],
  )

  return (
    <article className="rounded-lg border border-sky-800 bg-slate-900 p-4" data-print-section="true">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="text-base font-semibold text-sky-300">{dimension.label}</h3>
          <p className="mt-1 text-xs text-slate-400">Pulsa un encabezado para ordenar. Una segunda pulsación invierte el orden.</p>
        </div>
        <span className="rounded-full border border-sky-500 bg-sky-950 px-2.5 py-1 text-xs font-semibold text-sky-100">
          {alternatives.length} alternativas
        </span>
      </div>

      {dimension.multiMembership || dimension.dimension === 'blockType' ? (
        <p className="mt-3 rounded-md border border-sky-500 bg-sky-950/70 px-3 py-2 text-sm text-sky-100" role="note">
          Una jugada puede incluir varios tipos de bloqueo; por ese motivo, los porcentajes y los conteos de esta dimensión no suman 100 %.
        </p>
      ) : null}

      {alternatives.length === 0 ? (
        <p className="mt-4 rounded-md border border-slate-700 bg-slate-950 px-3 py-4 text-sm text-slate-300">
          No hay alternativas con datos para esta dimensión.
        </p>
      ) : (
        <div className="mt-4 overflow-x-auto">
          <table className="min-w-[1120px] w-full border-separate border-spacing-0 text-sm">
            <caption className="sr-only">Comparación de respuestas de protección para {dimension.label}</caption>
            <thead>
              <tr>
                {COLUMNS.map((column) => (
                  <SortHeader
                    column={column}
                    key={column.key}
                    sort={sort}
                    onSort={(key) => setSort((current) => nextSortState(current, key))}
                  />
                ))}
              </tr>
            </thead>
            <tbody>
              {alternatives.map((alternative) => (
                <tr className="align-top even:bg-slate-950/40" key={alternative.value}>
                  <th className="border-b border-slate-800 px-3 py-3 text-left font-semibold text-slate-100" scope="row">
                    {alternative.value}
                    <AlternativeSampleWarning alternative={alternative} />
                  </th>
                  <td className="border-b border-slate-800 px-3 py-3 text-right tabular-nums text-slate-100">
                    {int(alternative.plays)}
                  </td>
                  {COLUMNS.slice(2, -1).map((column) => (
                    <td
                      className={`border-b border-slate-800 px-3 py-3 text-right tabular-nums ${column.key === 'pffPressureRate' || column.key === 'averageThreatTime' ? 'text-orange-200' : 'text-slate-100'}`}
                      key={column.key}
                    >
                      {formatMetric(alternative, column.key)}
                    </td>
                  ))}
                  <td className="border-b border-slate-800 px-3 py-3 text-right text-slate-100">
                    <SampleBadge n={alternative.plays} quality={alternative.quality} label="Alternativa" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </article>
  )
}

export function ProtectionResponsesTable({ analysis }: { analysis: { protectionResponses: ProtectionDimension[] } }) {
  const dimensionsByKey = new Map(
    analysis.protectionResponses.map((dimension) => [dimension.dimension, dimension]),
  )

  return (
    <section aria-labelledby="protection-responses-title">
      <div className="mb-4 rounded-lg border border-sky-700 bg-slate-900 p-4">
        <h2 id="protection-responses-title" className="text-lg font-semibold text-sky-300">
          Respuestas de protección observadas
        </h2>
        <p className="mt-2 text-sm text-slate-300">
          Compara resultados observados por alternativa. Las tablas se ordenan inicialmente por menor tasa de Evento defensivo PFF y, en empates, por mayor n.
        </p>
        <p className="mt-2 text-xs text-slate-400">
          “Evento defensivo PFF (hit, hurry o sack)” es una definición operativa de PocketIQ. Estas comparaciones orientan la revisión en video.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {DIMENSIONS.map(({ key, label }) => {
          const response = dimensionsByKey.get(key)
          const dimension: ProtectionDimension = response ?? {
            dimension: key,
            label,
            multiMembership: key === 'blockType',
            alternatives: [],
          }

          return <DimensionTable dimension={dimension} key={key} />
        })}
      </div>
    </section>
  )
}
