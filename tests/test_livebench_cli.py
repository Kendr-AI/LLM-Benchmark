from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from kendr_bench.livebench_cli import (
    DEFAULT_BENCHMARKS,
    _current_run_question_ids,
    _generation_command,
    _paths_for_benches,
    _percentile,
)


def test_generation_command_uses_adapter_and_fixed_single_choice(tmp_path):
    args = Namespace(
        model="kc-intelligent",
        model_display_name="kendr-kc-intelligent",
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
