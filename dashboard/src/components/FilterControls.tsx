import { useEffect, useState, type FormEvent } from 'react'

import type { AnalysisFilters, FilterOptions } from '../types'

const EMPTY_FILTERS: AnalysisFilters = {
  opponent: '',
  down: null,
  distanceBand: null,
  exactDistance: null,
  offenseFormation: null,
  defensivePersonnel: null,
  playAction: null,
  passBlockers: null,
  fieldZone: null,
  dropBackType: null,
  coverage: null,
  week: null,
}

export function createInitialFilters(): AnalysisFilters {
  return { ...EMPTY_FILTERS }
}

export function parseExactDistance(value: string): number | null | undefined {
  if (value === '') return null
  if (!/^\d+$/.test(value)) return undefined

  const parsed = Number(value)
  return parsed >= 1 && parsed <= 99 ? parsed : undefined
}

interface FilterControlsProps {
  filters: AnalysisFilters
  options: FilterOptions
  loading: boolean
  optionsLoading?: boolean
  onChange: (filters: AnalysisFilters) => void
  onAnalyze: (filters: AnalysisFilters) => void
}

interface FilterFormProps extends FilterControlsProps {
  idPrefix: string
  onSubmitted?: () => void
}

const controlClass =
  'mt-1.5 w-full rounded-md border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-slate-100 shadow-sm focus:border-emerald-400 focus:ring-emerald-400 disabled:cursor-not-allowed disabled:opacity-60'

function stringValue(value: string | null | undefined): string {
  return value ?? ''
}

function numberValue(value: number | null | undefined): string {
  return value == null ? '' : String(value)
}

function stringOrNull(value: string): string | null {
  return value === '' ? null : value
}

function numberOrNull(value: string): number | null {
  return value === '' ? null : Number(value)
}

function SelectField({
  id,
  label,
  value,
  values,
  onChange,
  format = String,
}: {
  id: string
  label: string
  value: string
  values: Array<string | number>
  onChange: (value: string) => void
  format?: (value: string | number) => string
}) {
  return (
    <label className="block text-sm font-medium text-slate-200" htmlFor={id}>
      {label}
      <select className={controlClass} id={id} value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">Todos</option>
        {values.map((option) => (
          <option key={String(option)} value={String(option)}>
            {format(option)}
          </option>
        ))}
      </select>
    </label>
  )
}

