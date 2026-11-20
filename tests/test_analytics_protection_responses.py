"""Focused in-memory tests for task 4.2 protection-response comparisons."""

from __future__ import annotations

import pandas as pd

from backend.analytics import Engine, OpponentTrackingCache, REQUIRED_COLUMNS
from backend.schemas import AnalysisResponse


def _blank(filename: str, rows: int = 0) -> pd.DataFrame:
    return pd.DataFrame(
        {
            column: pd.Series([pd.NA] * rows, dtype="object")
            for column in REQUIRED_COLUMNS[filename]
        }
    )


def _engine() -> Engine:
    games = pd.DataFrame({"gameId": [1], "week": [1]})
    plays = _blank("plays.csv", 4)
    plays["gameId"] = 1
    plays["playId"] = [10, 20, 30, 40]
    plays["playDescription"] = [f"play {play_id}" for play_id in plays["playId"]]
    plays["quarter"] = 1
    plays["gameClock"] = "10:00"
    plays["down"] = 3
    plays["yardsToGo"] = 8
    plays["possessionTeam"] = "BUF"
    plays["defensiveTeam"] = "MIA"
    plays["yardlineSide"] = "BUF"
    plays["yardlineNumber"] = 25
    plays["offenseFormation"] = ["SHOTGUN", "SHOTGUN", pd.NA, "I_FORM"]
    plays["personnelO"] = ["11", "11", "12", pd.NA]
    plays["personnelD"] = "NICKEL"
    plays["defendersInBox"] = 6
    plays["pff_playAction"] = [1, 0, 0, pd.NA]
    plays["dropBackType"] = ["TRADITIONAL", pd.NA, "ROLL_OUT_LEFT", "ROLL_OUT_RIGHT"]
    plays["pff_passCoverage"] = "Cover-3"
    plays["pff_passCoverageType"] = "Zone"
    plays["passResult"] = ["C", "S", "I", pd.NA]
    plays["prePenaltyPlayResult"] = [8, -5, pd.NA, 4]
    plays["playResult"] = [9, -7, 0, pd.NA]

    engine = Engine.from_frames(
        games,
        plays,
        _blank("players.csv"),
        _blank("pffScoutingData.csv"),
        tracking_loader=lambda _game_id: (_ for _ in ()).throw(
            AssertionError("tracking cache should be used")
        ),
    )
    table = engine.analytical_table
    table["passBlockers"] = pd.array([5, 6, pd.NA, 5], dtype="Int64")
    table["hasPffPressure"] = pd.array([True, False, pd.NA, True], dtype="boolean")
    table["hasHurry"] = pd.array([False] * 4, dtype="boolean")
    table["hasHit"] = pd.array([False] * 4, dtype="boolean")
    table["hasSack"] = pd.array([False] * 4, dtype="boolean")
    table["timeToThrow"] = [2.0, 2.5, 3.0, 2.2]
    table["threatTime"] = [1.0, float("nan"), 3.0, float("nan")]
    table["blockTypes"] = [
        frozenset({"PP", "CH"}),
        frozenset({"PP"}),
        frozenset({"CH"}),
        frozenset(),
    ]
    engine._tracking_cache["MIA"] = OpponentTrackingCache(
        aggregates=pd.DataFrame(), trajectories={}, events={}, skipped_games=()
    )
    return engine


def _dimensions(result: dict) -> dict[str, dict]:
    return {row["dimension"]: row for row in result["protectionResponses"]}


def _alternatives(dimension: dict) -> dict[str, dict]:
    return {row["value"]: row for row in dimension["alternatives"]}


def test_protection_responses_include_six_dimensions_and_own_non_null_samples() -> None:
    result = _engine().analyze({"opponent": "MIA"})
    dimensions = result["protectionResponses"]

    assert [row["dimension"] for row in dimensions] == [
        "offenseFormation",
        "passBlockers",
        "playAction",
        "dropBackType",
        "blockType",
        "personnelO",
    ]
    by_dimension = _dimensions(result)
    assert sum(row["plays"] for row in by_dimension["offenseFormation"]["alternatives"]) == 3
    assert sum(row["plays"] for row in by_dimension["passBlockers"]["alternatives"]) == 3
    assert sum(row["plays"] for row in by_dimension["playAction"]["alternatives"]) == 3
    assert sum(row["plays"] for row in by_dimension["dropBackType"]["alternatives"]) == 3
    assert sum(row["plays"] for row in by_dimension["personnelO"]["alternatives"]) == 3
    assert set(_alternatives(by_dimension["playAction"])) == {"Convencional", "Play action"}
    assert by_dimension["blockType"]["multiMembership"] is True
    assert all(
        row["multiMembership"] is False
        for row in dimensions
        if row["dimension"] != "blockType"
    )
    AnalysisResponse.model_validate(result)


def test_block_type_multiple_membership_and_alternative_metrics() -> None:
    result = _engine().analyze({"opponent": "MIA"})
    dimensions = _dimensions(result)
    block_types = _alternatives(dimensions["blockType"])

    assert block_types["CH"]["plays"] == 2
    assert block_types["PP"]["plays"] == 2
    assert sum(row["plays"] for row in block_types.values()) == 4
    assert block_types["CH"] == {
        "value": "CH",
        "plays": 2,
        "pffPressureRate": 0.5,
        "sackRate": 0.0,
        "averageThreatTime": 2.0,
        "completionRate": 0.5,
        "avgPrePenaltyYards": 8.0,
        "avgPlayResult": 4.5,
        "quality": "insuficiente",
    }
    assert block_types["PP"]["averageThreatTime"] == 1.0


def test_null_threat_time_keeps_alternative_and_returns_null_average() -> None:
    result = _engine().analyze({"opponent": "MIA"})
    formations = _alternatives(_dimensions(result)["offenseFormation"])

    assert formations["I_FORM"]["plays"] == 1
    assert formations["I_FORM"]["averageThreatTime"] is None
    assert formations["I_FORM"]["pffPressureRate"] == 1.0
    assert formations["I_FORM"]["sackRate"] == 0.0
    assert formations["I_FORM"]["completionRate"] == 0.0
    assert formations["I_FORM"]["avgPrePenaltyYards"] == 4.0
    assert formations["I_FORM"]["avgPlayResult"] is None
