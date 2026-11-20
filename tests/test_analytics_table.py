"""Focused task 2.3 tests for the startup analytical table."""

from __future__ import annotations

import pandas as pd

from backend.analytics import Engine, REQUIRED_COLUMNS


def _blank_frame(filename: str, rows: int) -> pd.DataFrame:
    return pd.DataFrame({column: [pd.NA] * rows for column in REQUIRED_COLUMNS[filename]})


def _frames() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    games = pd.DataFrame({"gameId": [1], "week": [2]})
    plays = _blank_frame("plays.csv", 3)
    plays["gameId"] = 1
    plays["playId"] = [10, 20, 30]
    plays["playDescription"] = ["result sack", "PFF sack", "without PFF"]
    plays["possessionTeam"] = "BUF"
    plays["defensiveTeam"] = "MIA"
    plays["quarter"] = 1
    plays["gameClock"] = "10:00"
    plays["down"] = [3, 2, 1]
    plays["yardsToGo"] = [8, 2, pd.NA]
    plays["yardlineSide"] = ["BUF", "MIA", pd.NA]
    plays["yardlineNumber"] = [20, 15, pd.NA]
    plays["offenseFormation"] = "SHOTGUN"
    plays["personnelO"] = "1 RB, 1 TE, 3 WR"
    plays["personnelD"] = "4 DL, 2 LB, 5 DB"
    plays["defendersInBox"] = [6, 7, pd.NA]
    plays["pff_playAction"] = [1, 0, pd.NA]
    plays["dropBackType"] = "TRADITIONAL"
    plays["pff_passCoverage"] = "Cover-3"
    plays["pff_passCoverageType"] = "Zone"
    plays["passResult"] = ["S", "C", pd.NA]
    plays["prePenaltyPlayResult"] = [0, 5, pd.NA]
    plays["playResult"] = [0, 5, pd.NA]

    players = pd.DataFrame(
        {
            "nflId": range(1, 45),
            "displayName": [f"Player {n}" for n in range(1, 45)],
            "officialPosition": ["X"] * 44,
        }
    )
    roles = (
        ["Pass"] + ["Pass Block"] * 5 + ["Pass Route"] * 5
        + ["Pass Rush"] * 4 + ["Coverage"] * 7
    )
    pff = _blank_frame("pffScoutingData.csv", 44)
    pff["gameId"] = 1
    pff["playId"] = [10] * 22 + [20] * 22
    pff["nflId"] = range(1, 45)
    pff["pff_role"] = roles + roles
    pff["pff_positionLinedUp"] = "X"

    # Play 10 has a route chip and an offensive charge, but no PFF sack.
    pff.loc[6, "pff_blockType"] = "CH"
    pff.loc[6, "pff_nflIdBlockedPlayer"] = 12
    pff.loc[1, "pff_nflIdBlockedPlayer"] = 12
    pff.loc[2, "pff_nflIdBlockedPlayer"] = 12
    pff.loc[1, "pff_hurryAllowed"] = 1
    pff.loc[12, "pff_hurry"] = 1
    pff.loc[12:21, "pff_sack"] = 0

    # Play 20 has a PFF sack although its observed result is a completion.
    pff.loc[34:43, ["pff_hit", "pff_hurry", "pff_sack"]] = 0
    pff.loc[34, "pff_sack"] = 1
    return games, plays, players, pff


def test_table_preserves_every_play_and_builds_context_and_pending_tracking() -> None:
    engine = Engine.from_frames(*_frames())
    table = engine.analytical_table.set_index("playId")

    assert list(engine.analytical_table["playId"]) == [10, 20, 30]
    assert engine.analytical_table[["gameId", "playId"]].duplicated().sum() == 0
    assert table.loc[10, "week"] == 2
    assert table.loc[10, "distanceBand"] == "Larga"
    assert table.loc[10, "fieldZone"] == "Propio 1–20"
    assert table.loc[20, "distanceBand"] == "Corta"
    assert table.loc[20, "fieldZone"] == "Zona roja"
    assert pd.isna(table.loc[30, "distanceBand"])
    assert pd.isna(table.loc[30, "fieldZone"])
    assert table.loc[10, "playAction"] == True  # noqa: E712
    assert pd.isna(table.loc[30, "playAction"])
    assert set(table["trackingStatus"]) == {"pendiente"}
    assert table["timeToThrow"].isna().all()
    assert table.loc[10, "pressureSourceCandidate"] == (
        "Derrota individual", "Doble equipo", "Chip o ayuda"
    )
    assert table.loc[20, "pressureSourceCandidate"] == (
        "No determinado con los datos disponibles",
    )
    assert table.loc[30, "pressureSourceCandidate"] == (
        "No determinado con los datos disponibles",
    )


def test_pff_aggregates_keep_roles_chips_nulls_and_sack_sources_independent() -> None:
    table = Engine.from_frames(*_frames()).analytical_table.set_index("playId")

    assert table.loc[10, "passRushers"] == 4
    assert table.loc[10, "passBlockers"] == 5
    assert table.loc[10, "isApproximateBlitz"] == False  # noqa: E712
    assert table.loc[10, "hasPffPressure"] == True  # noqa: E712
    assert table.loc[10, "hasHurry"] == True  # noqa: E712
    assert table.loc[10, "hasSack"] == False  # noqa: E712
    assert table.loc[10, "hasOffensiveCharge"] == True  # noqa: E712
    assert table.loc[10, "chipFlag"] == True  # noqa: E712
    assert table.loc[10, "dblTeam"] == True  # noqa: E712
    assert table.loc[10, "blockTypes"] == frozenset()
    assert table.loc[10, "blockedIds"] == frozenset({12})

    assert table.loc[10, "passResult"] == "S" and not table.loc[10, "hasSack"]
    assert table.loc[20, "passResult"] == "C" and table.loc[20, "hasSack"]

    required_nulls = [
        "passRushers", "passBlockers", "hasPffPressure", "hasHurry", "hasHit",
        "hasSack", "hasBeatenBlocker", "hasOffensiveCharge",
    ]
    assert table.loc[30, required_nulls].isna().all()


def test_all_null_pff_sources_remain_null_instead_of_false() -> None:
    games, plays, players, pff = _frames()
    first_play = pff["playId"].eq(10)
    pff.loc[first_play, ["pff_hit", "pff_hurry", "pff_sack"]] = pd.NA
    pff.loc[first_play & pff["pff_role"].eq("Pass Block"), [
        "pff_hitAllowed", "pff_hurryAllowed", "pff_sackAllowed",
    ]] = pd.NA

    row = Engine.from_frames(games, plays, players, pff).analytical_table.set_index("playId").loc[10]
    assert pd.isna(row["hasPffPressure"])
    assert pd.isna(row["hasHit"])
    assert pd.isna(row["hasHurry"])
    assert pd.isna(row["hasSack"])
    assert pd.isna(row["hasOffensiveCharge"])
