from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config"
SCHEMA_NAMES = {
    "answer-v1.schema.json",
    "attempt-v1.schema.json",
    "evidence-manifest-v1.schema.json",
    "frozen-item-v1.schema.json",
    "global-observation-v1.schema.json",
    "global-protocol-v1.schema.json",
    "judgment-v1.schema.json",
    "schedule-cell-v1.schema.json",
    "scorecard-v1.schema.json",
    "system-card-v1.schema.json",
}
SHA = "a" * 64
NOW = "2026-08-08T00:00:00Z"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def validator(name: str) -> Draft202012Validator:
    return Draft202012Validator(
        load_json(CONFIG / name),
        format_checker=FormatChecker(),
    )


def valid_records() -> dict[str, dict]:
    return {
        "answer-v1.schema.json": {
            "schema_version": "1.0",
            "run_id": "run-1",
            "schedule_id": "schedule-1",
            "answer_id": "answer-1",
            "attempt_ids": ["attempt-1"],
            "status": "success",
            "content_sha256": SHA,
            "selected_attempt": 1,
            "finalized_at": NOW,
            "redaction_applied": False,
        },
        "attempt-v1.schema.json": {
            "schema_version": "1.0",
            "run_id": "run-1",
            "schedule_id": "schedule-1",
            "attempt_id": "attempt-1",
            "attempt_number": 1,
            "provider": "example-provider",
            "requested_model": "example-model",
            "actual_model": "example-model@2026-08-08",
            "started_at": NOW,
            "finished_at": "2026-08-08T00:00:01Z",
            "latency_ms": 1000,
            "status": "success",
            "will_retry": False,
            "input_tokens": 10,
            "output_tokens": 20,
            "cost_usd": 0.001,
            "request_parameters_sha256": SHA,
        },
        "evidence-manifest-v1.schema.json": {
            "schema_version": "1.0",
            "protocol_id": "KGBP-1.0",
            "run_id": "run-1",
            "created_at": NOW,
            "hash_algorithm": "sha256",
            "artifacts": [
                {
                    "path": "public/scorecard.json",
                    "media_type": "application/json",
                    "bytes": 123,
                    "sha256": SHA,
                    "classification": "public",
                }
            ],
            "signatures": [],
            "deviations": [],
            "privacy_review": {
                "completed": True,
                "reviewer_role": "release manager",
                "redaction_policy": "Exclude prompts, responses, and provider identifiers.",
            },
        },
        "frozen-item-v1.schema.json": {
            "schema_version": "1.0",
            "item_id": "item-1",
            "cluster_id": "cluster-1",
            "track": "reasoning",
            "language": "en",
            "locale": "en-US",
            "modality": "text",
            "difficulty": "moderate",
            "source": "private-holdout",
            "release_date": "2026-08-01",
            "content_sha256": SHA,
            "grader_id": "objective-grader-1",
            "production_weight": 1.0,
            "private_holdout": True,
            "canary": False,
        },
        "global-observation-v1.schema.json": {
            "schema_version": "1.0",
            "protocol_id": "KGBP-1.0",
            "run_id": "run-1",
            "schedule_id": "schedule-1",
            "system_id": "system-1",
            "item_id": "item-1",
            "cluster_id": "cluster-1",
            "repeat": 1,
            "track": "reasoning",
            "status": "success",
            "score": 1.0,
            "score_treatment": "successful-task-outcome",
            "language": "en",
            "locale": "en-US",
            "modality": "text",
            "difficulty": "moderate",
            "attempt_ids": ["attempt-1"],
            "answer_id": "answer-1",
            "judgment_id": "judgment-1",
            "deadline_ms": 30000,
            "budget_usd": 0.1,
            "output_cap_tokens": 512,
            "grader_id": "objective-grader-1",
            "grader_version": "1.0.0",
            "provenance": {
                "protocol_sha256": SHA,
                "item_sha256": SHA,
                "schedule_sha256": SHA,
                "system_card_sha256": SHA,
                "answer_sha256": SHA,
                "judgment_sha256": SHA,
            },
        },
        "judgment-v1.schema.json": {
            "schema_version": "1.0",
            "run_id": "run-1",
            "schedule_id": "schedule-1",
            "answer_id": "answer-1",
            "judgment_id": "judgment-1",
            "grader_id": "objective-grader-1",
            "grader_version": "1.0.0",
            "grader_type": "objective",
            "score": 1.0,
            "valid": True,
            "created_at": NOW,
            "prompt_or_rubric_sha256": SHA,
        },
        "schedule-cell-v1.schema.json": {
            "schema_version": "1.0",
            "schedule_id": "schedule-1",
            "protocol_id": "KGBP-1.0",
            "system_id": "system-1",
            "item_id": "item-1",
            "cluster_id": "cluster-1",
            "track": "reasoning",
            "repeat": 1,
            "day": 1,
            "region": "local",
            "block_position": 0,
            "within_item_position": 0,
            "language": "en",
            "locale": "en-US",
            "modality": "text",
            "difficulty": "moderate",
            "deadline_ms": 30000,
            "budget_usd": 0.1,
            "output_cap_tokens": 512,
            "seed": 7,
        },
        "scorecard-v1.schema.json": {
            "schema_version": "1.0",
            "protocol_id": "KGBP-1.0",
            "run_id": "run-1",
            "generated_at": NOW,
            "coverage": {
                "expected_observations": 1,
                "observed_observations": 1,
                "synthesized_missing_observations": 0,
                "complete_denominator_enforced": True,
            },
            "systems": [{"system_id": "system-1", "score": 1.0}],
            "comparisons": [],
            "claims": [],
            "artifact_sha256": SHA,
        },
        "system-card-v1.schema.json": {
            "schema_version": "1.0",
            "system_id": "system-1@immutable-snapshot",
            "display_name": "Example system",
            "provider": "Example provider",
            "owner": "Example owner",
            "system_type": "endpoint",
            "deployment_scope": "endpoint",
            "access_mode": "first-party-api",
            "version": "immutable-snapshot",
            "model_snapshot": "example-model@2026-08-08",
            "endpoint": "https://example.invalid/v1",
            "regions": ["test-region"],
            "input_modalities": ["text"],
            "output_modalities": ["text"],
            "declared_capabilities": ["reasoning"],
            "context_limit": 8192,
            "output_limit": 512,
            "elicitation": {"temperature": 0},
            "tools": [],
            "safeguards": ["provider-policy"],
            "pricing": {"input_usd_per_million_tokens": 1.0},
            "license": {"terms": "provider terms"},
            "captured_at": NOW,
        },
    }


