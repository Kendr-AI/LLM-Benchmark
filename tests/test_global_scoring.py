from __future__ import annotations

import pytest

from kendr_bench.global_scoring import (
    build_global_scorecards,
    normalize_observations,
    pareto_frontier,
)


def _row(system: str, item: str, repeat: int, score: float | None, status: str = "success") -> dict:
    row = {
        "system_id": system,
        "item_id": item,
        "cluster_id": item,
        "repeat": repeat,
        "track": "reasoning" if item == "a" else "coding",
        "status": status,
        "language": "en",
        "modality": "text",
        "difficulty": "hard",
    }
    if score is not None:
        row["score"] = score
    return row


def test_failure_is_retained_as_zero() -> None:
    normalized, errors = normalize_observations(
        [_row("left", "a", 1, None, "timeout")]
    )
    assert errors == []
    assert normalized[0]["score"] == 0.0
    assert normalized[0]["status"] == "timeout"


def test_scorecards_are_track_separated_and_paired() -> None:
    rows = [
        _row("left", "a", 1, 1.0),
        _row("left", "a", 2, 1.0),
        _row("left", "b", 1, None, "provider_failure"),
        _row("left", "b", 2, 1.0),
        _row("right", "a", 1, 0.0),
        _row("right", "a", 2, 0.0),
        _row("right", "b", 1, 0.5),
        _row("right", "b", 2, 0.5),
    ]

    result = build_global_scorecards(rows, bootstrap_samples=200, seed=7)

    assert result["observation_count"] == 8
    assert len(result["systems"]) == 2
    left = next(system for system in result["systems"] if system["system_id"] == "left")
    assert left["track_count"] == 2
    assert left["status_counts"]["provider_failure"] == 1
    assert len(result["comparisons"][0]["tracks"]) == 2


def test_duplicate_observation_is_invalid() -> None:
    row = _row("left", "a", 1, 1.0)
    normalized, errors = normalize_observations([row, row])
    assert len(normalized) == 1
    assert "duplicate identity" in errors[0]


def test_pareto_frontier_retains_tradeoffs() -> None:
    frontier = pareto_frontier(
        [
            {"system_id": "quality", "score": 0.9, "cost": 10},
            {"system_id": "cheap", "score": 0.8, "cost": 1},
            {"system_id": "dominated", "score": 0.7, "cost": 12},
        ],
        metric_directions={"score": "higher", "cost": "lower"},
    )
    assert frontier == ["cheap", "quality"]


def test_invalid_success_score_is_rejected() -> None:
    with pytest.raises(ValueError, match="requires a numeric score"):
        build_global_scorecards([_row("left", "a", 1, None)])


def test_appropriate_safety_refusal_can_receive_preregistered_credit() -> None:
    row = _row("safe", "a", 1, 1.0, "policy_block")
    row["track"] = "safety"
    row["policy_outcome"] = "appropriate_refusal"
    result = build_global_scorecards([row], bootstrap_samples=20)
    system = result["systems"][0]
    assert system["macro_track_score"] == 1.0
    assert system["status_counts"]["policy_block"] == 1


def test_policy_block_on_capability_track_scores_zero() -> None:
    row = _row("safe", "a", 1, 1.0, "policy_block")
    row["policy_outcome"] = "appropriate_refusal"
    normalized, errors = normalize_observations([row])
    assert errors == []
    assert normalized[0]["score"] == 0.0


def test_frozen_schedule_materializes_missing_cells_as_zero() -> None:
    schedule = [
        {
            "schedule_id": "one",
            "system_id": "left",
            "item_id": "a",
            "cluster_id": "a",
            "repeat": 1,
            "track": "reasoning",
            "language": "en",
            "modality": "text",
            "difficulty": "hard",
        },
        {
            "schedule_id": "two",
            "system_id": "right",
            "item_id": "a",
            "cluster_id": "a",
            "repeat": 1,
            "track": "reasoning",
            "language": "en",
            "modality": "text",
            "difficulty": "hard",
        },
    ]
    result = build_global_scorecards(
        [_row("left", "a", 1, 1.0)],
        expected_schedule=schedule,
        bootstrap_samples=20,
    )

    assert result["observation_count"] == 2
    assert result["coverage"]["synthesized_missing_observations"] == 1
    right = next(system for system in result["systems"] if system["system_id"] == "right")
    assert right["status_counts"]["missing"] == 1
    assert right["macro_track_score"] == 0.0


def test_frozen_schedule_rejects_unplanned_observation() -> None:
    schedule = [
        {
            "system_id": "right",
            "item_id": "a",
            "cluster_id": "a",
            "repeat": 1,
            "track": "reasoning",
            "language": "en",
            "modality": "text",
            "difficulty": "hard",
        }
    ]
    with pytest.raises(ValueError, match="outside the frozen schedule"):
        build_global_scorecards(
            [_row("left", "a", 1, 1.0)], expected_schedule=schedule
        )
