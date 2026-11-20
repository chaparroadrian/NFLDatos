"""In-memory tests for task 4.1 filtered analysis assembly."""

from __future__ import annotations

import json
import random

import pandas as pd

from backend.analytics import (
    DIAGNOSES,
    Engine,
    OpponentTrackingCache,
    REQUIRED_COLUMNS,
    SECTORS,
)
from backend.schemas import AnalysisResponse, REPORT_SECTION_TITLES, ScoutingReport


def _blank(filename: str, rows: int = 0) -> pd.DataFrame:
    return pd.DataFrame(
        {column: pd.Series([pd.NA] * rows, dtype="object") for column in REQUIRED_COLUMNS[filename]}
    )


def _analysis_engine() -> Engine:
    games = pd.DataFrame({"gameId": [1, 2], "week": [1, 2]})
    plays = _blank("plays.csv", 5)
    plays["gameId"] = [1, 1, 2, 2, 2]
    plays["playId"] = [10, 20, 30, 40, 50]
    plays["playDescription"] = [f"play {number}" for number in plays["playId"]]
    plays["possessionTeam"] = "BUF"
    plays["defensiveTeam"] = ["MIA", "MIA", "MIA", "MIA", "NYJ"]
    plays["quarter"] = 1
    plays["gameClock"] = "10:00"
    plays["down"] = [3, 3, 2, 0, 3]
    plays["yardsToGo"] = [8, 3, 8, 2, 8]
    plays["yardlineSide"] = "BUF"
    plays["yardlineNumber"] = 25
    plays["offenseFormation"] = ["SHOTGUN", "I_FORM", "SHOTGUN", "SHOTGUN", "SHOTGUN"]
    plays["personnelO"] = "11"
    plays["personnelD"] = ["NICKEL", "BASE", "NICKEL", "NICKEL", "NICKEL"]
    plays["defendersInBox"] = 6
    plays["pff_playAction"] = [0, 1, 0, 0, 0]
    plays["dropBackType"] = "TRADITIONAL"
    plays["pff_passCoverage"] = ["Cover-3", "Cover-1", "Cover-3", "Cover-3", "Cover-3"]
    plays["pff_passCoverageType"] = "Zone"
    plays["passResult"] = ["S", "C", "C", "I", "C"]
    plays["prePenaltyPlayResult"] = [0, 7, 5, 0, 4]
    plays["playResult"] = [0, 7, 5, 0, 4]

    engine = Engine.from_frames(
        games,
        plays,
        _blank("players.csv"),
        _blank("pffScoutingData.csv"),
        tracking_loader=lambda _game_id: (_ for _ in ()).throw(AssertionError("cache should be used")),
    )
    table = engine.analytical_table
    table["passRushers"] = pd.array([5, 4, 6, 3, 4], dtype="Int64")
    table["passBlockers"] = pd.array([5, 6, 5, 5, 5], dtype="Int64")
    table["isApproximateBlitz"] = pd.array([True, False, True, False, False], dtype="boolean")
    table["hasPffPressure"] = pd.array([True, False, True, pd.NA, False], dtype="boolean")
    table["hasHurry"] = pd.array([True, False, True, False, False], dtype="boolean")
    table["hasHit"] = pd.array([False, False, True, False, False], dtype="boolean")
    table["hasSack"] = pd.array([False, False, True, False, False], dtype="boolean")
    table["timeToThrow"] = [2.0, 3.0, 2.5, float("nan"), 2.1]
    table["threatTime"] = [1.0, float("nan"), 1.5, float("nan"), 1.2]
    table["threatSide"] = ["Centro", pd.NA, "Izquierda", pd.NA, "Derecha"]
    table["staticDiagnoses"] = [
        ("Derrota individual",),
        (),
        ("Posible rusher libre",),
        (),
        (),
    ]
    table["pressureSourceCandidate"] = [
        ("Derrota individual",),
        ("No determinado con los datos disponibles",),
        ("Posible rusher libre",),
        ("No determinado con los datos disponibles",),
        ("No determinado con los datos disponibles",),
    ]
    table["qbMovementFlag"] = pd.array([False] * 5, dtype="boolean")
    engine._tracking_cache["MIA"] = OpponentTrackingCache(
        aggregates=pd.DataFrame(), trajectories={}, events={}, skipped_games=(2,)
    )
    return engine


