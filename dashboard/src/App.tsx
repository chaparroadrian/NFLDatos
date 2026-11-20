import { useCallback, useEffect, useState } from 'react'

import { ApiError, getFilters, postAnalysis } from './api'
import {
  CoreAnalysisPanels,
  DefensiveTrends,
  EmptyState,
  ErrorMessage,
  FilterControls,
  Header,
  LoadingState,
  PlayDetailModal,
  ProtectionResponsesTable,
  RepresentativePlays,
  createInitialFilters,
} from './components'
import type {
  AnalysisFilters,
  AnalysisResponse,
  FilterOptions,
  RepresentativePlay,
} from './types'

const EMPTY_OPTIONS: FilterOptions = {
  opponents: [],
  downs: [],
  distanceBands: [],
  offenseFormations: [],
  defensivePersonnels: [],
  blockerCounts: [],
  fieldZones: [],
  dropBackTypes: [],
  coverages: [],
  weeks: [],
}

type AnalysisStatus = 'idle' | 'loading' | 'ok' | 'error'

export default function App() {
  const [filters, setFilters] = useState<AnalysisFilters>(createInitialFilters)
  const [filterOptions, setFilterOptions] = useState<FilterOptions>(EMPTY_OPTIONS)
  const [optionsLoading, setOptionsLoading] = useState(true)
  const [optionsError, setOptionsError] = useState<string | null>(null)
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null)
  const [analysisStatus, setAnalysisStatus] = useState<AnalysisStatus>('idle')
  const [analysisError, setAnalysisError] = useState<string | null>(null)
  const [selectedPlay, setSelectedPlay] = useState<RepresentativePlay | null>(null)

  const loadFilterOptions = useCallback(async () => {
    setOptionsLoading(true)
    setOptionsError(null)
    try {
      setFilterOptions(await getFilters())
    } catch (error) {
      setOptionsError(error instanceof Error ? error.message : 'No se pudieron cargar los filtros.')
    } finally {
      setOptionsLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadFilterOptions()
  }, [loadFilterOptions])

  async function analyze(selectedFilters: AnalysisFilters) {
    if (analysisStatus === 'loading') return

    setAnalysisStatus('loading')
    setAnalysisError(null)
    try {
      const response = await postAnalysis(selectedFilters)
      setAnalysis(response)
      setSelectedPlay((current) => {
        if (!current) return null
        return response.representativePlays.some(
          (play) => play.gameId === current.gameId && play.playId === current.playId,
        )
          ? current
          : null
      })
      setAnalysisStatus('ok')
    } catch (error) {
      setAnalysis(null)
      setAnalysisStatus('error')
      if (error instanceof ApiError && error.kind === 'validation') {
        setAnalysisError(`Filtro inválido: ${error.message}`)
      } else {
        setAnalysisError(error instanceof Error ? error.message : 'El análisis no se pudo completar.')
      }
    }
  }

  function expandFilter(field: 'week' | 'coverage' | 'exactDistance') {
    const expandedFilters = { ...filters, [field]: null }
    setFilters(expandedFilters)
    void analyze(expandedFilters)
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <Header />
      <main className="mx-auto grid max-w-[1920px] grid-cols-1 gap-4 px-4 py-4 sm:px-6 md:grid-cols-[minmax(250px,320px)_minmax(0,1fr)] lg:gap-6 lg:px-8">
        <div>
          {optionsError ? (
            <ErrorMessage
              title="No se pudieron cargar los filtros"
              message={optionsError}
              onRetry={() => void loadFilterOptions()}
            />
          ) : null}
          <div className={optionsError ? 'mt-3' : ''}>
            <FilterControls
              filters={filters}
              options={filterOptions}
              loading={analysisStatus === 'loading'}
              optionsLoading={optionsLoading}
              onChange={setFilters}
              onAnalyze={(request) => void analyze(request)}
            />
          </div>
        </div>

        <section className="min-w-0" aria-live="polite" aria-busy={analysisStatus === 'loading'}>
          {analysisStatus === 'loading' ? <LoadingState /> : null}
          {analysisStatus === 'error' && analysisError ? (
            <ErrorMessage
              title="No se pudo cargar el análisis"
              message={analysisError}
              retryLabel="Reintentar análisis"
              onRetry={() => void analyze(filters)}
            />
          ) : null}
          {analysisStatus === 'idle' ? (
            <div className="rounded-lg border border-slate-700 bg-slate-900 p-6">
              <h2 className="text-lg font-semibold text-emerald-300">Configura el análisis</h2>
              <p className="mt-2 max-w-2xl text-slate-300">
                Selecciona un Rival y combina los filtros de situación. La consulta se ejecuta al pulsar “Analizar defensa”.
              </p>
            </div>
          ) : null}
          {analysisStatus === 'ok' && analysis && analysis.sample.plays === 0 ? (
            <EmptyState
              activeFilters={analysis.activeFilters}
              description="Esta combinación de filtros no tiene jugadas comparables. Ajusta uno o más filtros y vuelve a analizar."
            />
          ) : null}
          {analysisStatus === 'ok' && analysis && analysis.sample.plays > 0 ? (
            <div className="space-y-8">
              <CoreAnalysisPanels analysis={analysis} onExpandFilter={expandFilter} />
              <DefensiveTrends analysis={analysis} />
              <ProtectionResponsesTable analysis={analysis} />
              <RepresentativePlays
                plays={analysis.representativePlays}
                onSelectPlay={setSelectedPlay}
              />
            </div>
          ) : null}
        </section>
      </main>

      {selectedPlay ? (
        <PlayDetailModal play={selectedPlay} onClose={() => setSelectedPlay(null)} />
      ) : null}
    </div>
  )
}
