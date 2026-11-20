"""Pydantic contracts shared by PocketIQ API endpoints."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr, model_validator


Quality = Literal["amplia", "moderada", "pequeña", "insuficiente"]
Source = Literal["observada", "PFF", "inferida"]

Down = Annotated[StrictInt, Field(ge=0, le=4)]
ExactDistance = Annotated[StrictInt, Field(ge=1, le=99)]
BlockerCount = Annotated[StrictInt, Field(ge=0, le=11)]
Week = Annotated[StrictInt, Field(ge=1, le=8)]
Opponent = Annotated[StrictStr, Field(min_length=1, max_length=10)]


class APIModel(BaseModel):
    """Base contract that rejects undeclared API fields."""

    model_config = ConfigDict(extra="forbid")


class AnalysisRequest(APIModel):
    opponent: Opponent
    down: Down | None = None
    distanceBand: StrictStr | None = None
    exactDistance: ExactDistance | None = None
    offenseFormation: StrictStr | None = None
    defensivePersonnel: StrictStr | None = None
    playAction: StrictBool | None = None
    passBlockers: BlockerCount | None = None
    fieldZone: StrictStr | None = None
    dropBackType: StrictStr | None = None
    coverage: StrictStr | None = None
    week: Week | None = None


class SampleInfo(APIModel):
    n: int = Field(ge=0)
    quality: Quality


class Sample(APIModel):
    plays: int = Field(ge=0)
    games: int = Field(ge=0)
    quality: Quality
    warning: str | None


class SackDiscrepancy(APIModel):
    resultRate: float | None
    pffRate: float | None
    discrepantPlays: int = Field(ge=0)


class Summary(APIModel):
    text: str
    blitzRate: float | None
    averageRushers: float | None
    pffPressureRate: float | None
    hurryRate: float | None
    hitRate: float | None
    sackRate: float | None
    pffSackRate: float | None
    sackDiscrepancy: SackDiscrepancy | None
    averageThreatTime: float | None
    averageTimeToThrow: float | None
    threatTimeSample: SampleInfo
    timeToThrowSample: SampleInfo
    pressureSample: SampleInfo
    sources: dict[str, Source]


class SectorStat(APIModel):
    sector: str
    plays: int = Field(ge=0)
    share: float = Field(ge=0, le=1)
    averageThreatTime: float | None
    hurries: int = Field(ge=0)
    hits: int = Field(ge=0)
    sacks: int = Field(ge=0)
    quality: Quality


class DiagnosisStat(APIModel):
    label: str
    source: Source
    plays: int = Field(ge=0)
    share: float | None = Field(default=None, ge=0, le=1)
    hurries: int = Field(ge=0)
    hits: int = Field(ge=0)
    sacks: int = Field(ge=0)
    averageThreatTime: float | None
    threatTimeN: int = Field(ge=0)


class RusherBucket(APIModel):
    rushers: int = Field(ge=0)
    plays: int = Field(ge=0)
    share: float = Field(ge=0, le=1)


class RusherDistribution(APIModel):
    buckets: list[RusherBucket]
    blitzPlays: int = Field(ge=0)
    blitzShare: float | None = Field(default=None, ge=0, le=1)
    sample: SampleInfo


class CategoryBucket(APIModel):
    value: str
    plays: int = Field(ge=0)
    share: float = Field(ge=0, le=1)


class DownDistanceBucket(APIModel):
    down: int = Field(ge=0, le=4)
    distanceBand: str
    plays: int = Field(ge=0)
    pffPressureRate: float | None = Field(default=None, ge=0, le=1)


class ProtectionAlternative(APIModel):
    value: str
    plays: int = Field(ge=1)
    pffPressureRate: float | None = Field(default=None, ge=0, le=1)
    sackRate: float | None = Field(default=None, ge=0, le=1)
    averageThreatTime: float | None
    completionRate: float | None = Field(default=None, ge=0, le=1)
    avgPrePenaltyYards: float | None
    avgPlayResult: float | None
    quality: Quality


ProtectionDimensionName = Literal[
    "offenseFormation",
    "passBlockers",
    "playAction",
    "dropBackType",
    "blockType",
    "personnelO",
]


class ProtectionDimension(APIModel):
    dimension: ProtectionDimensionName
    label: str
    multiMembership: bool
    alternatives: list[ProtectionAlternative]


class DiagnosisTag(APIModel):
    label: str
    source: Source


RepresentativeCategory = Literal[
    "típica",
    "amenaza temprana",
    "sack",
    "protección exitosa comparable",
    "Posible intercambio o stunt o Posible rusher libre",
]


class RepresentativePlay(APIModel):
    category: RepresentativeCategory
    gameId: int
    playId: int
    week: int
    down: int
    yardsToGo: int
    offenseFormation: str | None
    personnelD: str | None
    passRushers: int | None
    passBlockers: int | None
    coverage: str | None
    timeToThrow: float | None
    threatTime: float | None
    passResult: str | None
    playResult: int | None
    playDescription: str
    diagnoses: list[DiagnosisTag]
    confidence: Literal["alto", "medio", "bajo"]


class ActiveFilter(APIModel):
    field: str
    label: str
    value: str | int | bool


class AnalysisResponse(APIModel):
    filtersApplied: dict[str, str | int | bool]
    activeFilters: list[ActiveFilter]
    sample: Sample
    trackingGamesSkipped: int = Field(ge=0)
    contextualThreshold: float | None
    summary: Summary
    pressureMap: list[SectorStat]
    diagnoses: list[DiagnosisStat]
    rusherDistribution: list[RusherBucket]
    rusherDistributionMeta: RusherDistribution | None
    coverageDistribution: list[CategoryBucket]
    personnelDistribution: list[CategoryBucket]
    downDistanceDistribution: list[DownDistanceBucket]
    protectionResponses: list[ProtectionDimension]
    representativePlays: list[RepresentativePlay]


class FiltersResponse(APIModel):
    opponents: list[str]
    downs: list[int]
    distanceBands: list[str]
    offenseFormations: list[str]
    defensivePersonnels: list[str]
    blockerCounts: list[int]
    fieldZones: list[str]
    dropBackTypes: list[str]
    coverages: list[str]
    weeks: list[int]


class PlayerInfo(APIModel):
    nflId: int
    name: str | None
    position: str | None
    role: str | None


class TrajectoryPoint(APIModel):
    frameId: int
    x_norm: float | None
    y_norm: float | None


class PlayerTrajectory(APIModel):
    nflId: int | None
    isBall: bool
    points: list[TrajectoryPoint]


class EventInfo(APIModel):
    frameId: int
    event: str


class LabeledValue(APIModel):
    value: float | int | str | bool | None
    source: Source


class PlayDetailResponse(APIModel):
    context: dict[str, Any]
    fieldSources: dict[str, Source]
    playDescription: str
    players: list[PlayerInfo]
    trajectories: list[PlayerTrajectory]
    events: list[EventInfo]
    snapFrame: int | None
    passFrame: int | None
    endFrame: int | None
    snapSource: Literal["manual", "automática", "ausente"]
    passSource: Literal["manual", "automática", "ausente"]
    trajectoryReason: str | None
    diagnoses: list[DiagnosisTag]


class StatusResponse(APIModel):
    opponent: str
    trackingReady: bool
    inProgress: bool


class AIUnavailable(APIModel):
    available: Literal[False] = False
    status: Literal["IA no disponible"] = "IA no disponible"
    reason: str


class Fact(APIModel):
    field: str
    value: float | int | str | bool | None
    source: Source
    text: str | None = None


class TrendsLLMOutput(APIModel):
    text: str = Field(min_length=1)
    facts: list[Fact]


class TrendsResponse(APIModel):
    available: Literal[True]
    modelId: str | None
    sample: Sample
    text: str
    facts: list[Fact]
    removedFacts: int = Field(ge=0)
    languageWarning: bool
    smallSampleWarning: str | None


class DiagnosisRequest(AnalysisRequest):
    gameId: StrictInt | None = None
    playId: StrictInt | None = None

    @model_validator(mode="after")
    def require_complete_play_key(self) -> DiagnosisRequest:
        if (self.gameId is None) != (self.playId is None):
            missing = "playId" if self.playId is None else "gameId"
            raise ValueError(f"{missing} es obligatorio cuando se identifica una jugada")
        return self


class HechoLLM(APIModel):
    text: str
    field: str
    value: float | int | str | bool | None
    source: Source


class HipotesisLLM(APIModel):
    text: str


class DiagnosisLLMOutput(APIModel):
    hechos: list[HechoLLM]
    hipotesis: list[HipotesisLLM]


class Hecho(HechoLLM):
    languageWarning: bool


class Hipotesis(APIModel):
    text: str
    type: Literal["hipótesis"] = "hipótesis"
    validation: Literal["requiere validación en video"] = "requiere validación en video"
    unverified: bool = False
    languageWarning: bool


class DiagnosisResponse(APIModel):
    available: Literal[True]
    modelId: str | None
    sample: Sample
    text: str | None
    hechos: list[Hecho]
    hipotesis: list[Hipotesis]


class CitedPlay(APIModel):
    gameId: int
    playId: int


class Recommendation(APIModel):
    text: str
    label: Literal["recomendación", "observación con muestra pequeña"]
    dimension: str
    alternative: str
    n: int = Field(ge=1)
    quality: Quality
    citedPlays: list[CitedPlay] = Field(min_length=1)


REPORT_SECTION_TITLES = (
    "Resumen de tendencias",
    "Cómo entra la presión",
    "Diagnóstico de protección",
    "Recomendaciones ofensivas",
    "Jugadas comparables",
    "Limitaciones",
)
ReportSectionTitle = Literal[
    "Resumen de tendencias",
    "Cómo entra la presión",
    "Diagnóstico de protección",
    "Recomendaciones ofensivas",
    "Jugadas comparables",
    "Limitaciones",
]


class ReportSection(APIModel):
    title: ReportSectionTitle
    text: str
    items: list[Recommendation] | list[CitedPlay] | None = None
    languageWarning: bool


class ScoutingReport(APIModel):
    sections: list[ReportSection]

    @model_validator(mode="after")
    def require_six_ordered_sections(self) -> ScoutingReport:
        titles = tuple(section.title for section in self.sections)
        if titles != REPORT_SECTION_TITLES:
            raise ValueError("sections debe contener las seis secciones requeridas en el orden aprobado")
        return self


class ScoutingReportResponse(APIModel):
    available: bool
    generatedBy: Literal["Amazon Nova", "sin IA"]
    modelId: str | None = None
    status: Literal["IA no disponible"] | None = None
    reason: str | None = None
    sample: Sample
    report: ScoutingReport
