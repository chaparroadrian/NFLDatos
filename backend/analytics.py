"""Pure analytical rules and JSON-safe conversion for PocketIQ.

This module intentionally contains no data loading or persistence.  The rules here are
small, deterministic building blocks used by the analytical engine in later tasks.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable, Mapping, Sequence
import copy
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import date, datetime
from enum import Enum
import json
import logging
import math
from pathlib import Path
import re
import threading
import unicodedata
from typing import Any

import numpy as np
import pandas as pd


TRACKING_COLUMNS = [
    "gameId",
    "playId",
    "nflId",
    "frameId",
    "team",
    "playDirection",
    "x",
    "y",
    "event",
]
TRACKING_DTYPES = {
    "gameId": "int64",
    "playId": "int32",
    "nflId": "float64",
    "frameId": "int16",
    "team": "category",
    "playDirection": "category",
    "x": "float32",
    "y": "float32",
    "event": "string",
}
THREAT_DISTANCE_YD = 2.0
STUNT_MIN_FRAMES = 3
STUNT_BLOCKER_MAX_DIST_YD = 3.0
CONTEXT_PERCENTILE = 75
CONTEXT_MIN_VALID = 10
QB_POCKET_LATERAL_MARGIN_YD = 1.0
QB_POCKET_DEFAULT_HALF_WIDTH_YD = 4.0
QB_POCKET_DEPTH_YD = 3.0
QB_CLOSING_MIN_YD = 1.0
LATERAL_SIGN = +1
RESULT_CACHE_MAX = 256

SOURCE_OBSERVED = "observada"
SOURCE_PFF = "PFF"
SOURCE_INFERRED = "inferida"
SOURCES = [SOURCE_OBSERVED, SOURCE_PFF, SOURCE_INFERRED]

SECTORS = [
    "Izquierda",
    "Interior izquierda",
    "Centro",
    "Interior derecha",
    "Derecha",
]
DIAGNOSES = [
    "Derrota individual",
    "Posible rusher libre",
    "Doble equipo",
    "Chip o ayuda",
    "Posible intercambio o stunt",
    "Posible presión prolongada por movimiento o retención del QB",
    "No determinado con los datos disponibles",
]
DIAGNOSIS_SOURCES = {
    "Derrota individual": SOURCE_PFF,
    "Posible rusher libre": SOURCE_INFERRED,
    "Doble equipo": SOURCE_PFF,
    "Chip o ayuda": SOURCE_PFF,
    "Posible intercambio o stunt": SOURCE_INFERRED,
    "Posible presión prolongada por movimiento o retención del QB": SOURCE_INFERRED,
    "No determinado con los datos disponibles": SOURCE_INFERRED,
}
DISTANCE_BANDS = ["Corta", "Media", "Larga", "Muy larga", "Conversión"]
FIELD_ZONES = [
    "Propio 1–20",
    "Propio 21–40",
    "Medio campo",
    "Territorio rival",
    "Zona roja",
    "Conversión de dos puntos",
]

FORBIDDEN_PHRASES = [
    "esta formación evita la presión",
    "el tackle causó el sack",
    "esta es la mejor jugada",
]
FORBIDDEN_WORDS = ["causa", "causó", "evita", "garantiza", "la mejor", "la peor"]
BLAME_WORDS = ["responsable", "culpable", "falló"]


def _is_missing(value: Any) -> bool:
    """Return whether a scalar value represents missing data."""

    if value is None:
        return True
    try:
        missing = pd.isna(value)
    except (TypeError, ValueError):
        return False
    return bool(missing) if isinstance(missing, (bool, np.bool_)) else False


def _finite_number(value: Any) -> float | None:
    """Convert a finite, non-boolean numeric scalar to float, otherwise return None."""

    if _is_missing(value) or isinstance(value, (bool, np.bool_)):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def distance_band(down: Any, yards_to_go: Any) -> str | None:
    """Classify yards to go, giving two-point conversions priority."""

    if down == 0:
        return "Conversión"
    yards = _finite_number(yards_to_go)
    if yards is None or yards < 1:
        return None
    if yards <= 3:
        return "Corta"
    if yards <= 6:
        return "Media"
    if yards <= 10:
        return "Larga"
    return "Muy larga"


def distance_to_endzone(
    yardline_number: Any, yardline_side: Any, possession_team: Any
) -> int | None:
    """Calculate distance to the opponent end zone from play-level field context."""

    number = _finite_number(yardline_number)
    if number is None or not number.is_integer():
        return None
    yardline = int(number)
    if yardline == 50:
        return 50
    if not 1 <= yardline <= 49 or _is_missing(yardline_side):
        return None
    return 100 - yardline if yardline_side == possession_team else yardline


def field_zone(down: Any, distance_to_goal: Any) -> str | None:
    """Classify field position from the offense's distance to the end zone."""

    if down == 0:
        return "Conversión de dos puntos"
    distance = _finite_number(distance_to_goal)
    if distance is None or not 1 <= distance <= 99:
        return None
    if distance >= 80:
        return "Propio 1–20"
    if distance >= 60:
        return "Propio 21–40"
    if distance >= 40:
        return "Medio campo"
    if distance >= 21:
        return "Territorio rival"
    return "Zona roja"


def sample_quality(n: int) -> str:
    """Return the approved sample-quality label for a nonnegative count."""

    if isinstance(n, (bool, np.bool_)) or not isinstance(n, (int, np.integer)) or n < 0:
        raise ValueError("n debe ser un entero mayor o igual a 0")
    if n >= 100:
        return "amplia"
    if n >= 30:
        return "moderada"
    if n >= 10:
        return "pequeña"
    return "insuficiente"


def safe_rate(numerator: int, denominator: int) -> float | None:
    """Divide valid counts, returning None for a zero denominator."""

    values = (numerator, denominator)
    if any(
        isinstance(value, (bool, np.bool_))
        or not isinstance(value, (int, np.integer))
        for value in values
    ):
        raise ValueError("numerador y denominador deben ser enteros")
    if denominator < 0 or numerator < 0:
        raise ValueError("los conteos deben ser mayores o iguales a 0")
    if denominator == 0:
        return None
    if numerator > denominator:
        raise ValueError("los conteos deben cumplir numerador <= denominador")
    return float(numerator / denominator)


def normalize_xy(x: Any, y: Any, play_direction: Any) -> tuple[float | None, float | None]:
    """Normalize coordinates so every offense moves toward increasing x."""

    x_value = _finite_number(x)
    y_value = _finite_number(y)
    if x_value is None or y_value is None:
        return None, None
    if play_direction == "right":
        return x_value, y_value
    if play_direction == "left":
        return 120.0 - x_value, 53.3 - y_value
    return None, None


def select_event_frame(
    ball_events: pd.DataFrame,
    manual: str,
    automatic: str,
) -> tuple[int | None, str]:
    """Choose the earliest exact manual event, then the earliest automatic event."""

    required = {"frameId", "event"}
    missing = required.difference(ball_events.columns)
    if missing:
        names = ", ".join(sorted(missing))
        raise ValueError(f"faltan columnas de eventos: {names}")

    for event_name, source in ((manual, "manual"), (automatic, "automática")):
        matching = ball_events.loc[ball_events["event"].eq(event_name), "frameId"]
        numeric = pd.to_numeric(matching, errors="coerce").dropna()
        if not numeric.empty:
            return int(numeric.min()), source
    return None, "ausente"


def time_to_throw(
    snap_frame: int | None, pass_frame: int | None
) -> tuple[float | None, str | None]:
    """Calculate time to throw at ten frames per second with an explicit null reason."""

    if _is_missing(snap_frame):
        return None, "sin snap"
    if _is_missing(pass_frame):
        return None, "sin pase"
    snap = int(snap_frame)  # frame identifiers are validated as integers at ingestion.
    pass_ = int(pass_frame)
    if pass_ <= snap:
        return None, "pase no posterior al snap"
    return round((pass_ - snap) / 10, 1), None


def sector_for(lateral_delta: float) -> str:
    """Map a finite lateral delta to exactly one ordered pressure sector."""

    delta = _finite_number(lateral_delta)
    if delta is None:
        raise ValueError("lateral_delta debe ser un número real finito")
    if delta >= 4.0:
        return "Izquierda"
    if delta >= 1.5:
        return "Interior izquierda"
    if delta > -1.5:
        return "Centro"
    if delta > -4.0:
        return "Interior derecha"
    return "Derecha"


def contextual_threshold(values: Sequence[float]) -> float | None:
    """Return the 75th percentile when at least ten finite values are available."""

    valid = [number for value in values if (number := _finite_number(value)) is not None]
    if len(valid) < CONTEXT_MIN_VALID:
        return None
    return float(np.percentile(valid, CONTEXT_PERCENTILE, method="linear"))


def _term_pattern(term: str) -> re.Pattern[str]:
    return re.compile(r"(?<!\w)" + re.escape(term) + r"(?!\w)")


def forbidden_language(text: str, include_blame: bool = False) -> bool:
    """Detect approved prohibited wording using case-insensitive whole terms."""

    normalized = unicodedata.normalize("NFC", text).casefold()
    terms = FORBIDDEN_PHRASES + FORBIDDEN_WORDS
    if include_blame:
        terms += BLAME_WORDS
    return any(_term_pattern(term).search(normalized) is not None for term in terms)


def _stable_sort_key(value: Any) -> tuple[str, str]:
    safe = json_safe(value)
    return type(safe).__name__, repr(safe)


def json_safe(obj: Any) -> Any:
    """Recursively convert pandas/numpy values into deterministic JSON-safe values."""

    if obj is None or isinstance(obj, (str, bool, int)):
        return obj
    if isinstance(obj, Enum):
        return json_safe(obj.value)
    if isinstance(obj, (float, np.floating)):
        value = float(obj)
        return value if math.isfinite(value) else None
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    if obj is pd.NA or obj is pd.NaT:
        return None
    if isinstance(obj, np.datetime64):
        return None if np.isnat(obj) else str(obj)
    if isinstance(obj, (pd.Timestamp, datetime, date)):
        return obj.isoformat()
    if isinstance(obj, np.ndarray):
        return [json_safe(value) for value in obj.tolist()]
    if isinstance(obj, Mapping):
        return {json_safe(key): json_safe(value) for key, value in obj.items()}
    if isinstance(obj, (set, frozenset)):
        return [json_safe(value) for value in sorted(obj, key=_stable_sort_key)]
    if isinstance(obj, (list, tuple)):
        return [json_safe(value) for value in obj]
    if _is_missing(obj):
        return None
    return obj


# Startup data loading -------------------------------------------------------


TrackingLoader = Callable[[int], pd.DataFrame]
TrackingProcessor = Callable[[pd.DataFrame, pd.DataFrame, pd.DataFrame], Any]


@dataclass(frozen=True)
class TrackingIngestionResult:
    """Per-game processor outputs and games omitted because tracking was unreadable."""

    processed: tuple[Any, ...]
    skipped_games: tuple[int, ...]


logger = logging.getLogger(__name__)

APPROVED_STARTUP_FILES = (
    "games.csv",
    "plays.csv",
    "players.csv",
    "pffScoutingData.csv",
)

REQUIRED_COLUMNS: dict[str, frozenset[str]] = {
    "games.csv": frozenset({"gameId", "week"}),
    "plays.csv": frozenset(
        {
            "gameId",
            "playId",
            "playDescription",
            "quarter",
            "gameClock",
            "down",
            "yardsToGo",
            "possessionTeam",
            "defensiveTeam",
            "yardlineSide",
            "yardlineNumber",
            "offenseFormation",
            "personnelO",
            "personnelD",
            "defendersInBox",
            "pff_playAction",
            "dropBackType",
            "pff_passCoverage",
            "pff_passCoverageType",
            "passResult",
            "prePenaltyPlayResult",
            "playResult",
        }
    ),
    "players.csv": frozenset({"nflId", "displayName", "officialPosition"}),
    "pffScoutingData.csv": frozenset(
        {
            "gameId",
            "playId",
            "nflId",
            "pff_role",
            "pff_positionLinedUp",
            "pff_hit",
            "pff_hurry",
            "pff_sack",
            "pff_beatenByDefender",
            "pff_hitAllowed",
            "pff_hurryAllowed",
            "pff_sackAllowed",
            "pff_nflIdBlockedPlayer",
            "pff_blockType",
        }
    ),
}

OFFENSIVE_PFF_ROLES = frozenset({"Pass Block", "Pass Route", "Pass"})
DEFENSIVE_PFF_ROLES = frozenset({"Pass Rush", "Coverage"})


class DataLoadError(RuntimeError):
    """Raised when an approved startup CSV cannot be loaded safely."""


class AnalysisError(RuntimeError):
    """Base error for analytical computations that cannot be completed."""


class TrackingComputationError(AnalysisError):
    """Raised when an opponent's tracking aggregation fails before commit."""


@dataclass(frozen=True)
class ValidationIssue:
    """A summarized non-fatal integrity issue."""

    check: str
    filename: str
    affected: int


