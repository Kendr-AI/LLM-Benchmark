from __future__ import annotations

import csv
import json
from argparse import Namespace
from decimal import Decimal
from pathlib import Path

import pytest

from kendr_bench.livebench_cli import (
    DEFAULT_BENCHMARKS,
    _benchmark_selection,
    _current_run_question_ids,
    _generation_command,
    _json_sha256,
    _normalize_missing_failed_judgments,
    _paths_for_benches,
    _percentile,
    _planned_question_records,
    _write_report,
    _write_summary,
    finalize_interrupted_run,
)


def test_missing_judgment_is_materialized_only_for_failed_answer():
    judgments: list[dict] = []
    answers = [
        {
            "answer_id": "a1",
            "question_id": "q1",
            "choices": [{"turns": ["$ERROR$"]}],
        }
    ]
    normalized = _normalize_missing_failed_judgments(
        judgments=judgments,
        answers=answers,
        planned_questions=[
            {"question_id": "q1", "category": "math", "task": "math_comp"}
        ],
        planned_ids=["q1"],
        model_display_name="model-a",
    )

    assert normalized == ["q1"]
    assert judgments[0]["score"] == 0.0
    assert judgments[0]["answer_id"] == "a1"
    assert judgments[0]["_source_file"].startswith("protocol://")


