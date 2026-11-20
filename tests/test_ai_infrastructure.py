"""Focused non-network tests for task 6.1 Bedrock infrastructure."""

from __future__ import annotations

import json
import time

import pytest

from backend import ai


class FakeConverseClient:
    def __init__(self, payload: dict | None = None, delay: float = 0) -> None:
        self.payload = payload or {"ok": True}
        self.delay = delay
        self.calls: list[dict] = []

    def converse(self, **kwargs):
        self.calls.append(kwargs)
        if self.delay:
            time.sleep(self.delay)
        return {
            "output": {
                "message": {
                    "content": [{"text": json.dumps(self.payload)}],
                }
            }
        }


@pytest.fixture(autouse=True)
def restore_client_factory():
    yield
    ai.set_client_factory(ai.default_client_factory)


def test_defaults_and_timeout_bounds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BEDROCK_MODEL_ID", raising=False)
    monkeypatch.delenv("AWS_REGION", raising=False)
    monkeypatch.delenv("AI_TIMEOUT_SECONDS", raising=False)
    assert ai.model_id() == "us.amazon.nova-pro-v1:0"
    assert ai.region() == "us-east-1"
    assert ai.timeout_seconds() == 30

    for raw, expected in [
        ("1", 1.0),
        ("12.5", 12.5),
        ("120", 120.0),
        ("0", 30.0),
        ("0.5", 30.0),
        ("121", 30.0),
        ("not-a-number", 30.0),
        ("inf", 30.0),
    ]:
        monkeypatch.setenv("AI_TIMEOUT_SECONDS", raw)
        assert ai.timeout_seconds() == expected


def test_default_factory_passes_only_service_region_and_network_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[tuple, dict]] = []
    sentinel = object()

    def fake_boto_client(*args, **kwargs):
        calls.append((args, kwargs))
        return sentinel

    monkeypatch.setenv("AWS_REGION", "ca-central-1")
    monkeypatch.setenv("AI_TIMEOUT_SECONDS", "17")
    monkeypatch.setattr(ai.boto3, "client", fake_boto_client)

    assert ai.default_client_factory() is sentinel
    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args == ("bedrock-runtime",)
    assert set(kwargs) == {"region_name", "config"}
    assert kwargs["region_name"] == "ca-central-1"
    assert kwargs["config"].connect_timeout == 17
    assert kwargs["config"].read_timeout == 17


def test_client_factory_is_lazy_and_converse_receives_only_structured_context() -> None:
    fake = FakeConverseClient({"text": "resultado"})
    factory_calls = 0

    def factory():
        nonlocal factory_calls
        factory_calls += 1
        return fake

    ai.set_client_factory(factory)
    assert factory_calls == 0

    context = {
        "filters": {"opponent": "MIA"},
        "fields": {"sample.plays": {"value": 4, "source": "observada"}},
        "representativePlays": [],
        "play": None,
    }
    assert ai.invoke_nova("Responde solo JSON", context) == {"text": "resultado"}
    assert factory_calls == 1
    assert len(fake.calls) == 1
    call = fake.calls[0]
    assert call["modelId"] == "us.amazon.nova-pro-v1:0"
    assert call["system"] == [{"text": "Responde solo JSON"}]
    assert json.loads(call["messages"][0]["content"][0]["text"]) == context
    assert call["inferenceConfig"] == {"maxTokens": 2000, "temperature": 0}


def test_invoke_nova_enforces_total_timeout_without_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeConverseClient(delay=0.05)
    ai.set_client_factory(lambda: fake)
    monkeypatch.setattr(ai, "timeout_seconds", lambda: 0.01)

    started = time.monotonic()
    with pytest.raises(ai.AIUnavailableError, match="IA no disponible"):
        ai.invoke_nova("prompt", {"fields": {}})
    assert time.monotonic() - started < 0.2


def test_build_context_flattens_aggregates_and_excludes_detail_payloads() -> None:
    result = {
        "filtersApplied": {"opponent": "MIA", "down": "Todos"},
        "sample": {"plays": 4, "games": 2, "quality": "insuficiente", "warning": "x"},
        "summary": {
            "text": "not sent",
            "blitzRate": 0.5,
            "averageThreatTime": 1.2,
            "sources": {"blitzRate": "inferida", "averageThreatTime": "inferida"},
        },
        "pressureMap": [
            {"sector": "Centro", "plays": 2, "share": 1.0, "averageThreatTime": 1.2,
             "hurries": 1, "hits": 0, "sacks": 0, "quality": "insuficiente"}
        ],
        "diagnoses": [
            {"label": "Doble equipo", "source": "PFF", "plays": 1, "share": 0.25,
             "hurries": 0, "hits": 0, "sacks": 0, "averageThreatTime": None}
        ],
        "protectionResponses": [
            {"dimension": "passBlockers", "alternatives": [
                {"value": "6", "plays": 3, "quality": "insuficiente",
                 "pffPressureRate": 0.25, "sackRate": 0.0,
                 "completionRate": 0.5, "avgPrePenaltyYards": 5.0,
                 "avgPlayResult": 4.0, "averageThreatTime": 1.4}
            ]}
        ],
        "representativePlays": [
            {"category": "típica", "gameId": 1, "playId": 10,
             "playDescription": "must not be sent"}
        ],
        "rawTracking": [{"x": 1, "y": 2}],
    }
    play = {
        "context": {"gameId": 1, "playId": 10, "threatTime": 1.2},
        "fieldSources": {"gameId": "observada", "playId": "observada", "threatTime": "inferida"},
        "trajectories": [{"points": [{"x_norm": 1.0, "y_norm": 2.0}]}],
        "events": [{"frameId": 1, "event": "ball_snap"}],
        "players": [{"name": "Player"}],
    }

    context = ai.build_context(result, play)
    fields = context["fields"]
    assert fields["sample.plays"] == {"value": 4, "source": "observada"}
    assert fields["summary.blitzRate"] == {"value": 0.5, "source": "inferida"}
    assert fields["pressureMap.Centro.hurries"] == {"value": 1, "source": "inferida"}
    assert fields["diagnoses.Doble equipo.plays"] == {"value": 1, "source": "PFF"}
    assert fields["protectionResponses.passBlockers.6.pffPressureRate"] == {
        "value": 0.25,
        "source": "PFF",
    }
    assert fields["play.threatTime"] == {"value": 1.2, "source": "inferida"}
    assert context["representativePlays"] == [
        {"category": "típica", "gameId": 1, "playId": 10}
    ]

    serialized = json.dumps(context, ensure_ascii=False)
    for excluded in ("rawTracking", "trajectories", "x_norm", "events", "players", "playDescription"):
        assert excluded not in serialized
