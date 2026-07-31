from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "generate_matrix_documentation.py"
)


@pytest.fixture(scope="module")
def generator():
    spec = importlib.util.spec_from_file_location("matrix_docs", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _summary(
    *,
    requested_model: str,
    quality: float | None,
    quality_points: float,
    questions: int,
    cost_usd: str | None = "0.010000",
    tokens_per_quality_point: float | None = 100.0,
    usd_per_quality_point: float | None = 0.005,
    quality_points_per_usd: float | None = 200.0,
) -> dict[str, Any]:
    return {
        "run_id": f"run-{requested_model}",
        "model": requested_model,
        "requested_model": requested_model,
        "livebench": {"revision": "abc123", "release": "2026-06-25"},
        "current_api_run": {
            "input_tokens": 1000,
            "output_tokens": 500,
            "total_tokens": 1500,
            "cost_usd": cost_usd,
            "kendr_credits": "5.000000",
            "maximum_output_tokens_observed": 3000,
        },
        "current_run_quality": {
            "questions_scored": questions,
            "quality_points": quality_points,
            "objective_score_mean": quality,
            "perfect_score_rate": 0.5,
            "nonzero_score_rate": 0.5,
        },
        "efficiency": {
            "total_tokens_per_quality_point": tokens_per_quality_point,
            "usd_per_quality_point": usd_per_quality_point,
            "quality_points_per_usd": quality_points_per_usd,
        },
        "latency": {
            "end_to_end_ms": {
                "mean": 1000.0,
                "p50": 900.0,
                "p95": 1400.0,
                "maximum": 1500.0,
            },
            "failed_request_ms": {"mean": None, "p50": None, "p95": None},
        },
        "reliability": {
            "successful_answers": questions,
            "failed_answers": 0,
            "answer_success_rate": 1.0,
            "scoring_coverage": 1.0,
            "output_cap_compliance_rate": 1.0,
            "calls_exceeding_requested_output_cap": 0,
            "route_distribution": {"kc-a": 1, "kc-b": 1},
            "provider_error_distribution": {},
        },
        "workspace_snapshot": {
            "answers": questions,
            "failed_answers": 0,
            "judgments": questions,
            "question_weighted_mean_score": quality,
            "standard_group_scores": {},
        },
    }


def _write_run(
    runs_root: Path,
    *,
    key: str,
    requested_model: str,
    scores: list[tuple[str, str, float]],
    failed_question_ids: tuple[str, ...] = (),
    summary_overrides: dict[str, Any] | None = None,
) -> None:
    run_dir = runs_root / f"run-{key}"
    run_dir.mkdir(parents=True)
    quality_points = sum(
        0.0 if question_id in failed_question_ids else score
        for question_id, _, score in scores
    )
    summary = _summary(
        requested_model=requested_model,
        quality=quality_points / len(scores) if scores else None,
        quality_points=quality_points,
        questions=len(scores),
        **(summary_overrides or {}),
    )
    (run_dir / "summary.json").write_text(
        json.dumps(summary), encoding="utf-8"
    )
    (run_dir / "manifest.json").write_text(
        json.dumps(
            {"provider": "kendr", "requested_model": requested_model}
        ),
        encoding="utf-8",
    )
    with (run_dir / "judgments.jsonl").open("w", encoding="utf-8") as handle:
        for question_id, category, score in scores:
            handle.write(
                json.dumps(
                    {
                        "question_id": question_id,
                        "category": category,
                        "task": category,
                        "score": score,
                        "model": requested_model,
                    }
                )
                + "\n"
            )
    with (run_dir / "answers.jsonl").open("w", encoding="utf-8") as handle:
        for question_id, _, _ in scores:
            turns = (
                ["$ERROR$"]
                if question_id in failed_question_ids
                else ["an answer"]
            )
            handle.write(
                json.dumps(
                    {
                        "question_id": question_id,
                        "choices": [{"turns": turns}],
                        "total_input_tokens": 100,
                        "total_output_tokens": 50,
                        "api_info": {"benchmark_calls": []},
                    }
                )
                + "\n"
            )
    (run_dir / "calls.jsonl").write_text(
        "".join(
            json.dumps(
                {
                    "request_id": f"req-{question_id}",
                    "usage": {"prompt_tokens": 100, "completion_tokens": 50},
                    "latency_ms": 900.0,
                }
            )
            + "\n"
            for question_id, _, _ in scores
        ),
        encoding="utf-8",
    )


def _build_matrix(root: Path, models: list[dict[str, Any]]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "matrix_id": "test-matrix",
                "models": models,
                "livebench_release": "2026-06-25",
                "tasks": ["live_bench/reasoning/zebra_puzzle"],
                "questions_per_task": 3,
                "max_tokens": 2048,
                "parallel_requests": 2,
                "parallel_grading": 4,
                "kendr_usd_per_credit": "0.002",
            }
        ),
        encoding="utf-8",
    )


