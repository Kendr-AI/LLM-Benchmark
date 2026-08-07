from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from kendr_bench.global_protocol import audit_protocol, load_protocol, render_audit_markdown


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "config" / "global-protocol-v1.example.json"


def _example() -> dict:
    return load_protocol(EXAMPLE)


def test_example_clears_every_design_dimension() -> None:
    audit = audit_protocol(_example())

    assert audit.design_ready is True
    assert audit.design_score == 10.0
    assert audit.minimum_dimension_score == 10.0
    assert all(dimension.score > 9 for dimension in audit.dimensions)
    assert audit.execution_ready is False
    assert audit.evidence_bundle_structurally_complete is False
    assert audit.global_publication_candidate is False
    assert "not 'executed'" in audit.execution_blockers[0]


def test_critical_failure_caps_dimension_below_gate() -> None:
    config = _example()
    config["sampling"]["minimum_items"] = 15
    config["sampling"]["repeats_per_item"] = 1

    audit = audit_protocol(config)
    statistics = next(
        dimension
        for dimension in audit.dimensions
        if dimension.dimension == "statistical_validity"
    )

    assert statistics.score <= 8.9
    assert statistics.passed is False
    assert {check.check_id for check in statistics.failed_checks} == {"ST01", "ST02"}
    assert audit.design_ready is False


def test_execution_requires_external_evidence() -> None:
    config = _example()
    config["study"]["status"] = "executed"
    config["evidence"] = {
        "preregistration_uri": "https://registry.example/study",
        "raw_artifact_bundle_uri": "https://artifacts.example/run",
        "signed_manifest_uri": "https://log.example/manifest",
        "independent_review_uri": "https://review.example/report",
        "replication_reports": [
            "https://lab-one.example/report",
            "https://lab-two.example/report"
        ],
        "benchmark_card_uri": "https://benchmark.example/card",
        "standards_crosswalk_uri": "https://benchmark.example/crosswalk",
        "protocol_deviations_resolved": True,
        "all_primary_tracks_adequately_powered": True
    }

    audit = audit_protocol(config)

    assert audit.design_ready is True
    assert audit.execution_blockers == ()
    assert audit.execution_ready is True
    assert audit.evidence_bundle_structurally_complete is True
    assert audit.global_publication_candidate is False


def test_router_profile_requires_router_specific_evidence() -> None:
    config = _example()
    config["specialized"]["router"]["full_candidate_counterfactuals"] = False

    audit = audit_protocol(config)
    systems = next(
        dimension
        for dimension in audit.dimensions
        if dimension.dimension == "system_classification_and_specialized_evaluation"
    )

    assert systems.passed is False
    assert "SY03" in {check.check_id for check in systems.failed_checks}


def test_config_hash_is_canonical() -> None:
    config = _example()
    reversed_config = {key: config[key] for key in reversed(config)}

    assert audit_protocol(config).config_sha256 == audit_protocol(reversed_config).config_sha256


def test_markdown_contains_failures_and_execution_warning() -> None:
    config = _example()
    config["freshness"]["maximum_item_age_days"] = 800
    audit = audit_protocol(config)

    report = render_audit_markdown(audit)

    assert "FR01: Fresh item ceiling" in report
    assert "PILOT / NOT DESIGN READY" in report
    assert "necessary, not sufficient" in report


def test_example_is_valid_json_and_round_trips() -> None:
    config = _example()
    assert json.loads(json.dumps(config)) == config
    assert copy.deepcopy(config) == config


def test_load_protocol_rejects_structurally_incomplete_config(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text('{"study": {}}', encoding="utf-8")
    with pytest.raises(ValueError, match="Protocol schema validation failed"):
        load_protocol(path)
