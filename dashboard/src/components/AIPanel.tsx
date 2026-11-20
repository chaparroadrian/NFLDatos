import { useEffect, useState } from 'react'

import { postAI } from '../api'
import type {
  AnalysisFilters,
  CitedPlay,
  DiagnosisAPIResponse,
  DiagnosisFilters,
  Fact,
  ScoutingReportAPIResponse,
  TrendsAPIResponse,
} from '../types'
import {
  ErrorMessage,
  SampleBadge,
  SmallSampleWarning,
  SourceTag,
  WarningMarker,
} from './shared'

type ActionStatus = 'idle' | 'loading' | 'done' | 'error'

interface ActionState<T> {
  status: ActionStatus
  result: T | null
  error: string | null
}

const initialActionState = <T,>(): ActionState<T> => ({
  status: 'idle',
  result: null,
  error: null,
})

export interface CitedPlayButtonProps {
  play: CitedPlay
  onSelectPlay: (play: CitedPlay) => void
}

/** Opens an API-cited play without coupling the AI panel to the tracking modal. */
export function CitedPlayButton({ play, onSelectPlay }: CitedPlayButtonProps) {
  return (
    <button
      className="rounded-md border border-sky-400 px-2.5 py-1.5 text-sm font-semibold text-sky-100 hover:bg-sky-950 focus-visible:ring-sky-300"
      type="button"
      onClick={() => onSelectPlay(play)}
    >
      Ver gameId={play.gameId}, playId={play.playId}
    </button>
  )
}

function GeneratedByAILabel() {
  return (
    <p className="text-sm font-semibold text-violet-200" role="note">
      Generado por IA (Amazon Nova) – requiere validación
    </p>
  )
}

function formatFactValue(value: Fact['value']): string {
  if (value === null) return 'sin datos'
  if (typeof value === 'boolean') return value ? 'Sí' : 'No'
  return String(value)
}

function citedPlaysFromReport(result: ScoutingReportAPIResponse): CitedPlay[] {
  const unique = new Map<string, CitedPlay>()

  for (const section of result.report.sections) {
    for (const item of section.items ?? []) {
      if ('gameId' in item && 'playId' in item) {
        unique.set(`${item.gameId}-${item.playId}`, { gameId: item.gameId, playId: item.playId })
      }
      if ('citedPlays' in item) {
        for (const play of item.citedPlays) {
          unique.set(`${play.gameId}-${play.playId}`, play)
        }
      }
    }
  }

  return [...unique.values()].sort((left, right) =>
    left.gameId === right.gameId ? left.playId - right.playId : left.gameId - right.gameId,
  )
}

const REPORT_SECTION_TITLES = [
  'Resumen de tendencias',
  'Cómo entra la presión',
  'Diagnóstico de protección',
  'Recomendaciones ofensivas',
  'Jugadas comparables',
  'Limitaciones',
] as const

function orderedReportSections(result: ScoutingReportAPIResponse) {
  return REPORT_SECTION_TITLES.map((title) =>
    result.report.sections.find((section) => section.title === title) ?? {
      title,
      text: '',
      items: null,
      languageWarning: false,
    },
  )
}

/** Produces the same complete, ordered report text used by the copy action. */
export function scoutingReportText(result: ScoutingReportAPIResponse): string {
  return orderedReportSections(result)
    .map((section) => {
      const itemLines = (section.items ?? []).map((item) => {
        if ('gameId' in item && 'playId' in item) {
          return `- gameId=${item.gameId}, playId=${item.playId}`
        }

        const citations = item.citedPlays
          .map((play) => `gameId=${play.gameId}, playId=${play.playId}`)
          .join('; ')
        return [
          `- ${item.label}: ${item.text}`,
          `  Dimensión: ${item.dimension}; alternativa: ${item.alternative}; n = ${item.n}; calidad: ${item.quality}`,
          citations ? `  Jugadas citadas: ${citations}` : '',
        ].filter(Boolean).join('\n')
      })

      return [section.title, section.text, ...itemLines].filter(Boolean).join('\n')
    })
    .join('\n\n')
}