def test_analysis_applies_filters_jointly_and_exact_distance_overrides_band() -> None:
    engine = _analysis_engine()
    result = engine.analyze(
        {
            "opponent": "MIA",
            "down": 3,
            "distanceBand": "Corta",
            "exactDistance": 8,
            "offenseFormation": "SHOTGUN",
            "defensivePersonnel": "NICKEL",
            "playAction": False,
            "passBlockers": 5,
            "fieldZone": "Propio 21–40",
            "dropBackType": "TRADITIONAL",
            "coverage": "Cover-3",
            "week": 1,
        }
    )

    assert result["sample"] == {
        "plays": 1,
        "games": 1,
        "quality": "insuficiente",
        "warning": "Muestra insuficiente: interprete los resultados con cautela.",
    }
    assert result["summary"]["blitzRate"] == 1.0
    assert result["summary"]["sackRate"] == 1.0
    assert result["summary"]["pffSackRate"] == 0.0
    assert result["summary"]["sackDiscrepancy"]["discrepantPlays"] == 1
    assert result["trackingGamesSkipped"] == 1
    assert [row["sector"] for row in result["pressureMap"]] == SECTORS
    assert len(result["pressureMap"]) == 5
    assert [row["label"] for row in result["diagnoses"]] == DIAGNOSES
    assert result["filtersApplied"]["distanceBand"] == "Corta"
    assert {item["field"] for item in result["activeFilters"]} == set(result["filtersApplied"])
    AnalysisResponse.model_validate(result)
    json.dumps(result, allow_nan=False)


def test_analysis_builds_distributions_subset_samples_and_cache_safe_values() -> None:
    engine = _analysis_engine()
    filters = {"opponent": "MIA"}
    result = engine.analyze(filters)

    assert result["sample"]["plays"] == 4
    assert result["sample"]["games"] == 2
    assert result["summary"]["pressureSample"] == {"n": 3, "quality": "insuficiente"}
    assert result["summary"]["threatTimeSample"] == {"n": 2, "quality": "insuficiente"}
    assert result["summary"]["timeToThrowSample"] == {"n": 3, "quality": "insuficiente"}
    assert result["rusherDistributionMeta"]["sample"]["n"] == 4
    assert sum(bucket["plays"] for bucket in result["rusherDistribution"]) == 4
    assert [bucket["value"] for bucket in result["coverageDistribution"]] == ["Cover-3", "Cover-1"]
    assert result["downDistanceDistribution"][0]["down"] == 0
    assert result["summary"]["sources"]["pffPressureRate"] == "PFF"
    assert result["summary"]["sources"]["averageThreatTime"] == "inferida"

    result["sample"]["plays"] = 999
    assert engine.analyze(filters)["sample"]["plays"] == 4


def test_empty_analysis_retains_active_filters_and_complete_null_safe_shape() -> None:
    engine = _analysis_engine()
    result = engine.analyze({"opponent": "MIA", "coverage": "Cover-0"})

    assert result["sample"]["plays"] == result["sample"]["games"] == 0
    assert result["sample"]["quality"] == "insuficiente"
    numeric_summary = [
        "blitzRate", "averageRushers", "pffPressureRate", "hurryRate", "hitRate",
        "sackRate", "pffSackRate", "averageThreatTime", "averageTimeToThrow",
    ]
    assert all(result["summary"][name] is None for name in numeric_summary)
    assert all(row["plays"] == 0 and row["share"] == 0 for row in result["pressureMap"])
    for collection in (
        "diagnoses", "rusherDistribution", "coverageDistribution",
        "personnelDistribution", "downDistanceDistribution", "protectionResponses",
        "representativePlays",
    ):
        assert result[collection] == []
    assert result["activeFilters"] == [
        {"field": "opponent", "label": "Rival", "value": "MIA"},
        {"field": "coverage", "label": "Cobertura ejecutada", "value": "Cover-0"},
    ]
    AnalysisResponse.model_validate(result)
    json.dumps(result, allow_nan=False)


def test_filter_lists_are_unique_null_free_and_use_approved_order() -> None:
    options = _analysis_engine().filters()
    assert options["opponents"] == ["MIA", "NYJ"]
    assert options["downs"] == [0, 2, 3]
    assert options["distanceBands"] == ["Corta", "Larga", "Conversión"]
    assert options["fieldZones"] == ["Propio 21–40", "Conversión de dos puntos"]
    assert options["coverages"] == ["Cover-1", "Cover-3"]


