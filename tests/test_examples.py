from __future__ import annotations

import json
from pathlib import Path

from kendr_bench.global_scoring import build_global_scorecards


ROOT = Path(__file__).resolve().parents[1]


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def compact_scorecard(report: dict) -> dict:
    def tracks(values: list[dict]) -> list[dict]:
        return [
            {
                "track": value["track"],
                "estimate": value["estimate"],
                "low": value["low"],
                "high": value["high"],
            }
            for value in values
        ]

    return {
        "fixture_version": "1.0",
        "coverage": report["coverage"],
        "systems": [
            {
                "system_id": system["system_id"],
                "macro_track_score": system["macro_track_score"],
                "status_counts": system["status_counts"],
                "tracks": tracks(system["tracks"]),
            }
            for system in report["systems"]
        ],
        "comparisons": [
            {
                "left_system": comparison["left_system"],
                "right_system": comparison["right_system"],
                "effect_direction": comparison["effect_direction"],
                "tracks": tracks(comparison["tracks"]),
            }
            for comparison in report["comparisons"]
        ],
    }


def test_toy_example_matches_checked_in_expected_summary() -> None:
    observations = read_jsonl(ROOT / "examples/toy-observations.jsonl")
    schedule = read_jsonl(ROOT / "examples/toy-schedule.jsonl")
    expected = json.loads(
        (ROOT / "examples/expected/toy-scorecards-summary.json").read_text(
            encoding="utf-8"
        )
    )

    actual = build_global_scorecards(
        observations,
        expected_schedule=schedule,
        bootstrap_samples=500,
        seed=7,
    )

    assert compact_scorecard(actual) == expected
    assert actual["observation_count"] == 6
    assert actual["coverage"]["synthesized_missing_observations"] == 1
