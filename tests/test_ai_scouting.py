"""Fake-client tests for Nova scouting-report validation and fallback."""

from __future__ import annotations

import json
from typing import Any

import pytest

from backend import ai
from backend.schemas import REPORT_SECTION_TITLES, ScoutingReportResponse


class FakeConverseClient:
    def __init__(self, payload: Any) -> None:
        self.payload = payload
        self.calls: list[dict[str, Any]] = []

    def converse(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        text = self.payload if isinstance(self.payload, str) else json.dumps(self.payload)
        return {"output": {"message": {"content": [{"text": text}]}}}


class FakeEngine:
    def __init__(self, result: dict[str, Any]) -> None:
        self.result = result
        self.deterministic_calls = 0

    def analyze(self, _filters: Any) -> dict[str, Any]:
        return self.result

    def scouting_report_deterministic(self, _result: Any) -> dict[str, Any]:
        self.deterministic_calls += 1
        sections = [
            {"title": title, "text": "", "items": None, "languageWarning": False}
            for title in REPORT_SECTION_TITLES
        ]
        sections[3]["items"] = []
        sections[4]["items"] = []
        sections[5]["text"] = (
            "No hay jugadas comparables contra MIA con los filtros activos."
            if self.result["sample"]["plays"] == 0
            else "Calidad de muestra: pequeña (n = 12). Los Diagnósticos con fuente "
            "inferida no son asignaciones confirmadas por el equipo ni por video y "
            "requiere validación en video. Elementos retirados: 0."
        )
        return {"sections": sections}


@pytest.fixture(autouse=True)
def restore_client_factory():
    yield
    ai.set_client_factory(ai.default_client_factory)


def analysis_result(plays: int = 12) -> dict[str, Any]:
    return {
        "filtersApplied": {"opponent": "MIA"},
        "sample": {
            "plays": plays,
            "games": 2 if plays else 0,
            "quality": "pequeña" if plays else "insuficiente",
            "warning": "Muestra pequeña" if plays else "Muestra insuficiente",
        },
        "summary": {"sources": {}},
        "pressureMap": [],
        "diagnoses": [],
        "protectionResponses": [
            {
                "dimension": "passBlockers",
                "alternatives": [
                    {"value": "6", "plays": 12, "quality": "pequeña"},
                    {"value": "7", "plays": 3, "quality": "insuficiente"},
                ],
            }
        ],
        "representativePlays": [
            {"category": "típica", "gameId": 2, "playId": 20},
            {"category": "sack", "gameId": 1, "playId": 10},
        ],
    }


def nova_report(recommendations: list[dict[str, Any]]) -> dict[str, Any]:
    sections = [
        {"title": title, "text": f"Texto {title}", "items": None, "languageWarning": False}
        for title in REPORT_SECTION_TITLES
    ]
    sections[3]["items"] = recommendations
    sections[4]["items"] = []
    return {"sections": sections}


def recommendation(**overrides: Any) -> dict[str, Any]:
    value = {
        "text": "Recomendación: usar seis bloqueadores en esta muestra.",
        "label": "recomendación",
        "dimension": "passBlockers",
        "alternative": "6",
        "n": 12,
        "quality": "pequeña",
        "citedPlays": [{"gameId": 2, "playId": 20}],
    }
    value.update(overrides)
    return value


def test_validate_recommendations_requires_exact_support_and_real_citations() -> None:
    result = analysis_result()
    valid, removed = ai.validate_recommendations(
        [
            recommendation(),
            recommendation(alternative="missing"),
            recommendation(n=11),
            recommendation(quality="insuficiente"),
            recommendation(citedPlays=[{"gameId": 99, "playId": 99}]),
            recommendation(citedPlays=[{"gameId": 3, "playId": 30}]),
        ],
        result,
        {(3, 30)},
    )

    assert removed == 4
    assert len(valid) == 2
    assert all(item["label"] == "observación con muestra pequeña" for item in valid)
    assert all("recomendación" not in item["text"].casefold() for item in valid)
    assert valid[1]["citedPlays"] == [{"gameId": 3, "playId": 30}]


def test_scouting_report_removes_unsupported_items_and_merges_comparables() -> None:
    fake = FakeConverseClient(
        nova_report(
            [
                recommendation(
                    citedPlays=[
                        {"gameId": 2, "playId": 20},
                        {"gameId": 99, "playId": 99},
                    ]
                ),
                recommendation(n=99),
                recommendation(citedPlays=[]),
            ]
        )
    )
    ai.set_client_factory(lambda: fake)

    response = ai.scouting_report(FakeEngine(analysis_result()), {"opponent": "MIA"})

    assert response["available"] is True
    assert response["generatedBy"] == "Amazon Nova"
    recommendations = response["report"]["sections"][3]["items"]
    assert len(recommendations) == 1
    assert recommendations[0]["citedPlays"] == [{"gameId": 2, "playId": 20}]
    assert response["report"]["sections"][4]["items"] == [
        {"gameId": 1, "playId": 10},
        {"gameId": 2, "playId": 20},
    ]
    limitations = response["report"]["sections"][5]["text"]
    assert "Calidad de muestra: pequeña" in limitations
    assert "requiere validación en video" in limitations
    assert "Elementos retirados: 2" in limitations
    assert len(fake.calls) == 1
    ScoutingReportResponse.model_validate(response)


def test_scouting_report_marks_forbidden_nova_section_language() -> None:
    payload = nova_report([])
    payload["sections"][0]["text"] = "Esta formación evita la presión."
    fake = FakeConverseClient(payload)
    ai.set_client_factory(lambda: fake)

    response = ai.scouting_report(FakeEngine(analysis_result()), {"opponent": "MIA"})

    assert response["report"]["sections"][0]["languageWarning"] is True
    assert response["report"]["sections"][1]["languageWarning"] is False


def test_invalid_nova_report_returns_complete_deterministic_fallback() -> None:
    fake = FakeConverseClient("not json")
    engine = FakeEngine(analysis_result())
    ai.set_client_factory(lambda: fake)

    response = ai.scouting_report(engine, {"opponent": "MIA"})

    assert response["available"] is False
    assert response["generatedBy"] == "sin IA"
    assert response["status"] == "IA no disponible"
    assert response["reason"] == ai.AI_UNAVAILABLE_REASON
    assert tuple(
        section["title"] for section in response["report"]["sections"]
    ) == REPORT_SECTION_TITLES
    assert engine.deterministic_calls == 1
    ScoutingReportResponse.model_validate(response)


def test_empty_scouting_report_bypasses_fake_client() -> None:
    factory_calls = 0

    def factory() -> FakeConverseClient:
        nonlocal factory_calls
        factory_calls += 1
        return FakeConverseClient({})

    engine = FakeEngine(analysis_result(0))
    ai.set_client_factory(factory)
    response = ai.scouting_report(engine, {"opponent": "MIA"})

    assert response["available"] is True
    assert response["generatedBy"] == "sin IA"
    assert all(section["text"] == "" for section in response["report"]["sections"][:5])
    assert "No hay jugadas comparables" in response["report"]["sections"][5]["text"]
    assert factory_calls == 0
    ScoutingReportResponse.model_validate(response)