def test_missing_judgment_for_successful_answer_is_not_synthesized():
    with pytest.raises(RuntimeError, match="successful answers"):
        _normalize_missing_failed_judgments(
            judgments=[],
            answers=[
                {
                    "answer_id": "a1",
                    "question_id": "q1",
                    "choices": [{"turns": ["valid answer"]}],
                }
            ],
            planned_questions=[
                {
                    "question_id": "q1",
                    "category": "math",
                    "task": "math_comp",
                }
            ],
            planned_ids=["q1"],
            model_display_name="model-a",
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


def test_finalize_refuses_workspace_answers_not_linked_to_captured_calls(
    tmp_path, monkeypatch
):
    livebench_root = tmp_path / "LiveBench"
    work_dir = livebench_root / "livebench"
    answer_path = (
        work_dir
        / "data"
        / "live_bench"
        / "reasoning"
        / "zebra_puzzle"
        / "model_answer"
        / "model.jsonl"
    )
    answer_path.parent.mkdir(parents=True)
    answer_path.write_text(
        json.dumps(
            {
                "question_id": "q1",
                "choices": [{"turns": ["answer"]}],
                "api_info": {
                    "benchmark_calls": [
                        {
                            "run_id": "run-1",
                            "request_id": "different-request",
                            "input_messages": [
                                {"role": "user", "content": "different"}
                            ],
                        }
                    ]
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    planned = [
        {
            "question_id": "q1",
            "category": "reasoning",
            "task": "zebra_puzzle",
            "livebench_release_date": "2024-11-25",
        }
    ]
    (run_dir / "manifest.json").write_text(
        json.dumps(
            {
                "run_id": "run-1",
                "livebench_revision": (
                    "4355e9b04222745ccc02a2661d1deebe767a85a2"
                ),
                "livebench_release": "2026-06-25",
                "benchmarks": ["live_bench/reasoning/zebra_puzzle"],
                "provider": "kendr",
                "requested_model": "kc-model",
                "model_display_name": "model",
                "planned_questions": planned,
                "planned_question_ids": ["q1"],
                "planned_question_descriptor_sha256": _json_sha256(planned),
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "calls.jsonl").write_text(
        json.dumps(
            {
                "run_id": "run-1",
                "request_id": "captured-request",
                "input_messages": [{"role": "user", "content": "prompt"}],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "kendr_bench.livebench_cli._validate_checkout",
        lambda _: (True, "ok"),
    )

    with pytest.raises(RuntimeError, match="not fully linked"):
        finalize_interrupted_run(
            run_dir,
            livebench_root=livebench_root,
        )


def test_benchmark_selection_preserves_multiword_categories_and_overlaps():
    selection = _benchmark_selection(
        [
            "live_bench/data_analysis/tablejoin",
            "live_bench/instruction_following",
            "live_bench/data_analysis/cta",
        ]
    )

    assert selection == {
        "data_analysis": {"tablejoin", "cta"},
        "instruction_following": None,
    }


def test_planned_questions_freeze_the_per_task_slice_as_exact_ids():
    records = [
        {"question_id": "a0", "category": "a", "task": "one"},
        {"question_id": "a1", "category": "a", "task": "one"},
        {"question_id": "b0", "category": "b", "task": "two"},
        {"question_id": "b1", "category": "b", "task": "two"},
    ]

    planned = _planned_question_records(
        records,
        question_ids=None,
        question_begin=1,
        question_end=2,
    )

    assert [record["question_id"] for record in planned] == ["a1", "b1"]


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


def test_current_run_question_ids_links_blank_id_failure_by_messages():
    call = {
        "request_id": "",
        "provider": "openai",
        "requested_model": "model",
        "input_messages": [{"role": "user", "content": "Question"}],
        "error": {"type": "APIConnectionError"},
    }
    answers = [
        {
            "question_id": "failed-question",
            "choices": [{"turns": ["$ERROR$"]}],
            "api_info": {"benchmark_calls": [dict(call)]},
        }
    ]

    assert _current_run_question_ids([call], answers) == {
        "failed-question"
    }


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
    # Headline conformance is question-level: one question breached on a
    # failed retry and one passed. Attempt-level diagnostics retain 2/3.
    assert reliability["output_cap_compliance_rate"] == 0.5
    assert reliability["output_cap_attempt_conformance"][
        "measured_rate"
    ] == 2 / 3
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


def test_write_summary_treats_explicit_no_charge_as_known_zero(tmp_path):
    failed = _call(
        "failed",
        output_tokens=10,
        cost_usd=None,
        error={"type": "UpstreamFailure"},
    )
    failed["retry_reason"] = "no_credits_charged"
    answer = _answer("q1", ["failed"], failed=True)

    summary = _write_summary(
        args=_summary_args(),
        run_id="run",
        run_dir=tmp_path,
        root=tmp_path,
        calls=[failed],
        answers=[answer],
        judgments=[{"question_id": "q1", "category": "math", "score": 0}],
        usd_per_credit=Decimal("0.002"),
        copied_scores=[],
    )

    api = summary["current_api_run"]
    assert api["cost_usd"] == "0"
    assert api["cost_records_reported"] == 1
    assert api["cost_records_missing"] == 0
    assert api["cost_total_is_lower_bound"] is False


def test_write_summary_marks_missing_usage_as_token_lower_bound(tmp_path):
    call = _call("failed", output_tokens=0, error={"type": "Timeout"})
    call["usage"] = {}
    answer = _answer("q1", ["failed"], failed=True)

    summary = _write_summary(
        args=_summary_args(),
        run_id="run",
        run_dir=tmp_path,
        root=tmp_path,
        calls=[call],
        answers=[answer],
        judgments=[{"question_id": "q1", "category": "math", "score": 0}],
        usd_per_credit=Decimal("0.002"),
        copied_scores=[],
    )

    api = summary["current_api_run"]
    assert api["usage_records_reported"] == 0
    assert api["usage_records_missing"] == 1
    assert api["token_total_is_lower_bound"] is True


def test_single_run_exports_bounds_and_conservative_cap_rate(tmp_path):
    known = _call("known", output_tokens=10, cost_usd="0.001")
    unknown = _call(
        "unknown",
        output_tokens=0,
        cost_usd=None,
        error={"type": "APIConnectionError"},
    )
    unknown["usage"] = {}
    answers = [
        _answer("q1", ["known"]),
        _answer("q2", ["unknown"], failed=True),
    ]
    judgments = [
        {"question_id": "q1", "category": "math", "score": 1},
        {"question_id": "q2", "category": "math", "score": 0},
    ]

    summary = _write_summary(
        args=_summary_args(),
        run_id="run",
        run_dir=tmp_path,
        root=tmp_path,
        calls=[known, unknown],
        answers=answers,
        judgments=judgments,
        usd_per_credit=Decimal("0.002"),
        copied_scores=[],
    )
    _write_report(tmp_path, summary)

    api = summary["current_api_run"]
    reliability = summary["reliability"]
    assert api["token_total_is_lower_bound"] is True
    assert api["cost_total_is_lower_bound"] is True
    assert reliability["output_cap_compliance_rate"] == 0.5
    assert reliability["output_cap_measured_rate"] == 1.0
    assert reliability["output_cap_unknown_questions"] == 1

    with (tmp_path / "metrics.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        metric = next(csv.DictReader(handle))
    assert metric["token_total_is_lower_bound"] == "True"
    assert metric["cost_records_reported"] == "1"
    assert metric["cost_records_missing"] == "1"
    assert metric["cost_total_is_lower_bound"] == "True"
    assert float(metric["output_cap_compliance_rate"]) == 0.5
    assert float(metric["output_cap_measured_rate"]) == 1.0
    assert metric["output_cap_unknown_questions"] == "1"
    assert float(metric["output_cap_attempt_measured_rate"]) == 1.0
    assert metric["output_cap_measured_attempts"] == "1"
    assert metric["output_cap_unknown_attempts"] == "1"

    report = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "Tokens in/out: ≥100 / ≥10" in report
    assert "Cost in this run: ≥$0.001" in report
    assert "Usage telemetry reported/missing: 1 / 1" in report
    assert "Cost telemetry reported/missing: 1 / 1" in report
    assert "Total tokens per quality point: ≥" in report
    assert "Quality points per 1,000 tokens: ≤" in report
    assert "USD per quality point: ≥" in report
    assert "Output-cap compliance (conservative question-level): 50.00%" in report
    assert "Output-cap compliance (measured question-level): 100.00%" in report
    assert "1 attempt(s) lacked usage telemetry" in report


def test_planned_denominator_keeps_missing_work_as_zero(tmp_path):
    args = _summary_args()
    args.planned_questions = [
        {
            "question_id": "q1",
            "category": "reasoning",
            "task": "zebra_puzzle",
            "livebench_release_date": "2024-11-25",
        },
        {
            "question_id": "q2",
            "category": "reasoning",
            "task": "zebra_puzzle",
            "livebench_release_date": "2024-11-25",
        },
    ]
    args.allow_incomplete = False
    calls = [_call("c1", output_tokens=10)]
    answers = [_answer("q1", ["c1"])]
    judgments = [
        {"question_id": "q1", "category": "reasoning", "score": 1.0}
    ]

    summary = _write_summary(
        args=args,
        run_id="run",
        run_dir=tmp_path,
        root=tmp_path,
        calls=calls,
        answers=answers,
        judgments=judgments,
        usd_per_credit=Decimal("0.002"),
        copied_scores=[],
    )

    assert summary["current_run_quality"]["score_denominator"] == 2
    assert summary["current_run_quality"]["questions_scored"] == 1
    assert summary["current_run_quality"]["objective_score_mean"] == 0.5
    assert summary["current_run_quality"]["category_scores"] == {
        "reasoning": 0.5
    }
    assert summary["reliability"]["answer_success_rate"] == 0.5
    assert summary["completeness"]["complete"] is False
    assert summary["completeness"]["missing_answer_ids"] == ["q2"]
    assert summary["completeness"]["missing_judgment_ids"] == ["q2"]
    assert summary["completeness"]["missing_call_link_ids"] == ["q2"]


def test_stale_judgment_answer_id_cannot_satisfy_completeness(tmp_path):
    args = _summary_args()
    args.planned_questions = [
        {
            "question_id": "q1",
            "category": "reasoning",
            "task": "zebra_puzzle",
            "livebench_release_date": "2024-11-25",
        }
    ]
    args.allow_incomplete = False
    calls = [_call("c1", output_tokens=10)]
    answer = _answer("q1", ["c1"])
    answer["answer_id"] = "new-answer"
    judgments = [
        {
            "question_id": "q1",
            "answer_id": "old-answer",
            "category": "reasoning",
            "score": 1.0,
        }
    ]

    summary = _write_summary(
        args=args,
        run_id="run",
        run_dir=tmp_path,
        root=tmp_path,
        calls=calls,
        answers=[answer],
        judgments=judgments,
        usd_per_credit=Decimal("0.002"),
        copied_scores=[],
    )

    assert summary["current_run_quality"]["objective_score_mean"] == 0.0
    assert summary["current_run_quality"]["questions_scored"] == 0
    assert summary["completeness"]["complete"] is False
    assert summary["completeness"]["missing_judgment_ids"] == ["q1"]
    assert summary["completeness"][
        "mismatched_answer_id_judgment_ids"
    ] == ["q1"]
    assert summary["reliability"]["score_weighted_goodput"][
        "conservative_mean"
    ] == 0.0
