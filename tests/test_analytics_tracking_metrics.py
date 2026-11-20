"""In-memory tests for task 3.2 tracking windows and trajectories."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backend.analytics import ValidationLog, process_game


def _tracking(rows: list[tuple]) -> pd.DataFrame:
    columns = [
        "gameId", "playId", "nflId", "frameId", "team", "playDirection",
        "x", "y", "event", "x_norm", "y_norm",
    ]
    return pd.DataFrame(rows, columns=columns)


def _plays(*play_ids: int) -> pd.DataFrame:
    return pd.DataFrame({"gameId": [1] * len(play_ids), "playId": list(play_ids)})


def _pff(play_id: int, qb: int = 10, rushers: tuple[int, ...] = (20, 21)) -> pd.DataFrame:
    return pd.DataFrame(
        [(1, play_id, qb, "Pass"), *[(1, play_id, rusher, "Pass Rush") for rusher in rushers]],
        columns=["gameId", "playId", "nflId", "pff_role"],
    )


def test_process_game_prioritizes_manual_events_window_and_threat_ties() -> None:
    rows: list[tuple] = []
    # Automatic snap occurs first, but manual snap at frame 3 must win. A sack at 6
    # ends the window before the manual pass at 8. At frame 5, rushers are tied at
    # one yard, so nflId 20 must activate the threat and classify to QB-left.
    for frame, event in [
        (1, "autoevent_ballsnap"), (2, "None"), (3, "ball_snap"),
        (4, "None"), (5, "None"), (6, "qb_sack"), (7, "None"),
        (8, "pass_forward"), (9, "autoevent_passforward"),
    ]:
        rows.append((1, 10, pd.NA, frame, "football", "right", 0, 0, event, 0, 0))
        rows.append((1, 10, 10, frame, "BUF", "right", 40, 26, "None", 40, 26))
        rusher_20_y = 27 if frame == 5 else 30
        rusher_21_y = 25 if frame == 5 else 22
        rows.append((1, 10, 20, frame, "MIA", "right", 40, rusher_20_y, "None", 40, rusher_20_y))
        rows.append((1, 10, 21, frame, "MIA", "right", 40, rusher_21_y, "None", 40, rusher_21_y))

    result = process_game(_tracking(rows), _plays(10), _pff(10))
    aggregate = result.aggregates.iloc[0]

    assert aggregate["snapFrame"] == 3
    assert aggregate["snapSource"] == "manual"
    assert aggregate["passFrame"] == 8
    assert aggregate["passSource"] == "manual"
    assert aggregate["timeToThrow"] == 0.5
    assert aggregate["endFrame"] == 6
    assert aggregate["threatFrame"] == 5
    assert aggregate["threatTime"] == 0.2
    assert aggregate["threatRusherId"] == 20
    assert aggregate["lateralDelta"] == 1.0
    assert aggregate["threatSide"] == "Centro"
    assert result.events[(1, 10)] == (
        (1, "autoevent_ballsnap"),
        (3, "ball_snap"),
        (6, "qb_sack"),
        (8, "pass_forward"),
        (9, "autoevent_passforward"),
    )

    trajectory = result.trajectories[(1, 10)]
    assert trajectory.frameIds.tolist() == [3, 4, 5, 6]
    assert trajectory.nflIds.tolist() == [-1, 10, 20, 21]
    assert trajectory.x_norm.shape == (4, 4)
    for array in (trajectory.nflIds, trajectory.frameIds, trajectory.x_norm, trajectory.y_norm):
        assert not array.flags.writeable
        with pytest.raises(ValueError):
            array.flat[0] = 999
    with pytest.raises(TypeError):
        result.trajectories[(1, 99)] = trajectory  # type: ignore[index]


def test_process_game_records_minimum_and_ignores_missing_coordinate_pairs() -> None:
    rows = [
        (1, 11, pd.NA, 2, "football", "right", 0, 0, "ball_snap", 0, 0),
        (1, 11, 10, 2, "BUF", "right", 40, 26, "None", 40, 26),
        (1, 11, 20, 2, "MIA", "right", 45, 26, "None", 45, 26),
        (1, 11, pd.NA, 3, "football", "right", 0, 0, "None", 0, 0),
        (1, 11, 10, 3, "BUF", "right", 40, 26, "None", np.nan, np.nan),
        (1, 11, 20, 3, "MIA", "right", 43, 26, "None", 43, 26),
        (1, 11, pd.NA, 4, "football", "right", 0, 0, "None", 0, 0),
        (1, 11, 10, 4, "BUF", "right", 40, 26, "None", 40, 26),
        (1, 11, 20, 4, "MIA", "right", 42.01, 26, "None", 42.01, 26),
        (1, 11, pd.NA, 5, "football", "right", 0, 0, "pass_forward", 0, 0),
        (1, 11, 10, 5, "BUF", "right", 40, 26, "None", 40, 26),
        (1, 11, 20, 5, "MIA", "right", 43, 26, "None", 43, 26),
    ]
    result = process_game(_tracking(rows), _plays(11), _pff(11, rushers=(20,)))
    aggregate = result.aggregates.iloc[0]

    assert pd.isna(aggregate["threatFrame"])
    assert pd.isna(aggregate["threatTime"])
    assert aggregate["threatReason"] == "sin amenaza"
    assert aggregate["minRusherDistance"] == 2.01
    assert aggregate["minDistanceTime"] == 0.2
    assert pd.isna(aggregate["threatSide"])
    trajectory = result.trajectories[(1, 11)]
    qb_index = trajectory.nflIds.tolist().index(10)
    frame_index = trajectory.frameIds.tolist().index(3)
    assert np.isnan(trajectory.x_norm[qb_index, frame_index])


def test_process_game_handles_missing_snap_and_logs_invalid_time_once() -> None:
    rows = [
        (1, 12, pd.NA, 1, "football", "right", 0, 0, "pass_forward", 0, 0),
        (1, 12, 10, 1, "BUF", "right", 40, 26, "None", 40, 26),
        (1, 12, 20, 1, "MIA", "right", 43, 26, "None", 43, 26),
        (1, 13, pd.NA, 2, "football", "right", 0, 0, "pass_forward", 0, 0),
        (1, 13, pd.NA, 3, "football", "right", 0, 0, "ball_snap", 0, 0),
    ]
    pff = pd.concat([_pff(12, rushers=(20,)), _pff(13, rushers=(20,))], ignore_index=True)
    log = ValidationLog()
    result = process_game(
        _tracking(rows), _plays(12, 13), pff, log, "tracking_1.csv"
    )
    missing_snap = result.aggregates.set_index("playId").loc[12]
    invalid_time = result.aggregates.set_index("playId").loc[13]

    assert missing_snap["timeToThrowReason"] == "sin snap"
    assert missing_snap["threatReason"] == "sin snap"
    assert (1, 12) not in result.trajectories
    assert invalid_time["timeToThrowReason"] == "pase no posterior al snap"
    assert pd.isna(invalid_time["timeToThrow"])
    assert [(issue.check, issue.affected) for issue in log.issues] == [("tiempo_invalido", 1)]
