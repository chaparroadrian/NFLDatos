"""Focused in-memory tests for task 4.3 representative plays and detail."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from backend.analytics import (
    Engine,
    OpponentTrackingCache,
    REQUIRED_COLUMNS,
    Trajectory,
)
from backend.schemas import AnalysisResponse, PlayDetailResponse


def _blank(filename: str, rows: int = 0) -> pd.DataFrame:
    return pd.DataFrame(
        {
            column: pd.Series([pd.NA] * rows, dtype="object")
            for column in REQUIRED_COLUMNS[filename]
        }
    )


def _engine() -> Engine:
    games = pd.DataFrame({"gameId": [1, 2], "week": [1, 2]})
    plays = _blank("plays.csv", 5)
    plays["gameId"] = [1, 1, 1, 1, 2]
    plays["playId"] = [10, 20, 30, 40, 50]
    plays["playDescription"] = [f"play {play_id}" for play_id in plays["playId"]]
    plays["quarter"] = 1
    plays["gameClock"] = "10:00"
    plays["down"] = 3
    plays["yardsToGo"] = 8
    plays["possessionTeam"] = "BUF"
    plays["defensiveTeam"] = "MIA"
    plays["yardlineSide"] = "BUF"
    plays["yardlineNumber"] = 25
    plays["offenseFormation"] = "SHOTGUN"
    plays["personnelO"] = "11"
    plays["personnelD"] = "NICKEL"
    plays["defendersInBox"] = 6
    plays["pff_playAction"] = 0
    plays["dropBackType"] = "TRADITIONAL"
    plays["pff_passCoverage"] = "Cover-3"
    plays["pff_passCoverageType"] = "Zone"
    plays["passResult"] = ["I", "S", "C", "I", "C"]
    plays["prePenaltyPlayResult"] = [0, -7, 12, 2, 6]
    plays["playResult"] = [0, -7, 12, 2, 6]

    players = pd.DataFrame(
        {
            "nflId": [100, 200, 300],
            "displayName": ["Quarterback", "Rusher", "Tackle"],
            "officialPosition": ["QB", "DE", "LT"],
        }
    )
    pff_rows = []
    for game_id, play_id in zip(plays["gameId"], plays["playId"], strict=True):
        for nfl_id, role, position in (
            (100, "Pass", "QB"),
            (200, "Pass Rush", "LE"),
            (300, "Pass Block", "LT"),
        ):
            row = {column: pd.NA for column in REQUIRED_COLUMNS["pffScoutingData.csv"]}
            row.update(
                gameId=game_id,
                playId=play_id,
                nflId=nfl_id,
                pff_role=role,
                pff_positionLinedUp=position,
            )
            pff_rows.append(row)
    pff = pd.DataFrame(pff_rows)

    engine = Engine.from_frames(games, plays, players, pff, tracking_loader=None)
    table = engine.analytical_table
    table["passRushers"] = pd.array([5, 4, 4, 4, 4], dtype="Int64")
    table["passBlockers"] = pd.array([5, 5, 6, 5, 6], dtype="Int64")
    table["isApproximateBlitz"] = pd.array([True, False, False, False, False], dtype="boolean")
    table["hasPffPressure"] = pd.array([True, True, False, True, False], dtype="boolean")
    table["hasHurry"] = pd.array([True, False, False, False, False], dtype="boolean")
    table["hasHit"] = pd.array([False] * 5, dtype="boolean")
    table["hasSack"] = pd.array([False, True, False, False, False], dtype="boolean")
    table["timeToThrow"] = [2.0, 2.5, 4.0, 2.2, np.nan]
    table["threatTime"] = [2.0, 1.0, 3.0, 2.0, np.nan]
    table["threatSide"] = ["Centro", "Izquierda", "Derecha", "Centro", pd.NA]
    table["snapFrame"] = pd.array([2, 2, 2, pd.NA, pd.NA], dtype="Int64")
    table["passFrame"] = pd.array([5, 6, 7, 4, pd.NA], dtype="Int64")
    table["endFrame"] = pd.array([5, 6, 7, 4, pd.NA], dtype="Int64")
    table["snapSource"] = ["manual", "manual", "manual", "ausente", pd.NA]
    table["passSource"] = ["manual", "manual", "manual", "manual", pd.NA]
    table["trackingStatus"] = ["ok", "ok", "ok", "ok", "pendiente"]
    table["staticDiagnoses"] = [
        ("Derrota individual",),
        ("Posible rusher libre",),
        ("Derrota individual", "Posible rusher libre"),
        (),
        (),
    ]
    table["qbMovementFlag"] = pd.array([False] * 5, dtype="boolean")

    trajectory = Trajectory(
        nflIds=np.array([-1, 100, 200, 300], dtype=np.int64),
        frameIds=np.array([2, 3, 4, 5], dtype=np.int16),
        x_norm=np.array(
            [[30, 31, 32, 33], [40, 40, np.nan, 40], [45, 44, 43, 42], [39, 39, 39, 39]],
            dtype=np.float32,
        ),
        y_norm=np.array(
            [[26, 26, 26, 26], [26, 26, np.nan, 26], [30, 29, 28, 27], [28, 28, 28, 28]],
            dtype=np.float32,
        ),
    )
    engine._tracking_cache["MIA"] = OpponentTrackingCache(
        aggregates=pd.DataFrame(),
        trajectories={(1, 10): trajectory},
        events={(1, 10): ((2, "ball_snap"), (5, "pass_forward")), (1, 40): ((4, "pass_forward"),)},
        skipped_games=(2,),
    )
    return engine


def test_representative_selection_is_deterministic_and_uses_approved_rules() -> None:
    engine = _engine()
    first = engine.analyze({"opponent": "MIA"})
    second = engine.analyze({"opponent": "MIA"})
    representatives = first["representativePlays"]

    assert first == second
    assert [(row["category"], row["playId"]) for row in representatives] == [
        ("típica", 10),
        ("amenaza temprana", 20),
        ("sack", 20),
        ("protección exitosa comparable", 30),
        ("Posible intercambio o stunt o Posible rusher libre", 20),
    ]
    assert [row["confidence"] for row in representatives] == [
        "alto", "bajo", "bajo", "medio", "bajo"
    ]
    AnalysisResponse.model_validate(first)


def test_play_detail_exposes_context_players_sources_and_dense_safe_trajectories() -> None:
    detail = _engine().play_detail(1, 10)

    assert detail is not None
    assert detail["context"]["gameId"] == 1
    assert detail["context"]["pressureSourceCandidate"] == ["Derrota individual"]
    assert detail["fieldSources"]["hasPffPressure"] == "PFF"
    assert detail["fieldSources"]["threatTime"] == "inferida"
    assert detail["fieldSources"]["timeToThrow"] == "observada"
    assert [(player["nflId"], player["role"]) for player in detail["players"]] == [
        (100, "Pass"), (200, "Pass Rush"), (300, "Pass Block")
    ]
    assert detail["events"] == [
        {"frameId": 2, "event": "ball_snap"},
        {"frameId": 5, "event": "pass_forward"},
    ]
    assert detail["snapFrame"] == 2
    assert detail["passFrame"] == 5
    assert detail["trajectoryReason"] is None
    assert len(detail["trajectories"]) == 4
    assert all(
        [point["frameId"] for point in trajectory["points"]] == [2, 3, 4, 5]
        for trajectory in detail["trajectories"]
    )
    quarterback = next(row for row in detail["trajectories"] if row["nflId"] == 100)
    assert quarterback["points"][2]["x_norm"] is None
    PlayDetailResponse.model_validate(detail)
    json.dumps(detail, allow_nan=False)


def test_play_detail_distinguishes_unknown_missing_snap_and_missing_tracking() -> None:
    engine = _engine()

    assert engine.play_detail(99, 99) is None
    no_snap = engine.play_detail(1, 40)
    assert no_snap is not None
    assert no_snap["trajectoryReason"] == "sin snap"
    assert no_snap["trajectories"] == []
    assert no_snap["events"] == [{"frameId": 4, "event": "pass_forward"}]
    assert no_snap["playDescription"] == "play 40"

    no_tracking = engine.play_detail(2, 50)
    assert no_tracking is not None
    assert no_tracking["trajectoryReason"] == "sin tracking"
    assert no_tracking["snapSource"] == "ausente"
    assert no_tracking["passSource"] == "ausente"
    assert no_tracking["players"]
    assert no_tracking["context"]["timeToThrow"] is None
    PlayDetailResponse.model_validate(no_snap)
    PlayDetailResponse.model_validate(no_tracking)