export interface ScoutingReportViewProps {
  result: ScoutingReportAPIResponse
  onSelectCitedPlay?: (play: CitedPlay) => void
}

/** Renders the fixed report shape and exposes native browser copy/print actions. */
export function ScoutingReportView({ result, onSelectCitedPlay }: ScoutingReportViewProps) {
  const [copyStatus, setCopyStatus] = useState<'idle' | 'copied' | 'error'>('idle')
  const sections = orderedReportSections(result)
  const deterministic = result.generatedBy === 'sin IA'

  useEffect(() => {
    setCopyStatus('idle')
  }, [result])

  async function copyReport() {
    try {
      if (!navigator.clipboard?.writeText) throw new Error('Clipboard API unavailable')
      await navigator.clipboard.writeText(scoutingReportText(result))
      setCopyStatus('copied')
    } catch {
      setCopyStatus('error')
    }
  }

  return (
    <div className="space-y-4">
      {deterministic ? (
        <div className="space-y-2">
          <p className="font-semibold text-red-200" role="status">IA no disponible</p>
          {result.reason ? <p className="text-sm text-slate-300">{result.reason}</p> : null}
          <p className="font-semibold text-amber-200" role="note">Reporte determinista sin IA</p>
        </div>
      ) : (
        <GeneratedByAILabel />
      )}

      <div className="flex flex-wrap items-center gap-2">
        <SampleBadge n={result.sample.plays} quality={result.sample.quality} />
        <span className="rounded-md border border-slate-600 bg-slate-800 px-2.5 py-1 text-xs font-semibold text-slate-100">
          Partidos: {result.sample.games}
        </span>
      </div>
      <SmallSampleWarning
        n={result.sample.plays}
        quality={result.sample.quality}
        message={result.sample.warning}
      />

      <div className="flex flex-wrap gap-2" data-print-hidden="true">
        <button
          className="rounded-md border border-sky-400 px-3 py-2 text-sm font-semibold text-sky-100 hover:bg-sky-950 focus-visible:ring-sky-300"
          type="button"
          onClick={() => void copyReport()}
        >
          Copiar
        </button>
        <button
          className="rounded-md border border-slate-400 px-3 py-2 text-sm font-semibold text-slate-100 hover:bg-slate-800"
          type="button"
          onClick={() => window.print()}
        >
          Imprimir
        </button>
      </div>
      {copyStatus === 'copied' ? (
        <p className="text-sm font-semibold text-emerald-200" role="status">Reporte copiado.</p>
      ) : null}
      {copyStatus === 'error' ? (
        <p className="rounded-md border border-red-400 bg-red-950/60 px-3 py-2 text-sm font-semibold text-red-100" role="alert">
          No se pudo copiar el reporte.
        </p>
      ) : null}

      <div className="space-y-4">
        {sections.map((section) => (
          <section
            className="rounded-lg border border-slate-700 bg-slate-950/60 p-4"
            data-print-section="true"
            key={section.title}
            aria-labelledby={`scouting-${REPORT_SECTION_TITLES.indexOf(section.title as typeof REPORT_SECTION_TITLES[number])}`}
          >
            <h4
              className="font-semibold text-emerald-300"
              id={`scouting-${REPORT_SECTION_TITLES.indexOf(section.title as typeof REPORT_SECTION_TITLES[number])}`}
            >
              {section.title}
            </h4>
            <WarningMarker languageWarning={section.languageWarning} className="mt-2">
              {section.text ? (
                <p className="whitespace-pre-wrap text-sm leading-6 text-slate-100">{section.text}</p>
              ) : (
                <p className="text-sm text-slate-400">Sin contenido para esta sección.</p>
              )}

              {section.items && section.items.length > 0 ? (
                <ul className="mt-3 space-y-3">
                  {section.items.map((item, index) => (
                    <li className="rounded-md border border-slate-700 bg-slate-900 p-3" key={index}>
                      {'gameId' in item && 'playId' in item ? (
                        onSelectCitedPlay ? (
                          <CitedPlayButton play={item} onSelectPlay={onSelectCitedPlay} />
                        ) : (
                          <p className="text-sm text-slate-100">gameId={item.gameId}, playId={item.playId}</p>
                        )
                      ) : (
                        <div className="space-y-2">
                          <p className="text-sm font-semibold text-sky-200">{item.label}</p>
                          <p className="text-sm leading-6 text-slate-100">{item.text}</p>
                          <p className="text-sm text-slate-300">
                            Dimensión: {item.dimension} · Alternativa: {item.alternative} · n = {item.n} · Calidad: {item.quality}
                          </p>
                          {item.citedPlays.length > 0 ? (
                            <div className="flex flex-wrap gap-2">
                              {item.citedPlays.map((play) => onSelectCitedPlay ? (
                                <CitedPlayButton
                                  key={`${play.gameId}-${play.playId}`}
                                  play={play}
                                  onSelectPlay={onSelectCitedPlay}
                                />
                              ) : (
                                <span className="text-sm text-slate-200" key={`${play.gameId}-${play.playId}`}>
                                  gameId={play.gameId}, playId={play.playId}
                                </span>
                              ))}
                            </div>
                          ) : null}
                        </div>
                      )}
                    </li>
                  ))}
                </ul>
              ) : null}
            </WarningMarker>
          </section>
        ))}
      </div>
    </div>
  )
}

