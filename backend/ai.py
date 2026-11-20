"""Lazy Amazon Bedrock Converse infrastructure for PocketIQ.

The analytical engine calculates every value. This module sends only a compact,
source-labelled aggregate context to Amazon Nova and never creates a client at import.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
import json
import logging
import os
import threading
from typing import Any

import boto3
from botocore.config import Config

from backend.analytics import SOURCE_INFERRED, SOURCE_OBSERVED, json_safe


DEFAULT_MODEL_ID = "us.amazon.nova-pro-v1:0"
DEFAULT_REGION = "us-east-1"
DEFAULT_TIMEOUT_SECONDS = 30.0
MAX_CONVERSE_WORKERS = 4

logger = logging.getLogger(__name__)


class AIUnavailableError(RuntimeError):
    """Raised when Bedrock does not return a usable structured response."""


ClientFactory = Callable[[], Any]


def model_id() -> str:
    """Return the configured Nova model identifier or the approved default."""

    return os.environ.get("BEDROCK_MODEL_ID", DEFAULT_MODEL_ID)


def region() -> str:
    """Return the configured Bedrock region or the approved default."""

    return os.environ.get("AWS_REGION", DEFAULT_REGION)


def timeout_seconds() -> float:
    """Parse the total Converse timeout, accepting only values from 1 to 120."""

    raw = os.environ.get("AI_TIMEOUT_SECONDS")
    try:
        value = float(raw) if raw is not None else DEFAULT_TIMEOUT_SECONDS
    except (TypeError, ValueError, OverflowError):
        return DEFAULT_TIMEOUT_SECONDS
    return value if 1.0 <= value <= 120.0 else DEFAULT_TIMEOUT_SECONDS


def default_client_factory() -> Any:
    """Create the sole AWS client lazily, configured only for region and networking."""

    timeout = timeout_seconds()
    network_config = Config(
        connect_timeout=timeout,
        read_timeout=timeout,
        retries={"max_attempts": 1},
    )
    return boto3.client(
        "bedrock-runtime",
        region_name=region(),
        config=network_config,
    )


_client_factory: ClientFactory = default_client_factory
_executor: ThreadPoolExecutor | None = None
_executor_lock = threading.Lock()


def set_client_factory(factory: ClientFactory) -> None:
    """Replace the lazy client factory, primarily for deterministic tests."""

    if not callable(factory):
        raise TypeError("factory debe ser invocable")
    global _client_factory
    _client_factory = factory


def _get_executor() -> ThreadPoolExecutor:
    """Create the bounded worker pool only when the first AI request is made."""

    global _executor
    with _executor_lock:
        if _executor is None:
            _executor = ThreadPoolExecutor(
                max_workers=MAX_CONVERSE_WORKERS,
                thread_name_prefix="pocketiq-bedrock",
            )
        return _executor


def _extract_converse_text(response: Mapping[str, Any]) -> str:
    """Extract the first text block from a Bedrock Converse response."""

    try:
        content = response["output"]["message"]["content"]
        text = content[0]["text"]
    except (KeyError, IndexError, TypeError) as exc:
        raise AIUnavailableError("IA no disponible") from exc
    if not isinstance(text, str) or not text.strip():
        raise AIUnavailableError("IA no disponible")
    stripped = text.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 3:
            stripped = "\n".join(lines[1:-1]).strip()
    return stripped


def invoke_nova(system_prompt: str, context: Mapping[str, Any]) -> dict[str, Any]:
    """Make one bounded Converse call and decode its JSON object response."""

    timeout = timeout_seconds()
    try:
        client = _client_factory()
        future = _get_executor().submit(
            client.converse,
            modelId=model_id(),
            system=[{"text": system_prompt}],
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "text": json.dumps(
                                json_safe(dict(context)),
                                ensure_ascii=False,
                                allow_nan=False,
                                sort_keys=True,
                            )
                        }
                    ],
                }
            ],
            inferenceConfig={"maxTokens": 2000, "temperature": 0},
        )
        response = future.result(timeout=timeout)
        decoded = json.loads(_extract_converse_text(response))
        if not isinstance(decoded, dict):
            raise AIUnavailableError("IA no disponible")
        return decoded
    except FutureTimeoutError as exc:
        future.cancel()
        logger.warning("ia_no_disponible tipo=%s", type(exc).__name__)
        raise AIUnavailableError("IA no disponible") from exc
    except AIUnavailableError as exc:
        logger.warning("ia_no_disponible tipo=%s", type(exc).__name__)
        raise
    except Exception as exc:
        logger.warning("ia_no_disponible tipo=%s", type(exc).__name__)
        raise AIUnavailableError("IA no disponible") from exc


def _add_field(
    fields: dict[str, dict[str, Any]],
    path: str,
    value: Any,
    source: str,
) -> None:
    fields[path] = {"value": json_safe(value), "source": source}


def build_context(
    result: Mapping[str, Any],
    play: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Flatten one analysis result into the only payload permitted for Nova.

    The function deliberately selects aggregate output fields rather than copying the
    complete result or play detail. Raw trajectories, events, player rows, environment
    values, and file content therefore cannot enter the model payload.
    """

    fields: dict[str, dict[str, Any]] = {}
    sample = result.get("sample", {})
    if not isinstance(sample, Mapping):
        sample = {}
    for name in ("plays", "games", "quality"):
        _add_field(fields, f"sample.{name}", sample.get(name), SOURCE_OBSERVED)

    summary = result.get("summary", {})
    if not isinstance(summary, Mapping):
        summary = {}
    summary_sources = summary.get("sources", {})
    if not isinstance(summary_sources, Mapping):
        summary_sources = {}
    for name, source in summary_sources.items():
        if name in summary and source in {"observada", "PFF", "inferida"}:
            _add_field(fields, f"summary.{name}", summary[name], str(source))

    pressure_map = result.get("pressureMap", [])
    if isinstance(pressure_map, list):
        for row in pressure_map:
            if not isinstance(row, Mapping) or row.get("sector") is None:
                continue
            prefix = f"pressureMap.{row['sector']}"
            for name in ("plays", "share", "averageThreatTime", "hurries", "hits", "sacks"):
                _add_field(fields, f"{prefix}.{name}", row.get(name), SOURCE_INFERRED)

    diagnoses = result.get("diagnoses", [])
    if isinstance(diagnoses, list):
        for row in diagnoses:
            if not isinstance(row, Mapping) or row.get("label") is None:
                continue
            source = row.get("source")
            if source not in {"observada", "PFF", "inferida"}:
                continue
            prefix = f"diagnoses.{row['label']}"
            for name in ("plays", "share", "hurries", "hits", "sacks", "averageThreatTime"):
                _add_field(fields, f"{prefix}.{name}", row.get(name), str(source))

    protection = result.get("protectionResponses", [])
    if isinstance(protection, list):
        source_by_metric = {
            "plays": SOURCE_OBSERVED,
            "quality": SOURCE_OBSERVED,
            "pffPressureRate": "PFF",
            "sackRate": SOURCE_OBSERVED,
            "completionRate": SOURCE_OBSERVED,
            "avgPrePenaltyYards": SOURCE_OBSERVED,
            "avgPlayResult": SOURCE_OBSERVED,
            "averageThreatTime": SOURCE_INFERRED,
        }
        for dimension in protection:
            if not isinstance(dimension, Mapping) or dimension.get("dimension") is None:
                continue
            alternatives = dimension.get("alternatives", [])
            if not isinstance(alternatives, list):
                continue
            for alternative in alternatives:
                if not isinstance(alternative, Mapping) or alternative.get("value") is None:
                    continue
                prefix = (
                    f"protectionResponses.{dimension['dimension']}."
                    f"{alternative['value']}"
                )
                for name, source in source_by_metric.items():
                    _add_field(fields, f"{prefix}.{name}", alternative.get(name), source)

    if play is not None:
        play_context = play.get("context", {})
        play_sources = play.get("fieldSources", {})
        if isinstance(play_context, Mapping) and isinstance(play_sources, Mapping):
            for name, value in play_context.items():
                source = play_sources.get(name)
                if source in {"observada", "PFF", "inferida"}:
                    _add_field(fields, f"play.{name}", value, str(source))

    representative = []
    plays = result.get("representativePlays", [])
    if isinstance(plays, list):
        for row in plays:
            if not isinstance(row, Mapping):
                continue
            game_id = row.get("gameId")
            play_id = row.get("playId")
            if game_id is None or play_id is None:
                continue
            representative.append(
                {
                    "category": json_safe(row.get("category")),
                    "gameId": json_safe(game_id),
                    "playId": json_safe(play_id),
                }
            )

    filters = result.get("filtersApplied", {})
    return json_safe(
        {
            "filters": dict(filters) if isinstance(filters, Mapping) else {},
            "fields": fields,
            "representativePlays": representative,
            "play": None if play is None else {
                "included": True,
                "gameId": fields.get("play.gameId", {}).get("value"),
                "playId": fields.get("play.playId", {}).get("value"),
            },
        }
    )


