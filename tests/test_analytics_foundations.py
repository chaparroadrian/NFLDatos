"""Focused examples for the foundational pure analytics rules."""

from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd
import pytest

from backend.analytics import (
    FIELD_ZONES,
    SECTORS,
    contextual_threshold,
    distance_band,
    distance_to_endzone,
    field_zone,
    forbidden_language,
    json_safe,
    normalize_xy,
    safe_rate,
    sample_quality,
    sector_for,
    select_event_frame,
    time_to_throw,
)


@pytest.mark.parametrize(
    ("down", "yards", "expected"),
    [
        (0, None, "Conversión"),
        (1, 3, "Corta"),
        (1, 4, "Media"),
        (2, 6, "Media"),
        (2, 7, "Larga"),
        (3, 10, "Larga"),
        (4, 11, "Muy larga"),
        (1, 0, None),
        (1, None, None),
    ],
)
def test_distance_band_boundaries(down: int, yards: int | None, expected: str | None) -> None:
    assert distance_band(down, yards) == expected


def test_endzone_distance_and_field_zone_boundaries() -> None:
    assert distance_to_endzone(50, None, "BUF") == 50
    assert distance_to_endzone(20, "BUF", "BUF") == 80
    assert distance_to_endzone(20, "MIA", "BUF") == 20
    assert distance_to_endzone(20, None, "BUF") is None
    assert distance_to_endzone(20.5, "BUF", "BUF") is None

    expected = {
        20: "Zona roja",
        21: "Territorio rival",
        39: "Territorio rival",
        40: "Medio campo",
        59: "Medio campo",
        60: "Propio 21–40",
        79: "Propio 21–40",
        80: "Propio 1–20",
    }
    assert [field_zone(1, distance) for distance in expected] == list(expected.values())
    assert field_zone(0, None) == "Conversión de dos puntos"
    assert field_zone(1, None) is None
    assert FIELD_ZONES[-1] == "Conversión de dos puntos"


@pytest.mark.parametrize(
    ("n", "expected"),
    [(0, "insuficiente"), (9, "insuficiente"), (10, "pequeña"), (29, "pequeña"),
     (30, "moderada"), (99, "moderada"), (100, "amplia")],
)
def test_sample_quality_boundaries(n: int, expected: str) -> None:
    assert sample_quality(n) == expected


def test_safe_rate_handles_zero_and_rejects_invalid_counts() -> None:
    assert safe_rate(1, 4) == 0.25
    assert safe_rate(0, 0) is None
    assert safe_rate(1, 0) is None
    with pytest.raises(ValueError):
        safe_rate(2, 1)
    with pytest.raises(ValueError):
        sample_quality(-1)


def test_coordinate_normalization_and_missing_values() -> None:
    assert normalize_xy(10, 5, "right") == (10.0, 5.0)
    left = normalize_xy(10, 5, "left")
    assert left == pytest.approx((110.0, 48.3), abs=1e-6)
    assert normalize_xy(*left, "left") == pytest.approx((10.0, 5.0), abs=1e-6)
    assert normalize_xy(None, 5, "left") == (None, None)
    assert normalize_xy(10, 5, "LEFT") == (None, None)


def test_event_selection_uses_exact_manual_priority_and_earliest_frame() -> None:
    events = pd.DataFrame(
        {
            "frameId": [7, 4, 8, 3, 1],
            "event": [
                "autoevent_ballsnap",
                "ball_snap",
                "ball_snap",
                "None",
                "Ball_Snap",
            ],
        }
    )
    assert select_event_frame(events, "ball_snap", "autoevent_ballsnap") == (4, "manual")
    assert select_event_frame(
        events.loc[events["event"] != "ball_snap"],
        "ball_snap",
        "autoevent_ballsnap",
    ) == (7, "automática")
    assert select_event_frame(events, "pass_forward", "autoevent_passforward") == (
        None,
        "ausente",
    )


@pytest.mark.parametrize(
    ("snap", "pass_frame", "expected"),
    [
        (10, 35, (2.5, None)),
        (None, 35, (None, "sin snap")),
        (10, None, (None, "sin pase")),
        (10, 10, (None, "pase no posterior al snap")),
        (10, 9, (None, "pase no posterior al snap")),
    ],
)
def test_time_to_throw_rules(
    snap: int | None,
    pass_frame: int | None,
    expected: tuple[float | None, str | None],
) -> None:
    assert time_to_throw(snap, pass_frame) == expected


@pytest.mark.parametrize(
    ("delta", "expected"),
    [
        (4.0, "Izquierda"),
        (1.5, "Interior izquierda"),
        (1.499999, "Centro"),
        (-1.499999, "Centro"),
        (-1.5, "Interior derecha"),
        (-3.999999, "Interior derecha"),
        (-4.0, "Derecha"),
    ],
)
def test_sector_partition_boundaries(delta: float, expected: str) -> None:
    assert sector_for(delta) == expected
    assert expected in SECTORS


def test_contextual_threshold_requires_ten_finite_values() -> None:
    assert contextual_threshold(range(9)) is None
    values = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, np.nan, math.inf]
    assert contextual_threshold(values) == pytest.approx(6.75)


def test_forbidden_language_uses_whole_terms_and_optional_blame_words() -> None:
    assert forbidden_language("Esta formación EVITA la presión.")
    assert forbidden_language("Eso garantiza el resultado.")
    assert not forbidden_language("La evidencia muestra una asociación.")
    assert not forbidden_language("El responsable fue señalado.")
    assert forbidden_language("El responsable fue señalado.", include_blame=True)
    assert not forbidden_language("Una causalidad no está demostrada.")


def test_json_safe_recursively_removes_nonfinite_and_converts_numpy_values() -> None:
    value = {
        "nan": np.float64("nan"),
        "infinity": float("inf"),
        "missing": pd.NA,
        "integer": np.int64(4),
        "boolean": np.bool_(True),
        "array": np.array([1.5, np.nan]),
        "tuple": (np.float32(2.5),),
        "ordered": frozenset({"b", "a"}),
    }

    converted = json_safe(value)

    assert converted == {
        "nan": None,
        "infinity": None,
        "missing": None,
        "integer": 4,
        "boolean": True,
        "array": [1.5, None],
        "tuple": [2.5],
        "ordered": ["a", "b"],
    }
    encoded = json.dumps(converted, allow_nan=False)
    assert "NaN" not in encoded and "Infinity" not in encoded
