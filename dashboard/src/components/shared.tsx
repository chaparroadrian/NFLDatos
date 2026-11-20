import type { ReactNode } from 'react'

import type { ActiveFilter, SampleQuality, SourceLabel } from '../types'

const QUALITY_STYLES: Record<SampleQuality, string> = {
  amplia: 'border-emerald-400 bg-emerald-950 text-emerald-100',
  moderada: 'border-sky-400 bg-sky-950 text-sky-100',
  pequeña: 'border-amber-400 bg-amber-950 text-amber-100',
  insuficiente: 'border-red-400 bg-red-950 text-red-100',
}

const SOURCE_META: Record<SourceLabel, { icon: string; styles: string }> = {
  observada: {
    icon: '●',
    styles: 'border-slate-400 bg-slate-800 text-slate-100',
  },
  PFF: {
    icon: '◆',
    styles: 'border-sky-400 bg-sky-950 text-sky-100',
  },
  inferida: {
    icon: '◇',
    styles: 'border-orange-400 bg-orange-950 text-orange-100',
  },
}

export interface SampleBadgeProps {
  n: number
  quality: SampleQuality
  label?: string
}

/** Shows sample size and quality with text, border and color. */
export function SampleBadge({ n, quality, label = 'Muestra' }: SampleBadgeProps) {
  return (
    <span
      className={`inline-flex flex-wrap items-center gap-x-2 rounded-md border px-2.5 py-1 text-xs font-semibold ${QUALITY_STYLES[quality]}`}
      aria-label={`${label}: n = ${n}, calidad ${quality}`}
    >
      <span>{label}: n = {n}</span>
      <span aria-hidden="true">·</span>
      <span>Calidad: {quality}</span>
    </span>
  )
}

export interface SourceTagProps {
  source: SourceLabel
}

