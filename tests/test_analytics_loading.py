"""Task 2.2 tests for startup CSV loading and validation summaries."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import pytest

from backend.analytics import (
    APPROVED_STARTUP_FILES,
    DataLoadError,
    REQUIRED_COLUMNS,
    ValidationLog,
    load_engine,
)


def _frame(filename: str, rows: int = 1) -> pd.DataFrame:
    values: dict[str, list[object]] = {}
    for column in REQUIRED_COLUMNS[filename]:
        default: object = 0
        if column in {
            "playDescription", "gameClock", "possessionTeam", "defensiveTeam",
            "yardlineSide", "offenseFormation", "personnelO", "personnelD",
            "dropBackType", "pff_passCoverage", "pff_passCoverageType", "passResult",
            "displayName", "officialPosition", "pff_role", "pff_positionLinedUp",
            "pff_blockType",
        }:
            default = "value"
        values[column] = [default] * rows
    return pd.DataFrame(values)


def _valid_frames() -> dict[str, pd.DataFrame]:
    games = _frame("games.csv")
    games.loc[0, ["gameId", "week"]] = [1, 1]

    plays = _frame("plays.csv")
    plays.loc[0, ["gameId", "playId"]] = [1, 10]

    players = _frame("players.csv", 22)
    players["nflId"] = range(1, 23)

    pff = _frame("pffScoutingData.csv", 22)
    pff["gameId"] = 1
    pff["playId"] = 10
    pff["nflId"] = range(1, 23)
    pff["pff_role"] = ["Pass"] + ["Pass Block"] * 5 + ["Pass Route"] * 5 + ["Pass Rush"] * 4 + ["Coverage"] * 7
    return {
        "games.csv": games,
        "plays.csv": plays,
        "players.csv": players,
        "pffScoutingData.csv": pff,
    }


def _write_frames(data_dir: Path, frames: dict[str, pd.DataFrame]) -> None:
    data_dir.mkdir()
    for filename, frame in frames.items():
        frame.to_csv(data_dir / filename, index=False)


def test_load_engine_reads_only_four_approved_files_once_and_does_not_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir = tmp_path / "data"
    _write_frames(data_dir, _valid_frames())
    extra = data_dir / "unapproved.csv"
    extra.write_text("secret\nunchanged\n", encoding="utf-8")
    before = {path.name: (path.stat().st_size, path.stat().st_mtime_ns) for path in data_dir.iterdir()}

    original = pd.read_csv
    calls: list[Path] = []

    def spy(path: object, *args: object, **kwargs: object) -> pd.DataFrame:
        calls.append(Path(path))
        return original(path, *args, **kwargs)

    monkeypatch.setattr(pd, "read_csv", spy)
    engine = load_engine(data_dir)

    assert [path.name for path in calls] == list(APPROVED_STARTUP_FILES)
    assert len(engine.plays) == 1
    after = {path.name: (path.stat().st_size, path.stat().st_mtime_ns) for path in data_dir.iterdir()}
    assert after == before


def test_load_engine_rejects_missing_file_and_required_column(tmp_path: Path) -> None:
    missing_dir = tmp_path / "missing"
    missing_dir.mkdir()
    with pytest.raises(DataLoadError, match="games.csv"):
        load_engine(missing_dir)

    frames = _valid_frames()
    frames["plays.csv"] = frames["plays.csv"].drop(columns="yardsToGo")
    invalid_dir = tmp_path / "invalid"
    _write_frames(invalid_dir, frames)
    with pytest.raises(DataLoadError, match=r"plays\.csv.*yardsToGo"):
        load_engine(invalid_dir)


def test_validation_preserves_first_play_and_summarizes_each_check_once(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    frames = _valid_frames()
    duplicate = frames["plays.csv"].copy()
    duplicate.loc[0, "playDescription"] = "second"
    frames["plays.csv"].loc[0, "playDescription"] = "first"
    frames["plays.csv"] = pd.concat([frames["plays.csv"], duplicate], ignore_index=True)
    frames["pffScoutingData.csv"].loc[0, "nflId"] = 999999
    frames["pffScoutingData.csv"].loc[1, "pff_role"] = "Unknown"
    data_dir = tmp_path / "data"
    _write_frames(data_dir, frames)

    with caplog.at_level(logging.WARNING, logger="backend.analytics"):
        engine = load_engine(data_dir)

    assert engine.plays.iloc[0]["playDescription"] == "first"
    assert len(engine.plays) == 1
    assert pd.isna(engine.pff_with_players.iloc[0]["displayName"])
    assert (1, 10) in engine.invalid_role_play_keys
    messages = [record.getMessage() for record in caplog.records]
    assert sum("plays_llave_duplicada" in message for message in messages) == 1
    assert sum("pff_nflId_sin_jugador" in message for message in messages) == 1
    assert sum("pff_roles_no_11_11" in message for message in messages) == 1
    assert all("casos=1" in message for message in messages)
    assert all(str(data_dir) not in message for message in messages)


def test_validation_log_omits_zero_and_deduplicates_check_file(
    caplog: pytest.LogCaptureFixture,
) -> None:
    log = ValidationLog()
    with caplog.at_level(logging.WARNING, logger="backend.analytics"):
        log.warn("check", "plays.csv", 0)
        log.warn("check", "plays.csv", 2)
        log.warn("check", "plays.csv", 9)

    assert len(log.issues) == 1
    assert log.issues[0].affected == 2
    assert len(caplog.records) == 1
