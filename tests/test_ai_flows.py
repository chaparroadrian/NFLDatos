"""Focused fake-client tests for task 6.2 AI validation flows."""

from __future__ import annotations

import json
from typing import Any

import pytest

from backend import ai


class FakeConverseClient:
    def __init__(self, payload: Any) -> None:
        self.payload = payload
        self.calls: list[dict[str, Any]] = []

    def converse(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        text = self.payload if isinstance(self.payload, str) else json.dumps(self.payload)
        return {"output": {"message": {"content": [{"text": text}]}}}


class FakeEngine:
    def __init__(self, result: dict[str, Any], play: dict[str, Any] | None = None) -> None:
        self.result = result
        self.play = play
        self.analysis_calls = 0
        self.detail_calls: list[tuple[int, int]] = []

    def analyze(self, _filters: Any) -> dict[str, Any]:
        self.analysis_calls += 1
        return self.result

    def play_detail(self, game_id: int, play_id: int) -> dict[str, Any] | None:
        self.detail_calls.append((game_id, play_id))
        return self.play


@pytest.fixture(autouse=True)
def restore_client_factory():
    yield
    ai.set_client_factory(ai.default_client_factory)


def analysis_result(plays: int = 12) -> dict[str, Any]:
    return {
        "filtersApplied": {"opponent": "MIA", "down": "Todos"},
        "sample": {
            "plays": plays,
            "games": 2 if plays else 0,
            "quality": "pequeña" if plays else "insuficiente",
            "warning": "Muestra pequeña: interprete los resultados con cautela." if plays else "Muestra insuficiente: no hay jugadas para los filtros seleccionados.",
        },
        "summary": {
            "blitzRate": 0.375,
            "averageRushers": 4.2,
            "sources": {"blitzRate": "inferida", "averageRushers": "PFF"},
        },
        "pressureMap": [],
        "diagnoses": [],
        "protectionResponses": [],
        "representativePlays": [],
    }


def test_trends_keeps_only_grounded_facts_and_corrects_sources() -> None:
    fake = FakeConverseClient(
        {
            "text": "En esta muestra se observó una asociación.",
            "facts": [
                {"field": "summary.blitzRate", "value": 37.5, "source": "PFF", "text": "37.5 %"},
                {"field": "summary.averageRushers", "value": 4.2, "source": "observada", "text": "4.2"},
                {"field": "summary.averageRushers", "value": 9.9, "source": "PFF", "text": "incorrecto"},
                {"field": "summary.unknown", "value": 1, "source": "PFF", "text": "inventado"},
            ],
        }
    )
    ai.set_client_factory(lambda: fake)

    response = ai.trends(FakeEngine(analysis_result()), {"opponent": "MIA"})

    assert response["available"] is True
    assert response["removedFacts"] == 2
    assert [fact["source"] for fact in response["facts"]] == ["inferida", "PFF"]
    assert response["smallSampleWarning"] == analysis_result()["sample"]["warning"]
    assert response["languageWarning"] is False
    assert len(fake.calls) == 1
    assert "menos de 30 jugadas" in fake.calls[0]["system"][0]["text"]


def test_trends_marks_forbidden_language_without_modifying_text() -> None:
    text = "Esta formación evita la presión."
    fake = FakeConverseClient({"text": text, "facts": []})
    ai.set_client_factory(lambda: fake)

    response = ai.trends(FakeEngine(analysis_result(30)), {"opponent": "MIA"})

    assert response["text"] == text
    assert response["languageWarning"] is True
    assert response["smallSampleWarning"] is None


def test_diagnosis_moves_unsupported_facts_and_marks_language() -> None:
    fake = FakeConverseClient(
        {
            "hechos": [
                {"text": "Llegó por el centro", "field": "summary.blitzRate", "value": 0.375, "source": "PFF"},
                {"text": "El tackle falló", "field": "missing", "value": 1, "source": "observada"},
            ],
            "hipotesis": [{"text": "El jugador fue responsable del ajuste"}],
        }
    )
    ai.set_client_factory(lambda: fake)

    response = ai.diagnosis(FakeEngine(analysis_result()), {"opponent": "MIA"})

    assert response["hechos"] == [
        {
            "text": "Posible Llegó por el centro",
            "field": "summary.blitzRate",
            "value": 0.375,
            "source": "inferida",
            "languageWarning": False,
        }
    ]
    assert len(response["hipotesis"]) == 2
    assert response["hipotesis"][0]["unverified"] is False
    assert response["hipotesis"][0]["languageWarning"] is True
    assert response["hipotesis"][1]["unverified"] is True
    assert response["hipotesis"][1]["languageWarning"] is True


def test_empty_samples_bypass_client_deterministically() -> None:
    factory_calls = 0

    def factory() -> FakeConverseClient:
        nonlocal factory_calls
        factory_calls += 1
        return FakeConverseClient({})

    ai.set_client_factory(factory)
    engine = FakeEngine(analysis_result(0))

    trends = ai.trends(engine, {"opponent": "MIA"})
    diagnosis = ai.diagnosis(engine, {"opponent": "MIA"})

    assert trends["text"] == "No hay jugadas comparables contra MIA con los filtros activos."
    assert trends["facts"] == []
    assert diagnosis["text"] == "No hay jugadas comparables con los filtros activos."
    assert diagnosis["hechos"] == diagnosis["hipotesis"] == []
    assert factory_calls == 0


@pytest.mark.parametrize(
    "payload",
    [
        "not json",
        {"text": "", "facts": []},
        {"hechos": [], "hipotesis": [{"wrong": "shape"}]},
    ],
)
def test_invalid_structured_output_returns_only_generic_failure(payload: Any) -> None:
    fake = FakeConverseClient(payload)
    ai.set_client_factory(lambda: fake)
    engine = FakeEngine(analysis_result())

    if isinstance(payload, dict) and "hechos" in payload:
        response = ai.diagnosis(engine, {"opponent": "MIA"})
    else:
        response = ai.trends(engine, {"opponent": "MIA"})

    assert response == {
        "available": False,
        "status": "IA no disponible",
        "reason": "El servicio de IA no respondió o devolvió una salida no válida.",
    }


def test_diagnosis_rejects_unknown_requested_play_before_converse() -> None:
    fake = FakeConverseClient({"hechos": [], "hipotesis": []})
    ai.set_client_factory(lambda: fake)

    with pytest.raises(ai.PlayNotFoundError, match="gameId=8 playId=9"):
        ai.diagnosis(FakeEngine(analysis_result(), play=None), {}, 8, 9)
    assert fake.calls == []