class ValidationLog:
    """Collect and log at most one warning for each check/file pair."""

    def __init__(self) -> None:
        self._issues: dict[tuple[str, str], ValidationIssue] = {}

    @property
    def issues(self) -> tuple[ValidationIssue, ...]:
        return tuple(self._issues.values())

    def warn(self, check: str, filename: str | Path, affected: int) -> None:
        count = int(affected)
        if count <= 0:
            return
        safe_filename = Path(filename).name
        key = (check, safe_filename)
        if key in self._issues:
            return
        issue = ValidationIssue(check=check, filename=safe_filename, affected=count)
        self._issues[key] = issue
        logger.warning(
            "validacion=%s archivo=%s casos=%d",
            issue.check,
            issue.filename,
            issue.affected,
        )


def canonical_filter_key(filters: Any) -> str:
    """Return a stable JSON key for one normalized filter combination."""

    if hasattr(filters, "model_dump"):
        values = filters.model_dump()
    elif is_dataclass(filters) and not isinstance(filters, type):
        values = asdict(filters)
    elif isinstance(filters, Mapping):
        values = dict(filters)
    else:
        raise TypeError("los filtros deben ser un modelo, dataclass o mapping")
    return json.dumps(
        json_safe(values),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


# Short name retained for the analysis flow described by the design document.
canonical_key = canonical_filter_key


@dataclass(frozen=True)
class Engine:
    """Validated startup frames and their one-row-per-play analytical table."""

    games: pd.DataFrame
    plays: pd.DataFrame
    players: pd.DataFrame
    pff: pd.DataFrame
    plays_with_games: pd.DataFrame
    pff_with_players: pd.DataFrame
    analytical_table: pd.DataFrame
    invalid_role_play_keys: frozenset[tuple[Any, Any]]
    validation_log: ValidationLog
    tracking_loader: TrackingLoader | None = None
    _tracking_cache: dict[str, "OpponentTrackingCache"] = field(
        default_factory=dict, init=False, repr=False, compare=False
    )
    _opponent_locks: dict[str, threading.Lock] = field(
        default_factory=dict, init=False, repr=False, compare=False
    )
    _cache_state_lock: threading.Lock = field(
        default_factory=threading.Lock, init=False, repr=False, compare=False
    )
    _tracking_in_progress: set[str] = field(
        default_factory=set, init=False, repr=False, compare=False
    )
    _result_cache: OrderedDict[str, Any] = field(
        default_factory=OrderedDict, init=False, repr=False, compare=False
    )
    _result_cache_lock: threading.Lock = field(
        default_factory=threading.Lock, init=False, repr=False, compare=False
    )

    @property
    def base_table(self) -> pd.DataFrame:
        """Expose the approved base-table name used by later tracking tasks."""

        return self.analytical_table

    def ensure_rival(
        self,
        opponent: str,
        processor: TrackingProcessor | None = None,
    ) -> "OpponentTrackingCache":
        """Return a complete cached opponent aggregation, computing it once.

        A private lock per opponent serializes duplicate requests while allowing
        different opponents to be processed concurrently. All processor output stays
        local until every game finishes, so exceptions cannot expose partial state.
        """

        with self._cache_state_lock:
            cached = self._tracking_cache.get(opponent)
            if cached is not None:
                return cached
            opponent_lock = self._opponent_locks.setdefault(opponent, threading.Lock())

        with opponent_lock:
            with self._cache_state_lock:
                cached = self._tracking_cache.get(opponent)
                if cached is not None:
                    return cached
                self._tracking_in_progress.add(opponent)

            try:
                selected_processor = processor or process_game
                ingestion = self.ingest_opponent_tracking(opponent, selected_processor)
                complete = _combine_opponent_tracking(ingestion)
                with self._cache_state_lock:
                    self._tracking_cache[opponent] = complete
                return complete
            except Exception as exc:
                # A failed attempt never commits local aggregates. A later request may
                # acquire the same lock and retry from an empty opponent cache entry.
                with self._cache_state_lock:
                    self._tracking_cache.pop(opponent, None)
                if isinstance(exc, TrackingComputationError):
                    raise
                raise TrackingComputationError(
                    f"no se pudo completar el tracking del Rival {opponent}"
                ) from exc
            finally:
                with self._cache_state_lock:
                    self._tracking_in_progress.discard(opponent)

    def rival_status(self, opponent: str) -> dict[str, Any]:
        """Report cache readiness without loading or waiting for tracking."""

        with self._cache_state_lock:
            return {
                "opponent": opponent,
                "trackingReady": opponent in self._tracking_cache,
                "inProgress": opponent in self._tracking_in_progress,
            }

    def get_cached_result(self, filters: Any) -> Any | None:
        """Return an isolated deterministic result-cache hit, or None on a miss."""

        key = canonical_filter_key(filters)
        with self._result_cache_lock:
            if key not in self._result_cache:
                return None
            value = self._result_cache.pop(key)
            self._result_cache[key] = value
            return copy.deepcopy(value)

    def cache_result(self, filters: Any, result: Any) -> Any:
        """Store a completed result in the bounded in-memory LRU cache."""

        key = canonical_filter_key(filters)
        stored = copy.deepcopy(result)
        with self._result_cache_lock:
            self._result_cache.pop(key, None)
            self._result_cache[key] = stored
            while len(self._result_cache) > RESULT_CACHE_MAX:
                self._result_cache.popitem(last=False)
        return copy.deepcopy(stored)

    @property
    def result_cache_size(self) -> int:
        """Expose the bounded cache size for diagnostics and focused tests."""

        with self._result_cache_lock:
            return len(self._result_cache)

    def ingest_opponent_tracking(
        self,
        opponent: str,
        processor: TrackingProcessor,
    ) -> TrackingIngestionResult:
        """Read, validate, process, and release each defensive game in sequence.

        ``processor`` must return only derived per-play information. It is called before
        the raw frame is released, which lets later tasks build aggregates and clipped
        trajectories without retaining complete tracking files.
        """

        if self.tracking_loader is None:
            raise RuntimeError("no hay cargador de tracking configurado")

        opponent_plays = self.plays_with_games.loc[
            self.plays_with_games["defensiveTeam"].eq(opponent)
        ]
        game_ids = sorted(
            int(game_id)
            for game_id in opponent_plays["gameId"].dropna().unique().tolist()
        )
        processed: list[Any] = []
        skipped_games: list[int] = []

        for game_id in game_ids:
            filename = f"tracking_{game_id}.csv"
            game_plays = opponent_plays.loc[opponent_plays["gameId"].eq(game_id)].copy()
            play_ids = frozenset(game_plays["playId"].dropna().tolist())
            try:
                raw = self.tracking_loader(game_id)
                _validate_tracking_columns(raw)
            except (FileNotFoundError, OSError, ValueError, pd.errors.ParserError):
                skipped_games.append(game_id)
                continue

            try:
                rival_raw = raw.loc[
                    raw["gameId"].eq(game_id) & raw["playId"].isin(play_ids)
                ].copy()
                validated = _validate_tracking_frame(
                    rival_raw,
                    game_plays,
                    self.validation_log,
                    filename,
                )
                game_pff = self.pff_with_players.loc[
                    self.pff_with_players["gameId"].eq(game_id)
                    & self.pff_with_players["playId"].isin(play_ids)
                ].copy()
                processed.append(processor(validated, game_plays, game_pff))
            finally:
                # Do not retain a raw tracking DataFrame before loading the next game.
                del raw

        return TrackingIngestionResult(
            processed=tuple(processed),
            skipped_games=tuple(skipped_games),
        )

    @classmethod
    def from_frames(
        cls,
        games: pd.DataFrame,
        plays: pd.DataFrame,
        players: pd.DataFrame,
        pff: pd.DataFrame,
        tracking_loader: TrackingLoader | None = None,
    ) -> "Engine":
        """Validate in-memory startup frames using the same rules as CSV loading."""

        frames = {
            "games.csv": games.copy(),
            "plays.csv": plays.copy(),
            "players.csv": players.copy(),
            "pffScoutingData.csv": pff.copy(),
        }
        _validate_required_columns(frames)
        return _prepare_engine(frames, tracking_loader=tracking_loader)


def _validate_tracking_columns(frame: pd.DataFrame) -> None:
    """Reject an unreadable tracking frame that lacks an approved input column."""

    missing = sorted(set(TRACKING_COLUMNS).difference(frame.columns))
    if missing:
        raise ValueError(f"faltan columnas de tracking: {', '.join(missing)}")


def _validate_tracking_frame(
    frame: pd.DataFrame,
    plays_context: pd.DataFrame,
    validation_log: ValidationLog,
    filename: str,
) -> pd.DataFrame:
    """Apply row, frame, and play integrity checks to one opponent game."""

    if frame.empty:
        validated = frame.loc[:, TRACKING_COLUMNS].copy()
        validated["x_norm"] = pd.Series(dtype="float64")
        validated["y_norm"] = pd.Series(dtype="float64")
        return validated

    context = plays_context[
        ["gameId", "playId", "possessionTeam", "defensiveTeam"]
    ]
    joined = frame.loc[:, TRACKING_COLUMNS].merge(
        context,
        on=["gameId", "playId"],
        how="left",
        validate="many_to_one",
    )
    valid_team = (
        joined["team"].eq("football")
        | joined["team"].eq(joined["possessionTeam"])
        | joined["team"].eq(joined["defensiveTeam"])
    )
    validation_log.warn(
        "tracking_team_invalido", filename, int((~valid_team).sum())
    )
    joined = joined.loc[valid_team].drop(
        columns=["possessionTeam", "defensiveTeam"]
    )

    frame_keys = ["gameId", "playId", "frameId"]
    ball_counts = (
        joined.assign(_is_ball=joined["team"].eq("football").astype("int8"))
        .groupby(frame_keys, sort=False, dropna=False)["_is_ball"]
        .sum()
    )
    invalid_frames = ball_counts.loc[ball_counts.ne(1)]
    validation_log.warn(
        "tracking_balon_no_unico_por_cuadro", filename, len(invalid_frames)
    )
    if not invalid_frames.empty:
        invalid_index = pd.MultiIndex.from_tuples(
            invalid_frames.index.tolist(), names=frame_keys
        )
        row_index = pd.MultiIndex.from_frame(joined[frame_keys])
        joined = joined.loc[~row_index.isin(invalid_index)]

    directions = joined.groupby(
        ["gameId", "playId"], sort=False, dropna=False
    )["playDirection"]
    invalid_direction_keys: set[tuple[Any, Any]] = set()
    for play_key, values in directions:
        unique = set(values.dropna().tolist())
        if values.isna().any() or len(unique) != 1 or not unique.issubset({"left", "right"}):
            invalid_direction_keys.add(play_key)
    validation_log.warn(
        "playDirection_invalido", filename, len(invalid_direction_keys)
    )

    validated = joined.loc[:, TRACKING_COLUMNS].copy()
    validated["x_norm"] = np.nan
    validated["y_norm"] = np.nan
    if not validated.empty:
        keys = list(zip(validated["gameId"], validated["playId"], strict=True))
        spatially_valid = np.array(
            [key not in invalid_direction_keys for key in keys], dtype=bool
        )
        right = spatially_valid & validated["playDirection"].eq("right").to_numpy()
        left = spatially_valid & validated["playDirection"].eq("left").to_numpy()
        x = pd.to_numeric(validated["x"], errors="coerce")
        y = pd.to_numeric(validated["y"], errors="coerce")
        validated.loc[right, "x_norm"] = x.loc[right]
        validated.loc[right, "y_norm"] = y.loc[right]
        validated.loc[left, "x_norm"] = 120.0 - x.loc[left]
        validated.loc[left, "y_norm"] = 53.3 - y.loc[left]
    return validated.reset_index(drop=True)


def _validate_required_columns(frames: Mapping[str, pd.DataFrame]) -> None:
    for filename in APPROVED_STARTUP_FILES:
        frame = frames[filename]
        missing = sorted(REQUIRED_COLUMNS[filename].difference(frame.columns))
        if missing:
            columns = ", ".join(missing)
            raise DataLoadError(f"{filename}: faltan columnas requeridas: {columns}")


def _read_startup_csv(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path, keep_default_na=True)
    except (OSError, ValueError, pd.errors.ParserError) as exc:
        raise DataLoadError(f"{path.name}: no se pudo leer el archivo") from exc


def _tri_state_any(frame: pd.DataFrame, columns: Sequence[str]) -> bool | Any:
    """Return true/false/NA without turning an all-null source into false."""

    if frame.empty:
        return pd.NA
    source = frame.loc[:, list(columns)]
    if not source.notna().to_numpy().any():
        return pd.NA
    return bool(source.eq(1).to_numpy().any())


def _pff_play_aggregates(
    pff: pd.DataFrame,
    invalid_role_play_keys: frozenset[tuple[Any, Any]],
) -> pd.DataFrame:
    """Build deterministic PFF summaries for each play represented in PFF."""

    columns = [
        "gameId", "playId", "passRushers", "passBlockers", "hasPffPressure",
        "hasHurry", "hasHit", "hasSack", "hasBeatenBlocker",
        "hasOffensiveCharge", "blockTypes", "blockedIds", "dblTeam",
        "chipFlag", "beaten",
    ]
    records: list[dict[str, Any]] = []
    for (game_id, play_id), play_pff in pff.groupby(
        ["gameId", "playId"], sort=False, dropna=False
    ):
        rushers = play_pff.loc[play_pff["pff_role"].eq("Pass Rush")]
        blockers = play_pff.loc[play_pff["pff_role"].eq("Pass Block")]
        chips = play_pff.loc[
            play_pff["pff_role"].eq("Pass Route")
            & (
                play_pff["pff_blockType"].notna()
                | play_pff["pff_nflIdBlockedPlayer"].notna()
            )
        ]
        valid_roles = (game_id, play_id) not in invalid_role_play_keys

        blocker_targets = blockers["pff_nflIdBlockedPlayer"].dropna()
        blocked_ids = frozenset(
            pd.concat(
                [blocker_targets, chips["pff_nflIdBlockedPlayer"].dropna()],
                ignore_index=True,
            ).tolist()
        )
        block_types = frozenset(blockers["pff_blockType"].dropna().astype(str))
        blocker_failure_columns = (
            "pff_beatenByDefender",
            "pff_hitAllowed",
            "pff_hurryAllowed",
            "pff_sackAllowed",
        )

        records.append(
            {
                "gameId": game_id,
                "playId": play_id,
                "passRushers": len(rushers) if valid_roles else pd.NA,
                "passBlockers": len(blockers) if valid_roles else pd.NA,
                "hasPffPressure": _tri_state_any(
                    play_pff, ("pff_hit", "pff_hurry", "pff_sack")
                ),
                "hasHurry": _tri_state_any(play_pff, ("pff_hurry",)),
                "hasHit": _tri_state_any(play_pff, ("pff_hit",)),
                "hasSack": _tri_state_any(play_pff, ("pff_sack",)),
                "hasBeatenBlocker": _tri_state_any(
                    play_pff, ("pff_beatenByDefender",)
                ),
                "hasOffensiveCharge": _tri_state_any(
                    blockers,
                    ("pff_hitAllowed", "pff_hurryAllowed", "pff_sackAllowed"),
                ),
                "blockTypes": block_types,
                "blockedIds": blocked_ids,
                "dblTeam": bool(blocker_targets.duplicated(keep=False).any()),
                "chipFlag": bool(
                    play_pff["pff_blockType"].eq("CH").any() or not chips.empty
                ),
                "beaten": _tri_state_any(
                    blockers, blocker_failure_columns
                ) is True,
            }
        )
    return pd.DataFrame.from_records(records, columns=columns)


def _nullable_play_action(value: Any) -> bool | Any:
    if _is_missing(value):
        return pd.NA
    return bool(value == 1)


def _build_analytical_table(
    plays_with_games: pd.DataFrame,
    pff: pd.DataFrame,
    invalid_role_play_keys: frozenset[tuple[Any, Any]],
    validation_log: ValidationLog,
) -> pd.DataFrame:
    """Construct the startup table with one row per preserved play."""

    table = plays_with_games.copy()
    table["distanceBand"] = [
        distance_band(down, yards)
        for down, yards in zip(table["down"], table["yardsToGo"], strict=True)
    ]
    distances = [
        distance_to_endzone(number, side, team)
        for number, side, team in zip(
            table["yardlineNumber"],
            table["yardlineSide"],
            table["possessionTeam"],
            strict=True,
        )
    ]
    table["fieldZone"] = [
        field_zone(down, distance)
        for down, distance in zip(table["down"], distances, strict=True)
    ]

    non_conversion = ~table["down"].eq(0)
    invalid_distance = non_conversion & table["distanceBand"].isna()
    field_down = pd.to_numeric(table["down"], errors="coerce").between(1, 4)
    invalid_field = field_down & table["fieldZone"].isna()
    validation_log.warn(
        "yardsToGo_inconsistente", "plays.csv", int(invalid_distance.sum())
    )
    validation_log.warn(
        "fieldZone_sin_datos", "plays.csv", int(invalid_field.sum())
    )

    table["playAction"] = table["pff_playAction"].map(_nullable_play_action).astype(
        "boolean"
    )
    table["coverage"] = table["pff_passCoverage"]
    table["coverageType"] = table["pff_passCoverageType"]

    aggregates = _pff_play_aggregates(pff, invalid_role_play_keys)
    table = table.merge(
        aggregates,
        on=["gameId", "playId"],
        how="left",
        validate="one_to_one",
        indicator="_pff_join",
    )
    has_pff = table["_pff_join"].eq("both")
    table = table.drop(columns="_pff_join")

    table["passRushers"] = pd.array(table["passRushers"], dtype="Int64")
    table["passBlockers"] = pd.array(table["passBlockers"], dtype="Int64")
    for column in (
        "hasPffPressure", "hasHurry", "hasHit", "hasSack",
        "hasBeatenBlocker", "hasOffensiveCharge", "dblTeam", "chipFlag", "beaten",
    ):
        table[column] = pd.array(table[column], dtype="boolean")
    table["isApproximateBlitz"] = pd.array(
        [pd.NA if _is_missing(value) else int(value) >= 5 for value in table["passRushers"]],
        dtype="boolean",
    )
    table["blockTypes"] = [
        value if present else frozenset()
        for value, present in zip(table["blockTypes"], has_pff, strict=True)
    ]
    table["blockedIds"] = [
        value if present else frozenset()
        for value, present in zip(table["blockedIds"], has_pff, strict=True)
    ]

    nullable_integer_columns = ("snapFrame", "passFrame", "endFrame", "threatFrame")
    for column in nullable_integer_columns:
        table[column] = pd.array([pd.NA] * len(table), dtype="Int64")
    nullable_float_columns = (
        "timeToThrow", "threatTime", "minRusherDistance", "minDistanceTime",
        "threatRusherId", "lateralDelta",
    )
    for column in nullable_float_columns:
        table[column] = np.nan
    for column in (
        "snapSource", "passSource", "timeToThrowReason", "threatReason", "threatSide",
    ):
        table[column] = pd.NA
    table["staticDiagnoses"] = [
        _ordered_diagnoses(
            [
                "Derrota individual" if not _is_missing(beaten) and bool(beaten) else None,
                "Doble equipo" if not _is_missing(double) and bool(double) else None,
                "Chip o ayuda" if not _is_missing(chip) and bool(chip) else None,
            ]
        )
        for beaten, double, chip in zip(
            table["beaten"], table["dblTeam"], table["chipFlag"], strict=True
        )
    ]
    table["qbMovementFlag"] = pd.array([pd.NA] * len(table), dtype="boolean")
    table["pressureSourceCandidate"] = [
        diagnoses if diagnoses else ("No determinado con los datos disponibles",)
        for diagnoses in table["staticDiagnoses"]
    ]
    table["sampleQuality"] = pd.NA
    table["trackingStatus"] = "pendiente"

    # Keep the original sack result and the PFF sack flag as independent columns.
    # Downstream rates must derive from passResult and hasSack separately.
    return table.drop(
        columns=["pff_playAction", "pff_passCoverage", "pff_passCoverageType"]
    )


def _prepare_engine(
    frames: Mapping[str, pd.DataFrame],
    tracking_loader: Callable[[int], pd.DataFrame] | None = None,
) -> Engine:
    validation_log = ValidationLog()
    games = frames["games.csv"].copy()
    plays = frames["plays.csv"].copy()
    players = frames["players.csv"].copy()
    pff = frames["pffScoutingData.csv"].copy()

    duplicate_plays = plays.duplicated(["gameId", "playId"], keep="first")
    validation_log.warn(
        "plays_llave_duplicada", "plays.csv", int(duplicate_plays.sum())
    )
    plays = plays.loc[~duplicate_plays].copy()

    # These are the only startup joins: game context by gameId and player
    # attributes by nflId. Left joins preserve every play and every PFF row.
    try:
        plays_with_games = plays.merge(
            games[["gameId", "week"]],
            on="gameId",
            how="left",
            validate="many_to_one",
        )
        pff_with_players = pff.merge(
            players[["nflId", "displayName", "officialPosition"]],
            on="nflId",
            how="left",
            validate="many_to_one",
            indicator="_player_join",
        )
    except pd.errors.MergeError as exc:
        raise DataLoadError("las llaves de identificación aprobadas no son únicas") from exc

    unknown_player_rows = pff_with_players["_player_join"].eq("left_only")
    pff_with_players = pff_with_players.drop(columns="_player_join")
    validation_log.warn(
        "pff_nflId_sin_jugador",
        "pffScoutingData.csv",
        int(unknown_player_rows.sum()),
    )

    role_counts = (
        pff.assign(
            _offense=pff["pff_role"].isin(OFFENSIVE_PFF_ROLES).astype("int8"),
            _defense=pff["pff_role"].isin(DEFENSIVE_PFF_ROLES).astype("int8"),
        )
        .groupby(["gameId", "playId"], sort=False, dropna=False)[
            ["_offense", "_defense"]
        ]
        .sum()
    )
    invalid_roles = role_counts.loc[
        role_counts["_offense"].ne(11) | role_counts["_defense"].ne(11)
    ]
    invalid_role_play_keys = frozenset(invalid_roles.index.tolist())
    validation_log.warn(
        "pff_roles_no_11_11",
        "pffScoutingData.csv",
        len(invalid_role_play_keys),
    )

    analytical_table = _build_analytical_table(
        plays_with_games,
        pff,
        invalid_role_play_keys,
        validation_log,
    )

    return Engine(
        games=games,
        plays=plays,
        players=players,
        pff=pff,
        plays_with_games=plays_with_games,
        pff_with_players=pff_with_players,
        analytical_table=analytical_table,
        invalid_role_play_keys=invalid_role_play_keys,
        validation_log=validation_log,
        tracking_loader=tracking_loader,
    )


def _tracking_csv_loader(data_dir: Path) -> TrackingLoader:
    tracking_dir = data_dir / "tracking"

    def load(game_id: int) -> pd.DataFrame:
        return pd.read_csv(
            tracking_dir / f"tracking_{int(game_id)}.csv",
            usecols=TRACKING_COLUMNS,
            dtype=TRACKING_DTYPES,
        )

    return load


def load_engine(data_dir: Path) -> Engine:
    """Read each approved small CSV exactly once and prepare validated startup data."""

    root = Path(data_dir)
    frames: dict[str, pd.DataFrame] = {}
    for filename in APPROVED_STARTUP_FILES:
        path = root / filename
        if not path.is_file():
            raise DataLoadError(f"{filename}: archivo requerido no encontrado")
        frames[filename] = _read_startup_csv(path)
    _validate_required_columns(frames)
    return _prepare_engine(frames, tracking_loader=_tracking_csv_loader(root))


# Per-game tracking metrics -------------------------------------------------

from types import MappingProxyType


@dataclass(frozen=True)
class Trajectory:
    """Immutable dense normalized trajectory for every tracked object in a play."""

    nflIds: np.ndarray
    frameIds: np.ndarray
    x_norm: np.ndarray
    y_norm: np.ndarray

    def __post_init__(self) -> None:
        expected = (len(self.nflIds), len(self.frameIds))
        if self.x_norm.shape != expected or self.y_norm.shape != expected:
            raise ValueError("las matrices de trayectoria no coinciden con sus ejes")
        for array in (self.nflIds, self.frameIds, self.x_norm, self.y_norm):
            array.setflags(write=False)


@dataclass(frozen=True)
class ProcessedGameTracking:
    """Derived play aggregates and compact detail data for one tracking file."""

    aggregates: pd.DataFrame
    trajectories: Mapping[tuple[int, int], Trajectory]
    events: Mapping[tuple[int, int], tuple[tuple[int, str], ...]]

    def __post_init__(self) -> None:
        object.__setattr__(self, "trajectories", MappingProxyType(dict(self.trajectories)))
        object.__setattr__(self, "events", MappingProxyType(dict(self.events)))


@dataclass(frozen=True)
class OpponentTrackingCache:
    """Complete in-memory tracking state committed atomically for one opponent."""

    aggregates: pd.DataFrame
    trajectories: Mapping[tuple[int, int], Trajectory]
    events: Mapping[tuple[int, int], tuple[tuple[int, str], ...]]
    skipped_games: tuple[int, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "trajectories", MappingProxyType(dict(self.trajectories)))
        object.__setattr__(self, "events", MappingProxyType(dict(self.events)))


def _combine_opponent_tracking(
    ingestion: TrackingIngestionResult,
) -> OpponentTrackingCache:
    """Combine completed per-game outputs without mutating shared cache state."""

    aggregate_frames: list[pd.DataFrame] = []
    trajectories: dict[tuple[int, int], Trajectory] = {}
    events: dict[tuple[int, int], tuple[tuple[int, str], ...]] = {}
    for processed in ingestion.processed:
        if not isinstance(processed, ProcessedGameTracking):
            raise TypeError("el procesador de tracking devolvió un resultado no válido")
        aggregate_frames.append(processed.aggregates.copy(deep=True))
        trajectories.update(processed.trajectories)
        events.update(processed.events)

    if aggregate_frames:
        aggregates = pd.concat(aggregate_frames, ignore_index=True)
        aggregates = aggregates.sort_values(
            ["gameId", "playId"], kind="stable"
        ).reset_index(drop=True)
    else:
        aggregates = pd.DataFrame(columns=TRACKING_AGGREGATE_COLUMNS)
    return OpponentTrackingCache(
        aggregates=aggregates,
        trajectories=trajectories,
        events=events,
        skipped_games=tuple(sorted(ingestion.skipped_games)),
    )


TRACKING_AGGREGATE_COLUMNS = (
    "gameId",
    "playId",
    "snapFrame",
    "passFrame",
    "endFrame",
    "snapSource",
    "passSource",
    "timeToThrow",
    "timeToThrowReason",
    "threatFrame",
    "threatTime",
    "threatReason",
    "minRusherDistance",
    "minDistanceTime",
    "threatRusherId",
    "lateralDelta",
    "threatSide",
    "staticDiagnoses",
    "qbMovementFlag",
    "trackingStatus",
)


def _present_events(play_tracking: pd.DataFrame) -> tuple[tuple[int, str], ...]:
    """Return non-empty ball events once, in stable frame/name order."""

    ball = play_tracking.loc[play_tracking["team"].eq("football"), ["frameId", "event"]]
    rows: list[tuple[int, str]] = []
    for frame_id, event in ball.itertuples(index=False, name=None):
        if _is_missing(event):
            continue
        name = str(event)
        if name == "None":
            continue
        number = _finite_number(frame_id)
        if number is not None and number.is_integer():
            rows.append((int(number), name))
    return tuple(sorted(set(rows), key=lambda item: (item[0], item[1])))


def _evaluation_end(
    play_tracking: pd.DataFrame,
    pass_frame: int | None,
    events: tuple[tuple[int, str], ...],
) -> int | None:
    """Choose the earliest pass, sack, or final available tracking frame."""

    numeric_frames = pd.to_numeric(play_tracking["frameId"], errors="coerce").dropna()
    if numeric_frames.empty:
        return None
    candidates = [int(numeric_frames.max())]
    if pass_frame is not None:
        candidates.append(int(pass_frame))
    sack_frames = [
        frame_id
        for frame_id, event in events
        if event in {"qb_sack", "qb_strip_sack"}
    ]
    if sack_frames:
        candidates.append(min(sack_frames))
    return min(candidates)


def _object_id(row: pd.Series) -> int:
    return -1 if row["team"] == "football" else int(row["nflId"])


def _clipped_trajectory(
    play_tracking: pd.DataFrame,
    play_pff: pd.DataFrame,
    snap_frame: int | None,
    end_frame: int | None,
) -> Trajectory | None:
    """Create a dense, read-only trajectory clipped to the approved window bounds."""

    if snap_frame is None or end_frame is None or end_frame < snap_frame:
        return None
    clipped = play_tracking.loc[
        play_tracking["frameId"].between(snap_frame, end_frame, inclusive="both")
    ].copy()
    if clipped.empty:
        return None
    clipped["_objectId"] = clipped.apply(_object_id, axis=1)
    pff_ids = pd.to_numeric(play_pff.get("nflId", pd.Series(dtype=float)), errors="coerce")
    expected_ids = {-1, *(int(value) for value in pff_ids.dropna())}
    expected_ids.update(int(value) for value in clipped["_objectId"].unique())
    object_ids = np.array(sorted(expected_ids), dtype=np.int64)
    frame_ids = np.array(
        sorted(int(value) for value in clipped["frameId"].unique()), dtype=np.int16
    )
    shape = (len(object_ids), len(frame_ids))
    x_values = np.full(shape, np.nan, dtype=np.float32)
    y_values = np.full(shape, np.nan, dtype=np.float32)
    object_index = {value: index for index, value in enumerate(object_ids.tolist())}
    frame_index = {value: index for index, value in enumerate(frame_ids.tolist())}
    ordered = clipped.sort_values(["_objectId", "frameId"], kind="stable")
    for object_id, frame_id, x_norm, y_norm in ordered[
        ["_objectId", "frameId", "x_norm", "y_norm"]
    ].itertuples(index=False, name=None):
        i = object_index[int(object_id)]
        j = frame_index[int(frame_id)]
        x = _finite_number(x_norm)
        y = _finite_number(y_norm)
        x_values[i, j] = np.nan if x is None else x
        y_values[i, j] = np.nan if y is None else y
    return Trajectory(object_ids, frame_ids, x_values, y_values)


def _role_ids(play_pff: pd.DataFrame, role: str) -> tuple[int, ...]:
    values = pd.to_numeric(
        play_pff.loc[play_pff["pff_role"].eq(role), "nflId"], errors="coerce"
    ).dropna()
    return tuple(sorted({int(value) for value in values}))


def _ordered_diagnoses(labels: Sequence[str | None]) -> tuple[str, ...]:
    """Deduplicate approved diagnoses and return them in requirement order."""

    selected = {label for label in labels if label in DIAGNOSIS_SOURCES}
    selected.discard("No determinado con los datos disponibles")
    ordered = tuple(label for label in DIAGNOSES[:-1] if label in selected)
    return ordered


def diagnosis_tags(labels: Sequence[str]) -> tuple[tuple[str, str], ...]:
    """Attach the fixed cautious source label to each ordered diagnosis."""

    ordered = _ordered_diagnoses(labels)
    if not ordered:
        ordered = ("No determinado con los datos disponibles",)
    return tuple((label, DIAGNOSIS_SOURCES[label]) for label in ordered)


def compute_static_diagnoses(
    play_pff: pd.DataFrame,
    tracking_aggs: Mapping[str, Any] | pd.Series | None = None,
) -> list[tuple[str, str]]:
    """Compute ordered PFF and tracking diagnoses, without contextual pressure."""

    required = [
        "pff_role", "pff_blockType", "pff_nflIdBlockedPlayer",
        "pff_beatenByDefender", "pff_hitAllowed", "pff_hurryAllowed",
        "pff_sackAllowed",
    ]
    pff_values = play_pff.reindex(columns=required)
    blockers = pff_values.loc[pff_values["pff_role"].eq("Pass Block")]
    chips = pff_values.loc[
        pff_values["pff_role"].eq("Pass Route")
        & (
            pff_values["pff_blockType"].notna()
            | pff_values["pff_nflIdBlockedPlayer"].notna()
        )
    ]
    failure_columns = [
        "pff_beatenByDefender",
        "pff_hitAllowed",
        "pff_hurryAllowed",
        "pff_sackAllowed",
    ]
    beaten = bool(
        blockers.reindex(columns=failure_columns).fillna(0).eq(1).to_numpy().any()
    )
    targets = blockers.get("pff_nflIdBlockedPlayer", pd.Series(dtype=float)).dropna()
    double_team = bool(targets.duplicated(keep=False).any())
    block_types = pff_values["pff_blockType"]
    chip = bool(block_types.eq("CH").any() or not chips.empty)
    tracking = tracking_aggs if tracking_aggs is not None else {}
    free_rusher = bool(tracking.get("freeRusherFlag", False))
    stunt = bool(tracking.get("stuntFlag", False))
    labels = _ordered_diagnoses(
        [
            "Derrota individual" if beaten else None,
            "Posible rusher libre" if free_rusher else None,
            "Doble equipo" if double_team else None,
            "Chip o ayuda" if chip else None,
            "Posible intercambio o stunt" if stunt else None,
        ]
    )
    return list(diagnosis_tags(labels))


def _window_positions(
    play_tracking: pd.DataFrame,
    nfl_ids: Sequence[int],
    snap_frame: int,
    end_frame: int,
) -> pd.DataFrame:
    return play_tracking.loc[
        play_tracking["nflId"].isin(nfl_ids)
        & play_tracking["frameId"].gt(snap_frame)
        & play_tracking["frameId"].le(end_frame),
        ["frameId", "nflId", "x_norm", "y_norm"],
    ].dropna(subset=["frameId", "nflId", "x_norm", "y_norm"])


def _free_rusher_detected(
    play_tracking: pd.DataFrame,
    play_pff: pd.DataFrame,
    snap_frame: int | None,
    end_frame: int | None,
) -> bool:
    """Infer an unassigned rusher only when it reaches the QB within the window."""

    if snap_frame is None or end_frame is None:
        return False
    qb_ids = _role_ids(play_pff, "Pass")
    rusher_ids = _role_ids(play_pff, "Pass Rush")
    if not qb_ids or not rusher_ids:
        return False
    assignment_rows = play_pff.reindex(
        columns=["pff_role", "pff_nflIdBlockedPlayer"]
    )
    assigned = set(
        pd.to_numeric(
            assignment_rows.loc[
                assignment_rows["pff_role"].isin(["Pass Block", "Pass Route"]),
                "pff_nflIdBlockedPlayer",
            ],
            errors="coerce",
        ).dropna().astype(int)
    )
    unassigned = [rusher for rusher in rusher_ids if rusher not in assigned]
    if not unassigned:
        return False
    qb = _window_positions(play_tracking, (qb_ids[0],), snap_frame, end_frame)
    rushers = _window_positions(play_tracking, unassigned, snap_frame, end_frame)
    if qb.empty or rushers.empty:
        return False
    pairs = rushers.merge(qb, on="frameId", suffixes=("_r", "_q"))
    distances = np.hypot(
        pairs["x_norm_r"] - pairs["x_norm_q"],
        pairs["y_norm_r"] - pairs["y_norm_q"],
    )
    return bool(distances.le(THREAT_DISTANCE_YD).any())


def _stunt_detected(
    play_tracking: pd.DataFrame,
    play_pff: pd.DataFrame,
    snap_frame: int | None,
    end_frame: int | None,
) -> bool:
    """Detect a sustained adjacent-lineman handoff plus a rusher crossing."""

    if snap_frame is None or end_frame is None:
        return False
    rusher_ids = _role_ids(play_pff, "Pass Rush")
    pff_positions = play_pff.reindex(
        columns=["nflId", "pff_role", "pff_positionLinedUp"]
    )
    linemen = pff_positions.loc[
        pff_positions["pff_role"].eq("Pass Block")
        & pff_positions["pff_positionLinedUp"].isin(["LT", "LG", "C", "RG", "RT"]),
        ["nflId", "pff_positionLinedUp"],
    ].dropna()
    if len(rusher_ids) < 2 or linemen.empty:
        return False
    position_by_id = {
        int(nfl_id): str(position)
        for nfl_id, position in linemen.itertuples(index=False, name=None)
    }
    line_ids = tuple(sorted(position_by_id))
    rush = _window_positions(play_tracking, rusher_ids, snap_frame, end_frame)
    line = _window_positions(play_tracking, line_ids, snap_frame, end_frame)
    if rush.empty or line.empty:
        return False

    nearest: dict[tuple[int, int], int] = {}
    pairs = rush.merge(line, on="frameId", suffixes=("_r", "_b"))
    pairs["distance"] = np.hypot(
        pairs["x_norm_r"] - pairs["x_norm_b"],
        pairs["y_norm_r"] - pairs["y_norm_b"],
    )
    pairs = pairs.loc[pairs["distance"].le(STUNT_BLOCKER_MAX_DIST_YD)].sort_values(
        ["nflId_r", "frameId", "distance", "nflId_b"], kind="stable"
    )
    for (rusher, frame), group in pairs.groupby(["nflId_r", "frameId"], sort=False):
        nearest[(int(rusher), int(frame))] = int(group.iloc[0]["nflId_b"])

    y_by_rusher_frame = {
        (int(nfl_id), int(frame)): float(y)
        for frame, nfl_id, _x, y in rush.itertuples(index=False, name=None)
    }
    crossed: dict[tuple[int, int], bool] = {}
    for index, first in enumerate(rusher_ids):
        for second in rusher_ids[index + 1 :]:
            shared = sorted(
                frame for frame in range(snap_frame + 1, end_frame + 1)
                if (first, frame) in y_by_rusher_frame and (second, frame) in y_by_rusher_frame
            )
            initial_sign = 0
            for frame in shared:
                delta = y_by_rusher_frame[(first, frame)] - y_by_rusher_frame[(second, frame)]
                sign = int(np.sign(delta))
                if initial_sign == 0 and sign != 0:
                    initial_sign = sign
                crossed[(first, frame)] = initial_sign != 0 and sign == -initial_sign
                crossed[(second, frame)] = crossed[(first, frame)]

    adjacent = {frozenset(pair) for pair in [("LT", "LG"), ("LG", "C"), ("C", "RG"), ("RG", "RT")]}
    for rusher in rusher_ids:
        for frame in range(snap_frame + 2, end_frame - STUNT_MIN_FRAMES + 2):
            previous = nearest.get((rusher, frame - 1))
            current = nearest.get((rusher, frame))
            if previous is None or current is None or previous == current:
                continue
            if frozenset((position_by_id[previous], position_by_id[current])) not in adjacent:
                continue
            sustained_frames = range(frame, frame + STUNT_MIN_FRAMES)
            if all(
                nearest.get((rusher, sustained)) == current
                and crossed.get((rusher, sustained), False)
                for sustained in sustained_frames
            ):
                return True
    return False


def _qb_movement_flag(
    play_tracking: pd.DataFrame,
    play_pff: pd.DataFrame,
    snap_frame: int | None,
    threat_frame: int | None,
    threat_rusher_id: Any,
) -> bool | Any:
    """Evaluate the documented pocket-exit and QB-to-rusher closing heuristic."""

    rusher_number = _finite_number(threat_rusher_id)
    qb_ids = _role_ids(play_pff, "Pass")
    if snap_frame is None or threat_frame is None or rusher_number is None or not qb_ids:
        return pd.NA
    qb_id = qb_ids[0]
    qb = play_tracking.loc[
        play_tracking["nflId"].eq(qb_id)
        & play_tracking["frameId"].between(snap_frame, threat_frame),
        ["frameId", "x_norm", "y_norm"],
    ].dropna()
    if qb.empty or not qb["frameId"].eq(snap_frame).any():
        return pd.NA
    qb0 = qb.loc[qb["frameId"].eq(snap_frame)].sort_values("frameId").iloc[0]

    positions = play_pff.set_index("nflId").get("pff_positionLinedUp", pd.Series(dtype=object))
    snap_players = play_tracking.loc[play_tracking["frameId"].eq(snap_frame)]
    tackle_y: dict[str, float] = {}
    for player_id, position in positions.items():
        if position not in {"LT", "RT"}:
            continue
        row = snap_players.loc[snap_players["nflId"].eq(player_id), "y_norm"].dropna()
        if not row.empty:
            tackle_y[str(position)] = float(row.iloc[0])
    if {"LT", "RT"}.issubset(tackle_y):
        low = min(tackle_y.values()) - QB_POCKET_LATERAL_MARGIN_YD
        high = max(tackle_y.values()) + QB_POCKET_LATERAL_MARGIN_YD
    else:
        low = float(qb0["y_norm"]) - QB_POCKET_DEFAULT_HALF_WIDTH_YD
        high = float(qb0["y_norm"]) + QB_POCKET_DEFAULT_HALF_WIDTH_YD
    after_snap = qb.loc[qb["frameId"].gt(snap_frame)]
    left_pocket = bool(
        ((after_snap["y_norm"] < low) | (after_snap["y_norm"] > high)).any()
        or (after_snap["x_norm"] - float(qb0["x_norm"])).abs().gt(QB_POCKET_DEPTH_YD).any()
    )

    rusher = play_tracking.loc[
        play_tracking["nflId"].eq(int(rusher_number))
        & play_tracking["frameId"].eq(threat_frame),
        ["x_norm", "y_norm"],
    ].dropna()
    qb_threat = qb.loc[qb["frameId"].eq(threat_frame)]
    if rusher.empty or qb_threat.empty:
        return left_pocket
    r = rusher.iloc[0]
    q = qb_threat.iloc[0]
    start_distance = math.hypot(
        float(qb0["x_norm"]) - float(r["x_norm"]),
        float(qb0["y_norm"]) - float(r["y_norm"]),
    )
    end_distance = math.hypot(
        float(q["x_norm"]) - float(r["x_norm"]),
        float(q["y_norm"]) - float(r["y_norm"]),
    )
    return left_pocket or start_distance - end_distance >= QB_CLOSING_MIN_YD


def apply_contextual_diagnoses(
    table: pd.DataFrame,
) -> tuple[pd.DataFrame, float | None]:
    """Apply p75 prolonged-pressure logic to a filtered play sample."""

    result = table.copy()
    threshold = contextual_threshold(result.get("timeToThrow", pd.Series(dtype=float)))
    candidates: list[tuple[str, ...]] = []
    for _, row in result.iterrows():
        labels = list(row.get("staticDiagnoses", ()) or ())
        throw_time = _finite_number(row.get("timeToThrow"))
        threat_time = _finite_number(row.get("threatTime"))
        movement = row.get("qbMovementFlag", pd.NA)
        if (
            threshold is not None
            and throw_time is not None
            and threat_time is not None
            and throw_time > threshold
            and threat_time > threshold
            and "Derrota individual" not in labels
            and not _is_missing(movement)
            and bool(movement)
        ):
            labels.append("Posible presión prolongada por movimiento o retención del QB")
        ordered = _ordered_diagnoses(labels)
        candidates.append(ordered or ("No determinado con los datos disponibles",))
    result["pressureSourceCandidate"] = candidates
    return result, threshold


def _threat_metrics(
    play_tracking: pd.DataFrame,
    play_pff: pd.DataFrame,
    snap_frame: int | None,
    end_frame: int | None,
    spatially_valid: bool,
) -> dict[str, Any]:
    empty = {
        "threatFrame": pd.NA,
        "threatTime": np.nan,
        "minRusherDistance": np.nan,
        "minDistanceTime": np.nan,
        "threatRusherId": np.nan,
        "lateralDelta": np.nan,
        "threatSide": pd.NA,
    }
    if snap_frame is None:
        return {**empty, "threatReason": "sin snap"}
    qb_ids = _role_ids(play_pff, "Pass")
    if not qb_ids:
        return {**empty, "threatReason": "sin QB"}
    rusher_ids = _role_ids(play_pff, "Pass Rush")
    if not rusher_ids:
        return {**empty, "threatReason": "sin rusher"}
    if not spatially_valid or end_frame is None:
        return {**empty, "threatReason": "sin tracking"}

    window = play_tracking.loc[
        play_tracking["frameId"].gt(snap_frame)
        & play_tracking["frameId"].le(end_frame)
    ]
    qb = window.loc[window["nflId"].isin(qb_ids), ["frameId", "x_norm", "y_norm"]]
    # A valid PFF play has one QB. Choosing the lowest ID keeps malformed input stable.
    qb_rows = window.loc[window["nflId"].eq(qb_ids[0]), ["frameId", "x_norm", "y_norm"]]
    if qb_rows.empty and not qb.empty:
        qb_rows = qb.sort_values(["frameId"], kind="stable")
    rushers = window.loc[
        window["nflId"].isin(rusher_ids), ["frameId", "nflId", "x_norm", "y_norm"]
    ]
    distances = rushers.merge(qb_rows, on="frameId", suffixes=("_r", "_q"))
    for column in ("x_norm_r", "y_norm_r", "x_norm_q", "y_norm_q"):
        distances[column] = pd.to_numeric(distances[column], errors="coerce")
    distances = distances.dropna(
        subset=["x_norm_r", "y_norm_r", "x_norm_q", "y_norm_q", "nflId"]
    )
    if distances.empty:
        return {**empty, "threatReason": "sin amenaza"}
    distances["distance"] = np.hypot(
        distances["x_norm_r"] - distances["x_norm_q"],
        distances["y_norm_r"] - distances["y_norm_q"],
    )
    distances = distances.sort_values(
        ["frameId", "distance", "nflId"], kind="stable"
    )
    threatening = distances.loc[distances["distance"].le(THREAT_DISTANCE_YD)]
    if threatening.empty:
        nearest = distances.sort_values(
            ["distance", "frameId", "nflId"], kind="stable"
        ).iloc[0]
        return {
            **empty,
            "threatReason": "sin amenaza",
            "minRusherDistance": round(float(nearest["distance"]), 2),
            "minDistanceTime": round((int(nearest["frameId"]) - snap_frame) / 10, 1),
        }

    first_frame = int(threatening["frameId"].min())
    chosen = threatening.loc[threatening["frameId"].eq(first_frame)].sort_values(
        ["distance", "nflId"], kind="stable"
    ).iloc[0]
    lateral_delta = LATERAL_SIGN * float(chosen["y_norm_r"] - chosen["y_norm_q"])
    return {
        **empty,
        "threatFrame": first_frame,
        "threatTime": round((first_frame - snap_frame) / 10, 1),
        "threatReason": None,
        "threatRusherId": int(chosen["nflId"]),
        "lateralDelta": lateral_delta,
        "threatSide": sector_for(lateral_delta),
    }


def process_game(
    tracking: pd.DataFrame,
    plays_context: pd.DataFrame,
    pff_context: pd.DataFrame,
    validation_log: ValidationLog | None = None,
    filename: str | None = None,
) -> ProcessedGameTracking:
    """Derive task-3.2 metrics without retaining the raw tracking DataFrame."""

    missing = sorted(
        {"gameId", "playId", "nflId", "frameId", "team", "event", "x_norm", "y_norm"}
        .difference(tracking.columns)
    )
    if missing:
        raise ValueError(f"faltan columnas de tracking procesado: {', '.join(missing)}")

    records: list[dict[str, Any]] = []
    trajectories: dict[tuple[int, int], Trajectory] = {}
    event_map: dict[tuple[int, int], tuple[tuple[int, str], ...]] = {}
    invalid_times = 0
    default_filename = filename or "tracking_en_memoria.csv"

    ordered_plays = plays_context.sort_values(["gameId", "playId"], kind="stable")
    for play in ordered_plays[["gameId", "playId"]].itertuples(index=False):
        key = (int(play.gameId), int(play.playId))
        play_tracking = tracking.loc[
            tracking["gameId"].eq(play.gameId) & tracking["playId"].eq(play.playId)
        ]
        play_pff = pff_context.loc[
            pff_context["gameId"].eq(play.gameId)
            & pff_context["playId"].eq(play.playId)
        ]
        events = _present_events(play_tracking)
        event_map[key] = events
        ball_events = pd.DataFrame(events, columns=["frameId", "event"])
        snap_frame, snap_source = select_event_frame(
            ball_events, "ball_snap", "autoevent_ballsnap"
        )
        pass_frame, pass_source = select_event_frame(
            ball_events, "pass_forward", "autoevent_passforward"
        )
        throw_time, throw_reason = time_to_throw(snap_frame, pass_frame)
        if throw_reason == "pase no posterior al snap":
            invalid_times += 1
        end_frame = _evaluation_end(play_tracking, pass_frame, events)
        spatially_valid = bool(
            not play_tracking.empty
            and play_tracking[["x_norm", "y_norm"]].notna().any(axis=None)
        )
        metrics = _threat_metrics(
            play_tracking, play_pff, snap_frame, end_frame, spatially_valid
        )
        free_rusher = bool(
            spatially_valid
            and _free_rusher_detected(
                play_tracking, play_pff, snap_frame, end_frame
            )
        )
        stunt = bool(
            spatially_valid
            and _stunt_detected(play_tracking, play_pff, snap_frame, end_frame)
        )
        static_diagnoses = tuple(
            label
            for label, _source in compute_static_diagnoses(
                play_pff,
                {"freeRusherFlag": free_rusher, "stuntFlag": stunt},
            )
            if label != "No determinado con los datos disponibles"
        )
        movement_flag = _qb_movement_flag(
            play_tracking,
            play_pff,
            snap_frame,
            None if _is_missing(metrics["threatFrame"]) else int(metrics["threatFrame"]),
            metrics["threatRusherId"],
        )
        trajectory = _clipped_trajectory(
            play_tracking, play_pff, snap_frame, end_frame
        )
        if trajectory is not None:
            trajectories[key] = trajectory
        if play_tracking.empty:
            tracking_status = "sin tracking"
        elif not spatially_valid:
            tracking_status = "dirección inválida"
        else:
            tracking_status = "ok"
        records.append(
            {
                "gameId": key[0],
                "playId": key[1],
                "snapFrame": snap_frame,
                "passFrame": pass_frame,
                "endFrame": end_frame,
                "snapSource": snap_source,
                "passSource": pass_source,
                "timeToThrow": throw_time,
                "timeToThrowReason": throw_reason,
                **metrics,
                "staticDiagnoses": static_diagnoses,
                "qbMovementFlag": movement_flag,
                "trackingStatus": tracking_status,
            }
        )

    if validation_log is not None:
        validation_log.warn("tiempo_invalido", default_filename, invalid_times)
    aggregates = pd.DataFrame.from_records(records, columns=TRACKING_AGGREGATE_COLUMNS)
    return ProcessedGameTracking(aggregates, trajectories, event_map)


# Filtered analysis assembly ------------------------------------------------


@dataclass(frozen=True)
class NormalizedFilters:
    """Canonical, nullable filter values used by the analytical engine."""

    opponent: str
    down: int | None = None
    distanceBand: str | None = None
    exactDistance: int | None = None
    offenseFormation: str | None = None
    defensivePersonnel: str | None = None
    playAction: bool | None = None
    passBlockers: int | None = None
    fieldZone: str | None = None
    dropBackType: str | None = None
    coverage: str | None = None
    week: int | None = None


_FILTER_FIELDS = tuple(field_.name for field_ in NormalizedFilters.__dataclass_fields__.values())
_FILTER_COLUMNS = {
    "down": "down",
    "offenseFormation": "offenseFormation",
    "defensivePersonnel": "personnelD",
    "playAction": "playAction",
    "passBlockers": "passBlockers",
    "fieldZone": "fieldZone",
    "dropBackType": "dropBackType",
    "coverage": "coverage",
    "week": "week",
}
_FILTER_LABELS = {
    "opponent": "Rival",
    "down": "Down",
    "distanceBand": "Banda de distancia",
    "exactDistance": "Distancia exacta",
    "offenseFormation": "Formación ofensiva",
    "defensivePersonnel": "Personal defensivo",
    "playAction": "Play action",
    "passBlockers": "Número de bloqueadores",
    "fieldZone": "Zona del campo",
    "dropBackType": "Tipo de dropback",
    "coverage": "Cobertura ejecutada",
    "week": "Semana",
}
_SUMMARY_SOURCES = {
    "blitzRate": SOURCE_INFERRED,
    "averageRushers": SOURCE_PFF,
    "pffPressureRate": SOURCE_PFF,
    "hurryRate": SOURCE_PFF,
    "hitRate": SOURCE_PFF,
    "sackRate": SOURCE_OBSERVED,
    "pffSackRate": SOURCE_PFF,
    "averageThreatTime": SOURCE_INFERRED,
    "averageTimeToThrow": SOURCE_OBSERVED,
}


def _normalized_filters(filters: Any) -> NormalizedFilters:
    if isinstance(filters, NormalizedFilters):
        return filters
    if hasattr(filters, "model_dump"):
        values = filters.model_dump()
    elif is_dataclass(filters) and not isinstance(filters, type):
        values = asdict(filters)
    elif isinstance(filters, Mapping):
        values = dict(filters)
    else:
        raise TypeError("los filtros deben ser un modelo, dataclass o mapping")
    unknown = set(values).difference(_FILTER_FIELDS)
    if unknown:
        raise ValueError(f"filtros desconocidos: {', '.join(sorted(unknown))}")
    return NormalizedFilters(**{name: values.get(name) for name in _FILTER_FIELDS})


def _distinct_values(series: pd.Series, *, numeric: bool = False) -> list[Any]:
    values = [json_safe(value) for value in series.dropna().unique().tolist()]
    if numeric:
        return sorted(values)
    return sorted((str(value) for value in values), key=lambda value: value.casefold())


def _ordered_present(series: pd.Series, approved_order: Sequence[str]) -> list[str]:
    present = set(str(value) for value in series.dropna().unique())
    return [value for value in approved_order if value in present]


def _mean(series: pd.Series) -> float | None:
    values = pd.to_numeric(series, errors="coerce")
    values = values[np.isfinite(values)]
    return None if values.empty else float(values.mean())


def _boolean_rate(series: pd.Series) -> float | None:
    valid = series.dropna()
    if valid.empty:
        return None
    return safe_rate(int(valid.astype(bool).sum()), len(valid))


def _equals_rate(series: pd.Series, expected: Any) -> float | None:
    valid = series.dropna()
    if valid.empty:
        return None
    return safe_rate(int(valid.eq(expected).sum()), len(valid))


def _sample_info(n: int) -> dict[str, Any]:
    return {"n": int(n), "quality": sample_quality(int(n))}


def _sample_warning(n: int) -> str | None:
    if n >= 30:
        return None
    quality = sample_quality(n)
    if n == 0:
        return "Muestra insuficiente: no hay jugadas para los filtros seleccionados."
    return f"Muestra {quality}: interprete los resultados con cautela."


def _active_and_applied(filters: NormalizedFilters) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    values = asdict(filters)
    applied: dict[str, Any] = {}
    active: list[dict[str, Any]] = []
    for field_name in _FILTER_FIELDS:
        value = values[field_name]
        applied[field_name] = "Todos" if value is None else value
        if value is not None:
            active.append(
                {"field": field_name, "label": _FILTER_LABELS[field_name], "value": value}
            )
    return applied, active


def _merge_tracking_table(base: pd.DataFrame, tracking: OpponentTrackingCache) -> pd.DataFrame:
    """Overlay complete tracking aggregates while retaining skipped-game plays."""

    result = base.copy()
    aggregates = tracking.aggregates
    if not aggregates.empty:
        indexed = aggregates.set_index(["gameId", "playId"])
        keys = pd.MultiIndex.from_frame(result[["gameId", "playId"]])
        for column in TRACKING_AGGREGATE_COLUMNS[2:]:
            if column in indexed.columns:
                values = indexed[column].reindex(keys)
                values.index = result.index
                present = keys.isin(indexed.index)
                if column == "staticDiagnoses":
                    result.loc[present, column] = values.loc[present]
                else:
                    result.loc[present, column] = values.loc[present]
    if tracking.skipped_games:
        skipped = result["gameId"].isin(tracking.skipped_games)
        result.loc[skipped, "trackingStatus"] = "sin tracking"
        result.loc[skipped, "timeToThrowReason"] = "sin tracking"
        result.loc[skipped, "threatReason"] = "sin tracking"
    return result


def _filter_table(table: pd.DataFrame, filters: NormalizedFilters) -> pd.DataFrame:
    mask = table["defensiveTeam"].eq(filters.opponent)
    for field_name, column in _FILTER_COLUMNS.items():
        value = getattr(filters, field_name)
        if value is not None:
            mask &= table[column].notna() & table[column].eq(value)
    if filters.exactDistance is not None:
        mask &= (
            table["yardsToGo"].notna()
            & table["yardsToGo"].eq(filters.exactDistance)
            & table["down"].ne(0)
            & table["distanceBand"].notna()
        )
    elif filters.distanceBand is not None:
        mask &= table["distanceBand"].notna() & table["distanceBand"].eq(filters.distanceBand)
    return table.loc[mask].copy()


def _summary(sample: pd.DataFrame) -> dict[str, Any]:
    rushers = sample["passRushers"].dropna()
    pass_results = sample["passResult"].dropna()
    pff_sacks = sample["hasSack"].dropna()
    result_sacks = pass_results.eq("S")
    sack_rate = safe_rate(int(result_sacks.sum()), len(pass_results))
    pff_sack_rate = safe_rate(int(pff_sacks.astype(bool).sum()), len(pff_sacks))

    result_by_key = sample.set_index(["gameId", "playId"])["passResult"]
    pff_by_key = sample.set_index(["gameId", "playId"])["hasSack"]
    comparable = result_by_key.notna() & pff_by_key.notna()
    discrepant = int(
        (result_by_key.loc[comparable].eq("S") != pff_by_key.loc[comparable].astype(bool)).sum()
    )
    threat_n = int(pd.to_numeric(sample["threatTime"], errors="coerce").notna().sum())
    throw_n = int(pd.to_numeric(sample["timeToThrow"], errors="coerce").notna().sum())
    pressure_n = int(sample["hasPffPressure"].notna().sum())
    return {
        "text": "",
        "blitzRate": _boolean_rate(sample["isApproximateBlitz"]),
        "averageRushers": _mean(rushers),
        "pffPressureRate": _boolean_rate(sample["hasPffPressure"]),
        "hurryRate": _boolean_rate(sample["hasHurry"]),
        "hitRate": _boolean_rate(sample["hasHit"]),
        "sackRate": sack_rate,
        "pffSackRate": pff_sack_rate,
        "sackDiscrepancy": (
            {
                "resultRate": sack_rate,
                "pffRate": pff_sack_rate,
                "discrepantPlays": discrepant,
            }
            if discrepant
            else None
        ),
        "averageThreatTime": _mean(sample["threatTime"]),
        "averageTimeToThrow": _mean(sample["timeToThrow"]),
        "threatTimeSample": _sample_info(threat_n),
        "timeToThrowSample": _sample_info(throw_n),
        "pressureSample": _sample_info(pressure_n),
        "sources": dict(_SUMMARY_SOURCES),
    }


def _pressure_map(sample: pd.DataFrame) -> list[dict[str, Any]]:
    total = int(sample["threatSide"].notna().sum())
    rows: list[dict[str, Any]] = []
    for sector in SECTORS:
        subset = sample.loc[sample["threatSide"].eq(sector)]
        plays = len(subset)
        rows.append(
            {
                "sector": sector,
                "plays": plays,
                "share": 0.0 if total == 0 else float(plays / total),
                "averageThreatTime": _mean(subset["threatTime"]),
                "hurries": int(subset["hasHurry"].fillna(False).astype(bool).sum()),
                "hits": int(subset["hasHit"].fillna(False).astype(bool).sum()),
                "sacks": int(subset["hasSack"].fillna(False).astype(bool).sum()),
                "quality": sample_quality(plays),
            }
        )
    return rows


def _diagnosis_distribution(sample: pd.DataFrame) -> list[dict[str, Any]]:
    if sample.empty:
        return []
    n = len(sample)
    rows: list[dict[str, Any]] = []
    for label in DIAGNOSES:
        included = sample["pressureSourceCandidate"].map(
            lambda labels: label in labels if isinstance(labels, (tuple, list, set, frozenset)) else False
        )
        subset = sample.loc[included]
        threat_n = int(subset["threatTime"].notna().sum())
        rows.append(
            {
                "label": label,
                "source": DIAGNOSIS_SOURCES[label],
                "plays": len(subset),
                "share": float(len(subset) / n),
                "hurries": int(subset["hasHurry"].fillna(False).astype(bool).sum()),
                "hits": int(subset["hasHit"].fillna(False).astype(bool).sum()),
                "sacks": int(subset["hasSack"].fillna(False).astype(bool).sum()),
                "averageThreatTime": _mean(subset["threatTime"]),
                "threatTimeN": threat_n,
            }
        )
    return rows


def _rusher_distribution(sample: pd.DataFrame) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    valid = sample.loc[sample["passRushers"].notna()]
    if valid.empty:
        return [], None
    buckets = [
        {"rushers": int(rushers), "plays": int(count), "share": float(count / len(valid))}
        for rushers, count in valid.groupby("passRushers", sort=True).size().items()
    ]
    blitz_plays = int(valid["passRushers"].ge(5).sum())
    meta = {
        "buckets": buckets,
        "blitzPlays": blitz_plays,
        "blitzShare": safe_rate(blitz_plays, len(valid)),
        "sample": _sample_info(len(valid)),
    }
    return buckets, meta


def _category_distribution(sample: pd.DataFrame, column: str) -> list[dict[str, Any]]:
    valid = sample.loc[sample[column].notna(), column].astype(str)
    if valid.empty:
        return []
    counts = valid.value_counts(sort=False)
    ordered = sorted(counts.items(), key=lambda item: (-int(item[1]), str(item[0])))
    return [
        {"value": value, "plays": int(count), "share": float(count / len(sample))}
        for value, count in ordered
    ]


def _down_distance_distribution(sample: pd.DataFrame) -> list[dict[str, Any]]:
    valid = sample.loc[sample["down"].notna() & sample["distanceBand"].notna()]
    rows: list[dict[str, Any]] = []
    if valid.empty:
        return rows
    order = {value: index for index, value in enumerate(DISTANCE_BANDS)}
    for (down, band), subset in valid.groupby(["down", "distanceBand"], sort=False):
        rows.append(
            {
                "down": int(down),
                "distanceBand": str(band),
                "plays": len(subset),
                "pffPressureRate": _boolean_rate(subset["hasPffPressure"]),
            }
        )
    return sorted(rows, key=lambda row: (row["down"], order.get(row["distanceBand"], 999)))


_PROTECTION_DIMENSIONS = (
    ("offenseFormation", "Formación ofensiva", False),
    ("passBlockers", "Número de Bloqueadores", False),
    ("playAction", "Play action", False),
    ("dropBackType", "Tipo de dropback", False),
    ("blockType", "Tipo de bloqueo", True),
    ("personnelO", "Personal ofensivo", False),
)


def _protection_value(value: Any, dimension: str) -> str:
    """Return the approved display value for one protection alternative."""

    if dimension == "playAction":
        return "Play action" if bool(value) else "Convencional"
    safe = json_safe(value)
    return str(safe)


def _protection_alternative(
    subset: pd.DataFrame,
    value: str,
) -> dict[str, Any]:
    """Calculate outcomes with the alternative play count as each rate denominator."""

    plays = len(subset)
    return {
        "value": value,
        "plays": plays,
        "pffPressureRate": safe_rate(
            int(subset["hasPffPressure"].fillna(False).astype(bool).sum()), plays
        ),
        "sackRate": safe_rate(int(subset["passResult"].eq("S").sum()), plays),
        "averageThreatTime": _mean(subset["threatTime"]),
        "completionRate": safe_rate(int(subset["passResult"].eq("C").sum()), plays),
        "avgPrePenaltyYards": _mean(subset["prePenaltyPlayResult"]),
        "avgPlayResult": _mean(subset["playResult"]),
        "quality": sample_quality(plays),
    }


def _protection_responses(sample: pd.DataFrame) -> list[dict[str, Any]]:
    """Compare six protection dimensions without cross-dimension null exclusion."""

    if sample.empty:
        return []

    responses: list[dict[str, Any]] = []
    for dimension, label, multi_membership in _PROTECTION_DIMENSIONS:
        alternatives: list[dict[str, Any]] = []
        if dimension == "blockType":
            block_types = sorted(
                {
                    str(block_type)
                    for memberships in sample["blockTypes"]
                    if isinstance(memberships, (set, frozenset, tuple, list))
                    for block_type in memberships
                    if not _is_missing(block_type)
                },
                key=str.casefold,
            )
            for block_type in block_types:
                included = sample["blockTypes"].map(
                    lambda memberships: block_type in memberships
                    if isinstance(memberships, (set, frozenset, tuple, list))
                    else False
                )
                subset = sample.loc[included]
                alternatives.append(_protection_alternative(subset, block_type))
        else:
            valid = sample.loc[sample[dimension].notna()]
            grouped: list[tuple[str, pd.DataFrame]] = []
            for value, subset in valid.groupby(dimension, sort=False, dropna=True):
                grouped.append((_protection_value(value, dimension), subset))
            for value, subset in sorted(grouped, key=lambda item: item[0].casefold()):
                alternatives.append(_protection_alternative(subset, value))

        responses.append(
            {
                "dimension": dimension,
                "label": label,
                "multiMembership": multi_membership,
                "alternatives": alternatives,
            }
        )
    return responses


_REPRESENTATIVE_DIAGNOSIS_CATEGORY = (
    "Posible intercambio o stunt o Posible rusher libre"
)


def _play_key(row: pd.Series) -> tuple[int, int]:
    return int(row["gameId"]), int(row["playId"])


def _diagnoses_for_row(row: pd.Series) -> list[dict[str, str]]:
    labels = row.get("pressureSourceCandidate", ())
    if not isinstance(labels, (tuple, list, set, frozenset)):
        labels = ()
    return [
        {"label": label, "source": source}
        for label, source in diagnosis_tags(labels)
    ]


def _diagnosis_confidence(diagnoses: Sequence[Mapping[str, str]]) -> str:
    """Derive confidence solely from the sources of a play's diagnoses."""

    if (
        len(diagnoses) == 1
        and diagnoses[0]["label"] == "No determinado con los datos disponibles"
    ):
        return "bajo"
    sources = {diagnosis["source"] for diagnosis in diagnoses}
    if sources and sources.issubset({SOURCE_PFF, SOURCE_OBSERVED}):
        return "alto"
    if SOURCE_INFERRED in sources and sources.intersection({SOURCE_PFF, SOURCE_OBSERVED}):
        return "medio"
    return "bajo"


def _representative_record(category: str, row: pd.Series) -> dict[str, Any]:
    diagnoses = _diagnoses_for_row(row)
    return {
        "category": category,
        "gameId": int(row["gameId"]),
        "playId": int(row["playId"]),
        "week": int(row["week"]),
        "down": int(row["down"]),
        "yardsToGo": int(row["yardsToGo"]),
        "offenseFormation": json_safe(row.get("offenseFormation")),
        "personnelD": json_safe(row.get("personnelD")),
        "passRushers": json_safe(row.get("passRushers")),
        "passBlockers": json_safe(row.get("passBlockers")),
        "coverage": json_safe(row.get("coverage")),
        "timeToThrow": json_safe(row.get("timeToThrow")),
        "threatTime": json_safe(row.get("threatTime")),
        "passResult": json_safe(row.get("passResult")),
        "playResult": json_safe(row.get("playResult")),
        "playDescription": str(row.get("playDescription", "")),
        "diagnoses": diagnoses,
        "confidence": _diagnosis_confidence(diagnoses),
    }


def _nearest_to_median(sample: pd.DataFrame, column: str) -> pd.Series | None:
    valid = sample.loc[pd.to_numeric(sample[column], errors="coerce").notna()].copy()
    if valid.empty:
        return None
    values = pd.to_numeric(valid[column], errors="coerce")
    median = float(values.median())
    valid["_representativeDistance"] = (values - median).abs()
    return valid.sort_values(
        ["_representativeDistance", "gameId", "playId"], kind="stable"
    ).iloc[0]


def _representative_plays(sample: pd.DataFrame) -> list[dict[str, Any]]:
    """Select at most one play per approved category using design A8."""

    if sample.empty:
        return []
    ordered = sample.sort_values(["gameId", "playId"], kind="stable")
    selected: list[tuple[str, pd.Series]] = []

    typical = _nearest_to_median(ordered, "threatTime")
    if typical is None:
        typical = _nearest_to_median(ordered, "timeToThrow")
    if typical is not None:
        selected.append(("típica", typical))

    threats = ordered.loc[pd.to_numeric(ordered["threatTime"], errors="coerce").notna()].copy()
    if not threats.empty:
        threats["_value"] = pd.to_numeric(threats["threatTime"], errors="coerce")
        early = threats.sort_values(["_value", "gameId", "playId"], kind="stable").iloc[0]
        selected.append(("amenaza temprana", early))

    sacks = ordered.loc[ordered["passResult"].eq("S")].copy()
    if not sacks.empty:
        sacks["_missing"] = pd.to_numeric(sacks["threatTime"], errors="coerce").isna()
        sacks["_value"] = pd.to_numeric(sacks["threatTime"], errors="coerce")
        sack = sacks.sort_values(
            ["_missing", "_value", "gameId", "playId"], kind="stable", na_position="last"
        ).iloc[0]
        selected.append(("sack", sack))

    successful = ordered.loc[
        ordered["hasPffPressure"].eq(False) & ordered["passResult"].eq("C")
    ].copy()
    if not successful.empty:
        successful["_missing"] = pd.to_numeric(
            successful["timeToThrow"], errors="coerce"
        ).isna()
        successful["_value"] = pd.to_numeric(
            successful["timeToThrow"], errors="coerce"
        )
        comparable = successful.sort_values(
            ["_missing", "_value", "gameId", "playId"],
            ascending=[True, False, True, True],
            kind="stable",
            na_position="last",
        ).iloc[0]
        selected.append(("protección exitosa comparable", comparable))

    diagnostic = ordered.loc[
        ordered["pressureSourceCandidate"].map(
            lambda labels: isinstance(labels, (tuple, list, set, frozenset))
            and bool(
                {"Posible intercambio o stunt", "Posible rusher libre"}.intersection(labels)
            )
        )
    ]
    if not diagnostic.empty:
        selected.append((_REPRESENTATIVE_DIAGNOSIS_CATEGORY, diagnostic.iloc[0]))

    return [_representative_record(category, row) for category, row in selected]


def _percent_text(value: Any) -> str:
    number = _finite_number(value)
    return "sin datos" if number is None else f"{number * 100:.1f}%"


def summary_text(result_fields: Mapping[str, Any], opponent: str) -> str:
    """Build the stable Spanish executive summary from calculated result fields."""

    sample = result_fields.get("sample", {})
    n = int(sample.get("plays", 0))
    if n == 0:
        return f"No hay jugadas comparables contra {opponent} con los filtros activos."

    summary = result_fields.get("summary", {})
    pressure_map = result_fields.get("pressureMap", [])
    diagnoses = result_fields.get("diagnoses", [])
    quality = str(sample.get("quality", sample_quality(n)))
    blitz = _percent_text(summary.get("blitzRate"))
    sentences = [
        f"En {n} jugadas de pase contra {opponent}, la defensa envió cinco o más "
        f"rushers (blitz aproximado) en el {blitz} de las jugadas."
    ]

    threat_time = _finite_number(summary.get("averageThreatTime"))
    available_sectors = [
        row for row in pressure_map if int(row.get("plays", 0)) > 0
    ]
    if threat_time is None:
        sentences.append("No se detectó amenaza por proximidad en esta muestra.")
    elif not available_sectors:
        sentences.append(
            "No se clasificó un Sector de amenaza por proximidad en esta muestra."
        )
    else:
        sector_order = {sector: index for index, sector in enumerate(SECTORS)}
        sector = min(
            available_sectors,
            key=lambda row: (
                -int(row.get("plays", 0)),
                sector_order.get(str(row.get("sector")), len(SECTORS)),
            ),
        )["sector"]
        sentences.append(
            "En esta muestra, la amenaza por proximidad entró con mayor frecuencia "
            f"por el sector {sector}, con un tiempo promedio hasta amenaza por "
            f"proximidad de {threat_time:.1f} s."
        )

    diagnosis_order = {label: index for index, label in enumerate(DIAGNOSES)}
    most_frequent = min(
        diagnoses,
        key=lambda row: (
            -int(row.get("plays", 0)),
            diagnosis_order.get(str(row.get("label")), len(DIAGNOSES)),
        ),
    )["label"]
    sentences.append(
        f"La posible fuente de presión más frecuente fue «{most_frequent}», "
        "que requiere validación en video."
    )
    sentences.append(f"Calidad de muestra: {quality} (n = {n}).")
    if n < 30:
        sentences.append(
            "La muestra es pequeña y debe interpretarse con cautela."
        )
    text = " ".join(sentences)
    if forbidden_language(text, include_blame=True):
        raise AnalysisError("el resumen determinista contiene lenguaje no permitido")
    return text


def _empty_analysis(filters: NormalizedFilters, skipped_games: int) -> dict[str, Any]:
    applied, active = _active_and_applied(filters)
    empty = pd.DataFrame(columns=Engine._analysis_columns())
    result = {
        "filtersApplied": applied,
        "activeFilters": active,
        "sample": {"plays": 0, "games": 0, "quality": "insuficiente", "warning": _sample_warning(0)},
        "trackingGamesSkipped": skipped_games,
        "contextualThreshold": None,
        "summary": _summary(empty),
        "pressureMap": _pressure_map(empty),
        "diagnoses": [],
        "rusherDistribution": [],
        "rusherDistributionMeta": None,
        "coverageDistribution": [],
        "personnelDistribution": [],
        "downDistanceDistribution": [],
        "protectionResponses": [],
        "representativePlays": [],
    }
    result["summary"]["text"] = summary_text(result, filters.opponent)
    return result


def _engine_analysis_columns() -> list[str]:
    return list(dict.fromkeys([*REQUIRED_COLUMNS["plays.csv"], "week", "distanceBand", "fieldZone", "playAction", "coverage", "coverageType", "passRushers", "passBlockers", "isApproximateBlitz", "hasPffPressure", "hasHurry", "hasHit", "hasSack", "timeToThrow", "threatTime", "threatSide", "pressureSourceCandidate"]))


def _engine_filters(self: Engine) -> dict[str, list[Any]]:
    table = self.analytical_table
    return json_safe(
        {
            "opponents": _distinct_values(table["defensiveTeam"]),
            "downs": _distinct_values(table["down"], numeric=True),
            "distanceBands": _ordered_present(table["distanceBand"], DISTANCE_BANDS),
            "offenseFormations": _distinct_values(table["offenseFormation"]),
            "defensivePersonnels": _distinct_values(table["personnelD"]),
            "blockerCounts": _distinct_values(table["passBlockers"], numeric=True),
            "fieldZones": _ordered_present(table["fieldZone"], FIELD_ZONES),
            "dropBackTypes": _distinct_values(table["dropBackType"]),
            "coverages": _distinct_values(table["coverage"]),
            "weeks": _distinct_values(table["week"], numeric=True),
        }
    )


def _engine_rival_table(self: Engine, opponent: str) -> tuple[pd.DataFrame, OpponentTrackingCache]:
    tracking = self.ensure_rival(opponent)
    base = self.analytical_table.loc[self.analytical_table["defensiveTeam"].eq(opponent)]
    return _merge_tracking_table(base, tracking), tracking


def _engine_analyze(self: Engine, filters: Any) -> dict[str, Any]:
    normalized = _normalized_filters(filters)
    cached = self.get_cached_result(normalized)
    if cached is not None:
        return cached

    table, tracking = self.rival_table(normalized.opponent)
    sample = _filter_table(table, normalized)
    skipped_games = len(tracking.skipped_games)
    if sample.empty:
        return self.cache_result(normalized, json_safe(_empty_analysis(normalized, skipped_games)))

    sample, threshold = apply_contextual_diagnoses(sample)
    applied, active = _active_and_applied(normalized)
    n = len(sample)
    rusher_buckets, rusher_meta = _rusher_distribution(sample)
    result = {
        "filtersApplied": applied,
        "activeFilters": active,
        "sample": {
            "plays": n,
            "games": int(sample["gameId"].nunique()),
            "quality": sample_quality(n),
            "warning": _sample_warning(n),
        },
        "trackingGamesSkipped": skipped_games,
        "contextualThreshold": threshold,
        "summary": _summary(sample),
        "pressureMap": _pressure_map(sample),
        "diagnoses": _diagnosis_distribution(sample),
        "rusherDistribution": rusher_buckets,
        "rusherDistributionMeta": rusher_meta,
        "coverageDistribution": _category_distribution(sample, "coverage"),
        "personnelDistribution": _category_distribution(sample, "personnelD"),
        "downDistanceDistribution": _down_distance_distribution(sample),
        "protectionResponses": _protection_responses(sample),
        "representativePlays": _representative_plays(sample),
    }
    result["summary"]["text"] = summary_text(result, normalized.opponent)
    return self.cache_result(normalized, json_safe(result))


_PLAY_CONTEXT_COLUMNS = (
    "gameId", "playId", "week", "possessionTeam", "defensiveTeam", "quarter",
    "gameClock", "down", "yardsToGo", "distanceBand", "fieldZone",
    "offenseFormation", "personnelO", "personnelD", "defendersInBox",
    "playAction", "dropBackType", "coverage", "coverageType", "passResult",
    "prePenaltyPlayResult", "playResult", "passRushers", "passBlockers",
    "hasPffPressure", "hasHurry", "hasHit", "hasSack", "hasBeatenBlocker",
    "hasOffensiveCharge", "timeToThrow", "threatTime", "threatSide",
    "pressureSourceCandidate", "sampleQuality",
)
_PFF_DETAIL_FIELDS = {
    "passRushers", "passBlockers", "hasPffPressure", "hasHurry", "hasHit",
    "hasSack", "hasBeatenBlocker", "hasOffensiveCharge", "coverage", "coverageType",
}
_INFERRED_DETAIL_FIELDS = {
    "distanceBand", "fieldZone", "threatTime", "threatSide",
    "pressureSourceCandidate", "sampleQuality",
}


def _detail_source(field_name: str) -> str:
    if field_name in _PFF_DETAIL_FIELDS:
        return SOURCE_PFF
    if field_name in _INFERRED_DETAIL_FIELDS:
        return SOURCE_INFERRED
    return SOURCE_OBSERVED


def _detail_players(engine: Engine, game_id: int, play_id: int) -> list[dict[str, Any]]:
    rows = engine.pff_with_players.loc[
        engine.pff_with_players["gameId"].eq(game_id)
        & engine.pff_with_players["playId"].eq(play_id)
    ].copy()
    rows["_nflId"] = pd.to_numeric(rows["nflId"], errors="coerce")
    rows = rows.loc[rows["_nflId"].notna()].sort_values("_nflId", kind="stable")
    players: list[dict[str, Any]] = []
    seen: set[int] = set()
    for record in rows.to_dict("records"):
        nfl_id = int(record["_nflId"])
        if nfl_id in seen:
            continue
        seen.add(nfl_id)
        players.append(
            {
                "nflId": nfl_id,
                "name": json_safe(record.get("displayName")),
                "position": json_safe(record.get("officialPosition")),
                "role": json_safe(record.get("pff_role")),
            }
        )
    return players


def _detail_trajectories(
    trajectory: Trajectory | None,
    player_ids: set[int],
) -> list[dict[str, Any]]:
    if trajectory is None:
        return []
    rows: list[dict[str, Any]] = []
    for object_index, object_id_value in enumerate(trajectory.nflIds.tolist()):
        object_id = int(object_id_value)
        if object_id != -1 and object_id not in player_ids:
            continue
        points = [
            {
                "frameId": int(frame_id),
                "x_norm": json_safe(trajectory.x_norm[object_index, frame_index]),
                "y_norm": json_safe(trajectory.y_norm[object_index, frame_index]),
            }
            for frame_index, frame_id in enumerate(trajectory.frameIds.tolist())
        ]
        rows.append(
            {
                "nflId": None if object_id == -1 else object_id,
                "isBall": object_id == -1,
                "points": points,
            }
        )
    return sorted(rows, key=lambda row: (-1 if row["isBall"] else int(row["nflId"])))


def _engine_play_detail(
    self: Engine, game_id: int, play_id: int
) -> dict[str, Any] | None:
    """Build a source-labelled play detail, or return None for an unknown key."""

    matches = self.analytical_table.loc[
        self.analytical_table["gameId"].eq(game_id)
        & self.analytical_table["playId"].eq(play_id)
    ]
    if matches.empty:
        return None

    base_row = matches.iloc[0]
    opponent = str(base_row["defensiveTeam"])
    rival_table, tracking = self.rival_table(opponent)
    contextual, _threshold = apply_contextual_diagnoses(rival_table)
    detail_rows = contextual.loc[
        contextual["gameId"].eq(game_id) & contextual["playId"].eq(play_id)
    ]
    row = detail_rows.iloc[0]
    row = row.copy()
    row["sampleQuality"] = sample_quality(len(contextual))
    key = (int(game_id), int(play_id))
    players = _detail_players(self, *key)
    trajectory = tracking.trajectories.get(key)
    snap_frame = None if _is_missing(row.get("snapFrame")) else int(row["snapFrame"])
    pass_frame = None if _is_missing(row.get("passFrame")) else int(row["passFrame"])
    end_frame = None if _is_missing(row.get("endFrame")) else int(row["endFrame"])
    tracking_status = row.get("trackingStatus")
    if tracking_status == "sin tracking":
        trajectory_reason = "sin tracking"
    elif snap_frame is None:
        trajectory_reason = "sin snap"
    elif trajectory is None:
        trajectory_reason = "sin tracking"
    else:
        trajectory_reason = None

    context = {name: json_safe(row.get(name)) for name in _PLAY_CONTEXT_COLUMNS}
    events = [
        {"frameId": int(frame_id), "event": event}
        for frame_id, event in tracking.events.get(key, ())
    ]
    diagnoses = _diagnoses_for_row(row)
    return json_safe(
        {
            "context": context,
            "fieldSources": {name: _detail_source(name) for name in _PLAY_CONTEXT_COLUMNS},
            "playDescription": str(row.get("playDescription", "")),
            "players": players,
            "trajectories": _detail_trajectories(
                None if trajectory_reason is not None else trajectory,
                {player["nflId"] for player in players},
            ),
            "events": events,
            "snapFrame": snap_frame,
            "passFrame": pass_frame,
            "endFrame": end_frame,
            "snapSource": "ausente" if _is_missing(row.get("snapSource")) else row["snapSource"],
            "passSource": "ausente" if _is_missing(row.get("passSource")) else row["passSource"],
            "trajectoryReason": trajectory_reason,
            "diagnoses": diagnoses,
        }
    )


def _report_section(
    title: str,
    text: str,
    items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Create a deterministic section and enforce cautious local wording."""

    if forbidden_language(text, include_blame=True):
        raise AnalysisError("el reporte determinista contiene lenguaje no permitido")
    if items is not None and any(
        forbidden_language(str(item.get("text", "")), include_blame=True)
        for item in items
    ):
        raise AnalysisError("el reporte determinista contiene lenguaje no permitido")
    return {
        "title": title,
        "text": text,
        "items": items,
        "languageWarning": False,
    }


def _filters_from_result(result: Mapping[str, Any]) -> NormalizedFilters:
    applied = result.get("filtersApplied", {})
    values = {
        name: None if applied.get(name, "Todos") == "Todos" else applied.get(name)
        for name in _FILTER_FIELDS
    }
    return NormalizedFilters(**values)


def _alternative_subset(
    sample: pd.DataFrame,
    dimension: str,
    alternative: str,
) -> pd.DataFrame:
    """Return rows belonging to one rendered protection alternative."""

    if dimension == "blockType":
        included = sample["blockTypes"].map(
            lambda memberships: alternative in memberships
            if isinstance(memberships, (set, frozenset, tuple, list))
            else False
        )
        return sample.loc[included]
    valid = sample.loc[sample[dimension].notna()]
    rendered = valid[dimension].map(
        lambda value: _protection_value(value, dimension)
    )
    return valid.loc[rendered.eq(alternative)]


def _deterministic_recommendations(
    sample: pd.DataFrame,
    result: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Select one supported lowest-rate alternative per protection dimension."""

    recommendations: list[dict[str, Any]] = []
    for dimension in result.get("protectionResponses", []):
        alternatives = [
            alternative
            for alternative in dimension.get("alternatives", [])
            if _finite_number(alternative.get("pffPressureRate")) is not None
        ]
        if not alternatives:
            continue
        selected = min(
            alternatives,
            key=lambda alternative: (
                float(alternative["pffPressureRate"]),
                str(alternative["value"]).casefold(),
            ),
        )
        subset = _alternative_subset(
            sample, str(dimension["dimension"]), str(selected["value"])
        )
        if subset.empty or len(subset) != int(selected["plays"]):
            continue
        cited = subset.sort_values(["gameId", "playId"], kind="stable").iloc[0]
        plays = int(selected["plays"])
        quality = str(selected["quality"])
        label = (
            "recomendación" if plays >= 30 else "observación con muestra pequeña"
        )
        text = (
            f"En esta muestra, {dimension['label']} = {selected['value']} presentó "
            "menor tasa observada de evento defensivo PFF "
            f"({_percent_text(selected['pffPressureRate'])}, n = {plays})."
        )
        recommendations.append(
            {
                "text": text,
                "label": label,
                "dimension": str(dimension["dimension"]),
                "alternative": str(selected["value"]),
                "n": plays,
                "quality": quality,
                "citedPlays": [
                    {"gameId": int(cited["gameId"]), "playId": int(cited["playId"])}
                ],
            }
        )
    return recommendations


def _engine_scouting_report_deterministic(
    self: Engine,
    result: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the exact six-section scouting report without external services."""

    n = int(result.get("sample", {}).get("plays", 0))
    opponent = str(result.get("filtersApplied", {}).get("opponent", "el Rival"))
    if n == 0:
        return {
            "sections": [
                _report_section("Resumen de tendencias", ""),
                _report_section("Cómo entra la presión", ""),
                _report_section("Diagnóstico de protección", ""),
                _report_section("Recomendaciones ofensivas", "", []),
                _report_section("Jugadas comparables", "", []),
                _report_section(
                    "Limitaciones",
                    f"No hay jugadas comparables contra {opponent} con los filtros activos.",
                ),
            ]
        }

    filters = _filters_from_result(result)
    rival_table, _tracking = self.rival_table(filters.opponent)
    sample = _filter_table(rival_table, filters)
    sample, _threshold = apply_contextual_diagnoses(sample)

    sectors = sorted(
        (row for row in result.get("pressureMap", []) if int(row.get("plays", 0)) > 0),
        key=lambda row: (-int(row["plays"]), SECTORS.index(str(row["sector"]))),
    )
    if sectors:
        pressure_text = " ".join(
            f"{row['sector']}: {_percent_text(row['share'])} de las amenazas "
            f"(n = {row['plays']}), con tiempo promedio de "
            f"{float(row['averageThreatTime']):.1f} s."
            for row in sectors
        )
    else:
        pressure_text = "No se detectó amenaza por proximidad en esta muestra."

    diagnosis_rows = [
        row for row in result.get("diagnoses", []) if int(row.get("plays", 0)) > 0
    ]
    diagnosis_text = " ".join(
        f"{row['label']} ({row['source']}): n = {row['plays']}; posible fuente "
        "que requiere validación en video."
        for row in diagnosis_rows
    )
    recommendations = _deterministic_recommendations(sample, result)

    comparable_keys = {
        (int(play["gameId"]), int(play["playId"]))
        for play in result.get("representativePlays", [])
    }
    for recommendation in recommendations:
        comparable_keys.update(
            (int(play["gameId"]), int(play["playId"]))
            for play in recommendation["citedPlays"]
        )
    comparable = [
        {"gameId": game_id, "playId": play_id}
        for game_id, play_id in sorted(comparable_keys)
    ]
    quality = str(result["sample"]["quality"])
    limitations = (
        f"Calidad de muestra: {quality} (n = {n}). Los Diagnósticos con fuente "
        "inferida no son asignaciones confirmadas por el equipo ni por video y "
        "requiere validación en video. Elementos retirados: 0."
    )
    report = {
        "sections": [
            _report_section("Resumen de tendencias", str(result["summary"]["text"])),
            _report_section("Cómo entra la presión", pressure_text),
            _report_section("Diagnóstico de protección", diagnosis_text),
            _report_section("Recomendaciones ofensivas", "", recommendations),
            _report_section("Jugadas comparables", "", comparable),
            _report_section("Limitaciones", limitations),
        ]
    }
    return json_safe(report)


# Bind these cohesive analysis operations to the frozen startup-engine class without
# changing its already-stable dataclass field layout.
Engine._analysis_columns = staticmethod(_engine_analysis_columns)  # type: ignore[attr-defined]
Engine.filters = _engine_filters  # type: ignore[attr-defined]
Engine.rival_table = _engine_rival_table  # type: ignore[attr-defined]
Engine.analyze = _engine_analyze  # type: ignore[attr-defined]
Engine.play_detail = _engine_play_detail  # type: ignore[attr-defined]
Engine.scouting_report_deterministic = _engine_scouting_report_deterministic  # type: ignore[attr-defined]
