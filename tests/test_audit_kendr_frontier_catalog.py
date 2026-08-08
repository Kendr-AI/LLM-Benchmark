from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.audit_kendr_frontier_catalog import (
    FrontierProfileError,
    audit_frontier_profile,
    main,
)


PROJECT_ROOT = Path(__file__).parents[1]
RELEASE_PROFILE = (
    PROJECT_ROOT / "config" / "kendr-current-frontier-profile-20260808.json"
)


def _model(model_id: str, label: str, **overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "id": model_id,
        "display_name": label,
        "owned_by": "kendr",
        "mode": "normal",
        "available": True,
        "capabilities": ["text"],
    }
    value.update(overrides)
    return value


def _profile() -> dict[str, object]:
    return {
        "profile_id": "test-frontier",
        "snapshot_date": "2026-08-08",
        "ga_cohort_id": "core-ga",
        "companion_cohort_id": "preview-companion",
        "cohorts": [
            {
                "id": "core-ga",
                "claim_class": "general-availability",
                "claim_scope": "GA candidates and baseline",
                "entries": [
                    {
                        "key": "core-model",
                        "label": "Core Model",
                        "vendor_model_id": "vendor-core-model",
                        "catalog_id": "core-model",
                        "role": "candidate",
                    },
                    {
                        "key": "baseline",
                        "label": "Reference baseline",
                        "expected_display_name": "Baseline Model",
                        "catalog_id": "baseline-model",
                        "role": "baseline",
                    },
                    {
                        "key": "coverage-only",
                        "label": "Coverage Only Model",
                        "vendor_model_id": "vendor-model-2026-08-08",
                        "role": "candidate",
                        "coverage_only": True,
                        "coverage_status": "staged",
                        "n_a_reason": (
                            "Staged coverage identity has no executable Kendr id."
                        ),
                    },
                ],
            },
            {
                "id": "preview-companion",
                "claim_class": "preview-or-limited-access",
                "claim_scope": "Separate preview companion",
                "entries": [
                    {
                        "key": "preview-model",
                        "label": "Preview Model",
                        "catalog_id": "preview-model",
                    }
                ],
            },
        ],
    }


def test_frontier_audit_builds_separate_ready_panels() -> None:
    catalog = [
        _model("core-model", "Core Model"),
        _model("baseline-model", "Baseline Model"),
        _model("preview-model", "Preview Model"),
        _model(
            "personal-router",
            "Personal Router",
            owned_by="kendr-user",
            custom_routing_profile=True,
        ),
    ]

    audit, panels = audit_frontier_profile(catalog, _profile())

    assert audit["ga_claim_ready"] is True
    assert audit["companion_claim_ready"] is True
    assert [row["model"] for row in panels["core-ga"]] == [
        "core-model",
        "baseline-model",
    ]
    coverage_only = next(
        entry
        for entry in audit["cohorts"][0]["entries"]
        if entry["key"] == "coverage-only"
    )
    assert coverage_only == {
        "key": "coverage-only",
        "label": "Coverage Only Model",
        "expected_display_name": "Coverage Only Model",
        "role": "candidate",
        "catalog_id": None,
        "required": False,
        "coverage_only": True,
        "vendor_model_id": "vendor-model-2026-08-08",
        "status": "coverage_only",
        "coverage_status": "staged",
        "execution_eligible": False,
        "reason": "Staged coverage identity has no executable Kendr id.",
    }
    assert [row["model"] for row in panels["preview-companion"]] == [
        "preview-model"
    ]
    assert all(
        row["model"] != "preview-model" for row in panels["core-ga"]
    )
    assert audit["catalog_excluded_entries"][0]["reason"] == (
        "user-owned alias excluded by default"
    )


def test_frontier_audit_never_resolves_identity_from_label_alone() -> None:
    profile = _profile()
    core_entries = profile["cohorts"][0]["entries"]  # type: ignore[index]
    core_entries[0]["catalog_id"] = None  # type: ignore[index]
    catalog = [
        _model("some-other-id", "Core Model"),
        _model("baseline-model", "Baseline Model"),
        _model("preview-model", "Preview Model"),
    ]

    audit, panels = audit_frontier_profile(catalog, profile)

    core = audit["cohorts"][0]
    unresolved = core["entries"][0]
    assert core["ready"] is False
    assert unresolved["status"] == "identity_unresolved"
    assert unresolved["candidate_catalog_ids_by_exact_label"] == [
        "some-other-id"
    ]
    assert [row["model"] for row in panels["core-ga"]] == ["baseline-model"]


def test_frontier_audit_preserves_declared_reason_for_missing_route() -> None:
    profile = _profile()
    core_entry = profile["cohorts"][0]["entries"][0]  # type: ignore[index]
    core_entry["n_a_reason"] = "Credential intentionally not configured."
    catalog = [
        _model("baseline-model", "Baseline Model"),
        _model("preview-model", "Preview Model"),
    ]

    audit, _ = audit_frontier_profile(catalog, profile)

    missing = audit["cohorts"][0]["entries"][0]
    assert missing["status"] == "missing"
    assert missing["vendor_model_id"] == "vendor-core-model"
    assert missing["reason"] == "Credential intentionally not configured."