export interface TrendsResultProps {
  result: TrendsAPIResponse
}

export function TrendsResult({ result }: TrendsResultProps) {
  if (!result.available) {
    return <ErrorMessage title="IA no disponible" message={result.reason} />
  }

  return (
    <div className="space-y-4">
      <GeneratedByAILabel />
      <div className="flex flex-wrap gap-2">
        <SampleBadge n={result.sample.plays} quality={result.sample.quality} />
        <span className="rounded-md border border-slate-600 bg-slate-800 px-2.5 py-1 text-xs font-semibold text-slate-100">
          Partidos: {result.sample.games}
        </span>
      </div>
      <SmallSampleWarning
        n={result.sample.plays}
        quality={result.sample.quality}
        message={result.smallSampleWarning ?? result.sample.warning}
      />
      <WarningMarker languageWarning={result.languageWarning}>
        <p className="text-sm leading-6 text-slate-100">{result.text}</p>
      </WarningMarker>

      <section aria-labelledby="ai-trends-facts-title">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h4 id="ai-trends-facts-title" className="font-semibold text-emerald-300">
            Hechos citados
          </h4>
          <span className="text-xs text-slate-400">Hechos retirados: {result.removedFacts}</span>
        </div>
        {result.facts.length > 0 ? (
          <ul className="mt-2 space-y-2">
            {result.facts.map((fact, index) => (
              <li
                className="rounded-md border border-slate-700 bg-slate-950/60 p-3 text-sm"
                key={`${fact.field}-${index}`}
              >
                {fact.text ? <p className="mb-2 text-slate-100">{fact.text}</p> : null}
                <div className="flex flex-wrap items-center gap-2 text-slate-300">
                  <code className="break-all rounded bg-slate-800 px-1.5 py-0.5 text-xs text-slate-100">
                    {fact.field}
                  </code>
                  <span>Valor: {formatFactValue(fact.value)}</span>
                  <SourceTag source={fact.source} />
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-sm text-slate-300">No hay Hechos verificables en esta respuesta.</p>
        )}
      </section>
    </div>
  )
}

export interface DiagnosisResultProps {
  result: DiagnosisAPIResponse
}

export function DiagnosisResult({ result }: DiagnosisResultProps) {
  if (!result.available) {
    return <ErrorMessage title="IA no disponible" message={result.reason} />
  }

  return (
    <div className="space-y-4">
      <GeneratedByAILabel />
      <div className="flex flex-wrap gap-2">
        <SampleBadge n={result.sample.plays} quality={result.sample.quality} />
        <span className="rounded-md border border-slate-600 bg-slate-800 px-2.5 py-1 text-xs font-semibold text-slate-100">
          Partidos: {result.sample.games}
        </span>
      </div>
      <SmallSampleWarning
        n={result.sample.plays}
        quality={result.sample.quality}
        message={result.sample.warning}
      />
      {result.text ? <p className="text-sm leading-6 text-slate-100">{result.text}</p> : null}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <section className="rounded-lg border border-slate-700 bg-slate-950/50 p-4" aria-labelledby="ai-diagnosis-facts-title">
          <h4 id="ai-diagnosis-facts-title" className="font-semibold text-emerald-300">Hechos</h4>
          {result.hechos.length > 0 ? (
            <ul className="mt-3 space-y-3">
              {result.hechos.map((fact, index) => (
                <li key={`${fact.field}-${index}`}>
                  <WarningMarker languageWarning={fact.languageWarning}>
                    <p className="text-sm text-slate-100">{fact.text}</p>
                    <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-slate-300">
                      <code className="break-all rounded bg-slate-800 px-1.5 py-0.5 text-xs text-slate-100">
                        {fact.field}
                      </code>
                      <span>Valor: {formatFactValue(fact.value)}</span>
                      <SourceTag source={fact.source} />
                    </div>
                  </WarningMarker>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-sm text-slate-300">No hay Hechos verificados.</p>
          )}
        </section>

        <section className="rounded-lg border border-slate-700 bg-slate-950/50 p-4" aria-labelledby="ai-diagnosis-hypotheses-title">
          <h4 id="ai-diagnosis-hypotheses-title" className="font-semibold text-amber-300">Hipótesis</h4>
          {result.hipotesis.length > 0 ? (
            <ul className="mt-3 space-y-3">
              {result.hipotesis.map((hypothesis, index) => (
                <li key={`${hypothesis.text}-${index}`}>
                  <WarningMarker
                    languageWarning={hypothesis.languageWarning}
                    unverified={hypothesis.unverified}
                  >
                    <p className="text-sm text-slate-100">{hypothesis.text}</p>
                    <p className="mt-2 text-xs font-semibold text-amber-100">
                      {hypothesis.validation}
                    </p>
                  </WarningMarker>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-sm text-slate-300">No hay Hipótesis propuestas.</p>
          )}
        </section>
      </div>
    </div>
  )
}

interface ActionCardProps {
  title: string
  description: string
  status: ActionStatus
  onRun: () => void
  children?: React.ReactNode
}

function ActionCard({ title, description, status, onRun, children }: ActionCardProps) {
  const loading = status === 'loading'

  return (
    <section className="min-w-0 rounded-lg border border-slate-700 bg-slate-900 p-4">
      <div className="flex flex-col items-start justify-between gap-3 sm:flex-row sm:items-center">
        <div>
          <h3 className="font-semibold text-emerald-300">{title}</h3>
          <p className="mt-1 text-sm text-slate-300">{description}</p>
        </div>
        <button
          className="shrink-0 rounded-md bg-emerald-700 px-3 py-2 text-sm font-semibold text-white hover:bg-emerald-600 disabled:cursor-wait disabled:opacity-60"
          type="button"
          disabled={loading}
          onClick={onRun}
        >
          {loading ? 'Generando…' : title}
        </button>
      </div>
      <div className="mt-4 border-t border-slate-700 pt-4" aria-live="polite" aria-busy={loading}>
        {status === 'idle' ? (
          <p className="text-sm text-slate-400">Activa esta acción para generar un resultado.</p>
        ) : null}
        {loading ? (
          <p className="flex items-center gap-2 text-sm font-semibold text-slate-100" role="status">
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-emerald-200 border-t-transparent" aria-hidden="true" />
            Generando…
          </p>
        ) : null}
        {status !== 'idle' && !loading ? children : null}
      </div>
    </section>
  )
}

export interface AIPanelProps {
  filters: AnalysisFilters
  diagnosisPlay?: CitedPlay | null
  onSelectCitedPlay?: (play: CitedPlay) => void
}

/** Owns one isolated request state per AI action. App integration is intentionally external. */
export function AIPanel({ filters, diagnosisPlay = null, onSelectCitedPlay }: AIPanelProps) {
  const [trends, setTrends] = useState<ActionState<TrendsAPIResponse>>(initialActionState)
  const [diagnosis, setDiagnosis] = useState<ActionState<DiagnosisAPIResponse>>(initialActionState)
  const [scouting, setScouting] = useState<ActionState<ScoutingReportAPIResponse>>(initialActionState)

  async function runTrends() {
    setTrends({ status: 'loading', result: null, error: null })
    try {
      const result = await postAI('trends', { ...filters })
      setTrends({ status: 'done', result, error: null })
    } catch {
      setTrends({ status: 'error', result: null, error: 'IA no disponible' })
    }
  }

  async function runDiagnosis() {
    setDiagnosis({ status: 'loading', result: null, error: null })
    const request: DiagnosisFilters = diagnosisPlay
      ? { ...filters, gameId: diagnosisPlay.gameId, playId: diagnosisPlay.playId }
      : { ...filters }

    try {
      const result = await postAI('diagnosis', request)
      setDiagnosis({ status: 'done', result, error: null })
    } catch {
      setDiagnosis({ status: 'error', result: null, error: 'IA no disponible' })
    }
  }

  async function runScouting() {
    setScouting({ status: 'loading', result: null, error: null })
    try {
      const result = await postAI('scouting-report', { ...filters })
      setScouting({ status: 'done', result, error: null })
    } catch {
      setScouting({ status: 'error', result: null, error: 'IA no disponible' })
    }
  }

  return (
    <section className="rounded-xl border border-violet-700 bg-slate-950/60 p-4 sm:p-5" aria-labelledby="ai-panel-title">
      <div className="mb-4">
        <h2 id="ai-panel-title" className="text-lg font-semibold text-violet-200">Panel de IA</h2>
        <p className="mt-1 text-sm text-slate-300">
          Cada acción usa los filtros actuales y mantiene su resultado y estado de carga por separado.
        </p>
      </div>

      <div className="grid min-w-0 grid-cols-1 gap-4 xl:grid-cols-2">
        <ActionCard
          title="Explicar tendencias"
          description="Resume patrones observados y enumera los Hechos verificables."
          status={trends.status}
          onRun={() => void runTrends()}
        >
          {trends.status === 'error' ? (
            <ErrorMessage message={trends.error ?? 'IA no disponible'} title="IA no disponible" onRetry={() => void runTrends()} />
          ) : null}
          {trends.status === 'done' && trends.result ? <TrendsResult result={trends.result} /> : null}
        </ActionCard>

        <ActionCard
          title="Asistente de diagnóstico"
          description={diagnosisPlay
            ? `Se enfocará en gameId=${diagnosisPlay.gameId}, playId=${diagnosisPlay.playId}.`
            : 'Separa los datos confirmados de las explicaciones que requieren video.'}
          status={diagnosis.status}
          onRun={() => void runDiagnosis()}
        >
          {diagnosis.status === 'error' ? (
            <ErrorMessage message={diagnosis.error ?? 'IA no disponible'} title="IA no disponible" onRetry={() => void runDiagnosis()} />
          ) : null}
          {diagnosis.status === 'done' && diagnosis.result ? <DiagnosisResult result={diagnosis.result} /> : null}
        </ActionCard>

        <ActionCard
          title="Generar scouting report"
          description="Prepara el reporte; su vista completa se incorpora por separado."
          status={scouting.status}
          onRun={() => void runScouting()}
        >
          {scouting.status === 'error' ? (
            <ErrorMessage message={scouting.error ?? 'IA no disponible'} title="IA no disponible" onRetry={() => void runScouting()} />
          ) : null}
          {scouting.status === 'done' && scouting.result ? (
            <ScoutingReportView
              result={scouting.result}
              onSelectCitedPlay={onSelectCitedPlay}
            />
          ) : null}
        </ActionCard>
      </div>
    </section>
  )
}