def _spec(key: str, model: str, label: str) -> dict[str, Any]:
    return {
        "key": key,
        "provider": "kendr",
        "model": model,
        "label": label,
        "access": "Open-weight via Kendr",
        "license": "MIT",
        "license_source": "https://example.com",
    }


def test_generator_runs_on_a_subset_without_the_baseline_model(
    generator, tmp_path, monkeypatch, capsys
):
    """A --include subset need not contain openai-sol.

    The efficiency baseline used to be looked up with a bare next(), so any
    panel without Sol aborted with StopIteration.
    """
    root = tmp_path / "matrix"
    models = [
        _spec("glm-5", "kc-glm-5", "GLM-5"),
        _spec("kimi-k2-5", "kc-kimi-k2.5", "Kimi K2.5"),
    ]
    _build_matrix(root, models)
    _write_run(
        root / "runs",
        key="glm-5",
        requested_model="kc-glm-5",
        scores=[("q1", "math", 1.0), ("q2", "math", 1.0), ("q3", "math", 0.0)],
    )
    _write_run(
        root / "runs",
        key="kimi",
        requested_model="kc-kimi-k2.5",
        scores=[("q1", "math", 0.0), ("q2", "math", 1.0), ("q3", "math", 0.0)],
    )

    monkeypatch.setattr("sys.argv", ["generate", str(root)])
    assert generator.main() == 0

    report = (root / "detailed-report.md").read_text(encoding="utf-8")
    assert "GLM-5" in report
    # No baseline, so efficiency multipliers must degrade to n/a, not crash.
    assert "n/a×" in report or "n/a" in report
    assert (root / "methodology-and-model-documentation.md").is_file()
    assert (root / "model-metrics.csv").is_file()


def test_generator_survives_a_model_that_scored_zero_quality_points(
    generator, tmp_path, monkeypatch
):
    """Zero quality points make efficiency metrics None, which used to crash."""
    root = tmp_path / "matrix"
    models = [
        _spec("openai-sol", "gpt-5.6-sol", "OpenAI GPT-5.6 Sol"),
        _spec("glm-5", "kc-glm-5", "GLM-5"),
    ]
    _build_matrix(root, models)
    _write_run(
        root / "runs",
        key="sol",
        requested_model="gpt-5.6-sol",
        scores=[("q1", "math", 1.0), ("q2", "math", 1.0), ("q3", "math", 1.0)],
    )
    _write_run(
        root / "runs",
        key="glm-5",
        requested_model="kc-glm-5",
        scores=[("q1", "math", 0.0), ("q2", "math", 0.0), ("q3", "math", 0.0)],
        summary_overrides={
            "tokens_per_quality_point": None,
            "usd_per_quality_point": None,
            "quality_points_per_usd": None,
        },
    )

    monkeypatch.setattr("sys.argv", ["generate", str(root)])
    assert generator.main() == 0

    rows = list(
        csv.DictReader(
            (root / "model-metrics.csv").read_text(
                encoding="utf-8"
            ).splitlines()
        )
    )
    zero = next(row for row in rows if row["panel_key"] == "glm-5")
    assert zero["quality_score"] == "0.0"
    assert zero["tokens_per_quality_point"] == ""


