"""Focused in-memory tests for task 3.4 tracking and result caches."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import random
import threading
import time

import pandas as pd
import pytest

import backend.analytics as analytics
from backend.analytics import (
    Engine,
    REQUIRED_COLUMNS,
    TRACKING_COLUMNS,
    TrackingComputationError,
    canonical_filter_key,
)


def _blank(filename: str, rows: int = 0) -> pd.DataFrame:
    return pd.DataFrame(
        {
            column: pd.Series([pd.NA] * rows, dtype="object")
            for column in REQUIRED_COLUMNS[filename]
        }
    )


def _engine(loader: analytics.TrackingLoader) -> Engine:
    games = pd.DataFrame({"gameId": [1], "week": [1]})
    plays = _blank("plays.csv", 1)
    plays.loc[0, ["gameId", "playId", "possessionTeam", "defensiveTeam"]] = [
        1,
        10,
        "BUF",
        "MIA",
    ]
    plays.loc[0, ["down", "yardsToGo", "yardlineNumber"]] = [1, 10, 20]
    plays.loc[0, "yardlineSide"] = "BUF"
    return Engine.from_frames(
        games,
        plays,
        _blank("players.csv"),
        _blank("pffScoutingData.csv"),
        tracking_loader=loader,
    )


def _tracking() -> pd.DataFrame:
    return pd.DataFrame(
        [
            (1, 10, pd.NA, 1, "football", "right", 30.0, 26.0, "ball_snap"),
            (1, 10, pd.NA, 2, "football", "right", 31.0, 26.0, "None"),
        ],
        columns=TRACKING_COLUMNS,
    )


def test_same_opponent_concurrency_computes_once_and_exposes_status() -> None:
    entered = threading.Event()
    release = threading.Event()
    calls = 0

    def loader(_game_id: int) -> pd.DataFrame:
        nonlocal calls
        calls += 1
        entered.set()
        assert release.wait(timeout=2)
        return _tracking()

    engine = _engine(loader)
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(engine.ensure_rival, "MIA")
        assert entered.wait(timeout=2)
        assert engine.rival_status("MIA") == {
            "opponent": "MIA",
            "trackingReady": False,
            "inProgress": True,
        }
        second = executor.submit(engine.ensure_rival, "MIA")
        time.sleep(0.02)
        release.set()
        first_result = first.result(timeout=2)
        second_result = second.result(timeout=2)

    assert calls == 1
    assert first_result is second_result
    assert first_result.aggregates[["gameId", "playId"]].values.tolist() == [[1, 10]]
    assert engine.rival_status("MIA") == {
        "opponent": "MIA",
        "trackingReady": True,
        "inProgress": False,
    }
    assert engine.ensure_rival("MIA") is first_result
    assert calls == 1


def test_failed_tracking_attempt_commits_nothing_releases_lock_and_can_retry() -> None:
    calls = 0

    def loader(_game_id: int) -> pd.DataFrame:
        nonlocal calls
        calls += 1
        return _tracking()

    def fail_processor(*_args: object) -> object:
        raise RuntimeError("processor failed")

    engine = _engine(loader)
    with pytest.raises(TrackingComputationError):
        engine.ensure_rival("MIA", fail_processor)

    assert engine.rival_status("MIA") == {
        "opponent": "MIA",
        "trackingReady": False,
        "inProgress": False,
    }
    recovered = engine.ensure_rival("MIA")
    assert calls == 2
    assert len(recovered.aggregates) == 1
    assert engine.rival_status("MIA")["trackingReady"] is True


def test_result_cache_is_canonical_bounded_lru_and_isolates_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(analytics, "RESULT_CACHE_MAX", 3)
    engine = _engine(lambda _game_id: _tracking())
    first_filters = {"opponent": "MIA", "down": 3, "week": None}
    reordered = {"week": None, "down": 3, "opponent": "MIA"}
    original = {"sample": {"plays": 4}, "values": [1, 2]}

    stored = engine.cache_result(first_filters, original)
    original["sample"]["plays"] = 99
    stored["values"].append(3)
    assert engine.get_cached_result(reordered) == {
        "sample": {"plays": 4},
        "values": [1, 2],
    }

    engine.cache_result({"key": "b"}, {"value": "b"})
    engine.cache_result({"key": "c"}, {"value": "c"})
    assert engine.get_cached_result(first_filters) is not None  # refresh LRU position
    engine.cache_result({"key": "d"}, {"value": "d"})

    assert engine.result_cache_size == 3
    assert engine.get_cached_result({"key": "b"}) is None
    assert engine.get_cached_result(reordered) == {
        "sample": {"plays": 4},
        "values": [1, 2],
    }


def test_canonical_filter_keys_and_cache_hits_ignore_mapping_order() -> None:
    """Property 18: deterministic result-cache reuse for normalized filters.

    **Validates: Requirements 2.8, 2.10, 12.13, 14.6**
    """

    rng = random.Random(3404)
    engine = _engine(lambda _game_id: _tracking())
    for case in range(100):
        pairs = [
            ("opponent", rng.choice(["MIA", "NYJ", "BUF"])),
            ("down", rng.choice([None, 0, 1, 2, 3, 4])),
            ("week", rng.choice([None, 1, 8])),
            ("coverage", rng.choice([None, "Cover-1", "Cover-3"])),
        ]
        first = dict(pairs)
        rng.shuffle(pairs)
        permuted = dict(pairs)
        assert canonical_filter_key(first) == canonical_filter_key(permuted)

        expected = {"case": case, "filters": first.copy()}
        engine.cache_result(first, expected)
        assert engine.get_cached_result(permuted) == expected
