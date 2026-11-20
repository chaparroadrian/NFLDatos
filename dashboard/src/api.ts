import type {
  AnalysisFilters,
  AnalysisResponse,
  DiagnosisAPIResponse,
  DiagnosisFilters,
  FilterOptions,
  OpponentStatus,
  PlayDetailResponse,
  ScoutingReportAPIResponse,
  TrendsAPIResponse,
} from './types'

export interface ValidationIssue {
  field: string
  message: string
}

export type ApiErrorKind = 'validation' | 'request'

export class ApiError extends Error {
  readonly kind: ApiErrorKind
  readonly status: number | null
  readonly validationIssues: ValidationIssue[]

  constructor(
    message: string,
    kind: ApiErrorKind,
    status: number | null = null,
    validationIssues: ValidationIssue[] = [],
  ) {
    super(message)
    this.name = 'ApiError'
    this.kind = kind
    this.status = status
    this.validationIssues = validationIssues
  }
}

type ErrorBody = {
  detail?: string | Array<{ field?: unknown; message?: unknown }>
}

async function readErrorBody(response: Response): Promise<ErrorBody | null> {
  try {
    return (await response.json()) as ErrorBody
  } catch {
    return null
  }
}

function validationIssues(body: ErrorBody | null): ValidationIssue[] {
  if (!Array.isArray(body?.detail)) return []

  return body.detail.flatMap((item) => {
    if (typeof item?.field !== 'string' || typeof item.message !== 'string') return []
    return [{ field: item.field, message: item.message }]
  })
}

function errorMessage(body: ErrorBody | null, fallback: string): string {
  if (typeof body?.detail === 'string' && body.detail.trim()) return body.detail

  const issues = validationIssues(body)
  if (issues.length > 0) {
    return issues.map(({ field, message }) => `${field}: ${message}`).join('; ')
  }

  return fallback
}

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  try {
    const response = await fetch(url, init)

    if (!response.ok) {
      const body = await readErrorBody(response)
      if (response.status === 422) {
        throw new ApiError(
          errorMessage(body, 'Uno o más filtros no son válidos.'),
          'validation',
          response.status,
          validationIssues(body),
        )
      }

      throw new ApiError(
        errorMessage(body, 'La solicitud no se pudo completar.'),
        'request',
        response.status,
      )
    }

    try {
      return (await response.json()) as T
    } catch {
      throw new ApiError('El servidor devolvió una respuesta no válida.', 'request', response.status)
    }
  } catch (error) {
    if (error instanceof ApiError) throw error
    throw new ApiError('No se pudo conectar con el servidor.', 'request')
  }
}

function postJson<T>(url: string, body: unknown): Promise<T> {
  return requestJson<T>(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export function getFilters(): Promise<FilterOptions> {
  return requestJson<FilterOptions>('api/filters')
}

export function postAnalysis(filters: AnalysisFilters): Promise<AnalysisResponse> {
  return postJson<AnalysisResponse>('api/analysis', filters)
}

export function getStatus(opponent: string): Promise<OpponentStatus> {
  return requestJson<OpponentStatus>(`api/status/${encodeURIComponent(opponent)}`)
}

export function getPlay(gameId: number, playId: number): Promise<PlayDetailResponse> {
  return requestJson<PlayDetailResponse>(`api/plays/${gameId}/${playId}`)
}

export type AIAction = 'trends' | 'diagnosis' | 'scouting-report'

interface AIResponseByAction {
  trends: TrendsAPIResponse
  diagnosis: DiagnosisAPIResponse
  'scouting-report': ScoutingReportAPIResponse
}

export function postAI(action: 'trends', filters: AnalysisFilters): Promise<TrendsAPIResponse>
export function postAI(action: 'diagnosis', filters: DiagnosisFilters): Promise<DiagnosisAPIResponse>
export function postAI(
  action: 'scouting-report',
  filters: AnalysisFilters,
): Promise<ScoutingReportAPIResponse>
export function postAI<T extends AIAction>(
  action: T,
  filters: T extends 'diagnosis' ? DiagnosisFilters : AnalysisFilters,
): Promise<AIResponseByAction[T]> {
  return postJson<AIResponseByAction[T]>(`api/ai/${action}`, filters)
}
