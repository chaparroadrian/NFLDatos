import { useEffect, useMemo, useState } from 'react'

import { getPlay } from '../api'
import { int, secs } from '../format'
import type {
  EventInfo,
  PlayDetailResponse,
  PlayerInfo,
  PlayerTrajectory,
  RepresentativePlay,
  RepresentativePlayCategory,
  SourceLabel,
  TrajectoryPoint,
} from '../types'
import { ErrorMessage, LoadingState, NullValue, SourceTag } from './shared'

const CATEGORIES: readonly RepresentativePlayCategory[] = [
  'típica',
  'amenaza temprana',
  'sack',
  'protección exitosa comparable',
  'Posible intercambio o stunt o Posible rusher libre',
]

const ROLE_LABELS = {
  rusher: 'Rusher',
  blocker: 'Bloqueador',
  chip: 'Ayuda o chip',
  quarterback: 'QB',
  ball: 'Balón',
  other: 'Otro jugador',
} as const

type VisualRole = keyof typeof ROLE_LABELS
type DetailStatus = 'loading' | 'ready' | 'error'

export interface RepresentativePlaysProps {
  plays: RepresentativePlay[]
  onSelectPlay: (play: RepresentativePlay) => void
}

export interface PlayDetailModalProps {
  play: RepresentativePlay
  onClose: () => void
}

function optionalText(value: string | number | null): string | null {
  if (value === null || value === '') return null
  return String(value)
}

function displayText(value: string | number | null) {
  const text = optionalText(value)
  return text === null ? <NullValue kind="unavailable" /> : text
}

function resultText(play: RepresentativePlay): string | null {
  const passResult = optionalText(play.passResult)
  const yards = Number.isFinite(play.playResult) ? `${int(play.playResult)} yd` : null
  return [passResult, yards].filter(Boolean).join(' · ') || null
}

function confidenceStyles(confidence: RepresentativePlay['confidence']): string {
  if (confidence === 'alto') return 'border-emerald-400 bg-emerald-950 text-emerald-100'
  if (confidence === 'medio') return 'border-amber-400 bg-amber-950 text-amber-100'
  return 'border-orange-400 bg-orange-950 text-orange-100'
}

