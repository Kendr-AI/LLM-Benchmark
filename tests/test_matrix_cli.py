from __future__ import annotations

import json
import subprocess

import pytest

import kendr_bench.matrix_cli as matrix_cli

from kendr_bench.matrix_cli import (
    DEFAULT_MATRIX_TASKS,
    DEFAULT_MODEL_PANEL,
    _category_scores,
    _leaderboard_row,
    _question_scores,
    _require_complete_panel,
    _ranking_key,
    _execution_software_provenance,
    _selected_panel,
    _select_rebuild_run,
    _write_leaderboard,
)


def _git(root, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def test_execution_software_provenance_records_commit_and_dirty_boolean(tmp_path):
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "benchmark@example.invalid")
    _git(tmp_path, "config", "user.name", "Benchmark Test")
    (tmp_path / "tracked.txt").write_text("frozen\n", encoding="utf-8")
    _git(tmp_path, "add", "tracked.txt")
    _git(tmp_path, "commit", "-m", "initial")

    clean = _execution_software_provenance(tmp_path)
    assert clean["package"] == "llm-benchmark-protocol"
    assert clean["version"] == "1.0.3"
    assert clean["source_commit"] == _git(tmp_path, "rev-parse", "HEAD")
    assert clean["source_worktree_dirty"] is False

    (tmp_path / "uncommitted.txt").write_text("dirty\n", encoding="utf-8")
    dirty = _execution_software_provenance(tmp_path)
    assert dirty["source_commit"] == clean["source_commit"]
    assert dirty["source_worktree_dirty"] is True


def test_execution_software_provenance_fails_without_a_source_commit(tmp_path):
    with pytest.raises(RuntimeError, match="source commit"):
        _execution_software_provenance(tmp_path)


def test_preflight_matrix_manifest_records_execution_software(
    tmp_path, monkeypatch
):
    panel_path = tmp_path / "panel.json"
    panel_path.write_text(
        json.dumps(
            [
                {
                    "key": "candidate",
                    "provider": "kendr",
                    "model": "kc-candidate",
                    "label": "Candidate",
                    "access": "Kendr",
                    "license": "Provider terms",
                    "license_source": "https://example.com/terms",
                }
            ]
        ),
        encoding="utf-8",
    )
    expected = {
        "package": "llm-benchmark-protocol",
        "version": "1.0.2",
        "source_repository": "https://github.com/Kendr-AI/LLM-Benchmark",
        "source_commit": "d" * 40,
        "source_worktree_dirty": True,
    }

    class Sampling:
        selected_ids = ("q1",)

        @staticmethod
        def to_dict():
            return {
                "mode": "seeded-random",
                "seed": 20260807,
                "selected_ids": ["q1"],
                "content_hash": "e" * 64,
                "content_hash_algorithm": "sha256",
            }

    monkeypatch.setattr(
        matrix_cli, "_execution_software_provenance", lambda: expected
    )
    monkeypatch.setattr(matrix_cli, "load_environment", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        matrix_cli,
        "load_livebench_question_records",
        lambda *args, **kwargs: [
            {
                "question_id": "q1",
                "category": "reasoning",
                "task": "zebra_puzzle",
                "livebench_release_date": "2024-11-25",
            }
        ],
    )
    monkeypatch.setattr(
        matrix_cli, "select_question_ids", lambda *args, **kwargs: Sampling()
    )
    args = matrix_cli._build_parser().parse_args(
        [
            "--preflight-only",
            "--panel-file",
            str(panel_path),
            "--output",
            str(tmp_path / "matrix-output"),
        ]
    )

    root = matrix_cli.run_matrix(args)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["execution_software"] == expected


def test_default_matrix_is_stratified_and_contains_open_weight_models():
    assert len(DEFAULT_MATRIX_TASKS) == 5
    assert len(DEFAULT_MODEL_PANEL) == 9
    assert sum(
        model.access == "Open-weight via Kendr"
        for model in DEFAULT_MODEL_PANEL
    ) == 4


def test_external_panel_file_supports_frozen_catalog_campaign(tmp_path):
    panel_path = tmp_path / "panel.json"
    panel_path.write_text(
        json.dumps(
            [
                {
                    "key": "catalog-a",
                    "provider": "kendr",
                    "model": "kc-model-a",
                    "label": "Catalog A",
                    "access": "Kendr API catalog snapshot",
                    "license": "Provider terms",
                    "license_source": "https://api.kendr.org"
                }
            ]
        ),
        encoding="utf-8",
    )

    panel = _selected_panel(None, panel_path)

    assert len(panel) == 1
    assert panel[0].model == "kc-model-a"