# Structured trends and diagnosis flows -------------------------------------

from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN, ROUND_HALF_UP

from pydantic import ValidationError

from backend.analytics import forbidden_language
from backend.schemas import DiagnosisLLMOutput, TrendsLLMOutput


AI_UNAVAILABLE_REASON = (
    "El servicio de IA no respondió o devolvió una salida no válida."
)

TRENDS_PROMPT = """Eres un analista de tendencias de fútbol americano. Responde en español y solo con un objeto JSON con esta forma: {\"text\": \"...\", \"facts\": [{\"field\": \"ruta exacta\", \"value\": valor, \"source\": \"observada|PFF|inferida\", \"text\": \"...\"}]}. Usa como números únicamente valores presentes en fields y cita su ruta exacta. Describe relaciones solo como asociaciones observadas en esta muestra. No uses afirmaciones causales, superlativos ni estas expresiones: causa, causó, evita, garantiza, la mejor, la peor, esta formación evita la presión, el tackle causó el sack, esta es la mejor jugada."""

DIAGNOSIS_PROMPT = """Eres un asistente de diagnóstico de fútbol americano. Responde en español y solo con un objeto JSON con esta forma: {\"hechos\": [{\"text\": \"...\", \"field\": \"ruta exacta\", \"value\": valor, \"source\": \"observada|PFF|inferida\"}], \"hipotesis\": [{\"text\": \"...\"}]}. Clasifica como hecho solo una afirmación respaldada por un campo de fields y cita su ruta, valor y fuente. Clasifica como hipótesis toda explicación no confirmada por fields. Trata las inferencias como posibles o heurísticas. No atribuyas culpa definitiva a jugadores. No uses responsable, culpable, falló, causa, causó, evita, garantiza, la mejor ni la peor."""