function RepresentativePlayCard({
  play,
  onOpen,
}: {
  play: RepresentativePlay
  onOpen: (play: RepresentativePlay) => void
}) {
  const fields = [
    ['Partido', int(play.gameId)],
    ['Semana', int(play.week)],
    ['Down y distancia', `${int(play.down)} y ${int(play.yardsToGo)}`],
    ['Formación', optionalText(play.offenseFormation)],
    ['Personal defensivo', optionalText(play.personnelD)],
    ['Rushers', play.passRushers === null ? null : int(play.passRushers)],
    ['Bloqueadores', play.passBlockers === null ? null : int(play.passBlockers)],
    ['Cobertura', optionalText(play.coverage)],
    ['timeToThrow', play.timeToThrow === null ? null : secs(play.timeToThrow)],
    ['Tiempo hasta amenaza', play.threatTime === null ? null : secs(play.threatTime)],
    ['Resultado', resultText(play)],
  ] as const

  return (
    <article className="flex h-full flex-col rounded-lg border border-slate-700 bg-slate-900 p-4" data-print-section="true">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h3 className="max-w-xl text-base font-semibold text-emerald-300">{play.category}</h3>
        <span
          className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${confidenceStyles(play.confidence)}`}
        >
          Confianza: {play.confidence}
        </span>
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 text-sm sm:grid-cols-3">
        {fields.map(([label, value]) => (
          <div key={label}>
            <dt className="text-xs font-semibold uppercase tracking-wide text-slate-400">{label}</dt>
            <dd className="mt-0.5 text-slate-100">{value === null ? <NullValue kind="unavailable" /> : value}</dd>
          </div>
        ))}
      </dl>

      <div className="mt-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Descripción</p>
        <p className="mt-1 text-sm leading-6 text-slate-200">
          {play.playDescription.trim() ? play.playDescription : <NullValue kind="unavailable" />}
        </p>
      </div>

      <div className="mt-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Diagnósticos</p>
        {play.diagnoses.length > 0 ? (
          <ul className="mt-2 flex flex-wrap gap-2">
            {play.diagnoses.map((diagnosis) => (
              <li
                className="flex flex-wrap items-center gap-2 rounded-md border border-slate-700 bg-slate-950 px-2.5 py-1.5 text-sm"
                key={`${diagnosis.label}-${diagnosis.source}`}
              >
                <span>{diagnosis.label}</span>
                <SourceTag source={diagnosis.source} />
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-1 text-sm"><NullValue kind="unavailable" /></p>
        )}
      </div>

      <button
        className="mt-5 self-start rounded-md border border-emerald-400 bg-emerald-950 px-3 py-2 text-sm font-semibold text-emerald-100 hover:bg-emerald-900"
        type="button"
        onClick={() => onOpen(play)}
      >
        Abrir detalle de tracking
      </button>
    </article>
  )
}

function EmptyCategory({ category }: { category: RepresentativePlayCategory }) {
  return (
    <article className="rounded-lg border border-dashed border-slate-600 bg-slate-900/70 p-4" data-print-section="true">
      <h3 className="text-base font-semibold text-emerald-300">{category}</h3>
      <p className="mt-3 text-sm text-slate-300">Sin ejemplos en la muestra.</p>
    </article>
  )
}

export function RepresentativePlays({ plays, onSelectPlay }: RepresentativePlaysProps) {
  const playsByCategory = useMemo(
    () => new Map(plays.map((play) => [play.category, play])),
    [plays],
  )

  return (
    <section aria-labelledby="representative-plays-title">
      <div className="mb-4 rounded-lg border border-emerald-700 bg-slate-900 p-4">
        <h2 id="representative-plays-title" className="text-lg font-semibold text-emerald-300">
          Jugadas representativas
        </h2>
        <p className="mt-2 text-sm text-slate-300">
          Cinco espacios de revisión seleccionados con reglas deterministas. Abre el tracking antes de validar el patrón en video.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {CATEGORIES.map((category) => {
          const play = playsByCategory.get(category)
          return play ? (
            <RepresentativePlayCard key={category} play={play} onOpen={onSelectPlay} />
          ) : (
            <EmptyCategory category={category} key={category} />
          )
        })}
      </div>
    </section>
  )
}

function sourceFor(detail: PlayDetailResponse, field: string): SourceLabel | null {
  return detail.fieldSources[field] ?? null
}

function contextValue(detail: PlayDetailResponse, field: string): string | number | boolean | null {
  const value = detail.context[field]
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return value
  return null
}

function DetailContext({ detail }: { detail: PlayDetailResponse }) {
  const contextFields = [
    ['down', 'Down'],
    ['yardsToGo', 'Distancia'],
    ['offenseFormation', 'Formación'],
    ['personnelD', 'Personal defensivo'],
    ['passRushers', 'Rushers'],
    ['passBlockers', 'Bloqueadores'],
    ['coverage', 'Cobertura'],
    ['timeToThrow', 'timeToThrow'],
    ['threatTime', 'Tiempo hasta amenaza'],
    ['passResult', 'Resultado de pase'],
    ['playResult', 'Yardas de resultado'],
  ] as const

  return (
    <div>
      <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-300">Contexto de la jugada</h3>
      <dl className="mt-2 grid grid-cols-2 gap-2 text-sm sm:grid-cols-3 lg:grid-cols-4">
        {contextFields.map(([field, label]) => {
          const value = contextValue(detail, field)
          const source = sourceFor(detail, field)
          const isTime = field === 'timeToThrow' || field === 'threatTime'
          return (
            <div className="rounded border border-slate-700 bg-slate-950 p-2" key={field}>
              <dt className="text-xs text-slate-400">{label}</dt>
              <dd className="mt-1 flex flex-wrap items-center gap-2 text-slate-100">
                <span>
                  {value === null ? (
                    <NullValue kind="unavailable" />
                  ) : isTime && typeof value === 'number' ? (
                    secs(value)
                  ) : typeof value === 'boolean' ? (
                    value ? 'Sí' : 'No'
                  ) : (
                    String(value)
                  )}
                </span>
                {source ? <SourceTag source={source} /> : null}
              </dd>
            </div>
          )
        })}
      </dl>
    </div>
  )
}

function normalizedRole(player: PlayerInfo | undefined, isBall: boolean): VisualRole {
  if (isBall) return 'ball'
  const role = `${player?.role ?? ''} ${player?.position ?? ''}`.toLocaleLowerCase('es')
  if (role.includes('chip') || role.includes('ayuda')) return 'chip'
  if (role.includes('pass rush')) return 'rusher'
  if (role.includes('pass block')) return 'blocker'
  if (role.includes('quarterback') || role.includes('qb') || player?.role === 'Pass') return 'quarterback'
  return 'other'
}

function frameIds(detail: PlayDetailResponse): number[] {
  const ids = new Set<number>()
  detail.trajectories.forEach((trajectory) => trajectory.points.forEach((point) => ids.add(point.frameId)))
  detail.events.forEach((event) => ids.add(event.frameId))
  if (detail.snapFrame !== null) ids.add(detail.snapFrame)
  if (detail.passFrame !== null) ids.add(detail.passFrame)
  if (detail.endFrame !== null) ids.add(detail.endFrame)
  return [...ids].sort((left, right) => left - right)
}

type ValidTrajectoryPoint = TrajectoryPoint & { x_norm: number; y_norm: number }

function validPoint(point: TrajectoryPoint): point is ValidTrajectoryPoint {
  return Number.isFinite(point.x_norm) && Number.isFinite(point.y_norm)
}

function currentPoint(trajectory: PlayerTrajectory, frameId: number): ValidTrajectoryPoint | null {
  const point = trajectory.points.find((candidate) => candidate.frameId === frameId)
  return point && validPoint(point) ? point : null
}

function trailPoints(trajectory: PlayerTrajectory, frameId: number): string {
  return trajectory.points
    .filter((point) => point.frameId <= frameId && validPoint(point))
    .map((point) => `${point.x_norm},${point.y_norm}`)
    .join(' ')
}

function PlayerShape({
  role,
  point,
}: {
  role: VisualRole
  point: TrajectoryPoint & { x_norm: number; y_norm: number }
}) {
  const { x_norm: x, y_norm: y } = point
  if (role === 'rusher') {
    return <polygon points={`${x},${y - 1.3} ${x - 1.25},${y + 1.1} ${x + 1.25},${y + 1.1}`} fill="#fb923c" stroke="#7c2d12" strokeWidth="0.35" />
  }
  if (role === 'blocker') {
    return <rect x={x - 1.05} y={y - 1.05} width="2.1" height="2.1" fill="#38bdf8" stroke="#082f49" strokeWidth="0.35" />
  }
  if (role === 'chip') {
    return <rect x={x - 1.05} y={y - 1.05} width="2.1" height="2.1" fill="#38bdf8" stroke="#e0f2fe" strokeDasharray="0.7 0.5" strokeWidth="0.5" />
  }
  if (role === 'quarterback') {
    return (
      <g>
        <circle cx={x} cy={y} r="1.25" fill="#f8fafc" stroke="#0f172a" strokeWidth="0.4" />
        <text x={x} y={y + 0.45} textAnchor="middle" fontSize="1.2" fontWeight="700" fill="#0f172a">QB</text>
      </g>
    )
  }
  if (role === 'ball') {
    return <polygon points={`${x},${y - 1.1} ${x + 0.85},${y} ${x},${y + 1.1} ${x - 0.85},${y}`} fill="#fbbf24" stroke="#422006" strokeWidth="0.4" />
  }
  return <circle cx={x} cy={y} r="0.85" fill="#94a3b8" stroke="#1e293b" strokeWidth="0.35" />
}

function FieldLegend() {
  const entries: Array<[VisualRole, string]> = [
    ['rusher', '▲'],
    ['blocker', '■'],
    ['chip', '▣ borde discontinuo'],
    ['quarterback', '● QB'],
    ['ball', '◆'],
    ['other', '●'],
  ]
  return (
    <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-2 text-xs text-slate-200" aria-label="Leyenda de jugadores">
      {entries.map(([role, symbol]) => (
        <li className="flex items-center gap-1.5" key={role}>
          <span className={role === 'rusher' ? 'text-orange-400' : role === 'blocker' || role === 'chip' ? 'text-sky-400' : 'text-slate-100'} aria-hidden="true">{symbol}</span>
          <span>{ROLE_LABELS[role]}</span>
        </li>
      ))}
    </ul>
  )
}

function EventList({ events, frameId }: { events: EventInfo[]; frameId: number }) {
  return (
    <div>
      <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-300">Eventos disponibles</h3>
      {events.length === 0 ? (
        <p className="mt-2 text-sm"><NullValue kind="unavailable" /></p>
      ) : (
        <ul className="mt-2 flex flex-wrap gap-2 text-xs">
          {events.map((event) => (
            <li
              className={`rounded border px-2 py-1 ${event.frameId === frameId ? 'border-orange-400 bg-orange-950 text-orange-100' : 'border-slate-600 bg-slate-950 text-slate-200'}`}
              key={`${event.frameId}-${event.event}`}
            >
              Cuadro {event.frameId}: {event.event}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function TrackingViewer({ detail }: { detail: PlayDetailResponse }) {
  const frames = useMemo(() => frameIds(detail), [detail])
  const initialFrame = detail.snapFrame ?? frames[0] ?? 0
  const [frameId, setFrameId] = useState(initialFrame)
  const playerById = useMemo(
    () => new Map(detail.players.map((player) => [player.nflId, player])),
    [detail.players],
  )
  const selectedIndex = Math.max(0, frames.indexOf(frameId))

  useEffect(() => setFrameId(initialFrame), [initialFrame])

  if (detail.trajectories.length === 0 || frames.length === 0) {
    return (
      <div className="rounded-lg border border-slate-700 bg-slate-950 p-4" role="status">
        <p className="font-semibold text-slate-100">Tracking no disponible</p>
        <p className="mt-1 text-sm text-slate-300">{detail.trajectoryReason ?? 'No hay trayectorias para esta jugada.'}</p>
      </div>
    )
  }

  return (
    <div>
      <div className="overflow-hidden rounded-lg border border-emerald-700 bg-emerald-950">
        <svg
          className="block h-auto w-full"
          viewBox="0 0 120 53.3"
          role="img"
          aria-label={`Campo normalizado en el cuadro ${frameId}`}
        >
          <rect width="120" height="53.3" fill="#064e3b" />
          <rect x="10" width="100" height="53.3" fill="#065f46" stroke="#d1fae5" strokeWidth="0.35" />
          {Array.from({ length: 11 }, (_, index) => index * 10 + 10).map((x) => (
            <line key={x} x1={x} x2={x} y1="0" y2="53.3" stroke="#a7f3d0" strokeWidth="0.16" opacity="0.75" />
          ))}
          <line x1="0" x2="120" y1="26.65" y2="26.65" stroke="#a7f3d0" strokeDasharray="1 1" strokeWidth="0.16" opacity="0.7" />

          {detail.trajectories.map((trajectory, index) => {
            const player = trajectory.nflId === null ? undefined : playerById.get(trajectory.nflId)
            const role = normalizedRole(player, trajectory.isBall)
            const point = currentPoint(trajectory, frameId)
            const trail = trailPoints(trajectory, frameId)
            const key = trajectory.isBall ? 'ball' : `${trajectory.nflId ?? 'unknown'}-${index}`
            return (
              <g key={key} aria-label={`${ROLE_LABELS[role]} ${player?.name ?? trajectory.nflId ?? ''}`.trim()}>
                {trail.includes(' ') ? (
                  <polyline
                    points={trail}
                    fill="none"
                    stroke={role === 'rusher' ? '#fdba74' : role === 'blocker' || role === 'chip' ? '#7dd3fc' : '#cbd5e1'}
                    strokeWidth="0.3"
                    opacity="0.55"
                  />
                ) : null}
                {point ? <PlayerShape role={role} point={point} /> : null}
              </g>
            )
          })}

          {detail.snapFrame === frameId ? <text x="2" y="4" fill="#f8fafc" fontSize="2.2" fontWeight="700">Cuadro_Snap</text> : null}
          {detail.passFrame === frameId ? <text x="2" y="7" fill="#fbbf24" fontSize="2.2" fontWeight="700">Cuadro_Pase</text> : null}
        </svg>
      </div>
      <FieldLegend />

      <div className="mt-4 rounded-md border border-slate-700 bg-slate-950 p-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <label className="font-semibold text-slate-100" htmlFor="tracking-frame">
            Cuadro {frameId}
          </label>
          <div className="flex flex-wrap gap-2 text-xs">
            <span className="rounded border border-slate-600 px-2 py-1">Snap: {detail.snapFrame ?? 'ausente'} ({detail.snapSource})</span>
            <span className="rounded border border-slate-600 px-2 py-1">Pase: {detail.passFrame ?? 'ausente'} ({detail.passSource})</span>
            <span className="rounded border border-slate-600 px-2 py-1">Fin: {detail.endFrame ?? 'ausente'}</span>
          </div>
        </div>
        <input
          id="tracking-frame"
          className="mt-3 w-full accent-orange-400"
          type="range"
          min={0}
          max={frames.length - 1}
          step={1}
          value={selectedIndex}
          onChange={(event) => setFrameId(frames[Number(event.currentTarget.value)])}
          aria-valuetext={`Cuadro ${frameId}`}
        />
      </div>

      <div className="mt-4">
        <EventList events={detail.events} frameId={frameId} />
      </div>
    </div>
  )
}

function DetailContent({ detail }: { detail: PlayDetailResponse }) {
  return (
    <div className="space-y-5">
      <p className="rounded-md border border-slate-700 bg-slate-950 p-3 text-sm leading-6 text-slate-200">
        {detail.playDescription.trim() ? detail.playDescription : <NullValue kind="unavailable" />}
      </p>
      <DetailContext detail={detail} />
      <TrackingViewer detail={detail} />
      <div>
        <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-300">Diagnósticos</h3>
        {detail.diagnoses.length > 0 ? (
          <ul className="mt-2 flex flex-wrap gap-2">
            {detail.diagnoses.map((diagnosis) => (
              <li className="flex items-center gap-2 rounded border border-slate-700 bg-slate-950 px-2.5 py-1.5 text-sm" key={`${diagnosis.label}-${diagnosis.source}`}>
                <span>{diagnosis.label}</span>
                <SourceTag source={diagnosis.source} />
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-sm"><NullValue kind="unavailable" /></p>
        )}
      </div>
      <div>
        <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-300">Jugadores PFF</h3>
        {detail.players.length > 0 ? (
          <ul className="mt-2 grid grid-cols-1 gap-2 text-sm sm:grid-cols-2 lg:grid-cols-3">
            {detail.players.map((player) => (
              <li className="rounded border border-slate-700 bg-slate-950 px-3 py-2" key={player.nflId}>
                <span className="font-semibold">{player.name ?? `nflId ${player.nflId}`}</span>
                <span className="mt-1 block text-slate-300">{player.position ?? 'posición no disponible'} · {player.role ?? 'rol no disponible'}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-sm"><NullValue kind="unavailable" /></p>
        )}
      </div>
    </div>
  )
}

export function PlayDetailModal({ play, onClose }: PlayDetailModalProps) {
  const [status, setStatus] = useState<DetailStatus>('loading')
  const [detail, setDetail] = useState<PlayDetailResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [requestVersion, setRequestVersion] = useState(0)

  useEffect(() => {
    let active = true
    setStatus('loading')
    setDetail(null)
    setError(null)

    void getPlay(play.gameId, play.playId)
      .then((response) => {
        if (!active) return
        setDetail(response)
        setStatus('ready')
      })
      .catch(() => {
        if (!active) return
        setError(`El detalle no está disponible para gameId=${play.gameId}, playId=${play.playId}.`)
        setStatus('error')
      })

    return () => {
      active = false
    }
  }, [play.gameId, play.playId, requestVersion])

  useEffect(() => {
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
  }, [onClose])

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-950/90 p-3 sm:p-6"
      role="dialog"
      aria-modal="true"
      aria-labelledby="play-detail-title"
    >
      <div className="my-auto w-full max-w-6xl rounded-xl border border-emerald-600 bg-slate-900 shadow-2xl">
        <div className="sticky top-0 z-10 flex items-center justify-between gap-4 rounded-t-xl border-b border-slate-700 bg-slate-900 px-4 py-3 sm:px-6">
          <div>
            <h2 id="play-detail-title" className="text-lg font-semibold text-emerald-300">Detalle de tracking</h2>
            <p className="text-sm text-slate-300">Partido {play.gameId} · jugada {play.playId}</p>
          </div>
          <button
            className="rounded-md border border-slate-500 px-3 py-2 text-sm font-semibold text-slate-100 hover:bg-slate-800"
            type="button"
            onClick={onClose}
          >
            Cerrar
          </button>
        </div>

        <div className="p-4 sm:p-6">
          {status === 'loading' ? <LoadingState message="Cargando detalle de tracking…" /> : null}
          {status === 'error' && error ? (
            <ErrorMessage
              title="Detalle no disponible"
              message={error}
              retryLabel="Reintentar detalle"
              onRetry={() => setRequestVersion((version) => version + 1)}
            />
          ) : null}
          {status === 'ready' && detail ? <DetailContent detail={detail} /> : null}
        </div>
      </div>
    </div>
  )
}
