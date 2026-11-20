"""Focused API lifecycle and error tests for task 5.1."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from backend import analytics, main
from backend.main import app, get_engine


EMPTY_ANALYSIS = {
    "filtersApplied": {
        "opponent": "MIA",
        "down": "Todos",
        "distanceBand": "Todos",
        "exactDistance": "Todos",
        "offenseFormation": "Todos",
        "defensivePersonnel": "Todos",
        "playAction": "Todos",
        "passBlockers": "Todos",
        "fieldZone": "Todos",
        "dropBackType": "Todos",
        "coverage": "Todos",
        "week": "Todos",
    },
    "activeFilters": [{"field": "opponent", "label": "Rival", "value": "MIA"}],
    "sample": {
        "plays": 0,
        "games": 0,
        "quality": "insuficiente",
        "warning": "Muestra insuficiente: no hay jugadas para los filtros seleccionados.",
    },
    "trackingGamesSkipped": 0,
    "contextualThreshold": None,
    "summary": {
        "text": "No hay jugadas comparables contra MIA con los filtros activos.",
        "blitzRate": None,
        "averageRushers": None,
        "pffPressureRate": None,
        "hurryRate": None,
        "hitRate": None,
        "sackRate": None,
        "pffSackRate": None,
        "sackDiscrepancy": None,
        "averageThreatTime": None,
        "averageTimeToThrow": None,
        "threatTimeSample": {"n": 0, "quality": "insuficiente"},
        "timeToThrowSample": {"n": 0, "quality": "insuficiente"},
        "pressureSample": {"n": 0, "quality": "insuficiente"},
        "sources": {
            "blitzRate": "inferida",
            "averageRushers": "PFF",
            "pffPressureRate": "PFF",
            "hurryRate": "PFF",
            "hitRate": "PFF",
            "sackRate": "observada",
            "pffSackRate": "PFF",
            "averageThreatTime": "inferida",
            "averageTimeToThrow": "observada",
        },
    },
    "pressureMap": [
        {
            "sector": sector,
            "plays": 0,
            "share": 0.0,
            "averageThreatTime": None,
            "hurries": 0,
            "hits": 0,
            "sacks": 0,
            "quality": "insuficiente",
        }
        for sector in analytics.SECTORS
    ],
    "diagnoses": [],
    "rusherDistribution": [],
    "rusherDistributionMeta": None,
    "coverageDistribution": [],
    "personnelDistribution": [],
    "downDistanceDistribution": [],
    "protectionResponses": [],
    "representativePlays": [],
}


class StubEngine:
    def __init__(self) -> None:
        self.analysis_calls = 0

    def filters(self) -> dict[str, Any]:
        return {
            "opponents": ["MIA"],
            "downs": [1, 3],
            "distanceBands": ["Corta", "Larga"],
            "offenseFormations": ["SHOTGUN"],
            "defensivePersonnels": ["NICKEL"],
            "blockerCounts": [5],
            "fieldZones": ["Medio campo"],
            "dropBackTypes": ["TRADITIONAL"],
            "coverages": ["Cover-3"],
            "weeks": [1],
        }

    def analyze(self, _request: Any) -> dict[str, Any]:
        self.analysis_calls += 1
        return EMPTY_ANALYSIS

    def play_detail(self, game_id: int, play_id: int) -> None:
        return None

    def rival_status(self, opponent: str) -> dict[str, Any]:
        return {"opponent": opponent, "trackingReady": False, "inProgress": True}


class FailingEngine(StubEngine):
    def analyze(self, _request: Any) -> dict[str, Any]:
        raise analytics.TrackingComputationError("private path: /data/tracking/file.csv")


def _client(engine: StubEngine) -> TestClient:
    app.dependency_overrides[get_engine] = lambda: engine
    return TestClient(app)


def test_health_filters_analysis_and_status_routes() -> None:
    engine = StubEngine()
    client = _client(engine)
    try:
        assert client.get("/health").json() == {"status": "ok"}
        assert client.get("/api/filters").json()["opponents"] == ["MIA"]

        response = client.post("/api/analysis", json={"opponent": "MIA"})
        assert response.status_code == 200
        assert response.json()["sample"]["plays"] == 0
        assert engine.analysis_calls == 1

        status = client.get("/api/status/MIA")
        assert status.status_code == 200
        assert status.json() == {
            "opponent": "MIA",
            "trackingReady": False,
            "inProgress": True,
        }
    finally:
        app.dependency_overrides.clear()


def test_invalid_analysis_and_path_parameters_return_field_safe_422() -> None:
    engine = StubEngine()
    client = _client(engine)
    try:
        response = client.post(
            "/api/analysis", json={"opponent": "MIA", "exactDistance": 0}
        )
        assert response.status_code == 422
        assert response.json()["detail"][0]["field"] == "exactDistance"
        assert engine.analysis_calls == 0

        response = client.get("/api/plays/not-an-int/2")
        assert response.status_code == 422
        assert response.json()["detail"][0]["field"] == "game_id"
    finally:
        app.dependency_overrides.clear()


def test_missing_play_and_tracking_failure_use_safe_json_errors() -> None:
    client = _client(StubEngine())
    try:
        missing = client.get("/api/plays/10/20")
        assert missing.status_code == 404
        assert missing.json() == {
            "detail": "No existe la jugada gameId=10 playId=20"
        }
    finally:
        app.dependency_overrides.clear()

    client = _client(FailingEngine())
    try:
        failed = client.post("/api/analysis", json={"opponent": "MIA"})
        assert failed.status_code == 500
        assert failed.json() == {
            "detail": "El análisis de tracking del Rival no se pudo completar"
        }
        assert "/data/" not in failed.text
    finally:
        app.dependency_overrides.clear()


def test_lifespan_initializes_engine_once_and_clears_it(monkeypatch: Any) -> None:
    engine = StubEngine()
    calls: list[Any] = []

    def load_engine(data_dir: Any) -> StubEngine:
        calls.append(data_dir)
        return engine

    monkeypatch.setattr(analytics, "load_engine", load_engine)
    with TestClient(app) as client:
        assert client.get("/api/filters").status_code == 200
        assert client.get("/api/filters").status_code == 200
    assert len(calls) == 1

    assert TestClient(app).get("/api/filters").status_code == 503


def test_static_build_serves_assets_and_spa_fallback(
    monkeypatch: Any, tmp_path: Any
) -> None:
    dist = tmp_path / "dist"
    assets = dist / "assets"
    assets.mkdir(parents=True)
    (dist / "index.html").write_text("<html>pocketiq</html>", encoding="utf-8")
    (assets / "app.js").write_text("console.log('ok')", encoding="utf-8")
    monkeypatch.setattr(main, "DIST_DIR", dist)

    client = _client(StubEngine())
    try:
        root = client.get("/")
        assert root.status_code == 200
        assert root.text == "<html>pocketiq</html>"

        asset = client.get("/assets/app.js")
        assert asset.status_code == 200
        assert asset.text == "console.log('ok')"

        spa_route = client.get("/analysis/MIA")
        assert spa_route.status_code == 200
        assert spa_route.text == "<html>pocketiq</html>"
    finally:
        app.dependency_overrides.clear()


def test_missing_build_unknown_api_and_traversal_return_json_404(
    monkeypatch: Any, tmp_path: Any
) -> None:
    missing_dist = tmp_path / "missing-dist"
    monkeypatch.setattr(main, "DIST_DIR", missing_dist)

    client = _client(StubEngine())
    try:
        missing = client.get("/")
        assert missing.status_code == 404
        assert missing.json() == {"detail": "Dashboard no compilado"}
        assert client.get("/health").json() == {"status": "ok"}

        for method in ("get", "post", "put", "patch", "delete"):
            unknown = getattr(client, method)("/api/does-not-exist")
            assert unknown.status_code == 404
            assert unknown.headers["content-type"].startswith("application/json")
            assert unknown.json() == {"detail": "Ruta de API no encontrada"}
    finally:
        app.dependency_overrides.clear()

    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("private spa", encoding="utf-8")
    monkeypatch.setattr(main, "DIST_DIR", dist)
    traversal = main.serve_dist("../secret.txt")
    assert traversal.status_code == 404
    assert traversal.body == b'{"detail":"Ruta no encontrada"}'
