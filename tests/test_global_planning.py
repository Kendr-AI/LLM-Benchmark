from __future__ import annotations

from collections import Counter

import pytest

from kendr_bench.global_planning import build_interleaved_schedule, validate_schedule


ITEMS = [
    {"item_id": "a", "cluster_id": "c1", "track": "reasoning"},
    {"item_id": "b", "cluster_id": "c2", "track": "coding"},
    {"item_id": "c", "cluster_id": "c3", "track": "reasoning"},
]

LIMITS = {
    "protocol_id": "test-protocol",
    "deadline_ms": 30_000,
    "budget_usd": 0.5,
    "output_cap_tokens": 512,
}


def test_schedule_is_complete_balanced_and_deterministic() -> None:
    first = build_interleaved_schedule(
        ITEMS,
        ["model-a", "model-b"],
        repeats=3,
        days=3,
        regions=["us", "eu", "ap"],
        seed=42,
        **LIMITS,
    )
    second = build_interleaved_schedule(
        ITEMS,
        ["model-a", "model-b"],
        repeats=3,
        days=3,
        regions=["us", "eu", "ap"],
        seed=42,
        **LIMITS,
    )

    assert first == second
    assert len(first) == 3 * 2 * 3
    validation = validate_schedule(
        first,
        item_ids=["a", "b", "c"],
        system_ids=["model-a", "model-b"],
        repeats=3,
    )
    assert validation["valid"] is True
    assert Counter(row["system_id"] for row in first) == {"model-a": 9, "model-b": 9}
    assert all(row["language"] == "unspecified" for row in first)
    assert all(row["modality"] == "unspecified" for row in first)


def test_schedule_rejects_duplicate_items() -> None:
    with pytest.raises(ValueError, match="unique"):
        build_interleaved_schedule(
            [{"item_id": "a"}, {"item_id": "a"}],
            ["model-a"],
            repeats=1,
            days=1,
            regions=["us"],
            seed=1,
            **LIMITS,
        )


def test_validation_detects_missing_cell() -> None:
    schedule = build_interleaved_schedule(
        ITEMS,
        ["model-a", "model-b"],
        repeats=1,
        days=1,
        regions=["us"],
        seed=1,
        **LIMITS,
    )
    result = validate_schedule(
        schedule[:-1],
        item_ids=["a", "b", "c"],
        system_ids=["model-a", "model-b"],
        repeats=1,
    )
    assert result["valid"] is False
    assert len(result["missing"]) == 1
