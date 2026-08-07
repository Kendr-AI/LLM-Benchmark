from __future__ import annotations

import pytest

from kendr_bench.advanced_statistics import (
    approximate_required_items,
    hierarchical_cluster_bootstrap,
    paired_hierarchical_bootstrap,
    wilson_interval,
)


def test_wilson_interval_handles_boundary_rate() -> None:
    result = wilson_interval(10, 10)

    assert result.estimate == 1.0
    assert 0.7 < result.low < 1
    assert result.high == 1.0


def test_wilson_interval_handles_empty_denominator() -> None:
    result = wilson_interval(0, 0)
    assert result.estimate is None
    assert result.low is None


def test_hierarchical_bootstrap_weights_items_not_repeat_rows() -> None:
    rows = [
        {"item_id": "a", "cluster_id": "passage-1", "score": 0.0},
        {"item_id": "a", "cluster_id": "passage-1", "score": 0.0},
        {"item_id": "a", "cluster_id": "passage-1", "score": 0.0},
        {"item_id": "b", "cluster_id": "passage-2", "score": 1.0},
    ]

    result = hierarchical_cluster_bootstrap(rows, samples=500, seed=4)

    assert result.estimate == 0.5
    assert result.items == 2
    assert result.clusters == 2
    assert result.observations == 4
    assert result.low <= result.estimate <= result.high


def test_paired_hierarchical_bootstrap_uses_shared_items() -> None:
    rows = [
        {"system_id": "left", "item_id": "a", "cluster_id": "x", "score": 1.0},
        {"system_id": "right", "item_id": "a", "cluster_id": "x", "score": 0.0},
        {"system_id": "left", "item_id": "b", "cluster_id": "y", "score": 0.5},
        {"system_id": "right", "item_id": "b", "cluster_id": "y", "score": 0.5},
        {"system_id": "left", "item_id": "left-only", "cluster_id": "z", "score": 1.0},
    ]

    result = paired_hierarchical_bootstrap(
        rows,
        left_system="left",
        right_system="right",
        samples=500,
        seed=9,
    )

    assert result.estimate == 0.5
    assert result.items == 2
    assert result.observations == 4


def test_power_planner_behaves_monotonically() -> None:
    easier = approximate_required_items(
        minimum_detectable_effect=0.1,
        standard_deviation=0.25,
        power=0.8,
        paired_correlation=0.5,
    )
    harder = approximate_required_items(
        minimum_detectable_effect=0.02,
        standard_deviation=0.25,
        power=0.9,
        paired_correlation=0.5,
    )

    assert easier > 0
    assert harder > easier


@pytest.mark.parametrize(
    "successes,trials",
    [(-1, 2), (3, 2), (1, -1)],
)
def test_wilson_rejects_invalid_counts(successes: int, trials: int) -> None:
    with pytest.raises(ValueError):
        wilson_interval(successes, trials)
