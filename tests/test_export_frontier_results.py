from __future__ import annotations

import copy
import csv
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "scripts" / "export_frontier_results.py"
SPEC = importlib.util.spec_from_file_location("export_frontier_results", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _profile() -> dict:
    return {
        "schema_version": "1.0",
        "profile_id": "kendr-current-frontier-20260808",
        "snapshot_date": "2026-08-08",
        "ga_cohort_id": "core-ga",
        "companion_cohort_id": "preview-companion",
        "cohorts": [
            {
                "id": "core-ga",
                "claim_class": "general-availability",
                "claim_scope": "Current-frontier GA endpoints plus baseline",
                "entries": [
                    {
                        "key": "candidate-a",
                        "label": "Candidate A",
                        "catalog_id": "kc-candidate-a",
                        "role": "candidate",
                    },
                    {
                        "key": "candidate-blocked",
                        "label": "Candidate Blocked",
                        "catalog_id": "kc-candidate-blocked",
                        "role": "candidate",
                    },
                    {
                        "key": "candidate-coverage-only",
                        "label": "Candidate Coverage Only",
                        "vendor_model_id": "vendor-candidate-2026-08-08",
                        "role": "candidate",
                        "coverage_only": True,
                        "coverage_status": "staged",
                        "n_a_reason": (
                            "Staged coverage target has no executable Kendr id."
                        ),
                    },
                    {
                        "key": "gpt-5-5-baseline",
                        "label": "GPT-5.5 baseline",
                        "catalog_id": "kc-openai-gpt-5-5",
                        "role": "baseline",
                    },
                ],
            },
            {
                "id": "preview-companion",
                "claim_class": "preview-or-limited-access",
                "claim_scope": "Preview companion",
                "entries": [
                    {
                        "key": "preview-d",
                        "label": "Preview D",
                        "catalog_id": "kc-preview-d",
                        "role": "candidate",
                    }
                ],
            },
        ],
    }


def _panel() -> list[dict]:
    return [
        {
            "key": "candidate-a-run",
            "provider": "kendr",
            "model": "kc-candidate-a",
            "label": "Candidate A (Kendr served default)",
            "access": "Kendr managed route",
            "license": "Provider terms",
            "license_source": "https://example.com/terms",
        },
        {
            "key": "gpt-5-5-run",
            "provider": "kendr",
            "model": "kc-openai-gpt-5-5",
            "label": "GPT-5.5 (Kendr served baseline)",
            "access": "Kendr managed route",
            "license": "Provider terms",
            "license_source": "https://example.com/terms",
        },
    ]


def _manifest(panel: list[dict] | None = None) -> dict:
    panel = panel or _panel()
    return {
        "matrix_id": "frontier-matrix",
        "created_at": "2026-08-08T12:00:00+00:00",
        "models": panel,
        "livebench_release": "2026-06-25",
        "tasks": ["live_bench/math/a", "live_bench/reasoning/b"],
        "questions_per_task": 1,
        "sampling": {
            "mode": "seeded-random",
            "seed": 20260807,
            "selected_ids": ["q1", "q2"],
            "content_hash": "1" * 64,
            "content_hash_algorithm": "sha256",
            "selected_date_distribution": {"2024-11-25": 2},
        },
        "max_tokens": 2048,
        "deadline_ms": 120000,
        "max_cost_usd_per_answer": None,
        "practical_equivalence_margin": 0.02,
        "parallel_requests": 2,
        "parallel_grading": 4,
        "reasoning_effort": "none",
        "kendr_usd_per_credit": "0.002",
        "execution_software": {
            "package": "llm-benchmark-protocol",
            "version": "1.0.2",
            "source_repository": "https://github.com/Kendr-AI/LLM-Benchmark",
            "source_commit": "c" * 40,
            "source_worktree_dirty": True,
        },
        # These private paths are source-only and must not be copied.
        "panel_file": "D:/private/panel.json",
        "pricing_catalog": "D:/private/pricing.json",
    }


def _result(
    *,
    rank: int,
    panel_key: str,
    model_id: str,
    label: str,
    goodput: float,
) -> dict:
    return {
        "rank": rank,
        "panel_key": panel_key,
        "provider": "kendr",
        "requested_model": model_id,
        "model": label,
        "questions_scored": 2,
        "quality_points": goodput * 2,
        "quality_score": goodput,
        "score_weighted_operational_goodput": goodput,
        "operational_goodput_ci95_low": max(0.0, goodput - 0.1),
        "operational_goodput_ci95_high": min(1.0, goodput + 0.1),
        "quality_ci95_low": max(0.0, goodput - 0.1),
        "quality_ci95_high": min(1.0, goodput + 0.1),
        "conditional_quality_score": goodput,
        "availability": 1.0,
        "tier": 1,
        "successful_answers": 2,
        "failed_answers": 0,
        "missing_answers": 0,
        "latency_p50_ms": 1000.0,
        "latency_p95_ms": 1500.0,
        "cost_usd": "0.010000",
        "cost_total_is_lower_bound": False,
        "data_analysis_score": None,
        "instruction_following_score": None,
        "language_score": None,
        "math_score": goodput,
        "reasoning_score": goodput,
        "provider_error_distribution": {},
        "complete": True,
        "run_dir": "D:/private/run",
    }


def _leaderboard() -> dict:
    # Baseline leads the raw matrix. Candidate A deliberately has a real zero
    # goodput to prove that scheduled zero evidence is not rewritten as N/A.
    return {
        "matrix_id": "frontier-matrix",
        "created_at": "2026-08-08T12:30:00+00:00",
        "livebench_release": "2026-06-25",
        "tasks": ["live_bench/math/a", "live_bench/reasoning/b"],
        "questions_per_task": 1,
        "requested_max_output_tokens": 2048,
        "parallel_requests": 2,
        "ranking_rule": "Operational goodput descending.",
        "results": [
            _result(
                rank=1,
                panel_key="gpt-5-5-run",
                model_id="kc-openai-gpt-5-5",
                label="GPT-5.5 (Kendr served baseline)",
                goodput=0.8,
            ),
            _result(
                rank=2,
                panel_key="candidate-a-run",
                model_id="kc-candidate-a",
                label="Candidate A (Kendr served default)",
                goodput=0.0,
            ),
        ],
        "pairwise_test_family": {
            "method": "paired sign-randomization with Holm correction"
        },
        "pairwise_tests": [
            {
                "comparison_id": "gpt-5-5-run|candidate-a-run",
                "higher_panel_key": "gpt-5-5-run",
                "lower_panel_key": "candidate-a-run",
                "mean_difference": 0.8,
                "ci95_low": 0.2,
                "ci95_high": 1.0,
                "randomization_p_value": 0.01,
                "holm_adjusted_p_value": 0.01,
                # The current matrix field, intentionally not `holm_reject`.
                "separates_at_fwer_05": True,
            }
        ],
        "failures": [],
    }


def _catalog() -> list[dict]:
    return [
        {
            "id": "kc-candidate-a",
            "display_name": "Candidate A",
            "available": True,
            "capabilities": ["text"],
        },
        {
            "id": "kc-candidate-blocked",
            "display_name": "Candidate Blocked",
            "available": False,
            "capabilities": ["text"],
        },
        {
            "id": "kc-openai-gpt-5-5",
            "display_name": "gpt-5.5",
            "available": True,
            "capabilities": ["text"],
        },
        {
            "id": "kc-preview-d",
            "display_name": "Preview D",
            "available": True,
            "capabilities": ["text"],
        },
    ]


def _audit() -> dict:
    return {
        "schema_version": "1.0",
        "profile_id": "kendr-current-frontier-20260808",
        "snapshot_date": "2026-08-08",
        "catalog_entries": 4,
        "catalog_sha256": MODULE.catalog_sha256(_catalog()),
        "ga_claim_ready": False,
        "companion_claim_ready": True,
        "claim_separation": "Preview results must be reported separately.",
        "catalog_source": "D:/private/catalog.json",
        "profile_source": "D:/private/profile.json",
        "cohorts": [
            {
                "id": "core-ga",
                "ready": False,
                "entries": [
                    {
                        "key": "candidate-a",
                        "label": "Candidate A",
                        "role": "candidate",
                        "catalog_id": "kc-candidate-a",
                        "status": "present",
                    },
                    {
                        "key": "candidate-blocked",
                        "label": "Candidate Blocked",
                        "role": "candidate",
                        "catalog_id": "kc-candidate-blocked",
                        "status": "ineligible",
                        "reason": "Catalog entry has available=false.",
                    },
                    {
                        "key": "candidate-coverage-only",
                        "label": "Candidate Coverage Only",
                        "role": "candidate",
                        "catalog_id": None,
                        "required": False,
                        "coverage_only": True,
                        "vendor_model_id": "vendor-candidate-2026-08-08",
                        "coverage_status": "staged",
                        "execution_eligible": False,
                        "status": "coverage_only",
                        "reason": (
                            "Staged coverage target has no executable Kendr id."
                        ),
                    },
                    {
                        "key": "gpt-5-5-baseline",
                        "label": "GPT-5.5 baseline",
                        "role": "baseline",
                        "catalog_id": "kc-openai-gpt-5-5",
                        "status": "present",
                    },
                ],
            },
            {
                "id": "preview-companion",
                "ready": True,
                "entries": [
                    {
                        "key": "preview-d",
                        "label": "Preview D",
                        "role": "candidate",
                        "catalog_id": "kc-preview-d",
                        "status": "present",
                    }
                ],
            },
        ],
    }


def _build() -> dict:
    return MODULE.build_publication(
        manifest=_manifest(),
        leaderboard=_leaderboard(),
        profile=_profile(),
        execution_panel=_panel(),
        coverage_audit=_audit(),
        catalog=_catalog(),
        source_hashes={"matrix_manifest_sha256": "b" * 64},
    )


def test_publication_separates_candidate_rank_baseline_and_na_rows():
    bundle = _build()
    by_id = {row["endpoint_id"]: row for row in bundle["rows"]}

    candidate = by_id["kc-candidate-a"]
    assert candidate["benchmark_status"] == "scored"
    assert candidate["rank"] == 1
    assert candidate["execution_rank"] == 2
    assert candidate["operational_goodput"] == 0.0
    assert candidate["n_a_reason"] is None

    baseline = by_id["kc-openai-gpt-5-5"]
    assert baseline["role"] == "baseline"
    assert baseline["rank"] is None
    assert baseline["execution_rank"] == 1

    blocked = by_id["kc-candidate-blocked"]
    assert blocked["benchmark_status"] == "not_measured"
    assert blocked["rank"] is None
    assert blocked["operational_goodput"] is None
    assert blocked["n_a_reason_code"] == "ineligible"

    coverage_only = next(
        row
        for row in bundle["rows"]
        if row["vendor_model_id"] == "vendor-candidate-2026-08-08"
    )
    assert coverage_only["benchmark_status"] == "not_measured"
    assert coverage_only["endpoint_id"] is None
    assert coverage_only["catalog_status"] == "staged"
    assert coverage_only["n_a_reason_code"] == "coverage_only_staged"
    assert coverage_only["operational_goodput"] is None

    preview = by_id["kc-preview-d"]
    assert preview["cohort"] == "preview-companion"
    assert preview["benchmark_status"] == "not_measured"
    assert preview["n_a_reason_code"] == "preview_companion_not_scheduled"

    assert bundle["scope"] == {
        "profile_entries": 5,
        "core_ga_candidates": 3,
        "scored_core_ga_candidates": 1,
        "not_measured_core_ga_candidates": 2,
        "scored_baselines": 1,
        "preview_companion_entries": 1,
        "scored_preview_companion_entries": 0,
    }
    assert bundle["pairwise_inference"]["holm_rejections"] == 1
    assert bundle["pairwise_inference"]["rejection_field"] == "separates_at_fwer_05"
    assert "run_dir" not in set(MODULE._walk_keys(bundle))
    assert "D:/private" not in json.dumps(bundle)
    assert bundle["execution_software"] == _manifest()["execution_software"]


def test_complete_zero_availability_is_scored_with_conditional_quality_na():
    leaderboard = _leaderboard()
    candidate = leaderboard["results"][1]
    candidate["availability"] = 0.0
    candidate["conditional_quality_score"] = None

    bundle = MODULE.build_publication(
        manifest=_manifest(),
        leaderboard=leaderboard,
        profile=_profile(),
        execution_panel=_panel(),
        coverage_audit=_audit(),
        catalog=_catalog(),
    )

    row = next(
        row for row in bundle["rows"] if row["endpoint_id"] == "kc-candidate-a"
    )
    assert row["benchmark_status"] == "scored"
    assert row["operational_goodput"] == 0.0
    assert row["conditional_quality_score"] is None
    assert row["n_a_reason"] is None


@pytest.mark.parametrize(
    ("catalog", "message"),
    [
        ([], "must not be empty"),
        (
            [
                {
                    "id": "kc-unrelated",
                    "display_name": "Unrelated",
                    "available": True,
                    "capabilities": ["text"],
                }
            ],
            "does not match coverage_audit.catalog_sha256",
        ),
    ],
)
def test_publication_binds_audit_to_the_exact_nonempty_matrix_catalog(
    catalog: list[dict], message: str
):
    with pytest.raises(MODULE.FrontierPublicationError, match=message):
        MODULE.build_publication(
            manifest=_manifest(),
            leaderboard=_leaderboard(),
            profile=_profile(),
            execution_panel=_panel(),
            coverage_audit=_audit(),
            catalog=catalog,
        )


def test_publication_requires_execution_software_and_accepts_clean_or_dirty():
    manifest = _manifest()
    manifest["execution_software"]["source_worktree_dirty"] = False
    clean = MODULE.build_publication(
        manifest=manifest,
        leaderboard=_leaderboard(),
        profile=_profile(),
        execution_panel=_panel(),
        coverage_audit=_audit(),
        catalog=_catalog(),
    )
    assert clean["execution_software"]["source_worktree_dirty"] is False
    assert "worktree was clean" in MODULE.render_markdown(clean, _leaderboard())

    del manifest["execution_software"]["source_commit"]
    with pytest.raises(MODULE.FrontierPublicationError, match="source commit"):
        MODULE.build_publication(
            manifest=manifest,
            leaderboard=_leaderboard(),
            profile=_profile(),
            execution_panel=_panel(),
            coverage_audit=_audit(),
            catalog=_catalog(),
        )


def test_writer_is_stable_private_free_and_hashes_all_public_artifacts(tmp_path: Path):
    bundle = _build()
    paths = MODULE.write_publication(
        bundle=bundle,
        leaderboard=_leaderboard(),
        output_dir=tmp_path,
        stem="frontier",
    )

    json_path = tmp_path / "frontier.json"
    csv_path = tmp_path / "frontier.csv"
    markdown_path = tmp_path / "frontier.md"
    checksum_path = tmp_path / "SHA256SUMS"
    assert paths == [json_path, csv_path, markdown_path, checksum_path]
    for path in paths:
        assert b"\r" not in path.read_bytes()

    document = json.loads(json_path.read_text(encoding="utf-8"))
    assert document["privacy_review"]["local_paths_included"] is False
    assert "D:/private" not in json_path.read_text(encoding="utf-8")

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        csv_rows = list(csv.DictReader(handle))
    by_id = {row["endpoint_id"]: row for row in csv_rows}
    assert by_id["kc-candidate-blocked"]["operational_goodput"] == "N/A"
    assert by_id["kc-openai-gpt-5-5"]["rank"] == "N/A"
    assert by_id["kc-candidate-a"]["operational_goodput"] == "0.0"
    coverage_only = next(
        row
        for row in csv_rows
        if row["vendor_model_id"] == "vendor-candidate-2026-08-08"
    )
    assert coverage_only["endpoint_id"] == "N/A"
    assert coverage_only["catalog_status"] == "staged"

    markdown = markdown_path.read_text(encoding="utf-8")
    assert "Core GA candidates reported as N/A" in markdown
    assert "GPT-5.5 baseline" in markdown
    assert "`vendor-candidate-2026-08-08`" in markdown
    assert "0 separated after" not in markdown
    assert "1 separated after" in markdown
    assert "llm-benchmark-protocol 1.0.2" in markdown
    assert "`" + "c" * 40 + "`" in markdown
    assert "contained uncommitted changes" in markdown

    checksum_entries = dict(
        reversed(line.split("  ", 1))
        for line in checksum_path.read_text(encoding="ascii").splitlines()
    )
    assert set(checksum_entries) == {"frontier.csv", "frontier.json", "frontier.md"}
    for name, digest in checksum_entries.items():
        assert digest == hashlib.sha256((tmp_path / name).read_bytes()).hexdigest()


def test_gpt_pairwise_handout_effect_is_oriented_sol_minus_baseline():
    note = "\n".join(
        MODULE._gpt_pairwise_note(
            {
                "results": [
                    {
                        "requested_model": "kc-openai-gpt-5-5",
                        "panel_key": "baseline",
                    },
                    {
                        "requested_model": "kc-gpt-5.6-sol",
                        "panel_key": "sol",
                    },
                ],
                "pairwise_tests": [
                    {
                        "higher_panel_key": "baseline",
                        "lower_panel_key": "sol",
                        "mean_difference": 0.035,
                        "ci95_low": -0.165,
                        "ci95_high": 0.235,
                        "randomization_p_value": 1.0,
                        "holm_adjusted_p_value": 1.0,
                    }
                ],
            }
        )
    )

    assert "Sol minus the GPT-5.5 baseline was -3.50 percentage points" in note
    assert "95% interval -23.50 to +16.50" in note


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda leaderboard, panel, audit: leaderboard["failures"].append(
                {"model": "x", "error": "failed"}
            ),
            "not publication-complete",
        ),
        (
            lambda leaderboard, panel, audit: leaderboard["results"][0].update(
                complete=False
            ),
            "must be complete",
        ),
        (
            lambda leaderboard, panel, audit: leaderboard["pairwise_tests"][0].pop(
                "separates_at_fwer_05"
            ),
            "separates_at_fwer_05",
        ),
        (
            lambda leaderboard, panel, audit: audit.update(profile_id="wrong"),
            "audit and profile ids differ",
        ),
    ],
)
def test_publication_fails_closed_on_incomplete_or_drifted_sources(
    mutation, message: str
):
    leaderboard = _leaderboard()
    panel = _panel()
    audit = _audit()
    mutation(leaderboard, panel, audit)
    with pytest.raises(MODULE.FrontierPublicationError, match=message):
        MODULE.build_publication(
            manifest=_manifest(panel),
            leaderboard=leaderboard,
            profile=_profile(),
            execution_panel=panel,
            coverage_audit=audit,
            catalog=_catalog(),
        )


