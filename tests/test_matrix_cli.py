from __future__ import annotations

import json

from kendr_bench.matrix_cli import (
    DEFAULT_MATRIX_TASKS,
    DEFAULT_MODEL_PANEL,
    _category_scores,
    _leaderboard_row,
    _write_leaderboard,
)


def test_default_matrix_is_stratified_and_contains_open_weight_models():
    assert len(DEFAULT_MATRIX_TASKS) == 5
    assert len(DEFAULT_MODEL_PANEL) == 9
    assert sum(
        model.access == "Open-weight via Kendr"
        for model in DEFAULT_MODEL_PANEL
    ) == 4


def test_write_leaderboard_ranks_quality_first(tmp_path):
    rows = [
        {
            "rank": None,
            "model": "Lower",
            "panel_key": "openai-terra",
            "provider": "openai",
            "requested_model": "gpt-5.6-terra",
            "access": "Direct proprietary API",
            "license": "Proprietary",
            "license_source": "https://example.com",
            "questions_scored": 5,
            "quality_score": 0.5,
            "input_tokens": 10,
            "output_tokens": 10,
            "total_tokens": 20,
            "cost_usd": "0.001",
            "latency_p50_ms": 10,
            "latency_p95_ms": 20,
            "tokens_per_quality_point": 8,
            "answer_success_rate": 1,
            "output_cap_compliance_rate": 1,
            "reasoning_score": 0.5,
            "quality_ci95_low": 0.3,
            "quality_ci95_high": 0.7,
            "quality_ci95_degenerate": False,
            "_capability_keys": ["reasoning"],
            "_question_scores": {"q1": 0.0, "q2": 1.0},
        },
        {
            "rank": None,
            "model": "Higher",
            "panel_key": "openai-sol",
            "provider": "openai",
            "requested_model": "gpt-5.6-sol",
            "access": "Direct proprietary API",
            "license": "Proprietary",
            "license_source": "https://example.com",
            "questions_scored": 5,
            "quality_score": 0.8,
            "input_tokens": 20,
            "output_tokens": 20,
            "total_tokens": 40,
            "cost_usd": "0.004",
            "latency_p50_ms": 20,
            "latency_p95_ms": 30,
            "tokens_per_quality_point": 10,
            "answer_success_rate": 1,
            "output_cap_compliance_rate": 1,
            "reasoning_score": 0.8,
            "quality_ci95_low": 0.6,
            "quality_ci95_high": 1.0,
            "quality_ci95_degenerate": True,
            "_capability_keys": ["reasoning"],
            "_question_scores": {"q1": 1.0, "q2": 1.0},
        },
    ]

    _write_leaderboard(
        tmp_path,
        matrix_id="matrix",
        rows=rows,
        failures=[],
        tasks=["live_bench/reasoning/zebra_puzzle"],
        release="2026-06-25",
        questions_per_task=5,
        max_tokens=2048,
        parallel_requests=1,
    )

    document = json.loads(
        (tmp_path / "leaderboard.json").read_text(encoding="utf-8")
    )
    assert document["results"][0]["model"] == "Higher"
    assert (tmp_path / "leaderboard.csv").is_file()
    report = (tmp_path / "leaderboard.md").read_text(encoding="utf-8")
    assert "Quality by capability" in report
    # Overlapping intervals must not be presented as a separated ranking.
    assert [row["tier"] for row in document["results"]] == [1, 1]
    assert document["adjacent_pair_tests"][0]["separates_at_95"] is False
    assert "1 | Higher" not in report.replace("| 1 | 1 | Higher", "")
    # Intermediates stay out of the published artifacts.
    assert "_question_scores" not in json.dumps(document)
    assert "_capability_keys" not in (
        tmp_path / "leaderboard.csv"
    ).read_text(encoding="utf-8")
    # The overall-quality columns must not be rendered as capabilities.
    capability_header = report.split("## Quality by capability")[1]
    assert "End To End Quality" not in capability_header
    assert "Conditional Quality" not in capability_header


def test_leaderboard_row_separates_quality_from_availability(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "answers.jsonl").write_text("", encoding="utf-8")
    (run_dir / "judgments.jsonl").write_text("", encoding="utf-8")
    summary = {
        "current_api_run": {
            "input_tokens": 100,
            "output_tokens": 50,
            "total_tokens": 150,
            "cost_usd": "0.030",
            "kendr_credits": "0.120",
        },
        "current_run_quality": {
            "questions_scored": 4,
            "quality_points": 2.0,
            "objective_score_mean": 0.5,
            "perfect_score_rate": 0.25,
            "nonzero_score_rate": 0.5,
        },
        "efficiency": {
            "output_tokens_per_second": 10,
            "total_tokens_per_quality_point": 75,
            "quality_points_per_1000_tokens": 13.333,
            "usd_per_quality_point": 0.015,
            "quality_points_per_usd": 66.667,
        },
        "latency": {
            "end_to_end_ms": {"mean": 1000, "p50": 900, "p95": 1400},
            "failed_request_ms": {"mean": 60000, "p50": 60000, "p95": 60000},
        },
        "reliability": {
            "successful_answers": 2,
            "failed_answers": 2,
            "answer_success_rate": 0.5,
            "scoring_coverage": 1,
            "output_cap_compliance_rate": 1,
            "route_distribution": {"kc-glm-5": 2},
            "provider_error_distribution": {"InternalServerError": 2},
        },
    }

    row = _leaderboard_row(DEFAULT_MODEL_PANEL[0], run_dir, summary)

    assert row["end_to_end_quality_score"] == 0.5
    assert row["quality_score"] == 0.5
    assert row["conditional_quality_score"] == 1.0
    assert row["availability"] == 0.5
    assert row["attempted_answers"] == 4
    assert row["failed_latency_p50_ms"] == 60000
    assert row["cost_per_successful_answer"] == 0.015


def test_category_scores_normalize_failed_answer_to_zero(tmp_path):
    answers = tmp_path / "answers.jsonl"
    judgments = tmp_path / "judgments.jsonl"
    answers.write_text(
        json.dumps(
            {
                "question_id": "failed",
                "choices": [{"turns": ["$ERROR$"]}],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    judgments.write_text(
        json.dumps(
            {
                "question_id": "failed",
                "category": "instruction_following",
                "score": 0.333,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    assert _category_scores(judgments, answers) == {
        "instruction_following": 0.0
    }
