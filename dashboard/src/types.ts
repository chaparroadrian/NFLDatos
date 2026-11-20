export type SampleQuality = 'amplia' | 'moderada' | 'pequeña' | 'insuficiente'
export type SourceLabel = 'observada' | 'PFF' | 'inferida'
export type NullableNumber = number | null

export interface AnalysisFilters {
  opponent: string
  down?: number | null
  distanceBand?: string | null
  exactDistance?: number | null
  offenseFormation?: string | null
  defensivePersonnel?: string | null
  playAction?: boolean | null
  passBlockers?: number | null
  fieldZone?: string | null
  dropBackType?: string | null
  coverage?: string | null
  week?: number | null
}

export interface DiagnosisFilters extends AnalysisFilters {
  gameId?: number | null
  playId?: number | null
}

export interface FilterOptions {
  opponents: string[]
  downs: number[]
  distanceBands: string[]
  offenseFormations: string[]
  defensivePersonnels: string[]
  blockerCounts: number[]
  fieldZones: string[]
  dropBackTypes: string[]
  coverages: string[]
  weeks: number[]
}

export interface SampleInfo {
  n: number
  quality: SampleQuality
}

export interface Sample {
  plays: number
  games: number
  quality: SampleQuality
  warning: string | null
}

export interface ActiveFilter {
  field: string
  label: string
  value: string | number | boolean
}

export type AppliedFilterValue = string | number | boolean
export type FiltersApplied = Record<string, AppliedFilterValue>

export interface SackDiscrepancy {
  resultRate: NullableNumber
  pffRate: NullableNumber
  discrepantPlays: number
}

export interface Summary {
  text: string
  blitzRate: NullableNumber
  averageRushers: NullableNumber
  pffPressureRate: NullableNumber
  hurryRate: NullableNumber
  hitRate: NullableNumber
  sackRate: NullableNumber
  pffSackRate: NullableNumber
  sackDiscrepancy: SackDiscrepancy | null
  averageThreatTime: NullableNumber
  averageTimeToThrow: NullableNumber
  threatTimeSample: SampleInfo
  timeToThrowSample: SampleInfo
  pressureSample: SampleInfo
  sources: Record<string, SourceLabel>
}

export interface SectorStat {
  sector: string
  plays: number
  share: number
  averageThreatTime: NullableNumber
  hurries: number
  hits: number
  sacks: number
  quality: SampleQuality
}

export interface DiagnosisStat {
  label: string
  source: SourceLabel
  plays: number
  share: NullableNumber
  hurries: number
  hits: number
  sacks: number
  averageThreatTime: NullableNumber
  threatTimeN: number
}

export interface RusherBucket {
  rushers: number
  plays: number
  share: number
}

export interface RusherDistributionMeta {
  buckets: RusherBucket[]
  blitzPlays: number
  blitzShare: NullableNumber
  sample: SampleInfo
}

export interface CategoryBucket {
  value: string
  plays: number
  share: number
}

export interface DownDistanceBucket {
  down: number
  distanceBand: string
  plays: number
  pffPressureRate: NullableNumber
}

export type ProtectionDimensionKey =
  | 'offenseFormation'
  | 'passBlockers'
  | 'playAction'
  | 'dropBackType'
  | 'blockType'
  | 'personnelO'

export interface ProtectionAlternative {
  value: string
  plays: number
  pffPressureRate: NullableNumber
  sackRate: NullableNumber
  averageThreatTime: NullableNumber
  completionRate: NullableNumber
  avgPrePenaltyYards: NullableNumber
  avgPlayResult: NullableNumber
  quality: SampleQuality
}

export interface ProtectionDimension {
  dimension: ProtectionDimensionKey
  label: string
  multiMembership: boolean
  alternatives: ProtectionAlternative[]
}

export interface DiagnosisTag {
  label: string
  source: SourceLabel
}

export type RepresentativePlayCategory =
  | 'típica'
  | 'amenaza temprana'
  | 'sack'
  | 'protección exitosa comparable'
  | 'Posible intercambio o stunt o Posible rusher libre'

export type Confidence = 'alto' | 'medio' | 'bajo'

