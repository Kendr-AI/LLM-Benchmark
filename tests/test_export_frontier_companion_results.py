from __future__ import annotations

import copy
import csv
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "export_frontier_companion_results.py"
PANEL_PATH = (
    PROJECT_ROOT
    / "config"
    / "kendr-frontier-preview-execution-panel-20260808.json"
)
SPEC = importlib.util.spec_from_file_location(
    "export_frontier_companion_results", SCRIPT
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _profile() -> dict:
    return {
        "schema_version": "1.0",
        "profile_id": "frontier-profile",
        "snapshot_date": "2026-08-08",
        "ga_cohort_id": "core-ga",
        "companion_cohort_id": "preview-companion",
        "cohorts": [
            {
                "id": "core-ga",
                "claim_class": "general-availability",
                "entries": [
                    {
                        "key": "ga-model",
                        "label": "GA Model",
                        "catalog_id": "kc-ga-model",
                        "role": "candidate",
                    },
                    {
                        "key": "gpt-5-5-baseline",
                        "label": "GPT-5.5 baseline",
                        "expected_display_name": "GPT-5.5",
                        "catalog_id": "kc-openai-gpt-5-5",
                        "role": "baseline",
                    },
                ],
            },
            {
                "id": "preview-companion",
                "claim_class": "preview-or-limited-access",
                "entries": [
                    {
                        "key": "qwen-preview",
                        "label": "Qwen Preview",
                        "vendor_model_id": "qwen-preview",
                        "catalog_id": "kc-qwen-preview",
                        "role": "candidate",
                        "n_a_reason": "Dedicated preview access is unavailable.",
                    },
                    {
                        "key": "gemini-preview",
                        "label": "Gemini Preview",
                        "vendor_model_id": "gemini-preview",
                        "catalog_id": "kc-gemini-preview",
                        "role": "candidate",
                    },
                ],
            },
        ],
    }


def _panel() -> list[dict]:
    return [
        {
            "key": "gemini-preview-companion",
            "provider": "kendr",
            "model": "kc-gemini-preview",
            "label": "Gemini Preview (Kendr served preview companion)",
            "access": "Kendr managed preview route",
            "license": "Proprietary provider terms",
            "license_source": "https://example.com/terms",
        }
    ]


def _catalog(include_qwen: bool = False) -> list[dict]:
    rows = [
        {
            "id": "kc-ga-model",
            "display_name": "GA Model",
            "available": True,
            "capabilities": ["text"],
        },
        {
            "id": "kc-openai-gpt-5-5",
            "display_name": "GPT-5.5",
            "available": True,
            "capabilities": ["text"],
        },
        {
            "id": "kc-gemini-preview",
            "display_name": "Gemini Preview",
            "available": True,
            "capabilities": ["text", "vision"],
        },
    ]
    if include_qwen:
        rows.append(
            {
                "id": "kc-qwen-preview",
                "display_name": "Qwen Preview",
                "available": True,
                "capabilities": ["text"],
            }
        )
    return rows


def _audit(
    *,
    catalog: list[dict] | None = None,
    qwen_present: bool = False,
    profile_sha256: str = "a" * 64,
) -> dict:
    catalog = catalog or _catalog()
    return {
        "schema_version": "1.0",
        "profile_id": "frontier-profile",
        "snapshot_date": "2026-08-08",
        "profile_sha256": profile_sha256,
        "catalog_entries": len(catalog),
        "catalog_sha256": MODULE.frontier.catalog_sha256(catalog),
        "ga_claim_ready": True,
        "companion_claim_ready": qwen_present,
        "claim_separation": "Companion results stay separate from GA claims.",
        "cohorts": [
            {
                "id": "core-ga",
                "entries": [
                    {
                        "key": "ga-model",
                        "label": "GA Model",
                        "catalog_id": "kc-ga-model",
                        "role": "candidate",
                        "status": "present",
                        "observed_display_name": "GA Model",
                        "owned_by": None,
                        "mode": None,
                    },
                    {
                        "key": "gpt-5-5-baseline",
                        "label": "GPT-5.5 baseline",
                        "catalog_id": "kc-openai-gpt-5-5",
                        "role": "baseline",
                        "status": "present",
                        "observed_display_name": "GPT-5.5",
                        "owned_by": None,
                        "mode": None,
                    },
                ],
            },
            {
                "id": "preview-companion",
                "entries": [
                    {
                        "key": "qwen-preview",
                        "label": "Qwen Preview",
                        "catalog_id": "kc-qwen-preview",
                        "role": "candidate",
                        "status": "present" if qwen_present else "missing",
                        **(
                            {
                                "observed_display_name": "Qwen Preview",
                                "owned_by": None,
                                "mode": None,
                            }
                            if qwen_present
                            else {"reason": "Dedicated preview access is unavailable."}
                        ),
                    },
                    {
                        "key": "gemini-preview",
                        "label": "Gemini Preview",
                        "catalog_id": "kc-gemini-preview",
                        "role": "candidate",
                        "status": "present",
                        "observed_display_name": "Gemini Preview",
                        "owned_by": None,
                        "mode": None,
                    },
                ],
            },
        ],
    }


def _manifest(panel: list[dict] | None = None) -> dict:
    return {
        "matrix_id": "preview-matrix",
        "created_at": "2026-08-08T12:00:00+00:00",
        "models": copy.deepcopy(panel or _panel()),
        "livebench_release": "2026-06-25",
        "tasks": ["live_bench/math/a", "live_bench/reasoning/b"],
        "questions_per_task": 1,
        "sampling": {
            "mode": "seeded-random",
            "seed": 20260808,
            "selected_ids": ["q1", "q2"],
            "content_hash": "1" * 64,
            "content_hash_algorithm": "sha256",
            "selected_date_distribution": {"2024-11-25": 2},
        },
        "max_tokens": 2048,
        "deadline_ms": 120000,
        "max_cost_usd_per_answer": None,
        "practical_equivalence_margin": 0.02,
        "parallel_requests": 1,
        "parallel_grading": 2,
        "reasoning_effort": "none",
        "execution_software": {
            "package": "llm-benchmark-protocol",
            "version": "1.0.2",
            "source_repository": "https://github.com/Kendr-AI/LLM-Benchmark",
            "source_commit": "c" * 40,
            "source_worktree_dirty": True,
        },
        "panel_file": "D:/private/companion-panel.json",
    }


def _result(
    *,
    rank: int = 1,
    panel_key: str = "gemini-preview-companion",
    model_id: str = "kc-gemini-preview",
    label: str = "Gemini Preview (Kendr served preview companion)",
    goodput: float = 0.75,
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
        "operational_goodput_ci95_low": max(0.0, goodput - 0.2),
        "operational_goodput_ci95_high": min(1.0, goodput + 0.2),
        "quality_ci95_low": max(0.0, goodput - 0.2),
        "quality_ci95_high": min(1.0, goodput + 0.2),
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
        "raw_response": "private answer",
        "provider_request_id": "private-request-id",
        "error_message": "private provider message",
        "run_dir": "D:/private/run",
    }


def _leaderboard(panel: list[dict] | None = None) -> dict:
    del panel
    return {
        "matrix_id": "preview-matrix",
        "created_at": "2026-08-08T12:30:00+00:00",
        "livebench_release": "2026-06-25",
        "tasks": ["live_bench/math/a", "live_bench/reasoning/b"],
        "questions_per_task": 1,
        "requested_max_output_tokens": 2048,
        "parallel_requests": 1,
        "ranking_rule": "Operational goodput descending.",
        "results": [_result()],
        "pairwise_test_family": {
            "comparisons": 0,
            "test": "two-sided paired sign-randomization",
            "multiplicity_correction": "Holm family-wise error rate",
            "alpha": 0.05,
            "practical_equivalence_margin": 0.02,
        },
        "pairwise_tests": [],
        "failures": [],
    }


def _hashes(profile_sha256: str = "a" * 64) -> dict[str, str]:
    return {
        "coverage_audit_sha256": "b" * 64,
        "execution_panel_sha256": "d" * 64,
        "matrix_catalog_file_sha256": "e" * 64,
        "matrix_leaderboard_sha256": "f" * 64,
        "matrix_manifest_sha256": "1" * 64,
        "profile_sha256": profile_sha256,
    }


def _build() -> dict:
    return MODULE.build_publication(
        manifest=_manifest(),
        leaderboard=_leaderboard(),
        profile=_profile(),
        execution_panel=_panel(),
        coverage_audit=_audit(),
        catalog=_catalog(),
        source_hashes=_hashes(),
    )


def test_frozen_preview_panel_has_only_exact_gemini_configuration() -> None:
    panel = json.loads(PANEL_PATH.read_text(encoding="utf-8"))
    assert panel == [
        {
            "key": "gemini-3-1-pro-preview-kendr-companion",
            "provider": "kendr",
            "model": "kc-gemini-3.1-pro-preview",
            "label": "Gemini 3.1 Pro Preview (Kendr served preview companion)",
            "access": (
                "Kendr API managed Google preview route; separate preview "
                "companion cohort"
            ),
            "license": "Proprietary provider terms",
            "license_source": "https://ai.google.dev/gemini-api/terms",
        }
    ]


def test_single_callable_companion_is_descriptive_and_missing_entry_is_na() -> None:
    bundle = _build()
    by_id = {row["endpoint_id"]: row for row in bundle["rows"]}

    gemini = by_id["kc-gemini-preview"]
    assert gemini["benchmark_status"] == "scored"
    assert "companion_rank" not in gemini
    assert "execution_rank" not in gemini
    assert "tier" not in gemini
    assert gemini["operational_goodput"] == 0.75
    assert gemini["availability"] == 1.0
    assert gemini["license"] == "Proprietary provider terms"

    qwen = by_id["kc-qwen-preview"]
    assert qwen["benchmark_status"] == "not_measured"
    assert qwen["operational_goodput"] is None
    assert qwen["n_a_reason_code"] == "missing"
    assert "unavailable" in qwen["n_a_reason"]

    assert bundle["ranking"]["status"] == (
        "single-scored-endpoint-descriptive-no-rank"
    )
    assert bundle["pairwise_inference"]["comparisons"] == 0
    assert bundle["pairwise_inference"]["tests"] == []
    assert bundle["execution_software"]["source_worktree_dirty"] is True
    serialized = json.dumps(bundle)
    assert "kc-ga-model" not in serialized
    assert "kc-openai-gpt-5-5" not in serialized
    assert "D:/private" not in serialized
    assert "private-request-id" not in serialized
    assert "private provider message" not in serialized
    assert "raw_response" not in set(MODULE.frontier._walk_keys(bundle))


def test_writer_uses_dedicated_bundle_and_hashes_every_public_artifact(
    tmp_path: Path,
) -> None:
    output = tmp_path / "preview-companion"
    paths = MODULE.write_publication(
        bundle=_build(), output_dir=output, stem="companion-test"
    )
    assert {path.name for path in paths} == {
        "companion-test.json",
        "companion-test.csv",
        "companion-test.md",
        "SHA256SUMS",
    }
    for path in paths:
        assert b"\r" not in path.read_bytes()

    with (output / "companion-test.csv").open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        rows = list(csv.DictReader(handle))
    by_id = {row["endpoint_id"]: row for row in rows}
    assert "companion_rank" not in by_id["kc-gemini-preview"]
    assert "execution_rank" not in by_id["kc-gemini-preview"]
    assert by_id["kc-qwen-preview"]["operational_goodput"] == "N/A"

    markdown = (output / "companion-test.md").read_text(encoding="utf-8")
    assert "Not assigned (single row)" in markdown
    assert "zero GA or baseline endpoints" in markdown
    assert "contained uncommitted changes" in markdown
    assert "private-request-id" not in markdown

    checksum_entries = dict(
        reversed(line.split("  ", 1))
        for line in (output / "SHA256SUMS")
        .read_text(encoding="ascii")
        .splitlines()
    )
    assert set(checksum_entries) == {
        "companion-test.csv",
        "companion-test.json",
        "companion-test.md",
    }
    for name, digest in checksum_entries.items():
        assert digest == hashlib.sha256((output / name).read_bytes()).hexdigest()

    (output / "unrelated.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(
        MODULE.CompanionPublicationError, match="must be dedicated"
    ):
        MODULE.write_publication(
            bundle=_build(), output_dir=output, stem="companion-test"
        )


def test_manifest_must_match_every_exact_panel_field() -> None:
    manifest = _manifest()
    manifest["models"][0]["license_source"] = "https://example.com/drifted"
    with pytest.raises(
        MODULE.CompanionPublicationError, match="exactly match"
    ):
        MODULE.build_publication(
            manifest=manifest,
            leaderboard=_leaderboard(),
            profile=_profile(),
            execution_panel=_panel(),
            coverage_audit=_audit(),
            catalog=_catalog(),
            source_hashes=_hashes(),
        )


def test_ga_and_baseline_ids_are_rejected_before_publication() -> None:
    for forbidden_id in ("kc-ga-model", "kc-openai-gpt-5-5"):
        panel = _panel()
        panel[0]["model"] = forbidden_id
        with pytest.raises(
            MODULE.CompanionPublicationError,
            match="GA and baseline endpoints are forbidden",
        ):
            MODULE.build_publication(
                manifest=_manifest(panel),
                leaderboard=_leaderboard(),
                profile=_profile(),
                execution_panel=panel,
                coverage_audit=_audit(),
                catalog=_catalog(),
                source_hashes=_hashes(),
            )


def test_incomplete_matrix_and_catalog_hash_drift_fail_closed() -> None:
    leaderboard = _leaderboard()
    leaderboard["results"][0]["complete"] = False
    with pytest.raises(MODULE.CompanionPublicationError, match="must be complete"):
        MODULE.build_publication(
            manifest=_manifest(),
            leaderboard=leaderboard,
            profile=_profile(),
            execution_panel=_panel(),
            coverage_audit=_audit(),
            catalog=_catalog(),
            source_hashes=_hashes(),
        )

    audit = _audit()
    audit["catalog_sha256"] = "0" * 64
    with pytest.raises(
        MODULE.CompanionPublicationError, match="does not match"
    ):
        MODULE.build_publication(
            manifest=_manifest(),
            leaderboard=_leaderboard(),
            profile=_profile(),
            execution_panel=_panel(),
            coverage_audit=audit,
            catalog=_catalog(),
            source_hashes=_hashes(),
        )


@pytest.mark.parametrize(
    ("catalog_mutation", "message"),
    [
        (
            lambda row: row.update(owned_by="kendr-user"),
            "eligibility drift",
        ),
        (
            lambda row: row.update(display_name="Different Preview Identity"),
            "eligibility drift",
        ),
        (
            lambda row: row.update(available=False),
            "eligibility drift",
        ),
    ],
)
def test_tampered_present_audit_cannot_override_recomputed_catalog_eligibility(
    catalog_mutation, message: str
) -> None:
    catalog = _catalog()
    gemini = next(row for row in catalog if row["id"] == "kc-gemini-preview")
    catalog_mutation(gemini)
    # Deliberately retain the supplied audit's false `present` assertion while
    # rebinding its catalog hash, proving that hash agreement alone is not an
    # eligibility decision.
    audit = _audit(catalog=catalog)
    with pytest.raises(MODULE.CompanionPublicationError, match=message):
        MODULE.build_publication(
            manifest=_manifest(),
            leaderboard=_leaderboard(),
            profile=_profile(),
            execution_panel=_panel(),
            coverage_audit=audit,
            catalog=catalog,
            source_hashes=_hashes(),
        )


def test_scheduled_identity_requires_unique_normalized_eligible_label() -> None:
    catalog = _catalog()
    catalog.append(
        {
            "id": "kc-gemini-preview-alias",
            "display_name": "Gemini   Preview",
            "available": True,
            "capabilities": ["text"],
        }
    )
    audit = _audit(catalog=catalog)
    with pytest.raises(
        MODULE.CompanionPublicationError, match="unique eligible normalized"
    ):
        MODULE.build_publication(
            manifest=_manifest(),
            leaderboard=_leaderboard(),
            profile=_profile(),
            execution_panel=_panel(),
            coverage_audit=audit,
            catalog=catalog,
            source_hashes=_hashes(),
        )


def test_single_endpoint_family_must_have_zero_comparisons_and_no_tests() -> None:
    leaderboard = _leaderboard()
    leaderboard["pairwise_test_family"]["comparisons"] = 1
    with pytest.raises(
        MODULE.CompanionPublicationError, match="must declare comparisons=0"
    ):
        MODULE.build_publication(
            manifest=_manifest(),
            leaderboard=leaderboard,
            profile=_profile(),
            execution_panel=_panel(),
            coverage_audit=_audit(),
            catalog=_catalog(),
            source_hashes=_hashes(),
        )

    leaderboard = _leaderboard()
    leaderboard["pairwise_tests"] = [{"comparison_id": "forbidden"}]
    with pytest.raises(
        MODULE.CompanionPublicationError, match="must have no pairwise tests"
    ):
        MODULE.build_publication(
            manifest=_manifest(),
            leaderboard=leaderboard,
            profile=_profile(),
            execution_panel=_panel(),
            coverage_audit=_audit(),
            catalog=_catalog(),
            source_hashes=_hashes(),
        )


def test_multi_endpoint_companion_panel_is_rejected() -> None:
    panel = _panel() + [
        {
            "key": "qwen-preview-companion",
            "provider": "kendr",
            "model": "kc-qwen-preview",
            "label": "Qwen Preview (Kendr served preview companion)",
            "access": "Kendr managed preview route",
            "license": "Proprietary provider terms",
            "license_source": "https://example.com/qwen-terms",
        }
    ]
    with pytest.raises(
        MODULE.CompanionPublicationError,
        match="requires exactly one execution endpoint",
    ):
        MODULE.build_publication(
            manifest=_manifest(panel),
            leaderboard=_leaderboard(),
            profile=_profile(),
            execution_panel=panel,
            coverage_audit=_audit(
                catalog=_catalog(include_qwen=True), qwen_present=True
            ),
            catalog=_catalog(include_qwen=True),
            source_hashes=_hashes(),
        )


def test_multi_result_matrix_is_rejected_before_pairwise_publication() -> None:
    leaderboard = _leaderboard()
    leaderboard["results"].append(
        _result(
            rank=2,
            panel_key="unexpected-second",
            model_id="kc-unexpected-second",
            label="Unexpected second endpoint",
            goodput=0.5,
        )
    )
    with pytest.raises(
        MODULE.CompanionPublicationError,
        match="requires exactly one scored endpoint",
    ):
        MODULE.build_publication(
            manifest=_manifest(),
            leaderboard=leaderboard,
            profile=_profile(),
            execution_panel=_panel(),
            coverage_audit=_audit(),
            catalog=_catalog(),
            source_hashes=_hashes(),
        )


def test_nonfinite_public_metric_cannot_reach_json() -> None:
    leaderboard = _leaderboard()
    leaderboard["results"][0]["latency_p50_ms"] = float("nan")
    with pytest.raises(
        MODULE.CompanionPublicationError, match="strict finite JSON"
    ):
        MODULE.build_publication(
            manifest=_manifest(),
            leaderboard=leaderboard,
            profile=_profile(),
            execution_panel=_panel(),
            coverage_audit=_audit(),
            catalog=_catalog(),
            source_hashes=_hashes(),
        )


def test_cli_writes_only_companion_public_bundle(tmp_path: Path) -> None:
    matrix = tmp_path / "matrix"
    matrix.mkdir()
    output = tmp_path / "companion-output"
    profile_path = tmp_path / "profile.json"
    panel_path = tmp_path / "panel.json"
    audit_path = tmp_path / "audit.json"
    profile_path.write_text(json.dumps(_profile()), encoding="utf-8")
    panel_path.write_text(json.dumps(_panel()), encoding="utf-8")
    profile_hash = hashlib.sha256(profile_path.read_bytes()).hexdigest()
    catalog = _catalog()
    audit_path.write_text(
        json.dumps(_audit(catalog=catalog, profile_sha256=profile_hash)),
        encoding="utf-8",
    )
    (matrix / "manifest.json").write_text(
        json.dumps(_manifest()), encoding="utf-8"
    )
    (matrix / "leaderboard.json").write_text(
        json.dumps(_leaderboard()), encoding="utf-8"
    )
    (matrix / "kendr_model_catalog.json").write_text(
        json.dumps(catalog), encoding="utf-8"
    )

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
                "preview-test",
            ]
        )
        == 0
    )
    assert {path.name for path in output.iterdir()} == {
        "preview-test.json",
        "preview-test.csv",
        "preview-test.md",
        "SHA256SUMS",
    }
    public = json.loads((output / "preview-test.json").read_text(encoding="utf-8"))
    expected_hashes = {
        "profile_sha256": hashlib.sha256(profile_path.read_bytes()).hexdigest(),
        "execution_panel_sha256": hashlib.sha256(panel_path.read_bytes()).hexdigest(),
        "matrix_manifest_sha256": hashlib.sha256(
            (matrix / "manifest.json").read_bytes()
        ).hexdigest(),
        "matrix_leaderboard_sha256": hashlib.sha256(
            (matrix / "leaderboard.json").read_bytes()
        ).hexdigest(),
        "matrix_catalog_file_sha256": hashlib.sha256(
            (matrix / "kendr_model_catalog.json").read_bytes()
        ).hexdigest(),
        "coverage_audit_sha256": hashlib.sha256(
            audit_path.read_bytes()
        ).hexdigest(),
    }
    for name, digest in expected_hashes.items():
        assert public["provenance"][name] == digest