class PlayNotFoundError(LookupError):
    """Raised when a requested diagnosis play does not exist."""

    def __init__(self, game_id: int, play_id: int) -> None:
        self.game_id = int(game_id)
        self.play_id = int(play_id)
        super().__init__(
            f"No existe la jugada gameId={self.game_id} playId={self.play_id}"
        )


def _unavailable_response() -> dict[str, Any]:
    """Return the sole public failure shape for trends and diagnosis."""

    return {
        "available": False,
        "status": "IA no disponible",
        "reason": AI_UNAVAILABLE_REASON,
    }


def _sample_from_result(result: Mapping[str, Any]) -> dict[str, Any]:
    sample = result.get("sample", {})
    return json_safe(dict(sample)) if isinstance(sample, Mapping) else {}


def _decimal_places(value: Any) -> int:
    try:
        exponent = Decimal(str(value)).as_tuple().exponent
    except (InvalidOperation, ValueError):
        return 0
    return max(0, -int(exponent))


def _finite_decimal(value: Any) -> Decimal | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        decimal = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return decimal if decimal.is_finite() else None


def _values_match(cited: Any, expected: Any) -> bool:
    """Apply exact, displayed-rounding, percentage, and normalized-text equality."""

    if expected is None:
        return cited is None
    if isinstance(expected, bool) or isinstance(cited, bool):
        return isinstance(expected, bool) and isinstance(cited, bool) and cited == expected

    cited_number = _finite_decimal(cited)
    expected_number = _finite_decimal(expected)
    if cited_number is not None and expected_number is not None:
        epsilon = Decimal("1e-9")
        if abs(cited_number - expected_number) <= epsilon:
            return True
        places = _decimal_places(cited)
        quantum = Decimal(1).scaleb(-places)
        rounded = {
            expected_number.quantize(quantum, rounding=ROUND_HALF_EVEN),
            expected_number.quantize(quantum, rounding=ROUND_HALF_UP),
        }
        if any(abs(cited_number - value) <= epsilon for value in rounded):
            return True
        tolerance = Decimal("0.5") * quantum + epsilon
        return abs(cited_number - expected_number * 100) < tolerance

    if isinstance(cited, str) and isinstance(expected, str):
        return cited.strip().casefold() == expected.strip().casefold()
    return cited == expected


def _context_field(
    context: Mapping[str, Any], field_name: str
) -> Mapping[str, Any] | None:
    fields = context.get("fields", {})
    if not isinstance(fields, Mapping):
        return None
    entry = fields.get(field_name)
    if not isinstance(entry, Mapping):
        return None
    if entry.get("source") not in {"observada", "PFF", "inferida"}:
        return None
    return entry


def validate_facts(
    facts: Any,
    context: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], int]:
    """Keep only context-backed facts and replace model-provided sources."""

    validated: list[dict[str, Any]] = []
    items = facts if isinstance(facts, list) else list(facts)
    for fact in items:
        values = fact.model_dump() if hasattr(fact, "model_dump") else dict(fact)
        entry = _context_field(context, str(values.get("field", "")))
        if entry is None or not _values_match(values.get("value"), entry.get("value")):
            continue
        values["source"] = entry["source"]
        validated.append(json_safe(values))
    return validated, len(items) - len(validated)