export interface RepresentativePlay {
  category: RepresentativePlayCategory
  gameId: number
  playId: number
  week: number
  down: number
  yardsToGo: number
  offenseFormation: string | null
  personnelD: string | null
  passRushers: number | null
  passBlockers: number | null
  coverage: string | null
  timeToThrow: NullableNumber
  threatTime: NullableNumber
  passResult: string | null
  playResult: number | null
  playDescription: string
  diagnoses: DiagnosisTag[]
  confidence: Confidence
}

export interface AnalysisResponse {
  filtersApplied: FiltersApplied
  activeFilters: ActiveFilter[]
  sample: Sample
  trackingGamesSkipped: number
  contextualThreshold: NullableNumber
  summary: Summary
  pressureMap: SectorStat[]
  diagnoses: DiagnosisStat[]
  rusherDistribution: RusherBucket[]
  rusherDistributionMeta: RusherDistributionMeta | null
  coverageDistribution: CategoryBucket[]
  personnelDistribution: CategoryBucket[]
  downDistanceDistribution: DownDistanceBucket[]
  protectionResponses: ProtectionDimension[]
  representativePlays: RepresentativePlay[]
}

export interface PlayerInfo {
  nflId: number
  name: string | null
  position: string | null
  role: string | null
}

export interface TrajectoryPoint {
  frameId: number
  x_norm: NullableNumber
  y_norm: NullableNumber
}

export interface PlayerTrajectory {
  nflId: number | null
  isBall: boolean
  points: TrajectoryPoint[]
}

export interface EventInfo {
  frameId: number
  event: string
}

export interface PlayDetailResponse {
  context: Record<string, unknown>
  fieldSources: Record<string, SourceLabel>
  playDescription: string
  players: PlayerInfo[]
  trajectories: PlayerTrajectory[]
  events: EventInfo[]
  snapFrame: number | null
  passFrame: number | null
  endFrame: number | null
  snapSource: 'manual' | 'automática' | 'ausente'
  passSource: 'manual' | 'automática' | 'ausente'
  trajectoryReason: string | null
  diagnoses: DiagnosisTag[]
}

export interface OpponentStatus {
  opponent: string
  trackingReady: boolean
  inProgress: boolean
}

export interface AIUnavailable {
  available: false
  status: 'IA no disponible'
  reason: string
}

export interface Fact {
  field: string
  value: number | string | boolean | null
  source: SourceLabel
  text?: string | null
}

export interface TrendsResponse {
  available: true
  modelId: string | null
  sample: Sample
  text: string
  facts: Fact[]
  removedFacts: number
  languageWarning: boolean
  smallSampleWarning: string | null
}

export interface DiagnosisFact extends Fact {
  text: string
  languageWarning: boolean
}

export interface Hypothesis {
  text: string
  type: 'hipótesis'
  validation: 'requiere validación en video'
  unverified: boolean
  languageWarning: boolean
}

export interface DiagnosisResponse {
  available: true
  modelId: string | null
  sample: Sample
  text: string | null
  hechos: DiagnosisFact[]
  hipotesis: Hypothesis[]
}

export interface CitedPlay {
  gameId: number
  playId: number
}

export type RecommendationLabel = 'recomendación' | 'observación con muestra pequeña'

export interface Recommendation {
  text: string
  label: RecommendationLabel
  dimension: string
  alternative: string
  n: number
  quality: SampleQuality
  citedPlays: CitedPlay[]
}

export interface ReportSection {
  title: string
  text: string
  items: Recommendation[] | CitedPlay[] | null
  languageWarning: boolean
}

export interface ScoutingReport {
  sections: ReportSection[]
}

export interface ScoutingReportResponse {
  available: boolean
  generatedBy: 'Amazon Nova' | 'sin IA'
  modelId: string | null
  status: string | null
  reason: string | null
  sample: Sample
  report: ScoutingReport
}

export type TrendsAPIResponse = TrendsResponse | AIUnavailable
export type DiagnosisAPIResponse = DiagnosisResponse | AIUnavailable
export type ScoutingReportAPIResponse = ScoutingReportResponse