def test_preview_endpoint_cannot_be_pooled_into_ga_execution():
    profile = _profile()
    panel = _panel()
    panel[0] = {
        **panel[0],
        "key": "preview-d-run",
        "model": "kc-preview-d",
        "label": "Preview D",
    }
    leaderboard = _leaderboard()
    leaderboard["results"][1].update(
        panel_key="preview-d-run",
        requested_model="kc-preview-d",
        model="Preview D",
    )
    leaderboard["pairwise_tests"][0]["lower_panel_key"] = "preview-d-run"
    with pytest.raises(
        MODULE.FrontierPublicationError, match="cannot be pooled"
    ):
        MODULE.build_publication(
            manifest=_manifest(panel),
            leaderboard=leaderboard,
            profile=profile,
            execution_panel=panel,
            coverage_audit=_audit(),
            catalog=_catalog(),
        )


def test_coverage_only_profile_entry_cannot_claim_a_kendr_catalog_id():
    profile = _profile()
    coverage_only = profile["cohorts"][0]["entries"][2]
    coverage_only["catalog_id"] = "invented-kendr-id"

    with pytest.raises(
        MODULE.FrontierPublicationError, match="cannot declare"
    ):
        MODULE.build_publication(
            manifest=_manifest(),
            leaderboard=_leaderboard(),
            profile=profile,
            execution_panel=_panel(),
            coverage_audit=_audit(),
            catalog=_catalog(),
        )


