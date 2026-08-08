"""Export a separate, privacy-reviewed frontier preview companion bundle.

This command consumes completed matrix artifacts only. It never calls Kendr or
another model provider. The execution matrix must contain every companion
endpoint marked present by the frozen coverage audit, and it must contain no
GA candidate or baseline endpoint. Unavailable companion profile entries are
published as explicit N/A rows.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

try:
    from scripts import audit_kendr_frontier_catalog as frontier_auditor
    from scripts import export_frontier_results as frontier
except ImportError:  # Direct execution sets scripts/ rather than the repo on sys.path.
    import audit_kendr_frontier_catalog as frontier_auditor  # type: ignore[no-redef]
    import export_frontier_results as frontier  # type: ignore[no-redef]


PROJECT_TITLE = frontier.PROJECT_TITLE
PROTOCOL_PROFILE = frontier.PROTOCOL_PROFILE
CompanionPublicationError = frontier.FrontierPublicationError

PANEL_FIELDS = frozenset(
    {
        "key",
        "provider",
        "model",
        "label",
        "access",
        "license",
        "license_source",
    }
)

PUBLIC_CSV_FIELDS = (
    "display_order",
    "cohort",
    "claim_class",
    "role",
    "benchmark_status",
    "catalog_status",
    "endpoint_id",
    "vendor_model_id",
    "endpoint_label",
    "configuration_label",
    "configuration_access",
    "license",
    "license_source",
    "questions_scored",
    "operational_goodput",
    "operational_goodput_ci95_low",
    "operational_goodput_ci95_high",
    "quality_score",
    "quality_ci95_low",
    "quality_ci95_high",
    "conditional_quality_score",
    "availability",
    "successful_answers",
    "failed_answers",
    "missing_answers",
    "latency_p50_ms",
    "latency_p95_ms",
    "cost_usd",
    "cost_is_lower_bound",
    "data_analysis_score",
    "instruction_following_score",
    "language_score",
    "math_score",
    "reasoning_score",
    "n_a_reason_code",
    "n_a_reason",
)

SOURCE_HASH_FIELDS = frozenset(
    {
        "coverage_audit_sha256",
        "execution_panel_sha256",
        "matrix_catalog_file_sha256",
        "matrix_leaderboard_sha256",
        "matrix_manifest_sha256",
        "profile_sha256",
    }
)

FORBIDDEN_COMPANION_PUBLIC_KEYS = frontier.FORBIDDEN_PUBLIC_KEYS | {
    "error",
    "error_message",
    "errors",
    "failure_message",
    "provider_error_distribution",
    "provider_error_message",
}


def _validated_companion_panel(value: Any) -> list[dict[str, Any]]:
    panel = frontier._validated_execution_panel(value)
    if len(panel) != 1:
        raise CompanionPublicationError(
            "The dated preview companion campaign requires exactly one execution endpoint"
        )
    validated: list[dict[str, Any]] = []
    for row in panel:
        fields = set(map(str, row))
        if fields != PANEL_FIELDS:
            missing = sorted(PANEL_FIELDS - fields)
            extra = sorted(fields - PANEL_FIELDS)
            raise CompanionPublicationError(
                "Companion panel rows must contain the exact public field set; "
                f"missing={missing}, extra={extra}"
            )
        if row.get("provider") != "kendr":
            raise CompanionPublicationError(
                "Every companion execution endpoint must use provider 'kendr'"
            )
        for field in PANEL_FIELDS:
            if not isinstance(row.get(field), str) or not str(row[field]).strip():
                raise CompanionPublicationError(
                    f"Companion panel field {field!r} must be a non-empty string"
                )
        if not str(row["license_source"]).startswith("https://"):
            raise CompanionPublicationError(
                "Companion panel license_source must be a public HTTPS URL"
            )
        validated.append(dict(row))
    return validated


def _validated_source_hashes(value: Mapping[str, str] | None) -> dict[str, str]:
    hashes = dict(value or {})
    if set(hashes) != SOURCE_HASH_FIELDS:
        missing = sorted(SOURCE_HASH_FIELDS - set(hashes))
        extra = sorted(set(hashes) - SOURCE_HASH_FIELDS)
        raise CompanionPublicationError(
            "Companion publication requires the exact source-hash set; "
            f"missing={missing}, extra={extra}"
        )
    for name, digest in hashes.items():
        if not re.fullmatch(r"[0-9a-f]{64}", str(digest)):
            raise CompanionPublicationError(
                f"Invalid lowercase SHA-256 digest for {name!r}"
            )
    return {name: str(hashes[name]) for name in sorted(hashes)}


def _catalog_by_id(catalog: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for row in catalog:
        model_id = str(row.get("id") or "").strip()
        folded = model_id.casefold()
        if not model_id or folded in result:
            raise CompanionPublicationError(
                "Matrix Kendr catalog ids must be present and unique"
            )
        result[folded] = row
    return result


def _bind_profile_audit_catalog(
    *,
    profile: Mapping[str, Any],
    coverage_audit: Mapping[str, Any],
    catalog: Sequence[Mapping[str, Any]],
    source_hashes: Mapping[str, str],
) -> tuple[
    str,
    list[dict[str, Any]],
    dict[str, Mapping[str, Any]],
    Mapping[str, Any],
]:
    ga_id, companion_id, profile_rows = frontier._validated_profile(profile)
    del ga_id
    companion_rows = [
        dict(row) for row in profile_rows if row["cohort"] == companion_id
    ]
    if not companion_rows:
        raise CompanionPublicationError("Profile companion cohort must not be empty")
    if any(row["role"] != "candidate" for row in companion_rows):
        raise CompanionPublicationError(
            "The companion cohort may contain candidates only"
        )

    if coverage_audit.get("profile_id") != profile.get("profile_id"):
        raise CompanionPublicationError("Coverage audit and profile ids differ")
    if coverage_audit.get("snapshot_date") != profile.get("snapshot_date"):
        raise CompanionPublicationError(
            "Coverage audit and profile snapshot dates differ"
        )
    audit_profile_hash = str(coverage_audit.get("profile_sha256") or "")
    if audit_profile_hash != source_hashes["profile_sha256"]:
        raise CompanionPublicationError(
            "Coverage audit does not bind to the exact frontier profile bytes"
        )

    catalog_rows = frontier._require_object_list(
        list(catalog), "matrix Kendr catalog"
    )
    if not catalog_rows:
        raise CompanionPublicationError("Matrix Kendr catalog must not be empty")
    catalog_hash = str(coverage_audit.get("catalog_sha256") or "")
    if not re.fullmatch(r"[0-9a-f]{64}", catalog_hash):
        raise CompanionPublicationError(
            "Coverage audit lacks a lowercase SHA-256 catalog hash"
        )
    if frontier.catalog_sha256(catalog_rows) != catalog_hash:
        raise CompanionPublicationError(
            "Matrix Kendr catalog does not match coverage_audit.catalog_sha256"
        )
    if int(coverage_audit.get("catalog_entries") or -1) != len(catalog_rows):
        raise CompanionPublicationError(
            "Matrix Kendr catalog size does not match the coverage audit"
        )

    supplied_audit_by_key = frontier._audit_entries(
        coverage_audit, profile_rows
    )
    try:
        recomputed_audit, _ = frontier_auditor.audit_frontier_profile(
            catalog_rows, profile
        )
    except frontier_auditor.FrontierProfileError as exc:
        raise CompanionPublicationError(
            f"Unable to recompute frontier catalog eligibility: {exc}"
        ) from exc
    recomputed_audit_by_key = frontier._audit_entries(
        recomputed_audit, profile_rows
    )
    for key, recomputed in recomputed_audit_by_key.items():
        supplied = supplied_audit_by_key[key]
        if supplied.get("status") != recomputed.get("status"):
            raise CompanionPublicationError(
                f"Coverage audit eligibility drift for {key!r}: supplied "
                f"{supplied.get('status')!r}, recomputed "
                f"{recomputed.get('status')!r}"
            )
        if recomputed.get("status") == "present":
            for field in ("observed_display_name", "owned_by", "mode"):
                if supplied.get(field) != recomputed.get(field):
                    raise CompanionPublicationError(
                        f"Coverage audit identity drift for {key!r} field "
                        f"{field!r}"
                    )

    return (
        companion_id,
        companion_rows,
        recomputed_audit_by_key,
        recomputed_audit,
    )


def _assert_companion_execution_scope(
    *,
    panel: Sequence[Mapping[str, Any]],
    profile_rows: Sequence[Mapping[str, Any]],
    companion_id: str,
    audit_by_key: Mapping[str, Mapping[str, Any]],
    catalog: Sequence[Mapping[str, Any]],
) -> None:
    profile_by_id = {
        str(row["catalog_id"]): row
        for row in profile_rows
        if row.get("catalog_id") is not None
    }
    ga_or_baseline_ids = {
        str(row["catalog_id"])
        for row in profile_rows
        if row.get("catalog_id") is not None
        and (row["cohort"] != companion_id or row["role"] == "baseline")
    }
    execution_ids = {str(row["model"]) for row in panel}
    forbidden = sorted(execution_ids & ga_or_baseline_ids)
    if forbidden:
        raise CompanionPublicationError(
            "GA and baseline endpoints are forbidden in a companion matrix: "
            + ", ".join(forbidden)
        )
    unknown = sorted(execution_ids - set(profile_by_id))
    if unknown:
        raise CompanionPublicationError(
            "Companion panel contains endpoints outside the frontier profile: "
            + ", ".join(unknown)
        )
    wrong_cohort = sorted(
        model_id
        for model_id in execution_ids
        if profile_by_id[model_id]["cohort"] != companion_id
    )
    if wrong_cohort:
        raise CompanionPublicationError(
            "Companion panel contains endpoints outside the companion cohort: "
            + ", ".join(wrong_cohort)
        )

    eligible_ids = {
        str(row["catalog_id"])
        for row in profile_rows
        if row["cohort"] == companion_id
        and row.get("catalog_id") is not None
        and audit_by_key[str(row["key"])].get("status") == "present"
    }
    if execution_ids != eligible_ids:
        missing = sorted(eligible_ids - execution_ids)
        extra = sorted(execution_ids - eligible_ids)
        raise CompanionPublicationError(
            "Companion panel must schedule every and only audit-present companion "
            f"endpoint; missing={missing}, extra={extra}"
        )

    catalog_index = _catalog_by_id(catalog)
    for model_id in execution_ids:
        catalog_row = catalog_index.get(model_id.casefold())
        if catalog_row is None:
            raise CompanionPublicationError(
                f"Scheduled companion endpoint {model_id} is absent from the matrix catalog"
            )
        if catalog_row.get("available") is not True:
            raise CompanionPublicationError(
                f"Scheduled companion endpoint {model_id} is not catalog-available"
            )
        capabilities = catalog_row.get("capabilities") or []
        if not isinstance(capabilities, list) or "text" not in capabilities:
            raise CompanionPublicationError(
                f"Scheduled companion endpoint {model_id} is not text-capable"
            )
        exclusion_reason = frontier_auditor.catalog_exclusion_reason(catalog_row)
        if exclusion_reason is not None:
            raise CompanionPublicationError(
                f"Scheduled companion endpoint {model_id} is catalog-ineligible: "
                f"{exclusion_reason}"
            )
        normalized_label = frontier_auditor.normalize_display_label(
            catalog_row.get("display_name") or model_id
        )
        same_label = [
            candidate
            for candidate in catalog
            if frontier_auditor.catalog_exclusion_reason(candidate) is None
            and frontier_auditor.normalize_display_label(
                candidate.get("display_name") or candidate.get("id")
            )
            == normalized_label
        ]
        if not normalized_label or len(same_label) != 1:
            raise CompanionPublicationError(
                f"Scheduled companion endpoint {model_id} does not have a unique "
                "eligible normalized display identity"
            )


def _validate_exact_matrix(
    *,
    manifest: Mapping[str, Any],
    leaderboard: Mapping[str, Any],
    panel: Sequence[Mapping[str, Any]],
) -> tuple[list[Mapping[str, Any]], int]:
    declared_rows = frontier._require_object_list(
        leaderboard.get("results"), "leaderboard.results"
    )
    if len(declared_rows) != 1:
        raise CompanionPublicationError(
            "The dated preview companion campaign requires exactly one scored endpoint"
        )
    _single_endpoint_inference(
        leaderboard=leaderboard,
        rows=declared_rows,
    )
    rows, planned = frontier._validate_matrix(
        manifest=manifest,
        leaderboard=leaderboard,
        panel=panel,
    )
    manifest_models = frontier._require_object_list(
        manifest.get("models"), "manifest.models"
    )
    if [dict(row) for row in manifest_models] != [dict(row) for row in panel]:
        raise CompanionPublicationError(
            "Manifest model definitions do not exactly match the frozen companion panel"
        )

    panel_by_id = {str(row["model"]): row for row in panel}
    for source in rows:
        model_id = str(source.get("requested_model") or "")
        panel_row = panel_by_id[model_id]
        if source.get("provider") != "kendr":
            raise CompanionPublicationError(
                f"Companion result {model_id} does not identify provider 'kendr'"
            )
        if source.get("panel_key") != panel_row["key"]:
            raise CompanionPublicationError(
                f"Companion result {model_id} has the wrong frozen panel key"
            )
        if source.get("model") != panel_row["label"]:
            raise CompanionPublicationError(
                f"Companion result {model_id} has the wrong frozen label"
            )
        counts = []
        for field in ("successful_answers", "failed_answers", "missing_answers"):
            try:
                count = int(source.get(field))
            except (TypeError, ValueError) as exc:
                raise CompanionPublicationError(
                    f"Companion result {model_id} field {field!r} must be an integer"
                ) from exc
            if count < 0:
                raise CompanionPublicationError(
                    f"Companion result {model_id} has a negative answer count"
                )
            counts.append(count)
        if sum(counts) != planned:
            raise CompanionPublicationError(
                f"Companion result {model_id} answer counts do not sum to {planned}"
            )
    return rows, planned


def _single_endpoint_inference(
    *, leaderboard: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    if len(rows) != 1:
        raise CompanionPublicationError(
            "The dated preview companion campaign requires exactly one scored endpoint"
        )
    tests = frontier._require_object_list(
        leaderboard.get("pairwise_tests"), "leaderboard.pairwise_tests"
    )
    if tests:
        raise CompanionPublicationError(
            "The single-endpoint companion campaign must have no pairwise tests"
        )
    family = frontier._require_mapping(
        leaderboard.get("pairwise_test_family"),
        "leaderboard.pairwise_test_family",
    )
    comparisons = family.get("comparisons")
    if (
        isinstance(comparisons, bool)
        or not isinstance(comparisons, int)
        or comparisons != 0
    ):
        raise CompanionPublicationError(
            "The single-endpoint companion pairwise family must declare comparisons=0"
        )
    return {
        "family_scope": (
            "No pairwise family: this dated preview companion campaign has "
            "exactly one scored endpoint and excludes every GA and baseline endpoint."
        ),
        "comparisons": 0,
        "interpretation": (
            "No ranking or pairwise inference is defined for a one-endpoint campaign."
        ),
        "tests": [],
    }


def _public_metrics(source: Mapping[str, Any]) -> dict[str, Any]:
    metrics = frontier._scored_metrics(source)
    metrics.pop("provider_error_distribution", None)
    metrics.pop("tier", None)
    return metrics


def _empty_public_metrics() -> dict[str, Any]:
    metrics = frontier._empty_metrics()
    metrics.pop("provider_error_distribution", None)
    metrics.pop("tier", None)
    metrics["n_a_reason_code"] = None
    metrics["n_a_reason"] = None
    return metrics


def _assert_companion_public_safe(bundle: Mapping[str, Any]) -> None:
    exposed = sorted(
        {key.casefold() for key in frontier._walk_keys(bundle)}
        & FORBIDDEN_COMPANION_PUBLIC_KEYS
    )
    if exposed:
        raise CompanionPublicationError(
            "Companion public bundle exposes forbidden fields: "
            + ", ".join(exposed)
        )
    frontier._assert_public_safe(bundle)


def build_publication(
    *,
    manifest: Mapping[str, Any],
    leaderboard: Mapping[str, Any],
    profile: Mapping[str, Any],
    execution_panel: Sequence[Mapping[str, Any]],
    coverage_audit: Mapping[str, Any],
    catalog: Sequence[Mapping[str, Any]],
    source_hashes: Mapping[str, str],
) -> dict[str, Any]:
    """Build a companion-only public aggregate from completed local artifacts."""

    hashes = _validated_source_hashes(source_hashes)
    panel = _validated_companion_panel(list(execution_panel))
    ga_id, companion_id, all_profile_rows = frontier._validated_profile(profile)
    del ga_id
    (
        bound_companion_id,
        companion_rows,
        audit_by_key,
        recomputed_audit,
    ) = _bind_profile_audit_catalog(
        profile=profile,
        coverage_audit=coverage_audit,
        catalog=catalog,
        source_hashes=hashes,
    )
    if bound_companion_id != companion_id:
        raise CompanionPublicationError("Profile companion cohort identity drifted")
    _assert_companion_execution_scope(
        panel=panel,
        profile_rows=all_profile_rows,
        companion_id=companion_id,
        audit_by_key=audit_by_key,
        catalog=catalog,
    )
    matrix_rows, planned = _validate_exact_matrix(
        manifest=manifest,
        leaderboard=leaderboard,
        panel=panel,
    )
    execution_software = frontier._execution_software(manifest)
    inference = _single_endpoint_inference(
        leaderboard=leaderboard,
        rows=matrix_rows,
    )

    panel_by_id = {str(row["model"]): row for row in panel}
    source_by_id = {
        str(row["requested_model"]): row for row in matrix_rows
    }
    public_rows: list[dict[str, Any]] = []
    for profile_order, profile_row in enumerate(companion_rows, 1):
        model_id = (
            str(profile_row["catalog_id"])
            if profile_row.get("catalog_id") is not None
            else None
        )
        source = source_by_id.get(model_id) if model_id is not None else None
        panel_row = panel_by_id.get(model_id) if model_id is not None else None
        audit_row = audit_by_key[str(profile_row["key"])]
        row: dict[str, Any] = {
            "display_order": profile_order,
            "cohort": companion_id,
            "claim_class": profile_row["claim_class"],
            "role": "candidate",
            "benchmark_status": "scored" if source is not None else "not_measured",
            "catalog_status": audit_row.get("status"),
            "endpoint_id": model_id,
            "vendor_model_id": profile_row.get("vendor_model_id"),
            "endpoint_label": profile_row["label"],
            "configuration_label": panel_row.get("label") if panel_row else None,
            "configuration_access": panel_row.get("access") if panel_row else None,
            "license": panel_row.get("license") if panel_row else None,
            "license_source": panel_row.get("license_source") if panel_row else None,
        }
        if source is not None:
            row.update(_public_metrics(source))
        else:
            row.update(_empty_public_metrics())
            status = str(audit_row.get("status") or "unknown")
            reason = str(audit_row.get("reason") or "").strip()
            if profile_row.get("coverage_only"):
                coverage_status = str(
                    audit_row.get("coverage_status") or "unknown"
                )
                row["n_a_reason_code"] = f"coverage_only_{coverage_status}"
            else:
                row["n_a_reason_code"] = status
            row["n_a_reason"] = (
                reason
                or str(profile_row.get("n_a_reason") or "").strip()
                or "Endpoint did not pass the frozen companion eligibility audit."
            )
        public_rows.append(row)

    public_rows.sort(
        key=lambda row: (
            0 if row["benchmark_status"] == "scored" else 1,
            row["display_order"],
        )
    )
    for display_order, row in enumerate(public_rows, 1):
        row["display_order"] = display_order

    sampling = manifest.get("sampling") or {}
    if not isinstance(sampling, Mapping):
        raise CompanionPublicationError("manifest.sampling must be an object")
    bundle: dict[str, Any] = {
        "schema_version": "1.0",
        "project": PROJECT_TITLE,
        "protocol_profile": PROTOCOL_PROFILE,
        "campaign_type": "current-frontier-preview-companion",
        "scientific_status": (
            "Descriptive endpoint-as-served preview companion; separate from and "
            "not comparable as a rank against the GA leaderboard."
        ),
        "matrix_id": leaderboard.get("matrix_id"),
        "generated_at": leaderboard.get("created_at"),
        "profile_id": profile.get("profile_id"),
        "snapshot_date": profile.get("snapshot_date"),
        "cohort": {
            "id": companion_id,
            "claim_class": "preview-or-limited-access",
        },
        "livebench_release": leaderboard.get("livebench_release"),
        "sample": {
            "mode": sampling.get("mode"),
            "seed": sampling.get("seed"),
            "content_hash": sampling.get("content_hash"),
            "content_hash_algorithm": sampling.get("content_hash_algorithm"),
            "questions": planned,
            "tasks": leaderboard.get("tasks") or manifest.get("tasks") or [],
            "questions_per_task": leaderboard.get("questions_per_task")
            or manifest.get("questions_per_task"),
            "selected_date_distribution": sampling.get(
                "selected_date_distribution", {}
            ),
            "generations_per_endpoint_question": 1,
        },
        "execution_configuration": {
            "requested_max_output_tokens": leaderboard.get(
                "requested_max_output_tokens"
            )
            or manifest.get("max_tokens"),
            "deadline_ms": manifest.get("deadline_ms"),
            "max_cost_usd_per_answer": manifest.get(
                "max_cost_usd_per_answer"
            ),
            "parallel_requests": leaderboard.get("parallel_requests")
            or manifest.get("parallel_requests"),
            "parallel_grading": manifest.get("parallel_grading"),
            "requested_reasoning_effort": manifest.get("reasoning_effort"),
        },
        "execution_software": execution_software,
        "scope": {
            "companion_profile_entries": len(public_rows),
            "scored_companion_entries": len(matrix_rows),
            "not_measured_companion_entries": sum(
                row["benchmark_status"] == "not_measured" for row in public_rows
            ),
            "ga_or_baseline_entries": 0,
        },
        "ranking": {
            "status": "single-scored-endpoint-descriptive-no-rank",
            "scope": (
                "No rank is assigned because this dated campaign permits exactly "
                "one scored preview-companion endpoint. GA and baseline endpoints "
                "are excluded."
            ),
        },
        "n_a_policy": (
            "Audit-ineligible companion entries use null metrics and render as N/A. "
            "A scheduled endpoint with complete zero-goodput evidence remains a "
            "scored zero."
        ),
        "pairwise_inference": inference,
        "claim_readiness": {
            "companion_claim_ready": bool(
                recomputed_audit.get("companion_claim_ready")
            ),
            "claim_separation": recomputed_audit.get("claim_separation"),
        },
        "rows": public_rows,
        "provenance": {
            "catalog_sha256": str(coverage_audit.get("catalog_sha256")),
            **hashes,
        },
        "privacy_review": {
            "raw_prompts_included": False,
            "raw_responses_included": False,
            "provider_request_ids_included": False,
            "provider_error_messages_included": False,
            "local_paths_included": False,
        },
    }
    _assert_companion_public_safe(bundle)
    try:
        json.dumps(bundle, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise CompanionPublicationError(
            "Companion public bundle is not strict finite JSON"
        ) from exc
    return bundle


def _markdown_table(
    headers: Sequence[str], rows: Iterable[Sequence[Any]]
) -> str:
    return frontier._markdown_table(headers, list(rows))


def render_markdown(bundle: Mapping[str, Any]) -> str:
    rows = list(bundle["rows"])
    scored = [row for row in rows if row["benchmark_status"] == "scored"]
    not_measured = [
        row for row in rows if row["benchmark_status"] == "not_measured"
    ]
    software = bundle["execution_software"]
    sample = bundle["sample"]
    lines = [
        f"# Kendr frontier preview companion — {bundle.get('snapshot_date')}",
        "",
        f"**Matrix ID:** `{bundle.get('matrix_id')}`",
        "",
        "This is a separate preview/limited-access companion publication. It is "
        "not pooled into, and must not be read as a rank against, the GA leaderboard.",
        "",
        "## Scope",
        "",
        _markdown_table(
            ["Field", "Value"],
            [
                ["Companion profile entries", bundle["scope"]["companion_profile_entries"]],
                ["Scored companion entries", bundle["scope"]["scored_companion_entries"]],
                ["N/A companion entries", bundle["scope"]["not_measured_companion_entries"]],
                ["Questions", sample["questions"]],
                ["Tasks", len(sample["tasks"])],
                ["Generations per endpoint-question", sample["generations_per_endpoint_question"]],
                ["Ranking status", bundle["ranking"]["status"]],
            ],
        ),
        "",
        "## Companion result",
        "",
        _markdown_table(
            [
                "Ranking treatment",
                "Model",
                "Kendr endpoint",
                "Operational goodput",
                "95% interval",
                "Conditional quality",
                "Availability",
                "Successful / planned",
            ],
            [
                [
                    "Not assigned (single row)",
                    row["endpoint_label"],
                    f"`{row['endpoint_id']}`",
                    frontier._percent(row["operational_goodput"], 2),
                    (
                        f"{frontier._percent(row['operational_goodput_ci95_low'], 2)} to "
                        f"{frontier._percent(row['operational_goodput_ci95_high'], 2)}"
                    ),
                    frontier._percent(row["conditional_quality_score"], 2),
                    frontier._percent(row["availability"], 2),
                    f"{row['successful_answers']} / {row['questions_scored']}",
                ]
                for row in scored
            ],
        ),
        "",
        "Exactly one companion endpoint was scored, so no ordinal rank is "
        "assigned. The JSON and CSV retain the full-precision aggregate metrics.",
        "",
        "## Companion entries reported as N/A",
        "",
        _markdown_table(
            ["Model", "Configured endpoint", "Audit status", "Reason"],
            [
                [
                    row["endpoint_label"],
                    f"`{row['endpoint_id']}`" if row["endpoint_id"] else "N/A",
                    row["catalog_status"],
                    row["n_a_reason"],
                ]
                for row in not_measured
            ],
        ),
        "",
        "N/A means no inference was scheduled for that profile entry; it is not a zero score.",
        "",
        "## Companion-only paired inference",
        "",
    ]
    lines.extend(
        [
            "No pairwise test exists because this dated campaign permits exactly "
            "one scored companion endpoint. The comparison family contains zero "
            "GA or baseline endpoints.",
            "",
        ]
    )
    lines.extend(
        [
            "## Provenance and limitations",
            "",
            f"Execution software: `{software['package']} {software['version']}` at source commit `{software['source_commit']}`.",
            "",
            (
                "The execution worktree contained uncommitted changes. The commit "
                "identifies the base revision but cannot reconstruct those changes."
                if software["source_worktree_dirty"]
                else "The execution worktree was clean at the recorded source commit."
            ),
            "",
            "This small, one-generation endpoint-as-served snapshot does not establish "
            "a global model rank, production-model superiority, or stable preview behavior.",
            "",
            "## Privacy boundary",
            "",
            "The public bundle contains aggregate metrics, exact public endpoint and "
            "configuration identity, source hashes, and N/A reasons. It excludes raw "
            "prompts, raw responses, provider request identifiers, provider error "
            "messages, credentials, and machine-local paths. `SHA256SUMS` detects byte "
            "drift but is not a digital signature.",
            "",
        ]
    )
    return "\n".join(lines)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_lf(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def write_publication(
    *,
    bundle: Mapping[str, Any],
    output_dir: Path,
    stem: str,
) -> list[Path]:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", stem):
        raise CompanionPublicationError("Output stem contains unsafe characters")
    expected_names = {
        f"{stem}.json",
        f"{stem}.csv",
        f"{stem}.md",
        "SHA256SUMS",
    }
    if output_dir.exists():
        extras = sorted(
            path.name for path in output_dir.iterdir() if path.name not in expected_names
        )
        if extras:
            raise CompanionPublicationError(
                "Companion output directory must be dedicated; unexpected entries: "
                + ", ".join(extras)
            )
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{stem}.json"
    csv_path = output_dir / f"{stem}.csv"
    markdown_path = output_dir / f"{stem}.md"
    checksum_path = output_dir / "SHA256SUMS"

    _write_lf(
        json_path,
        json.dumps(bundle, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
    )
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=PUBLIC_CSV_FIELDS,
            extrasaction="raise",
            lineterminator="\n",
        )
        writer.writeheader()
        for source in bundle["rows"]:
            row = dict(source)
            for field in PUBLIC_CSV_FIELDS:
                if row.get(field) is None:
                    row[field] = "N/A"
            writer.writerow(row)
    _write_lf(markdown_path, render_markdown(bundle))

    artifacts = sorted((csv_path, json_path, markdown_path), key=lambda path: path.name)
    _write_lf(
        checksum_path,
        "\n".join(f"{_sha256(path)}  {path.name}" for path in artifacts) + "\n",
    )
    return [json_path, csv_path, markdown_path, checksum_path]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix-root", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--execution-panel", type=Path, required=True)
    parser.add_argument("--coverage-audit", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Dedicated directory for the companion JSON/CSV/Markdown bundle",
    )
    parser.add_argument(
        "--stem", default="kendr-frontier-preview-companion-2026-08-08"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    matrix_root = args.matrix_root.resolve()
    manifest_path = matrix_root / "manifest.json"
    leaderboard_path = matrix_root / "leaderboard.json"
    catalog_path = matrix_root / "kendr_model_catalog.json"
    for path in (manifest_path, leaderboard_path, catalog_path):
        if not path.is_file():
            raise CompanionPublicationError(
                f"Required companion matrix artifact not found: {path}"
            )

    manifest = frontier._require_mapping(
        frontier._read_json(manifest_path), "matrix manifest"
    )
    leaderboard = frontier._require_mapping(
        frontier._read_json(leaderboard_path), "matrix leaderboard"
    )
    profile = frontier._require_mapping(
        frontier._read_json(args.profile), "frontier profile"
    )
    panel = _validated_companion_panel(frontier._read_json(args.execution_panel))
    audit = frontier._require_mapping(
        frontier._read_json(args.coverage_audit), "frontier coverage audit"
    )
    catalog = frontier._require_object_list(
        frontier._read_json(catalog_path), "matrix Kendr catalog"
    )
    bundle = build_publication(
        manifest=manifest,
        leaderboard=leaderboard,
        profile=profile,
        execution_panel=panel,
        coverage_audit=audit,
        catalog=catalog,
        source_hashes={
            "profile_sha256": _sha256(args.profile),
            "execution_panel_sha256": _sha256(args.execution_panel),
            "matrix_manifest_sha256": _sha256(manifest_path),
            "matrix_leaderboard_sha256": _sha256(leaderboard_path),
            "matrix_catalog_file_sha256": _sha256(catalog_path),
            "coverage_audit_sha256": _sha256(args.coverage_audit),
        },
    )
    for path in write_publication(
        bundle=bundle,
        output_dir=args.output,
        stem=args.stem,
    ):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
