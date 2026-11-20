"""Focused task 3.1 tests for opponent-scoped tracking ingestion."""

from __future__ import annotations

import gc
import logging
from pathlib import Path
import weakref

import pandas as pd
import pytest

from backend.analytics import (
    Engine,
    REQUIRED_COLUMNS,
    TRACKING_COLUMNS,
    TRACKING_DTYPES,
    load_engine,
)


def _blank(filename: str, rows: int = 0) -> pd.DataFrame:
    return pd.DataFrame(
        {column: pd.Series([pd.NA] * rows, dtype="object") for column in REQUIRED_COLUMNS[filename]}
    )


def _frames() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    games = pd.DataFrame({"gameId": [1, 2, 3], "week": [1, 2, 3]})
    plays = _blank("plays.csv", 4)
    plays["gameId"] = [1, 1, 2, 3]
    plays["playId"] = [10, 11, 20, 30]
    plays["possessionTeam"] = "BUF"
    plays["defensiveTeam"] = ["MIA", "MIA", "MIA", "NYJ"]
    plays["down"] = 1
    plays["yardsToGo"] = 10
    plays["yardlineSide"] = "BUF"
    plays["yardlineNumber"] = 20
    return games, plays, _blank("players.csv"), _blank("pffScoutingData.csv")


def _tracking_rows() -> pd.DataFrame:
    rows = [
        # Valid frame for play 10.
        (1, 10, pd.NA, 1, "football", "right", 30.0, 26.0, "ball_snap"),
        (1, 10, 101, 1, "BUF", "right", 29.0, 25.0, "None"),
        # Two ball rows: the complete frame must be excluded.
        (1, 10, pd.NA, 2, "football", "right", 31.0, 26.0, "None"),
        (1, 10, pd.NA, 2, "football", "right", 31.1, 26.0, "None"),
        (1, 10, 101, 2, "BUF", "right", 30.0, 25.0, "None"),
        # No ball row: the complete frame must be excluded.
        (1, 10, 101, 3, "BUF", "right", 31.0, 25.0, "None"),
        # Invalid team row is removed without removing the valid ball row.
        (1, 10, pd.NA, 4, "football", "right", 33.0, 26.0, "None"),
        (1, 10, 999, 4, "DAL", "right", 32.0, 25.0, "None"),
        # Invalid play direction keeps event rows but suppresses spatial values.
        (1, 11, pd.NA, 1, "football", "RIGHT", 40.0, 20.0, "ball_snap"),
        (1, 11, 102, 1, "MIA", "RIGHT", 41.0, 21.0, "None"),
        # A non-opponent play in the same file must never reach the processor.
        (1, 99, pd.NA, 1, "football", "right", 1.0, 1.0, "None"),
    ]
    return pd.DataFrame(rows, columns=TRACKING_COLUMNS)


def test_ingestion_scopes_games_validates_integrity_and_skips_unreadable(
    caplog: pytest.LogCaptureFixture,
) -> None:
    calls: list[int] = []
    previous: weakref.ReferenceType[pd.DataFrame] | None = None

    def loader(game_id: int) -> pd.DataFrame:
        nonlocal previous
        gc.collect()
        assert previous is None or previous() is None, "previous raw frame remained alive"
        calls.append(game_id)
        if game_id == 2:
            raise OSError("unreadable")
        frame = _tracking_rows()
        previous = weakref.ref(frame)
        return frame

    seen: list[pd.DataFrame] = []
    engine = Engine.from_frames(*_frames(), tracking_loader=loader)
    with caplog.at_level(logging.WARNING, logger="backend.analytics"):
        result = engine.ingest_opponent_tracking(
            "MIA", lambda tracking, _plays, _pff: seen.append(tracking.copy()) or 1
        )

    assert calls == [1, 2]
    assert result.processed == (1,)
    assert result.skipped_games == (2,)
    validated = seen[0]
    assert set(validated["playId"]) == {10, 11}
    assert set(validated.loc[validated["playId"].eq(10), "frameId"]) == {1, 4}
    assert "DAL" not in set(validated["team"])
    assert validated.loc[validated["playId"].eq(10), "x_norm"].notna().all()
    assert validated.loc[validated["playId"].eq(11), ["x_norm", "y_norm"]].isna().all().all()

    messages = [record.getMessage() for record in caplog.records]
    assert sum("tracking_team_invalido" in message and "casos=1" in message for message in messages) == 1
    assert sum("tracking_balon_no_unico_por_cuadro" in message and "casos=2" in message for message in messages) == 1
    assert sum("playDirection_invalido" in message and "casos=1" in message for message in messages) == 1
    assert all("tracking_1.csv" in message for message in messages)


def test_default_tracking_loader_reads_only_approved_columns_and_does_not_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir = tmp_path / "data"
    tracking_dir = data_dir / "tracking"
    tracking_dir.mkdir(parents=True)
    games, plays, players, pff = _frames()
    for filename, frame in zip(
        ("games.csv", "plays.csv", "players.csv", "pffScoutingData.csv"),
        (games, plays, players, pff),
        strict=True,
    ):
        frame.to_csv(data_dir / filename, index=False)
    tracking = _tracking_rows()
    tracking["unapproved"] = "must not load"
    tracking.to_csv(tracking_dir / "tracking_1.csv", index=False)
    before = {
        path.relative_to(data_dir): (path.stat().st_size, path.stat().st_mtime_ns)
        for path in data_dir.rglob("*") if path.is_file()
    }

    original = pd.read_csv
    tracking_calls: list[dict[str, object]] = []

    def spy(path: object, *args: object, **kwargs: object) -> pd.DataFrame:
        if Path(path).name.startswith("tracking_"):
            tracking_calls.append(dict(kwargs))
        return original(path, *args, **kwargs)

    monkeypatch.setattr(pd, "read_csv", spy)
    engine = load_engine(data_dir)
    result = engine.ingest_opponent_tracking("MIA", lambda *_args: None)

    assert result.processed == (None,)
    assert result.skipped_games == (2,)
    assert len(tracking_calls) == 2
    assert tracking_calls[0]["usecols"] == TRACKING_COLUMNS
    assert tracking_calls[0]["dtype"] == TRACKING_DTYPES
    after = {
        path.relative_to(data_dir): (path.stat().st_size, path.stat().st_mtime_ns)
        for path in data_dir.rglob("*") if path.is_file()
    }
    assert after == before