/** Identifies a value's source without relying on color alone. */
export function SourceTag({ source }: SourceTagProps) {
  const meta = SOURCE_META[source]

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-semibold ${meta.styles}`}
      aria-label={`Fuente: ${source}`}
    >
      <span aria-hidden="true">{meta.icon}</span>
      <span>{source}</span>
    </span>
  )
}

export interface SmallSampleWarningProps {
  n: number
  quality: SampleQuality
  message?: string | null
}

/** Renders the required warning only for non-empty samples below 30 plays. */
export function SmallSampleWarning({ n, quality, message }: SmallSampleWarningProps) {
  if (n < 1 || n >= 30) return null

  const label = quality === 'insuficiente' ? 'Muestra insuficiente' : 'Muestra pequeña'

  return (
    <div
      className="rounded-md border-2 border-dashed border-amber-400 bg-amber-950/60 px-3 py-2 text-sm text-amber-100"
      role="note"
    >
      <p className="font-semibold">{label} (n = {n})</p>
      {message ? <p className="mt-1">{message}</p> : null}
    </div>
  )
}

export interface NullValueProps {
  kind?: 'data' | 'threat' | 'unavailable'
  className?: string
}

const NULL_TEXT: Record<NonNullable<NullValueProps['kind']>, string> = {
  data: 'sin datos',
  threat: 'sin amenaza por proximidad',
  unavailable: 'no disponible',
}

/** Gives null values an explicit, context-appropriate visible state. */
export function NullValue({ kind = 'data', className = '' }: NullValueProps) {
  return <span className={`text-slate-300 ${className}`.trim()}>{NULL_TEXT[kind]}</span>
}

export interface WarningMarkerProps {
  children: ReactNode
  languageWarning?: boolean
  unverified?: boolean
  className?: string
}

/** Adds visible borders and exact warning text to flagged AI content. */
export function WarningMarker({
  children,
  languageWarning = false,
  unverified = false,
  className = '',
}: WarningMarkerProps) {
  const flagged = languageWarning || unverified

  return (
    <div
      className={`${flagged ? 'rounded-md border-2 border-dashed border-amber-400 bg-amber-950/40 p-3' : ''} ${className}`.trim()}
    >
      {children}
      {flagged ? (
        <div className="mt-2 flex flex-wrap gap-2 text-xs font-semibold text-amber-100" role="note">
          {languageWarning ? (
            <span className="rounded border border-amber-300 px-2 py-1">
              Advertencia: lenguaje a revisar
            </span>
          ) : null}
          {unverified ? (
            <span className="rounded border border-amber-300 px-2 py-1">
              No verificado en los datos
            </span>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}

export interface LoadingStateProps {
  message?: string
}

export function LoadingState({ message = 'Procesando tracking del rival…' }: LoadingStateProps) {
  return (
    <div
      className="flex items-center gap-3 rounded-lg border border-emerald-700 bg-slate-900 px-4 py-3 text-slate-100"
      role="status"
      aria-live="polite"
    >
      <span
        className="h-4 w-4 animate-spin rounded-full border-2 border-emerald-200 border-t-transparent"
        aria-hidden="true"
      />
      <span className="font-medium">{message}</span>
    </div>
  )
}

export interface EmptyStateProps {
  activeFilters?: ActiveFilter[]
  title?: string
  description?: string
}

function displayFilterValue(value: ActiveFilter['value']): string {
  if (typeof value === 'boolean') return value ? 'Sí' : 'No'
  return String(value)
}

export function EmptyState({
  activeFilters = [],
  title = 'Sin jugadas comparables',
  description = 'Esta combinación de filtros no tiene jugadas.',
}: EmptyStateProps) {
  return (
    <section className="rounded-lg border border-slate-700 bg-slate-900 p-5 text-slate-100" role="status">
      <h2 className="text-base font-semibold text-emerald-300">{title}</h2>
      <p className="mt-2 text-slate-300">{description}</p>
      {activeFilters.length > 0 ? (
        <div className="mt-4">
          <p className="text-sm font-semibold text-slate-200">Filtros activos:</p>
          <ul className="mt-2 flex flex-wrap gap-2" aria-label="Filtros activos sin resultados">
            {activeFilters.map((filter) => (
              <li
                className="rounded border border-slate-600 bg-slate-800 px-2 py-1 text-sm text-slate-100"
                key={`${filter.field}-${String(filter.value)}`}
              >
                {filter.label}: {displayFilterValue(filter.value)}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  )
}

export interface ErrorMessageProps {
  message: string
  title?: string
  onRetry?: () => void
  retryLabel?: string
}

export function ErrorMessage({
  message,
  title = 'No se pudo cargar el análisis',
  onRetry,
  retryLabel = 'Reintentar',
}: ErrorMessageProps) {
  return (
    <div
      className="rounded-lg border-2 border-red-400 bg-red-950/70 p-4 text-red-100"
      role="alert"
      aria-live="assertive"
    >
      <p className="font-semibold">{title}</p>
      <p className="mt-1">{message}</p>
      {onRetry ? (
        <button
          className="mt-3 rounded-md border border-red-200 px-3 py-1.5 font-semibold text-red-50 hover:bg-red-900 focus-visible:ring-red-300"
          type="button"
          onClick={onRetry}
        >
          {retryLabel}
        </button>
      ) : null}
    </div>
  )
}

/** Shared disclaimer for inferred protection diagnoses. */
export function DiagnosisDisclaimer() {
  return (
    <div className="rounded-md border border-orange-400 bg-orange-950/40 px-3 py-2 text-sm text-orange-100" role="note">
      <p>Los diagnósticos inferidos son posibles heurísticas.</p>
      <p className="mt-1">No son asignaciones confirmadas por el equipo ni por video.</p>
    </div>
  )
}

/** Required caveat shown wherever the “Doble equipo” diagnosis appears. */
export function DoubleTeamNote() {
  return (
    <p className="text-sm text-slate-300" role="note">
      El doble equipo no necesariamente se mantuvo durante toda la jugada.
    </p>
  )
}
