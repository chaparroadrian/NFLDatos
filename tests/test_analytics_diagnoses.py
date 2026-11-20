"""In-memory tests for task 3.3 protection diagnoses."""

from __future__ import annotations

import random

import pandas as pd

from backend.analytics import (
    DIAGNOSES,
    apply_contextual_diagnoses,
    compute_static_diagnoses,
    diagnosis_tags,
    process_game,
)


def _pff_rows(play_id: int) -> pd.DataFrame:
    rows = [
        (1, play_id, 10, "Pass", "QB", pd.NA, pd.NA, 0, 0, 0, 0),
        (1, play_id, 30, "Pass Block", "LT", 20, pd.NA, 1, 0, 0, 0),
        (1, play_id, 31, "Pass Block", "LG", 20, pd.NA, 0, 0, 0, 0),
        (1, play_id, 32, "Pass Route", "TE", 21, "CH", 0, 0, 0, 0),
        (1, play_id, 20, "Pass Rush", "DE", pd.NA, pd.NA, 0, 0, 0, 0),
        (1, play_id, 21, "Pass Rush", "DT", pd.NA, pd.NA, 0, 0, 0, 0),
    ]
    return pd.DataFrame(
        rows,
        columns=[
            "gameId", "playId", "nflId", "pff_role", "pff_positionLinedUp",
            "pff_nflIdBlockedPlayer", "pff_blockType", "pff_beatenByDefender",
            "pff_hitAllowed", "pff_hurryAllowed", "pff_sackAllowed",
        ],
    )


def _tracking(play_id: int, positions: dict[int, dict[int, tuple[float, float]]]) -> pd.DataFrame:
    rows: list[tuple] = []
    for frame in range(1, 7):
        event = "ball_snap" if frame == 1 else "pass_forward" if frame == 6 else "None"
        rows.append((1, play_id, pd.NA, frame, "football", "right", 0.0, 0.0, event, 0.0, 0.0))
        for nfl_id, frames in positions.items():
            x, y = frames.get(frame, frames[max(key for key in frames if key <= frame)])
            team = "BUF" if nfl_id in {10, 30, 31, 32} else "MIA"
            rows.append((1, play_id, nfl_id, frame, team, "right", x, y, "None", x, y))
    return pd.DataFrame(
        rows,
        columns=[
            "gameId", "playId", "nflId", "frameId", "team", "playDirection",
            "x", "y", "event", "x_norm", "y_norm",
        ],
    )


def test_static_pff_diagnoses_are_ordered_deduplicated_and_source_labelled() -> None:
    tags = compute_static_diagnoses(
        _pff_rows(10), {"freeRusherFlag": True, "stuntFlag": True}
    )

    assert tags == [
        ("Derrota individual", "PFF"),
        ("Posible rusher libre", "inferida"),
        ("Doble equipo", "PFF"),
        ("Chip o ayuda", "PFF"),
        ("Posible intercambio o stunt", "inferida"),
    ]
    assert diagnosis_tags([tags[0][0], tags[0][0]]) == (("Derrota individual", "PFF"),)
    assert diagnosis_tags([]) == (("No determinado con los datos disponibles", "inferida"),)


def test_process_game_detects_free_rusher_stunt_and_qb_movement() -> None:
    pff = _pff_rows(10)
    # Rusher 21 is listed as chip-blocked. Rusher 20 is blocker-assigned, so the
    # stunt can be evaluated without also treating either player as free.
    positions = {
        10: {1: (20, 10), 2: (20, 10), 3: (20, 10), 4: (20, 10), 5: (20, 10), 6: (20, 10)},
        20: {1: (10, 0), 2: (10, 0), 3: (10, 4), 4: (10, 4), 5: (10, 4), 6: (10, 4)},
        21: {1: (10, 2), 2: (10, 2), 3: (10, 2), 4: (10, 2), 5: (10, 2), 6: (10, 2)},
        30: {1: (10, 0), 2: (10, 0), 3: (10, 0), 4: (10, 0), 5: (10, 0), 6: (10, 0)},
        31: {1: (10, 4), 2: (10, 4), 3: (10, 4), 4: (10, 4), 5: (10, 4), 6: (10, 4)},
        32: {1: (10, 6)},
    }
    result = process_game(
        _tracking(10, positions),
        pd.DataFrame({"gameId": [1], "playId": [10]}),
        pff,
    )
    row = result.aggregates.iloc[0]
    assert "Posible intercambio o stunt" in row["staticDiagnoses"]
    assert "Posible rusher libre" not in row["staticDiagnoses"]

    # A second play has an unassigned rusher reaching the QB after the QB exits
    # the default pocket by more than three yards.
    free_pff = pff.copy()
    free_pff.loc[free_pff["nflId"].eq(21), "pff_nflIdBlockedPlayer"] = pd.NA
    free_pff.loc[free_pff["nflId"].eq(32), "pff_nflIdBlockedPlayer"] = pd.NA
    free_positions = {
        10: {1: (40, 26), 2: (41, 26), 3: (42, 26), 4: (44, 26), 5: (44, 26), 6: (44, 26)},
        20: {1: (50, 20)},
        21: {1: (50, 26), 2: (48, 26), 3: (46, 26), 4: (45, 26), 5: (45, 26), 6: (45, 26)},
        30: {1: (40, 22)},
        31: {1: (40, 30)},
        32: {1: (40, 32)},
    }
    free = process_game(
        _tracking(10, free_positions),
        pd.DataFrame({"gameId": [1], "playId": [10]}),
        free_pff,
    ).aggregates.iloc[0]
    assert "Posible rusher libre" in free["staticDiagnoses"]
    assert free["qbMovementFlag"] == True  # noqa: E712


def test_contextual_p75_requires_ten_values_and_all_four_conditions() -> None:
    rows = []
    for play_id, value in enumerate(range(1, 12), start=1):
        rows.append(
            {
                "playId": play_id,
                "timeToThrow": float(value),
                "threatTime": float(value),
                "qbMovementFlag": True,
                "staticDiagnoses": tuple(),
            }
        )
    rows[-2]["staticDiagnoses"] = ("Derrota individual",)
    diagnosed, threshold = apply_contextual_diagnoses(pd.DataFrame(rows))

    assert threshold == 8.5
    assert diagnosed.iloc[-1]["pressureSourceCandidate"] == (
        "Posible presión prolongada por movimiento o retención del QB",
    )
    assert diagnosed.iloc[-2]["pressureSourceCandidate"] == ("Derrota individual",)
    assert diagnosed.iloc[0]["pressureSourceCandidate"] == (
        "No determinado con los datos disponibles",
    )

    short, short_threshold = apply_contextual_diagnoses(pd.DataFrame(rows[:9]))
    assert short_threshold is None
    assert all(
        labels == ("No determinado con los datos disponibles",)
        for labels in short["pressureSourceCandidate"]
    )


def test_diagnosis_order_and_nonempty_fallback_hold_for_random_inputs() -> None:
    """Seeded property check for ordering, deduplication, and source vocabulary."""

    rng = random.Random(3303)
    order = {label: index for index, label in enumerate(DIAGNOSES)}
    for _ in range(100):
        labels = [rng.choice(DIAGNOSES) for _ in range(rng.randint(0, 20))]
        tags = diagnosis_tags(labels)
        names = [name for name, _source in tags]
        assert names
        assert len(names) == len(set(names))
        assert names == sorted(names, key=order.__getitem__)
        assert all(source in {"PFF", "inferida"} for _name, source in tags)