function FilterForm({
  filters,
  options,
  loading,
  optionsLoading = false,
  onChange,
  onAnalyze,
  idPrefix,
  onSubmitted,
}: FilterFormProps) {
  const [exactDistanceInput, setExactDistanceInput] = useState(
    filters.exactDistance == null ? '' : String(filters.exactDistance),
  )

  useEffect(() => {
    setExactDistanceInput(filters.exactDistance == null ? '' : String(filters.exactDistance))
  }, [filters.exactDistance])

  const parsedExactDistance = parseExactDistance(exactDistanceInput)
  const exactDistanceInvalid = parsedExactDistance === undefined
  const rivalMissing = filters.opponent.trim() === ''

  function patch<K extends keyof AnalysisFilters>(key: K, value: AnalysisFilters[K]) {
    onChange({ ...filters, [key]: value })
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (exactDistanceInvalid || rivalMissing || loading || optionsLoading) return

    const request = { ...filters, exactDistance: parsedExactDistance }
    onChange(request)
    onAnalyze(request)
    onSubmitted?.()
  }

  return (
    <form className="space-y-5" onSubmit={submit} noValidate>
      <fieldset className="space-y-4" disabled={optionsLoading}>
        <legend className="text-sm font-bold uppercase tracking-wide text-emerald-300">
          Situación previa al snap
        </legend>

        <SelectField
          id={`${idPrefix}-opponent`}
          label="Rival"
          value={filters.opponent}
          values={options.opponents}
          onChange={(value) => patch('opponent', value)}
        />
        {rivalMissing ? <p className="-mt-2 text-xs text-amber-200">Selecciona un Rival para analizar.</p> : null}

        <div className="grid grid-cols-2 gap-3">
          <SelectField
            id={`${idPrefix}-down`}
            label="Down"
            value={numberValue(filters.down)}
            values={options.downs}
            onChange={(value) => patch('down', numberOrNull(value))}
          />
          <SelectField
            id={`${idPrefix}-week`}
            label="Semana"
            value={numberValue(filters.week)}
            values={options.weeks}
            onChange={(value) => patch('week', numberOrNull(value))}
          />
        </div>

        <div>
          <div className="flex items-center justify-between gap-2">
            <label className="text-sm font-medium text-slate-200" htmlFor={`${idPrefix}-distanceBand`}>
              Banda de distancia
            </label>
            <span className="rounded-full border border-emerald-500 px-2 py-0.5 text-[11px] font-semibold text-emerald-200">
              Recomendada
            </span>
          </div>
          <select
            className={controlClass}
            id={`${idPrefix}-distanceBand`}
            value={stringValue(filters.distanceBand)}
            onChange={(event) => patch('distanceBand', stringOrNull(event.target.value))}
          >
            <option value="">Todos</option>
            {options.distanceBands.map((value) => <option key={value} value={value}>{value}</option>)}
          </select>
          <p className="mt-1 text-xs text-slate-400">Agrupa situaciones comparables sin fragmentar la muestra.</p>
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-200" htmlFor={`${idPrefix}-exactDistance`}>
            Distancia exacta <span className="font-normal text-slate-400">(opción secundaria)</span>
          </label>
          <input
            aria-describedby={`${idPrefix}-exactDistance-help`}
            aria-invalid={exactDistanceInvalid}
            className={`${controlClass} ${exactDistanceInvalid ? 'border-red-400 focus:border-red-400 focus:ring-red-400' : ''}`}
            id={`${idPrefix}-exactDistance`}
            inputMode="numeric"
            min="1"
            max="99"
            pattern="[0-9]*"
            type="text"
            value={exactDistanceInput}
            onChange={(event) => {
              const value = event.target.value
              setExactDistanceInput(value)
              const parsed = parseExactDistance(value)
              if (parsed !== undefined) patch('exactDistance', parsed)
            }}
          />
          <p className={`mt-1 text-xs ${exactDistanceInvalid ? 'font-semibold text-red-300' : 'text-slate-400'}`} id={`${idPrefix}-exactDistance-help`}>
            {exactDistanceInvalid
              ? 'Ingresa un entero entre 1 y 99.'
              : 'Si la completas, reemplaza la Banda de distancia en el análisis.'}
          </p>
        </div>

        <SelectField
          id={`${idPrefix}-offenseFormation`}
          label="Formación ofensiva"
          value={stringValue(filters.offenseFormation)}
          values={options.offenseFormations}
          onChange={(value) => patch('offenseFormation', stringOrNull(value))}
        />
        <SelectField
          id={`${idPrefix}-defensivePersonnel`}
          label="Personal defensivo"
          value={stringValue(filters.defensivePersonnel)}
          values={options.defensivePersonnels}
          onChange={(value) => patch('defensivePersonnel', stringOrNull(value))}
        />
        <SelectField
          id={`${idPrefix}-playAction`}
          label="Play action"
          value={filters.playAction == null ? '' : String(filters.playAction)}
          values={['true', 'false']}
          format={(value) => value === 'true' ? 'Sí' : 'No'}
          onChange={(value) => patch('playAction', value === '' ? null : value === 'true')}
        />
        <SelectField
          id={`${idPrefix}-passBlockers`}
          label="Número de Bloqueadores"
          value={numberValue(filters.passBlockers)}
          values={options.blockerCounts}
          onChange={(value) => patch('passBlockers', numberOrNull(value))}
        />
        <SelectField
          id={`${idPrefix}-fieldZone`}
          label="Zona del campo"
          value={stringValue(filters.fieldZone)}
          values={options.fieldZones}
          onChange={(value) => patch('fieldZone', stringOrNull(value))}
        />
        <SelectField
          id={`${idPrefix}-dropBackType`}
          label="Tipo de dropback"
          value={stringValue(filters.dropBackType)}
          values={options.dropBackTypes}
          onChange={(value) => patch('dropBackType', stringOrNull(value))}
        />
      </fieldset>

      <fieldset className="space-y-3 border-t border-slate-700 pt-5" disabled={optionsLoading}>
        <legend className="px-1 text-sm font-bold uppercase tracking-wide text-orange-300">
          Análisis posterior al snap
        </legend>
        <p className="text-xs leading-5 text-slate-300">La cobertura ejecutada no se conoce antes del snap.</p>
        <SelectField
          id={`${idPrefix}-coverage`}
          label="Cobertura ejecutada (PFF)"
          value={stringValue(filters.coverage)}
          values={options.coverages}
          onChange={(value) => patch('coverage', stringOrNull(value))}
        />
      </fieldset>

      <button
        className="w-full rounded-md bg-emerald-500 px-4 py-2.5 text-sm font-bold text-slate-950 hover:bg-emerald-400 disabled:cursor-not-allowed disabled:bg-slate-600 disabled:text-slate-300"
        disabled={loading || optionsLoading || exactDistanceInvalid || rivalMissing}
        type="submit"
      >
        {loading ? 'Analizando…' : 'Analizar defensa'}
      </button>
    </form>
  )
}

export function FilterControls(props: FilterControlsProps) {
  const [mobileOpen, setMobileOpen] = useState(false)

  return (
    <>
      <aside className="hidden rounded-lg border border-emerald-700 bg-slate-900 p-4 md:sticky md:top-4 md:block md:max-h-[calc(100vh-2rem)] md:overflow-y-auto" aria-label="Filtros de análisis">
        <FilterForm {...props} idPrefix="desktop" />
      </aside>

      <section className="md:hidden" aria-label="Filtros de análisis móvil">
        <button
          aria-controls="mobile-filter-panel"
          aria-expanded={mobileOpen}
          className="flex w-full items-center justify-between rounded-lg border border-emerald-600 bg-slate-900 px-4 py-3 text-left font-semibold text-slate-100"
          type="button"
          onClick={() => setMobileOpen((open) => !open)}
        >
          <span>Filtros de análisis</span>
          <span aria-hidden="true">{mobileOpen ? '−' : '+'}</span>
        </button>
        {mobileOpen ? (
          <div className="mt-2 rounded-lg border border-emerald-700 bg-slate-900 p-4" id="mobile-filter-panel">
            <FilterForm {...props} idPrefix="mobile" onSubmitted={() => setMobileOpen(false)} />
          </div>
        ) : null}
      </section>
    </>
  )
}
