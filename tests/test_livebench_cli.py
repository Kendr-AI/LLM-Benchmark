from __future__ import annotations

import json
from argparse import Namespace
from decimal import Decimal
from pathlib import Path

from kendr_bench.livebench_cli import (
    DEFAULT_BENCHMARKS,
    _current_run_question_ids,
    _generation_command,
    _paths_for_benches,
    _percentile,
    _write_summary,
)


def test_generation_command_uses_adapter_and_fixed_single_choice(tmp_path):
    args = Namespace(
        model="kendr-intelligent",
        model_display_name="kendr-intelligent",
        api_base="https://kendr.org/v1",
        bench_name=["live_bench/reasoning"],
        livebench_release_option="2024-11-25",
        max_tokens=512,
        parallel_requests=2,
        question_begin=0,
        question_end=1,
        question_id=None,
        resume=True,
        retry_failures=True,
    )

    command = _generation_command(args, tmp_path)

    assert "kendr_bench.livebench_worker" in command
    assert command[command.index("--num-choices") + 1] == "1"
    assert command[command.index("--question-end") + 1] == "1"
    assert "--resume" in command
    assert "--retry-failures" in command


def test_paths_for_benches_stays_within_selected_category(tmp_path):
    selected = (
        tmp_path
        / "data"
        / "live_bench"
        / "reasoning"
        / "task"
        / "model_answer"
        / "model.jsonl"
    )
    unselected = (
        tmp_path
        / "data"
        / "live_bench"
        / "math"
        / "task"
        / "model_answer"
        / "model.jsonl"
    )
    selected.parent.mkdir(parents=True)
    unselected.parent.mkdir(parents=True)
    selected.write_text("{}\n", encoding="utf-8")
    unselected.write_text("{}\n", encoding="utf-8")

    found = _paths_for_benches(
        tmp_path,
        ["live_bench/reasoning"],
        "model_answer/model.jsonl",
    )

    assert found == [selected]
    assert len(DEFAULT_BENCHMARKS) == 6


def test_percentile_uses_linear_interpolation():
    assert _percentile([], 95) is None
    assert _percentile([10], 95) == 10
    assert _percentile([10, 20, 30], 50) == 20
    assert _percentile([10, 20], 95) == 19.5


def test_current_run_question_ids_joins_request_ids():
    calls = [{"request_id": "current-request"}]
    answers = [
        {
            "question_id": "current-question",
            "api_info": {
                "kendr_calls": [{"request_id": "current-request"}]
            },
        },
        {
            "question_id": "old-question",
            "api_info": {"kendr_calls": [{"request_id": "old-request"}]},
        },
    ]

    assert _current_run_question_ids(calls, answers) == {
        "current-question"
    }


def test_current_run_question_ids_supports_provider_neutral_metadata():
    calls = [{"request_id": "openai-request"}]
    answers = [
        {
            "question_id": "question",
            "api_info": {
                "benchmark_calls": [{"request_id": "openai-request"}]
            },
        }
    ]

    assert _current_run_question_ids(calls, answers) == {"question"}


def _summary_args(max_tokens: int = 2048) -> Namespace:
    return Namespace(
        provider="kendr",
        model="kendr-intelligent",
        model_display_name="kendr-intelligent",
        livebench_release_option="2026-06-25",
        bench_name=["live_bench/reasoning/zebra_puzzle"],
        max_tokens=max_tokens,
    )


def _call(
    request_id: str,
    *,
    output_tokens: int,
    error: dict | None = None,
    cost_usd: str | None = "0.001",
) -> dict:
    return {
        "request_id": request_id,
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": output_tokens,
        },
        "kendr_usage": {"credits_charged": "0.5"} if not error else {},
        "cost_usd": None if error else cost_usd,
        "latency_ms": 1000.0,
        "error": error,
    }


def _answer(question_id: str, request_ids: list[str], failed=False) -> dict:
    return {
        "question_id": question_id,
        "choices": [{"turns": ["$ERROR$" if failed else "answer"]}],
        "api_info": {
            "benchmark_calls": [
                {"request_id": request_id} for request_id in request_ids
            ]
        },
    }