def validate_hechos_hipotesis(
    raw: DiagnosisLLMOutput,
    context: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Ground diagnosis facts and convert unsupported claims into hypotheses."""

    hechos: list[dict[str, Any]] = []
    hipotesis: list[dict[str, Any]] = []

    for hypothesis in raw.hipotesis:
        text = hypothesis.text
        hipotesis.append(
            {
                "text": text,
                "type": "hipótesis",
                "validation": "requiere validación en video",
                "unverified": False,
                "languageWarning": forbidden_language(text, include_blame=True),
            }
        )

    for fact in raw.hechos:
        values = fact.model_dump()
        entry = _context_field(context, fact.field)
        if entry is None or not _values_match(fact.value, entry.get("value")):
            text = fact.text
            hipotesis.append(
                {
                    "text": text,
                    "type": "hipótesis",
                    "validation": "requiere validación en video",
                    "unverified": True,
                    "languageWarning": forbidden_language(text, include_blame=True),
                }
            )
            continue

        source = str(entry["source"])
        text = fact.text
        normalized = text.casefold()
        if source == SOURCE_INFERRED and not any(
            marker in normalized for marker in ("posible", "heurística", "heuristica")
        ):
            text = f"Posible {text}"
        values.update(
            source=source,
            text=text,
            languageWarning=forbidden_language(text, include_blame=True),
        )
        hechos.append(json_safe(values))

    return hechos, hipotesis


def _trends_prompt(small_sample: bool) -> str:
    if not small_sample:
        return TRENDS_PROMPT
    return (
        TRENDS_PROMPT
        + " La muestra tiene menos de 30 jugadas: describe solo lo observado en esta "
        "muestra, no recomiendes una protección y no presentes una tendencia del Rival "
        "como segura."
    )


def trends(engine: Any, filters: Any) -> dict[str, Any]:
    """Analyze filters once and return a grounded structured trends response."""

    result = engine.analyze(filters)
    sample = _sample_from_result(result)
    plays = int(sample.get("plays", 0))
    opponent = str(result.get("filtersApplied", {}).get("opponent", "el Rival"))
    if plays == 0:
        return {
            "available": True,
            "modelId": None,
            "sample": sample,
            "text": f"No hay jugadas comparables contra {opponent} con los filtros activos.",
            "facts": [],
            "removedFacts": 0,
            "languageWarning": False,
            "smallSampleWarning": sample.get("warning"),
        }

    context = build_context(result)
    try:
        raw = TrendsLLMOutput.model_validate(
            invoke_nova(_trends_prompt(plays < 30), context)
        )
    except (AIUnavailableError, ValidationError, TypeError, ValueError):
        return _unavailable_response()

    facts, removed = validate_facts(raw.facts, context)
    return json_safe(
        {
            "available": True,
            "modelId": model_id(),
            "sample": sample,
            "text": raw.text,
            "facts": facts,
            "removedFacts": removed,
            "languageWarning": forbidden_language(raw.text),
            "smallSampleWarning": sample.get("warning") if plays < 30 else None,
        }
    )


def diagnosis(
    engine: Any,
    filters: Any,
    game_id: int | None = None,
    play_id: int | None = None,
) -> dict[str, Any]:
    """Return grounded facts and explicitly unverified diagnostic hypotheses."""

    if (game_id is None) != (play_id is None):
        raise ValueError("gameId y playId deben proporcionarse juntos")

    result = engine.analyze(filters)
    play: Mapping[str, Any] | None = None
    if game_id is not None and play_id is not None:
        detail = engine.play_detail(int(game_id), int(play_id))
        if detail is None:
            raise PlayNotFoundError(game_id, play_id)
        play = detail

    sample = _sample_from_result(result)
    if int(sample.get("plays", 0)) == 0:
        return {
            "available": True,
            "modelId": None,
            "sample": sample,
            "text": "No hay jugadas comparables con los filtros activos.",
            "hechos": [],
            "hipotesis": [],
        }

    context = build_context(result, play)
    try:
        raw = DiagnosisLLMOutput.model_validate(
            invoke_nova(DIAGNOSIS_PROMPT, context)
        )
    except (AIUnavailableError, ValidationError, TypeError, ValueError):
        return _unavailable_response()

    hechos, hipotesis = validate_hechos_hipotesis(raw, context)
    return json_safe(
        {
            "available": True,
            "modelId": model_id(),
            "sample": sample,
            "text": None,
            "hechos": hechos,
            "hipotesis": hipotesis,
        }
    )