def test_random_filter_combinations_match_a_conjunctive_reference() -> None:
    """Property 13: all non-null filters are conjunctive.

    **Validates: Requirements 5.7, 6.4, 6.5, 10.1, 13.8, 13.9**
    """

    engine = _analysis_engine()
    rows = engine.analytical_table.loc[engine.analytical_table["defensiveTeam"].eq("MIA")]
    rng = random.Random(4101)
    for _case in range(100):
        filters = {
            "opponent": "MIA",
            "down": rng.choice([None, 0, 2, 3, 4]),
            "distanceBand": rng.choice([None, "Corta", "Larga", "Muy larga"]),
            "exactDistance": rng.choice([None, 2, 3, 8, 99]),
            "offenseFormation": rng.choice([None, "SHOTGUN", "I_FORM", "EMPTY"]),
            "coverage": rng.choice([None, "Cover-1", "Cover-3", "Cover-0"]),
            "week": rng.choice([None, 1, 2, 8]),
        }
        expected = 0
        for row in rows.to_dict("records"):
            checks = [
                filters["down"] is None or row["down"] == filters["down"],
                filters["offenseFormation"] is None
                or row["offenseFormation"] == filters["offenseFormation"],
                filters["coverage"] is None or row["coverage"] == filters["coverage"],
                filters["week"] is None or row["week"] == filters["week"],
            ]
            if filters["exactDistance"] is not None:
                checks.append(row["yardsToGo"] == filters["exactDistance"] and row["down"] != 0)
            elif filters["distanceBand"] is not None:
                checks.append(row["distanceBand"] == filters["distanceBand"])
            expected += int(all(checks))
        assert engine.analyze(filters)["sample"]["plays"] == expected, filters


def test_executive_summary_is_stable_cautious_and_handles_missing_threats() -> None:
    engine = _analysis_engine()
    first = engine.analyze({"opponent": "MIA"})
    second = engine.analyze({"opponent": "MIA"})

    assert first["summary"]["text"] == second["summary"]["text"]
    assert first["summary"]["text"] == (
        "En 4 jugadas de pase contra MIA, la defensa envió cinco o más rushers "
        "(blitz aproximado) en el 50.0% de las jugadas. En esta muestra, la amenaza "
        "por proximidad entró con mayor frecuencia por el sector Izquierda, con un "
        "tiempo promedio hasta amenaza por proximidad de 1.2 s. La posible fuente "
        "de presión más frecuente fue «No determinado con los datos disponibles», "
        "que requiere validación en video. Calidad de muestra: insuficiente (n = 4). "
        "La muestra es pequeña y debe interpretarse con cautela."
    )

    no_threat = engine.analyze({"opponent": "MIA", "offenseFormation": "I_FORM"})
    assert "No se detectó amenaza por proximidad en esta muestra." in no_threat["summary"]["text"]
    assert no_threat["summary"]["text"].endswith(
        "La muestra es pequeña y debe interpretarse con cautela."
    )

    empty = engine.analyze({"opponent": "MIA", "coverage": "Cover-0"})
    assert empty["summary"]["text"] == (
        "No hay jugadas comparables contra MIA con los filtros activos."
    )


def test_deterministic_scouting_report_has_six_sections_and_valid_small_sample_citations() -> None:
    engine = _analysis_engine()
    result = engine.analyze({"opponent": "MIA"})
    first = engine.scouting_report_deterministic(result)
    second = engine.scouting_report_deterministic(result)

    assert first == second
    assert tuple(section["title"] for section in first["sections"]) == REPORT_SECTION_TITLES
    recommendations = first["sections"][3]["items"]
    valid_keys = {(1, 10), (1, 20), (2, 30), (2, 40)}
    assert recommendations
    for recommendation in recommendations:
        assert recommendation["label"] == "observación con muestra pequeña"
        assert "recomendación" not in recommendation["text"].casefold()
        assert recommendation["quality"] == "insuficiente"
        assert {
            (play["gameId"], play["playId"])
            for play in recommendation["citedPlays"]
        }.issubset(valid_keys)

    comparable = first["sections"][4]["items"]
    assert comparable == sorted(comparable, key=lambda play: (play["gameId"], play["playId"]))
    assert len({(play["gameId"], play["playId"]) for play in comparable}) == len(comparable)
    assert "Elementos retirados: 0" in first["sections"][5]["text"]
    assert all(section["languageWarning"] is False for section in first["sections"])
    ScoutingReport.model_validate(first)


def test_empty_scouting_report_keeps_only_limitations_text() -> None:
    engine = _analysis_engine()
    result = engine.analyze({"opponent": "MIA", "coverage": "Cover-0"})
    report = engine.scouting_report_deterministic(result)

    assert tuple(section["title"] for section in report["sections"]) == REPORT_SECTION_TITLES
    assert all(section["text"] == "" for section in report["sections"][:5])
    assert report["sections"][3]["items"] == []
    assert report["sections"][4]["items"] == []
    assert report["sections"][5]["text"] == (
        "No hay jugadas comparables contra MIA con los filtros activos."
    )
    ScoutingReport.model_validate(report)