def test_generator_bootstraps_the_normalized_scores_not_raw_judgments(
    generator, tmp_path, monkeypatch
):
    """The interval must describe the same data as the point estimate.

    A format grader awards 0.5 to the literal $ERROR$ sentinel here. Quality
    normalizes that to zero, so the interval must be built from zeros too.
    """
    root = tmp_path / "matrix"
    _build_matrix(root, [_spec("glm-5", "kc-glm-5", "GLM-5")])
    _write_run(
        root / "runs",
        key="glm-5",
        requested_model="kc-glm-5",
        scores=[
            ("q1", "instruction_following", 0.5),
            ("q2", "instruction_following", 0.5),
            ("q3", "instruction_following", 0.5),
        ],
        failed_question_ids=("q1", "q2", "q3"),
    )

    monkeypatch.setattr("sys.argv", ["generate", str(root)])
    assert generator.main() == 0

    rows = list(
        csv.DictReader(
            (root / "model-metrics.csv").read_text(
                encoding="utf-8"
            ).splitlines()
        )
    )
    assert rows[0]["quality_score"] == "0.0"
    assert float(rows[0]["quality_ci95_low"]) == 0.0
    assert float(rows[0]["quality_ci95_high"]) == 0.0
    assert rows[0]["instruction_following_score"] == "0.0"
    # Intermediates must not reach the published CSV.
    assert "_question_scores" not in rows[0]


def test_generator_reports_missing_runs_instead_of_raising(
    generator, tmp_path, monkeypatch, capsys
):
    root = tmp_path / "matrix"
    models = [
        _spec("glm-5", "kc-glm-5", "GLM-5"),
        _spec("kimi-k2-5", "kc-kimi-k2.5", "Kimi K2.5"),
    ]
    _build_matrix(root, models)
    _write_run(
        root / "runs",
        key="glm-5",
        requested_model="kc-glm-5",
        scores=[("q1", "math", 1.0)],
    )

    monkeypatch.setattr("sys.argv", ["generate", str(root)])
    assert generator.main() == 0
    assert "Kimi K2.5" in capsys.readouterr().err


def test_generator_exits_nonzero_when_there_is_nothing_to_report(
    generator, tmp_path, monkeypatch
):
    root = tmp_path / "matrix"
    _build_matrix(root, [_spec("glm-5", "kc-glm-5", "GLM-5")])
    (root / "runs").mkdir()

    monkeypatch.setattr("sys.argv", ["generate", str(root)])
    assert generator.main() == 1


def test_generator_recovers_usage_from_both_error_body_shapes(generator):
    enveloped = {
        "error": {
            "body": {
                "error": {
                    "details": {
                        "kendr_routing": {"selected_model_alias": "kc-a"},
                        "attempts": [
                            {"usage": {"input_tokens": 5, "output_tokens": 7}}
                        ],
                    }
                }
            }
        }
    }
    flat = {
        "error": {
            "body": {
                "details": {
                    "kendr_routing": {"selected_model_alias": "kc-b"},
                    "attempts": [
                        {"usage": {"input_tokens": 9, "output_tokens": 11}}
                    ],
                }
            }
        }
    }
    assert generator.call_routing(enveloped)["selected_model_alias"] == "kc-a"
    assert generator.call_routing(flat)["selected_model_alias"] == "kc-b"
    assert generator.call_usage(enveloped)["completion_tokens"] == 7
    assert generator.call_usage(flat)["completion_tokens"] == 11
    assert generator.call_routing({"error": "plain string"}) == {}
    assert generator.call_usage({}) == {}


def test_generator_ratio_guards_none_and_zero(generator):
    assert generator.ratio(1, 0) is None
    assert generator.ratio(None, 5) is None
    assert generator.ratio(5, None) is None
    assert generator.ratio(10, 4) == 2.5