def test_selected_duplicate_labels_block_panel_emission(tmp_path) -> None:
    profile = _profile()
    core_entries = profile["cohorts"][0]["entries"]  # type: ignore[index]
    core_entries[1]["label"] = "Core Model"  # type: ignore[index]
    core_entries[1]["expected_display_name"] = "Core Model"  # type: ignore[index]
    catalog = [
        _model("core-model", "Core Model"),
        _model("baseline-model", "Core Model"),
        _model("preview-model", "Preview Model"),
    ]
    catalog_path = tmp_path / "catalog.json"
    profile_path = tmp_path / "profile.json"
    audit_path = tmp_path / "audit.json"
    panel_path = tmp_path / "core-panel.json"
    catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
    profile_path.write_text(json.dumps(profile), encoding="utf-8")
    audit_path.write_text('{"stale": true}', encoding="utf-8")
    panel_path.write_text('[{"model": "stale-model"}]', encoding="utf-8")

    with pytest.raises(FrontierProfileError, match="not ready"):
        main(
            [
                "--catalog",
                str(catalog_path),
                "--profile",
                str(profile_path),
                "--audit-output",
                str(audit_path),
                "--core-panel-output",
                str(panel_path),
            ]
        )

    assert audit_path.is_file()
    assert not panel_path.exists()
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    assert audit["ga_claim_ready"] is False
    assert len(audit["selected_duplicate_display_label_groups"]) == 1
    assert "catalog_source" not in audit
    assert "profile_source" not in audit
    assert len(audit["profile_sha256"]) == 64
    assert str(tmp_path) not in json.dumps(audit)


def test_invalid_input_removes_stale_generated_audit_and_panels(tmp_path) -> None:
    catalog_path = tmp_path / "catalog.json"
    profile_path = tmp_path / "profile.json"
    audit_path = tmp_path / "audit.json"
    core_panel_path = tmp_path / "core-panel.json"
    companion_panel_path = tmp_path / "companion-panel.json"
    catalog_path.write_text("not-json", encoding="utf-8")
    profile_path.write_text(json.dumps(_profile()), encoding="utf-8")
    for path in (audit_path, core_panel_path, companion_panel_path):
        path.write_text('{"stale": true}', encoding="utf-8")

    with pytest.raises(FrontierProfileError, match="Invalid JSON"):
        main(
            [
                "--catalog",
                str(catalog_path),
                "--profile",
                str(profile_path),
                "--audit-output",
                str(audit_path),
                "--core-panel-output",
                str(core_panel_path),
                "--companion-panel-output",
                str(companion_panel_path),
            ]
        )

    assert not audit_path.exists()
    assert not core_panel_path.exists()
    assert not companion_panel_path.exists()


def test_coverage_only_entries_cannot_claim_a_kendr_catalog_id() -> None:
    profile = _profile()
    coverage_only = profile["cohorts"][0]["entries"][2]  # type: ignore[index]
    coverage_only["catalog_id"] = "invented-kendr-id"  # type: ignore[index]

    with pytest.raises(FrontierProfileError, match="cannot declare"):
        audit_frontier_profile([], profile)


def test_release_profile_stages_unresolved_vendor_identities_without_kendr_ids() -> None:
    profile = json.loads(RELEASE_PROFILE.read_text(encoding="utf-8"))

    audit, panels = audit_frontier_profile([], profile)
    entries = {
        entry["key"]: entry
        for cohort in audit["cohorts"]
        for entry in cohort["entries"]
    }

    assert {
        key: (
            entries[key]["vendor_model_id"],
            entries[key]["catalog_id"],
            entries[key]["status"],
            entries[key]["required"],
            entries[key]["execution_eligible"],
        )
        for key in ("deepseek-v4-pro", "qwen-3-7-max-2026-05-20")
    } == {
        "deepseek-v4-pro": (
            "deepseek-v4-pro",
            None,
            "coverage_only",
            False,
            False,
        ),
        "qwen-3-7-max-2026-05-20": (
            "qwen3.7-max-2026-05-20",
            None,
            "coverage_only",
            False,
            False,
        ),
    }
    assert all(
        row["key"] not in {"deepseek-v4-pro", "qwen-3-7-max-2026-05-20"}
        for row in panels["core-ga"]
    )


def test_output_path_collision_cannot_delete_an_input(tmp_path) -> None:
    catalog_path = tmp_path / "catalog.json"
    profile_path = tmp_path / "profile.json"
    catalog_text = json.dumps([_model("core-model", "Core Model")])
    catalog_path.write_text(catalog_text, encoding="utf-8")
    profile_path.write_text(json.dumps(_profile()), encoding="utf-8")

    with pytest.raises(FrontierProfileError, match="must not reuse"):
        main(
            [
                "--catalog",
                str(catalog_path),
                "--profile",
                str(profile_path),
                "--audit-output",
                str(catalog_path),
            ]
        )

    assert catalog_path.read_text(encoding="utf-8") == catalog_text


def test_profile_rejects_mixing_companion_with_ga_claim_class() -> None:
    profile = _profile()
    profile["cohorts"][1]["claim_class"] = "general-availability"  # type: ignore[index]
    catalog = [
        _model("core-model", "Core Model"),
        _model("baseline-model", "Baseline Model"),
        _model("preview-model", "Preview Model"),
    ]

    with pytest.raises(FrontierProfileError, match="companion cohort"):
        audit_frontier_profile(catalog, profile)