def test_external_panel_rejects_duplicate_provider_model(tmp_path):
    panel_path = tmp_path / "panel.json"
    row = {
        "key": "catalog-a",
        "provider": "kendr",
        "model": "kc-model-a",
        "label": "Catalog A",
        "access": "Kendr API catalog snapshot",
        "license": "Provider terms",
        "license_source": "https://api.kendr.org"
    }
    duplicate = dict(row, key="catalog-b")
    panel_path.write_text(json.dumps([row, duplicate]), encoding="utf-8")

    with pytest.raises(RuntimeError, match="identities must be unique"):
        _selected_panel(None, panel_path)


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
            "cost_total_is_lower_bound": True,
            "token_total_is_lower_bound": True,
            "quality_points": 2.5,
            "usd_per_quality_point": 0.0004,
            "kendr_credits": None,
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
            "cost_total_is_lower_bound": False,
            "token_total_is_lower_bound": False,
            "quality_points": 4.0,
            "usd_per_quality_point": 0.001,
            "kendr_credits": None,
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
    assert document["pairwise_test_family"]["comparisons"] == 1
    paired = document["pairwise_tests"][0]
    assert paired["holm_adjusted_p_value"] is not None
    assert paired["separates_at_fwer_05"] is False
    assert paired["practically_equivalent_at_95"] is False
    assert (tmp_path / "artifact_hashes.json").is_file()
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
    assert "≥$0.001000" in report
    assert "≥$0.000400" in report
    assert "≤2.50×" in report
    assert "≥20" in report
    assert "≥8.0" in report
    assert "≤1.25×" in report
    assert "Attempt-level selected routes" in report
    assert "latency ordering is descriptive" in report

    # A catalog-frozen panel can contain keys that are intentionally absent
    # from the built-in convenience panel.  Publication must use the identity
    # already captured in each row instead of indexing DEFAULT_MODEL_PANEL.
    external_root = tmp_path / "external"
    external_root.mkdir()
    external_row = dict(
        rows[0],
        model="Catalog Only",
        panel_key="catalog-only",
        requested_model="kc-catalog-only",
        access="Frozen catalog snapshot",
        license="Provider terms",
        license_source="https://api.kendr.org",
    )
    _write_leaderboard(
        external_root,
        matrix_id="external-matrix",
        rows=[external_row],
        failures=[],
        tasks=["live_bench/reasoning/zebra_puzzle"],
        release="2026-06-25",
        questions_per_task=5,
        max_tokens=2048,
        parallel_requests=1,
    )
    external_report = (external_root / "leaderboard.md").read_text(
        encoding="utf-8"
    )
    assert "`kc-catalog-only`" in external_report
    assert "Frozen catalog snapshot" in external_report


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
            "operational_output_cap_conformance": {
                "measured_rate": 1.0,
                "conservative_rate": 0.5,
                "unknown": 2,
            },
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
    assert row["output_cap_compliance_rate"] == 0.5
    assert row["output_cap_measured_rate"] == 1.0
    assert row["output_cap_unknown_questions"] == 2


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


def test_ranking_prefers_conservative_goodput_before_raw_quality():
    high_quality_breach = {
        "quality_score": 0.95,
        "score_weighted_operational_goodput": 0.50,
        "cost_usd": "0.01",
        "latency_p50_ms": 10,
    }
    conforming = {
        "quality_score": 0.80,
        "score_weighted_operational_goodput": 0.80,
        "cost_usd": "0.02",
        "latency_p50_ms": 20,
    }

    assert sorted(
        [high_quality_breach, conforming], key=_ranking_key
    )[0] is conforming


def test_ranking_does_not_reward_a_lower_bound_cost_total():
    incomplete_cost = {
        "quality_score": 0.8,
        "score_weighted_operational_goodput": 0.8,
        "cost_usd": "0.001",
        "cost_total_is_lower_bound": True,
        "latency_p50_ms": 10,
    }
    complete_cost = {
        "quality_score": 0.8,
        "score_weighted_operational_goodput": 0.8,
        "cost_usd": "0.100",
        "cost_total_is_lower_bound": False,
        "latency_p50_ms": 20,
    }

    assert sorted(
        [incomplete_cost, complete_cost], key=_ranking_key
    )[0] is complete_cost


def test_incomplete_panel_is_preserved_but_not_successful(tmp_path):
    with pytest.raises(RuntimeError, match="1/2 endpoints"):
        _require_complete_panel(
            rows=[{"model": "complete"}],
            failures=[{"model": "failed", "error": "provider error"}],
            expected_count=2,
            matrix_root=tmp_path,
        )

    _require_complete_panel(
        rows=[{"model": "a"}, {"model": "b"}],
        failures=[],
        expected_count=2,
        matrix_root=tmp_path,
    )

    with pytest.raises(RuntimeError, match="1/2 endpoints"):
        _require_complete_panel(
            rows=[
                {"model": "a", "complete": True},
                {"model": "b", "complete": False},
            ],
            failures=[],
            expected_count=2,
            matrix_root=tmp_path,
        )


def test_rebuild_selects_first_captured_trial_not_later_clean_rerun(
    tmp_path,
):
    manifest_only = tmp_path / "001-manifest-only"
    first_trial = tmp_path / "002-first-trial"
    clean_rerun = tmp_path / "003-clean-rerun"
    for run_dir in (manifest_only, first_trial, clean_rerun):
        run_dir.mkdir()
    (first_trial / "calls.jsonl").write_text("{}\n", encoding="utf-8")
    (clean_rerun / "calls.jsonl").write_text("{}\n", encoding="utf-8")

    selected, attempted = _select_rebuild_run(
        [clean_rerun, manifest_only, first_trial]
    )

    assert selected == first_trial
    assert attempted == [first_trial, clean_rerun]


def test_question_scores_keep_missing_planned_ids_as_zero(tmp_path):
    answers = tmp_path / "answers.jsonl"
    judgments = tmp_path / "judgments.jsonl"
    answers.write_text(
        json.dumps(
            {
                "question_id": "present",
                "choices": [{"turns": ["answer"]}],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    judgments.write_text(
        json.dumps({"question_id": "present", "score": 1.0}) + "\n",
        encoding="utf-8",
    )

    assert _question_scores(
        judgments, answers, ["present", "missing"]
    ) == {"present": 1.0, "missing": 0.0}