def test_write_summary_counts_a_rejected_over_cap_attempt_as_a_violation(
    tmp_path,
):
    """The truncation that caused the failure is the loudest cap breach.

    Measuring compliance over successful calls only excluded it from both
    numerator and denominator, hiding it entirely.
    """
    calls = [
        _call("retry-failed", output_tokens=4096, error={"type": "Err"}),
        _call("retry-ok", output_tokens=500),
        _call("plain", output_tokens=600),
    ]
    answers = [
        _answer("q1", ["retry-failed", "retry-ok"]),
        _answer("q2", ["plain"]),
    ]
    judgments = [
        {"question_id": "q1", "category": "reasoning", "score": 1.0},
        {"question_id": "q2", "category": "reasoning", "score": 0.5},
    ]

    summary = _write_summary(
        args=_summary_args(),
        run_id="run",
        run_dir=tmp_path,
        root=tmp_path,
        calls=calls,
        answers=answers,
        judgments=judgments,
        usd_per_credit=Decimal("0.002"),
        copied_scores=[],
    )

    reliability = summary["reliability"]
    api = summary["current_api_run"]
    assert reliability["calls_exceeding_requested_output_cap"] == 1
    assert reliability["output_cap_measured_attempts"] == 3
    assert reliability["output_cap_compliance_rate"] == 2 / 3
    # The generated tokens are real even though the answer was rejected.
    assert api["maximum_output_tokens_observed"] == 4096
    assert api["failed_attempt_output_tokens"] == 4096
    assert api["output_tokens"] == 4096 + 500 + 600
    # An uncharged failed attempt must not add cost.
    assert api["cost_usd"] == "0.002"


def test_write_summary_normalizes_failed_answers_and_bounds_them(tmp_path):
    """A grader crediting the $ERROR$ sentinel must not raise quality."""
    calls = [_call("c1", output_tokens=10), _call("c2", output_tokens=10)]
    answers = [
        _answer("q1", ["c1"], failed=True),
        _answer("q2", ["c2"]),
    ]
    judgments = [
        {"question_id": "q1", "category": "instruction_following", "score": 0.5},
        {"question_id": "q2", "category": "instruction_following", "score": 1.0},
    ]

    summary = _write_summary(
        args=_summary_args(),
        run_id="run",
        run_dir=tmp_path,
        root=tmp_path,
        calls=calls,
        answers=answers,
        judgments=judgments,
        usd_per_credit=Decimal("0.002"),
        copied_scores=[],
    )

    quality = summary["current_run_quality"]
    assert quality["quality_points"] == 1.0
    assert quality["objective_score_mean"] == 0.5
    assert quality["category_scores"] == {"instruction_following": 0.5}
    # The interval must resample the normalized scores [0.0, 1.0].
    interval = quality["quality_ci95"]
    assert interval["low"] == 0.0
    assert interval["high"] == 1.0
    assert interval["degenerate"] is True
    assert summary["reliability"]["failed_answers"] == 1
    assert json.loads(
        (tmp_path / "summary.json").read_text(encoding="utf-8")
    )["current_run_quality"]["quality_points"] == 1.0


def test_write_summary_surfaces_a_cost_value_it_could_not_parse(tmp_path):
    calls = [
        _call("good", output_tokens=10, cost_usd="0.001"),
        _call("bad", output_tokens=10, cost_usd="not-a-number"),
    ]
    answers = [_answer("q1", ["good", "bad"])]
    judgments = [{"question_id": "q1", "category": "math", "score": 1.0}]

    summary = _write_summary(
        args=_summary_args(),
        run_id="run",
        run_dir=tmp_path,
        root=tmp_path,
        calls=calls,
        answers=answers,
        judgments=judgments,
        usd_per_credit=Decimal("0.002"),
        copied_scores=[],
    )

    assert summary["reliability"]["malformed_cost_records"] == ["bad"]