def test_schema_set_is_complete_unique_and_valid() -> None:
    paths = sorted(CONFIG.glob("*-v1.schema.json"))
    assert {path.name for path in paths} == SCHEMA_NAMES
    identifiers: list[str] = []
    for path in paths:
        schema = load_json(path)
        Draft202012Validator.check_schema(schema)
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["$id"].startswith("https://")
        identifiers.append(schema["$id"])
    assert len(identifiers) == len(set(identifiers))


def test_reference_protocol_validates_against_published_schema() -> None:
    validator("global-protocol-v1.schema.json").validate(
        load_json(CONFIG / "global-protocol-v1.example.json")
    )


@pytest.mark.parametrize("schema_name", sorted(valid_records()))
def test_representative_public_record_validates(schema_name: str) -> None:
    validator(schema_name).validate(valid_records()[schema_name])


def test_provider_failure_cannot_receive_nonzero_observation_score() -> None:
    record = valid_records()["global-observation-v1.schema.json"]
    record.update(
        status="provider_failure",
        score=1.0,
        score_treatment="successful-task-outcome",
        answer_id=None,
        judgment_id=None,
    )
    with pytest.raises(ValidationError):
        validator("global-observation-v1.schema.json").validate(record)


def test_toy_schedule_validates_as_frozen_schedule_cells() -> None:
    schedule_validator = validator("schedule-cell-v1.schema.json")
    lines = (ROOT / "examples/toy-schedule.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 6
    for line in lines:
        schedule_validator.validate(json.loads(line))