def test_coverage_only_audit_entry_cannot_be_relabelled_as_present():
    audit = _audit()
    coverage_only = audit["cohorts"][0]["entries"][2]
    coverage_only["status"] = "present"

    with pytest.raises(
        MODULE.FrontierPublicationError, match="staged non-executable"
    ):
        MODULE.build_publication(
            manifest=_manifest(),
            leaderboard=_leaderboard(),
            profile=_profile(),
            execution_panel=_panel(),
            coverage_audit=audit,
            catalog=_catalog(),
        )


def test_cli_writes_only_the_public_bundle(tmp_path: Path):
    matrix = tmp_path / "matrix"
    matrix.mkdir()
    panel_path = tmp_path / "panel.json"
    profile_path = tmp_path / "profile.json"
    audit_path = tmp_path / "audit.json"
    output = tmp_path / "public"

    (matrix / "manifest.json").write_text(
        json.dumps(_manifest()), encoding="utf-8"
    )
    (matrix / "leaderboard.json").write_text(
        json.dumps(_leaderboard()), encoding="utf-8"
    )
    (matrix / "kendr_model_catalog.json").write_text(
        json.dumps(_catalog()), encoding="utf-8"
    )
    panel_path.write_text(json.dumps(_panel()), encoding="utf-8")
    profile_path.write_text(json.dumps(_profile()), encoding="utf-8")
    audit_path.write_text(json.dumps(_audit()), encoding="utf-8")

    assert (
        MODULE.main(
            [
                "--matrix-root",
                str(matrix),
                "--profile",
                str(profile_path),
                "--execution-panel",
                str(panel_path),
                "--coverage-audit",
                str(audit_path),
                "--output",
                str(output),
                "--stem",
                "frontier-test",
            ]
        )
        == 0
    )
    assert {path.name for path in output.iterdir()} == {
        "frontier-test.json",
        "frontier-test.csv",
        "frontier-test.md",
        "SHA256SUMS",
    }
    public = json.loads((output / "frontier-test.json").read_text(encoding="utf-8"))
    assert public["provenance"]["catalog_sha256"] == MODULE.catalog_sha256(
        _catalog()
    )
    assert "catalog_source" not in set(MODULE._walk_keys(public))
