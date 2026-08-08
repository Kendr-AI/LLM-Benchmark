"""Export a privacy-reviewed current-frontier callable-subset publication.

This exporter is intentionally separate from ``export_public_results.py``.
That script belongs to the frozen 2026-08-07 catalog pilot and carries its
historical execution metadata and checksum layout.

The frontier exporter consumes only completed local matrix artifacts. It does
not make network or model calls. Its output is an allowlisted aggregate JSON,
a flat CSV, a Markdown handout, and a bundle-local SHA256SUMS file.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from itertools import combinations
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from kendr_bench.catalog_identity import catalog_sha256


PROJECT_TITLE = "LLM Benchmark Protocol"
PROTOCOL_PROFILE = "KGBP-1.0"
GPT_5_5_BASELINE_ID = "kc-openai-gpt-5-5"
COVERAGE_ONLY_STATUSES = frozenset({"staged", "missing", "hold"})

PUBLIC_CSV_FIELDS = (
    "display_order",
    "cohort",
    "claim_class",
    "role",
    "benchmark_status",
    "catalog_status",
    "rank",
    "execution_rank",
    "endpoint_id",
    "vendor_model_id",
    "endpoint_label",
    "configuration_label",
    "tier",
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
    "provider_error_distribution",
    "n_a_reason_code",
    "n_a_reason",
)

FORBIDDEN_PUBLIC_KEYS = {
    "answer",
    "api_key",
    "authorization",
    "catalog_source",
    "headers",
    "panel_file",
    "pricing_catalog",
    "profile_source",
    "prompt",
    "provider_request_id",
    "raw_request",
    "raw_response",
    "response",
    "run_dir",
}

WINDOWS_ABSOLUTE_PATH = re.compile(r"(?:^|\s)[A-Za-z]:[\\/]")
UNC_PATH = re.compile(r"(?:^|\s)\\\\[^\\\s]+\\")
SAFE_ERROR_CLASS = re.compile(r"[A-Za-z0-9_.:-]{1,80}")


class FrontierPublicationError(RuntimeError):
    """Raised when the source bundle is not safe or publication-complete."""


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FrontierPublicationError(f"Unable to read JSON {path}: {exc}") from exc


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise FrontierPublicationError(f"{label} must be a JSON object")
    return value


def _require_object_list(value: Any, label: str) -> list[Mapping[str, Any]]:
    if not isinstance(value, list) or any(not isinstance(item, Mapping) for item in value):
        raise FrontierPublicationError(f"{label} must be an array of objects")
    return list(value)


def _walk_keys(value: Any) -> Iterable[str]:
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield str(key)
            yield from _walk_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_keys(child)


def _walk_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for child in value.values():
            yield from _walk_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_strings(child)


def _assert_public_safe(bundle: Mapping[str, Any]) -> None:
    exposed = sorted(
        {key.casefold() for key in _walk_keys(bundle)} & FORBIDDEN_PUBLIC_KEYS
    )
    if exposed:
        raise FrontierPublicationError(
            "Public bundle exposes forbidden fields: " + ", ".join(exposed)
        )
    for value in _walk_strings(bundle):
        if (
            WINDOWS_ABSOLUTE_PATH.search(value)
            or UNC_PATH.search(value)
            or value.casefold().startswith("file://")
        ):
            raise FrontierPublicationError(
                "Public bundle contains a machine-local absolute path"
            )


def _validated_profile(
    profile: Mapping[str, Any],
) -> tuple[str, str, list[dict[str, Any]]]:
    profile_id = str(profile.get("profile_id") or "").strip()
    ga_cohort_id = str(profile.get("ga_cohort_id") or "").strip()
    companion_cohort_id = str(profile.get("companion_cohort_id") or "").strip()
    if not profile_id or not ga_cohort_id or not companion_cohort_id:
        raise FrontierPublicationError(
            "Profile must declare profile_id, ga_cohort_id, and companion_cohort_id"
        )
    if ga_cohort_id == companion_cohort_id:
        raise FrontierPublicationError("GA and companion cohort ids must differ")

    cohorts = _require_object_list(profile.get("cohorts"), "profile.cohorts")
    rows: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    seen_ids: set[str] = set()
    seen_vendor_model_ids: set[str] = set()
    seen_cohorts: set[str] = set()
    for cohort in cohorts:
        cohort_id = str(cohort.get("id") or "").strip()
        claim_class = str(cohort.get("claim_class") or "").strip()
        if not cohort_id or cohort_id in seen_cohorts:
            raise FrontierPublicationError("Profile cohort ids must be present and unique")
        seen_cohorts.add(cohort_id)
        entries = _require_object_list(
            cohort.get("entries"), f"profile cohort {cohort_id!r} entries"
        )
        for entry in entries:
            key = str(entry.get("key") or "").strip()
            label = str(entry.get("label") or "").strip()
            catalog_id = str(entry.get("catalog_id") or "").strip()
            vendor_model_id = str(
                entry.get("vendor_model_id") or ""
            ).strip()
            coverage_only = entry.get("coverage_only") is True
            coverage_status = str(
                entry.get("coverage_status") or ""
            ).strip()
            n_a_reason = str(entry.get("n_a_reason") or "").strip()
            role = str(entry.get("role") or "candidate").strip()
            if not key or not label:
                raise FrontierPublicationError(
                    f"Profile cohort {cohort_id!r} has an entry without key or label"
                )
            if key in seen_keys:
                raise FrontierPublicationError(
                    "Profile entry keys must be unique"
                )
            if role not in {"candidate", "baseline"}:
                raise FrontierPublicationError(f"Unsupported profile role {role!r}")
            if coverage_only:
                if catalog_id:
                    raise FrontierPublicationError(
                        "Coverage-only profile entries cannot declare a Kendr catalog id"
                    )
                if role != "candidate":
                    raise FrontierPublicationError(
                        "Coverage-only profile entries must be candidates"
                    )
                if (
                    not vendor_model_id
                    or vendor_model_id.casefold() in seen_vendor_model_ids
                ):
                    raise FrontierPublicationError(
                        "Coverage-only vendor model ids must be present and unique"
                    )
                if coverage_status not in COVERAGE_ONLY_STATUSES:
                    raise FrontierPublicationError(
                        "Coverage-only entries must declare a supported coverage_status"
                    )
                if not n_a_reason:
                    raise FrontierPublicationError(
                        "Coverage-only entries must declare an N/A reason"
                    )
                seen_vendor_model_ids.add(vendor_model_id.casefold())
            else:
                if not catalog_id:
                    raise FrontierPublicationError(
                        f"Executable profile entry {key!r} has no catalog_id"
                    )
                if catalog_id.casefold() in seen_ids:
                    raise FrontierPublicationError(
                        "Profile catalog ids must be unique"
                    )
                seen_ids.add(catalog_id.casefold())
            seen_keys.add(key)
            rows.append(
                {
                    "key": key,
                    "label": label,
                    "catalog_id": catalog_id or None,
                    "vendor_model_id": vendor_model_id or None,
                    "coverage_only": coverage_only,
                    "coverage_status": coverage_status or None,
                    "n_a_reason": n_a_reason or None,
                    "role": role,
                    "cohort": cohort_id,
                    "claim_class": claim_class,
                }
            )

    if ga_cohort_id not in seen_cohorts or companion_cohort_id not in seen_cohorts:
        raise FrontierPublicationError("Profile names a cohort that does not exist")
    by_cohort = {row["cohort"]: row["claim_class"] for row in rows}
    if by_cohort.get(ga_cohort_id) != "general-availability":
        raise FrontierPublicationError(
            "The GA cohort must use claim_class 'general-availability'"
        )
    if by_cohort.get(companion_cohort_id) != "preview-or-limited-access":
        raise FrontierPublicationError(
            "The companion cohort must use claim_class 'preview-or-limited-access'"
        )

    baselines = [row for row in rows if row["role"] == "baseline"]
    if len(baselines) != 1 or baselines[0]["catalog_id"] != GPT_5_5_BASELINE_ID:
        raise FrontierPublicationError(
            f"The profile must declare exactly one baseline: {GPT_5_5_BASELINE_ID}"
        )
    if baselines[0]["cohort"] != ga_cohort_id:
        raise FrontierPublicationError("GPT-5.5 baseline must be in the GA cohort")
    if any(
        row["role"] == "baseline" and row["cohort"] == companion_cohort_id
        for row in rows
    ):
        raise FrontierPublicationError("The companion cohort cannot contain a baseline")
    return ga_cohort_id, companion_cohort_id, rows


def _audit_entries(
    audit: Mapping[str, Any], profile_rows: Sequence[Mapping[str, Any]]
) -> dict[str, Mapping[str, Any]]:
    profile_by_key = {str(row["key"]): row for row in profile_rows}
    allowed_statuses = {
        "ambiguous_catalog_id",
        "identity_unresolved",
        "ineligible",
        "label_mismatch",
        "missing",
        "present",
        "coverage_only",
    }
    audit_rows: dict[str, Mapping[str, Any]] = {}
    for cohort in _require_object_list(audit.get("cohorts"), "audit.cohorts"):
        cohort_id = str(cohort.get("id") or "").strip()
        for entry in _require_object_list(
            cohort.get("entries"), f"audit cohort {cohort.get('id')!r} entries"
        ):
            key = str(entry.get("key") or "").strip()
            if not key or key in audit_rows:
                raise FrontierPublicationError("Audit entry keys must be present and unique")
            expected = profile_by_key.get(key)
            if expected is not None:
                if cohort_id != expected["cohort"]:
                    raise FrontierPublicationError(
                        f"Audit entry {key!r} is assigned to the wrong cohort"
                    )
                observed_catalog_id = str(entry.get("catalog_id") or "") or None
                if observed_catalog_id != expected["catalog_id"]:
                    raise FrontierPublicationError(
                        f"Audit entry {key!r} has the wrong catalog id"
                    )
                if str(entry.get("role") or "candidate") != expected["role"]:
                    raise FrontierPublicationError(
                        f"Audit entry {key!r} has the wrong role"
                    )
                if bool(entry.get("coverage_only")) != bool(
                    expected["coverage_only"]
                ):
                    raise FrontierPublicationError(
                        f"Audit entry {key!r} has the wrong coverage-only state"
                    )
                if expected["coverage_only"]:
                    if (
                        str(entry.get("vendor_model_id") or "")
                        != expected["vendor_model_id"]
                        or str(entry.get("coverage_status") or "")
                        != expected["coverage_status"]
                    ):
                        raise FrontierPublicationError(
                            f"Audit entry {key!r} has the wrong coverage identity"
                        )
            status = str(entry.get("status") or "")
            if status not in allowed_statuses:
                raise FrontierPublicationError(
                    f"Audit entry {key!r} has an unsupported status"
                )
            if expected is not None and expected["coverage_only"]:
                if (
                    status != "coverage_only"
                    or entry.get("required") is not False
                    or entry.get("execution_eligible") is not False
                    or str(entry.get("reason") or "") != expected["n_a_reason"]
                ):
                    raise FrontierPublicationError(
                        f"Audit entry {key!r} is not a staged non-executable identity"
                    )
            elif expected is not None and status == "coverage_only":
                raise FrontierPublicationError(
                    f"Executable audit entry {key!r} cannot use coverage_only status"
                )
            audit_rows[key] = entry
    expected = {str(row["key"]) for row in profile_rows}
    if set(audit_rows) != expected:
        missing = sorted(expected - set(audit_rows))
        extra = sorted(set(audit_rows) - expected)
        raise FrontierPublicationError(
            f"Audit/profile entry mismatch; missing={missing}, extra={extra}"
        )
    return audit_rows


def _validated_execution_panel(value: Any) -> list[Mapping[str, Any]]:
    panel = _require_object_list(value, "execution panel")
    if not panel:
        raise FrontierPublicationError("Execution panel must not be empty")
    keys: set[str] = set()
    model_ids: set[str] = set()
    for row in panel:
        key = str(row.get("key") or "").strip()
        model_id = str(row.get("model") or "").strip()
        if not key or not model_id:
            raise FrontierPublicationError(
                "Every execution-panel row must have key and model"
            )
        if key in keys or model_id.casefold() in model_ids:
            raise FrontierPublicationError(
                "Execution-panel keys and model ids must be unique"
            )
        keys.add(key)
        model_ids.add(model_id.casefold())
    return panel


def _planned_question_count(manifest: Mapping[str, Any]) -> int:
    sampling = manifest.get("sampling") or {}
    if not isinstance(sampling, Mapping):
        raise FrontierPublicationError("manifest.sampling must be an object")
    selected_ids = sampling.get("selected_ids") or []
    if selected_ids:
        if not isinstance(selected_ids, list) or len(set(map(str, selected_ids))) != len(
            selected_ids
        ):
            raise FrontierPublicationError("manifest sampling ids must be a unique array")
        return len(selected_ids)
    tasks = manifest.get("tasks") or []
    questions_per_task = int(manifest.get("questions_per_task") or 0)
    count = len(tasks) * questions_per_task if isinstance(tasks, list) else 0
    if count <= 0:
        raise FrontierPublicationError("Unable to determine planned question count")
    return count


def _execution_software(manifest: Mapping[str, Any]) -> dict[str, Any]:
    source = _require_mapping(
        manifest.get("execution_software"), "manifest.execution_software"
    )
    package = str(source.get("package") or "").strip()
    version = str(source.get("version") or "").strip()
    repository = str(source.get("source_repository") or "").strip()
    commit = str(source.get("source_commit") or "").strip()
    dirty = source.get("source_worktree_dirty")
    if package != "llm-benchmark-protocol" or not version:
        raise FrontierPublicationError(
            "Matrix manifest lacks the executing benchmark package/version"
        )
    if not repository.startswith("https://github.com/"):
        raise FrontierPublicationError(
            "Matrix manifest lacks the public source repository identity"
        )
    if not re.fullmatch(r"[0-9a-f]{40,64}", commit):
        raise FrontierPublicationError(
            "Matrix manifest lacks a canonical source commit"
        )
    if not isinstance(dirty, bool):
        raise FrontierPublicationError(
            "Matrix manifest source_worktree_dirty must be boolean"
        )
    return {
        "package": package,
        "version": version,
        "source_repository": repository,
        "source_commit": commit,
        "source_worktree_dirty": dirty,
    }


def _as_rate(value: Any, label: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise FrontierPublicationError(f"{label} must be numeric") from exc
    if not 0.0 <= parsed <= 1.0:
        raise FrontierPublicationError(f"{label} must be between zero and one")
    return parsed


def _safe_error_distribution(value: Any) -> dict[str, int]:
    if value in (None, {}):
        return {}
    if not isinstance(value, Mapping):
        raise FrontierPublicationError("provider_error_distribution must be an object")
    result: dict[str, int] = {}
    for key, count in value.items():
        name = str(key)
        if not SAFE_ERROR_CLASS.fullmatch(name):
            raise FrontierPublicationError(
                "Provider error distributions may contain error classes only"
            )
        try:
            parsed_count = int(count)
        except (TypeError, ValueError) as exc:
            raise FrontierPublicationError(
                "Provider error-distribution counts must be integers"
            ) from exc
        if parsed_count < 0:
            raise FrontierPublicationError(
                "Provider error-distribution counts cannot be negative"
            )
        result[name] = parsed_count
    return dict(sorted(result.items()))


def _scored_metrics(source: Mapping[str, Any]) -> dict[str, Any]:
    for field in (
        "score_weighted_operational_goodput",
        "operational_goodput_ci95_low",
        "operational_goodput_ci95_high",
        "quality_score",
        "quality_ci95_low",
        "quality_ci95_high",
        "availability",
    ):
        _as_rate(source.get(field), f"leaderboard row {source.get('requested_model')} {field}")
    availability = float(source["availability"])
    conditional_quality = source.get("conditional_quality_score")
    if conditional_quality is None:
        if availability != 0.0:
            raise FrontierPublicationError(
                "conditional_quality_score may be null only when availability is zero"
            )
    else:
        _as_rate(
            conditional_quality,
            f"leaderboard row {source.get('requested_model')} conditional_quality_score",
        )
    return {
        "tier": int(source["tier"]),
        "questions_scored": int(source["questions_scored"]),
        "operational_goodput": source.get("score_weighted_operational_goodput"),
        "operational_goodput_ci95_low": source.get(
            "operational_goodput_ci95_low"
        ),
        "operational_goodput_ci95_high": source.get(
            "operational_goodput_ci95_high"
        ),
        "quality_score": source.get("quality_score"),
        "quality_ci95_low": source.get("quality_ci95_low"),
        "quality_ci95_high": source.get("quality_ci95_high"),
        "conditional_quality_score": source.get("conditional_quality_score"),
        "availability": source.get("availability"),
        "successful_answers": int(source.get("successful_answers", 0)),
        "failed_answers": int(source.get("failed_answers", 0)),
        "missing_answers": int(source.get("missing_answers", 0)),
        "latency_p50_ms": source.get("latency_p50_ms"),
        "latency_p95_ms": source.get("latency_p95_ms"),
        "cost_usd": source.get("cost_usd"),
        "cost_is_lower_bound": bool(source.get("cost_total_is_lower_bound")),
        "data_analysis_score": source.get("data_analysis_score"),
        "instruction_following_score": source.get(
            "instruction_following_score"
        ),
        "language_score": source.get("language_score"),
        "math_score": source.get("math_score"),
        "reasoning_score": source.get("reasoning_score"),
        "provider_error_distribution": _safe_error_distribution(
            source.get("provider_error_distribution")
        ),
        "n_a_reason_code": None,
        "n_a_reason": None,
    }


def _empty_metrics() -> dict[str, Any]:
    return {
        "tier": None,
        "questions_scored": None,
        "operational_goodput": None,
        "operational_goodput_ci95_low": None,
        "operational_goodput_ci95_high": None,
        "quality_score": None,
        "quality_ci95_low": None,
        "quality_ci95_high": None,
        "conditional_quality_score": None,
        "availability": None,
        "successful_answers": None,
        "failed_answers": None,
        "missing_answers": None,
        "latency_p50_ms": None,
        "latency_p95_ms": None,
        "cost_usd": None,
        "cost_is_lower_bound": None,
        "data_analysis_score": None,
        "instruction_following_score": None,
        "language_score": None,
        "math_score": None,
        "reasoning_score": None,
        "provider_error_distribution": {},
    }


def _validate_matrix(
    *,
    manifest: Mapping[str, Any],
    leaderboard: Mapping[str, Any],
    panel: Sequence[Mapping[str, Any]],
) -> tuple[list[Mapping[str, Any]], int]:
    if leaderboard.get("matrix_id") != manifest.get("matrix_id"):
        raise FrontierPublicationError("Manifest and leaderboard matrix ids differ")
    if leaderboard.get("livebench_release") != manifest.get("livebench_release"):
        raise FrontierPublicationError(
            "Manifest and leaderboard LiveBench releases differ"
        )
    if list(leaderboard.get("tasks") or []) != list(manifest.get("tasks") or []):
        raise FrontierPublicationError("Manifest and leaderboard task sets differ")
    if int(leaderboard.get("questions_per_task") or 0) != int(
        manifest.get("questions_per_task") or 0
    ):
        raise FrontierPublicationError(
            "Manifest and leaderboard questions-per-task values differ"
        )
    requested_cap = leaderboard.get("requested_max_output_tokens")
    if requested_cap is not None and int(requested_cap) != int(
        manifest.get("max_tokens") or 0
    ):
        raise FrontierPublicationError(
            "Manifest and leaderboard requested output caps differ"
        )
    failures = leaderboard.get("failures") or []
    if not isinstance(failures, list) or failures:
        raise FrontierPublicationError(
            f"Matrix is not publication-complete: {len(failures) if isinstance(failures, list) else 'invalid'} orchestration failures"
        )
    rows = _require_object_list(leaderboard.get("results"), "leaderboard.results")
    if len(rows) != len(panel):
        raise FrontierPublicationError(
            f"Matrix has {len(rows)} rows for an execution panel of {len(panel)}"
        )
    ranks = sorted(int(row.get("rank") or 0) for row in rows)
    if ranks != list(range(1, len(rows) + 1)):
        raise FrontierPublicationError("Leaderboard ranks must be the sequence 1..N")
    if any(row.get("complete") is not True for row in rows):
        raise FrontierPublicationError("Every scored leaderboard row must be complete")

    panel_pairs = {
        (str(row["key"]), str(row["model"])) for row in panel
    }
    manifest_models = _require_object_list(manifest.get("models"), "manifest.models")
    manifest_pairs = {
        (str(row.get("key") or ""), str(row.get("model") or ""))
        for row in manifest_models
    }
    if manifest_pairs != panel_pairs or len(manifest_models) != len(panel):
        raise FrontierPublicationError(
            "Manifest model identities do not exactly match the execution panel"
        )
    panel_ids = {str(row["model"]) for row in panel}
    result_ids = {str(row.get("requested_model") or "") for row in rows}
    if result_ids != panel_ids or len(result_ids) != len(rows):
        raise FrontierPublicationError(
            "Leaderboard endpoint identities do not exactly match the execution panel"
        )

    planned = _planned_question_count(manifest)
    sampling = manifest.get("sampling") or {}
    if sampling.get("content_hash_algorithm") != "sha256" or not re.fullmatch(
        r"[0-9a-f]{64}", str(sampling.get("content_hash") or "")
    ):
        raise FrontierPublicationError(
            "Manifest sampling must carry a lowercase SHA-256 content hash"
        )
    for row in rows:
        model_id = str(row.get("requested_model"))
        if int(row.get("questions_scored") or 0) != planned:
            raise FrontierPublicationError(
                f"{model_id} does not preserve the frozen {planned}-question denominator"
            )
        if int(row.get("missing_answers") or 0) != 0:
            raise FrontierPublicationError(
                f"{model_id} has missing final records despite complete=true"
            )
        _scored_metrics(row)

    pairwise = _require_object_list(
        leaderboard.get("pairwise_tests") or [], "leaderboard.pairwise_tests"
    )
    expected_comparisons = len(rows) * (len(rows) - 1) // 2
    if len(pairwise) != expected_comparisons:
        raise FrontierPublicationError(
            f"Pairwise family has {len(pairwise)} comparisons; expected {expected_comparisons}"
        )
    if any("separates_at_fwer_05" not in test for test in pairwise):
        raise FrontierPublicationError(
            "Every pairwise test must expose separates_at_fwer_05"
        )
    panel_keys = {str(row.get("panel_key") or "") for row in rows}
    expected_pairs = {frozenset(pair) for pair in combinations(panel_keys, 2)}
    observed_pairs: set[frozenset[str]] = set()
    for test in pairwise:
        pair = frozenset(
            {
                str(test.get("higher_panel_key") or ""),
                str(test.get("lower_panel_key") or ""),
            }
        )
        if len(pair) != 2 or not pair <= panel_keys or pair in observed_pairs:
            raise FrontierPublicationError(
                "Pairwise tests must contain each scored endpoint pair exactly once"
            )
        observed_pairs.add(pair)
        for field in (
            "mean_difference",
            "ci95_low",
            "ci95_high",
            "randomization_p_value",
            "holm_adjusted_p_value",
        ):
            try:
                float(test[field])
            except (KeyError, TypeError, ValueError) as exc:
                raise FrontierPublicationError(
                    f"Pairwise field {field!r} must be numeric"
                ) from exc
        if not isinstance(test.get("separates_at_fwer_05"), bool):
            raise FrontierPublicationError(
                "Pairwise separates_at_fwer_05 values must be boolean"
            )
    if observed_pairs != expected_pairs:
        raise FrontierPublicationError(
            "Pairwise tests do not cover the complete scored endpoint family"
        )
    return rows, planned


def build_publication(
    *,
    manifest: Mapping[str, Any],
    leaderboard: Mapping[str, Any],
    profile: Mapping[str, Any],
    execution_panel: Sequence[Mapping[str, Any]],
    coverage_audit: Mapping[str, Any],
    catalog: Sequence[Mapping[str, Any]],
    source_hashes: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Build a public aggregate bundle from already-loaded source artifacts."""

    ga_id, companion_id, profile_rows = _validated_profile(profile)
    panel = _validated_execution_panel(list(execution_panel))
    rows, planned = _validate_matrix(
        manifest=manifest, leaderboard=leaderboard, panel=panel
    )
    execution_software = _execution_software(manifest)

    if coverage_audit.get("profile_id") != profile.get("profile_id"):
        raise FrontierPublicationError("Coverage audit and profile ids differ")
    if coverage_audit.get("snapshot_date") != profile.get("snapshot_date"):
        raise FrontierPublicationError("Coverage audit and profile snapshot dates differ")
    catalog_sha = str(coverage_audit.get("catalog_sha256") or "")
    if not re.fullmatch(r"[0-9a-f]{64}", catalog_sha):
        raise FrontierPublicationError("Coverage audit lacks a lowercase SHA-256 catalog hash")
    catalog_rows = _require_object_list(list(catalog), "matrix Kendr catalog")
    if not catalog_rows:
        raise FrontierPublicationError("Matrix Kendr catalog must not be empty")
    computed_catalog_sha = catalog_sha256(catalog_rows)
    if computed_catalog_sha != catalog_sha:
        raise FrontierPublicationError(
            "Matrix Kendr catalog does not match coverage_audit.catalog_sha256"
        )
    if int(coverage_audit.get("catalog_entries") or -1) != len(catalog_rows):
        raise FrontierPublicationError(
            "Matrix Kendr catalog size does not match the coverage audit"
        )
    audit_by_key = _audit_entries(coverage_audit, profile_rows)

    profile_by_id = {
        str(row["catalog_id"]): row
        for row in profile_rows
        if row["catalog_id"] is not None
    }
    execution_ids = {str(row["model"]) for row in panel}
    unknown_execution_ids = sorted(execution_ids - set(profile_by_id))
    if unknown_execution_ids:
        raise FrontierPublicationError(
            "Execution panel contains endpoints outside the frontier profile: "
            + ", ".join(unknown_execution_ids)
        )
    companion_execution = sorted(
        model_id
        for model_id in execution_ids
        if profile_by_id[model_id]["cohort"] == companion_id
    )
    if companion_execution:
        raise FrontierPublicationError(
            "Preview/limited-access endpoints cannot be pooled into the GA execution: "
            + ", ".join(companion_execution)
        )
    baseline_ids = {
        model_id
        for model_id in execution_ids
        if profile_by_id[model_id]["role"] == "baseline"
    }
    if baseline_ids != {GPT_5_5_BASELINE_ID}:
        raise FrontierPublicationError(
            f"The execution panel must include only the declared baseline {GPT_5_5_BASELINE_ID}"
        )

    result_by_id = {str(row["requested_model"]): row for row in rows}
    for model_id, source in result_by_id.items():
        profile_row = profile_by_id[model_id]
        audit_row = audit_by_key[str(profile_row["key"])]
        if audit_row.get("status") != "present":
            raise FrontierPublicationError(
                f"Scored endpoint {model_id} is not identity-eligible in the coverage audit"
            )
        if str(source.get("panel_key") or "") not in {
            str(row["key"]) for row in panel if str(row["model"]) == model_id
        }:
            raise FrontierPublicationError(
                f"Scored endpoint {model_id} has the wrong panel key"
            )

    scored_candidates = sorted(
        (
            source
            for model_id, source in result_by_id.items()
            if profile_by_id[model_id]["role"] == "candidate"
        ),
        key=lambda row: int(row["rank"]),
    )
    if not scored_candidates:
        raise FrontierPublicationError(
            "At least one GA frontier candidate must be scored"
        )
    candidate_rank = {
        str(source["requested_model"]): rank
        for rank, source in enumerate(scored_candidates, 1)
    }

    public_rows: list[dict[str, Any]] = []
    for profile_order, profile_row in enumerate(profile_rows, 1):
        model_id = (
            str(profile_row["catalog_id"])
            if profile_row["catalog_id"] is not None
            else None
        )
        coverage_only = bool(profile_row["coverage_only"])
        audit_row = audit_by_key[str(profile_row["key"])]
        source = result_by_id.get(model_id) if model_id is not None else None
        base = {
            "display_order": profile_order,
            "cohort": profile_row["cohort"],
            "claim_class": profile_row["claim_class"],
            "role": profile_row["role"],
            "benchmark_status": "scored" if source is not None else "not_measured",
            "catalog_status": (
                audit_row.get("coverage_status")
                if coverage_only
                else audit_row.get("status")
            ),
            "rank": candidate_rank.get(model_id) if model_id is not None else None,
            "execution_rank": int(source["rank"]) if source is not None else None,
            "endpoint_id": model_id,
            "vendor_model_id": profile_row.get("vendor_model_id"),
            "endpoint_label": profile_row["label"],
            "configuration_label": source.get("model") if source is not None else None,
        }
        if source is not None:
            base.update(_scored_metrics(source))
        else:
            base.update(_empty_metrics())
            status = str(audit_row.get("status") or "unknown")
            reason = str(audit_row.get("reason") or "").strip()
            if coverage_only:
                coverage_status = str(
                    audit_row.get("coverage_status") or "unknown"
                )
                reason_code = f"coverage_only_{coverage_status}"
                reason = reason or str(profile_row.get("n_a_reason") or "")
            elif profile_row["cohort"] == companion_id and status == "present":
                reason_code = "preview_companion_not_scheduled"
                reason = (
                    "Preview or limited-access companion was not scheduled in the "
                    "GA callable-subset matrix."
                )
            elif status == "present":
                reason_code = "not_scheduled"
                reason = "Eligible endpoint was not scheduled in this callable-subset matrix."
            else:
                reason_code = status
                reason = reason or "Endpoint did not pass the frozen catalog eligibility audit."
            base["n_a_reason_code"] = reason_code
            base["n_a_reason"] = reason
        public_rows.append(base)

    public_rows.sort(
        key=lambda row: (
            0
            if row["benchmark_status"] == "scored" and row["role"] == "candidate"
            else 1
            if row["role"] == "baseline"
            else 2
            if row["claim_class"] == "general-availability"
            else 3,
            row["rank"] if row["rank"] is not None else row["display_order"],
        )
    )
    for display_order, row in enumerate(public_rows, 1):
        row["display_order"] = display_order

    pairwise = list(leaderboard.get("pairwise_tests") or [])
    holm_rejections = sum(
        bool(test.get("separates_at_fwer_05")) for test in pairwise
    )
    sampling = manifest.get("sampling") or {}
    core_candidates = [
        row
        for row in public_rows
        if row["cohort"] == ga_id and row["role"] == "candidate"
    ]
    preview_rows = [row for row in public_rows if row["cohort"] == companion_id]
    baseline_rows = [row for row in public_rows if row["role"] == "baseline"]
    safe_hashes: dict[str, str] = {}
    for name, digest in (source_hashes or {}).items():
        if name not in {
            "coverage_audit_sha256",
            "execution_panel_sha256",
            "matrix_leaderboard_sha256",
            "matrix_manifest_sha256",
            "profile_sha256",
        } or not re.fullmatch(r"[0-9a-f]{64}", str(digest)):
            raise FrontierPublicationError(
                f"Invalid public source-hash entry {name!r}"
            )
        safe_hashes[name] = str(digest)

    bundle = {
        "schema_version": "1.0",
        "project": PROJECT_TITLE,
        "protocol_profile": PROTOCOL_PROFILE,
        "campaign_type": "current-frontier-callable-subset",
        "scientific_status": (
            "Descriptive endpoint-as-served engineering snapshot; not a global "
            "model ranking, certification, or proof of intrinsic model capability."
        ),
        "matrix_id": leaderboard.get("matrix_id"),
        "generated_at": leaderboard.get("created_at"),
        "profile_id": profile.get("profile_id"),
        "snapshot_date": profile.get("snapshot_date"),
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
            "max_cost_usd_per_answer": manifest.get("max_cost_usd_per_answer"),
            "parallel_requests": leaderboard.get("parallel_requests")
            or manifest.get("parallel_requests"),
            "parallel_grading": manifest.get("parallel_grading"),
            "requested_reasoning_effort": manifest.get("reasoning_effort"),
            "reasoning_effort_interpretation": (
                "This is the harness request value. Kendr endpoint labels state "
                "served default because provider-side effort/default behavior was "
                "not normalized across vendors."
            ),
        },
        "execution_software": execution_software,
        "scope": {
            "profile_entries": len(public_rows),
            "core_ga_candidates": len(core_candidates),
            "scored_core_ga_candidates": sum(
                row["benchmark_status"] == "scored" for row in core_candidates
            ),
            "not_measured_core_ga_candidates": sum(
                row["benchmark_status"] == "not_measured"
                for row in core_candidates
            ),
            "scored_baselines": sum(
                row["benchmark_status"] == "scored" for row in baseline_rows
            ),
            "preview_companion_entries": len(preview_rows),
            "scored_preview_companion_entries": 0,
        },
        "ranking_rule": leaderboard.get("ranking_rule"),
        "rank_scope": (
            "rank orders scored GA candidates only. execution_rank preserves the "
            "matrix ordering that also included the declared GPT-5.5 baseline."
        ),
        "tier_scope": (
            "tier is the matrix marginal-interval grouping and therefore includes "
            "the declared baseline; it is not a candidate-only inferential rank."
        ),
        "n_a_policy": (
            "Not-scheduled or audit-ineligible configurations use null metrics and "
            "render as N/A. A scheduled endpoint with complete zero-goodput evidence "
            "remains a scored zero and is never converted to N/A."
        ),
        "pairwise_inference": {
            "comparisons": len(pairwise),
            "holm_rejections": holm_rejections,
            "rejection_field": "separates_at_fwer_05",
            "interpretation": (
                "No pairwise difference survives the declared Holm family-wise correction."
                if holm_rejections == 0
                else "Consult corrected paired effects before interpreting point-estimate order."
            ),
        },
        "claim_readiness": {
            "ga_claim_ready": bool(coverage_audit.get("ga_claim_ready")),
            "companion_claim_ready": bool(
                coverage_audit.get("companion_claim_ready")
            ),
            "claim_separation": coverage_audit.get("claim_separation"),
        },
        "rows": public_rows,
        "provenance": {
            "catalog_sha256": catalog_sha,
            **safe_hashes,
        },
        "privacy_review": {
            "raw_prompts_included": False,
            "raw_responses_included": False,
            "provider_request_ids_included": False,
            "local_paths_included": False,
            "provider_error_messages_included": False,
        },
    }
    _assert_public_safe(bundle)
    return bundle


def _markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _markdown_table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    lines = [
        "| " + " | ".join(map(_markdown_cell, headers)) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend(
        "| " + " | ".join(_markdown_cell(value) for value in row) + " |"
        for row in rows
    )
    return "\n".join(lines)


def _percent(value: Any, digits: int = 1) -> str:
    return "N/A" if value is None else f"{float(value) * 100:.{digits}f}%"


def _milliseconds(value: Any) -> str:
    return "N/A" if value is None else f"{float(value):,.0f}"


def _money(value: Any, lower_bound: Any) -> str:
    if value in (None, ""):
        return "N/A"
    marker = "≥" if lower_bound else ""
    return f"{marker}${float(value):.6f}"


def _gpt_pairwise_note(leaderboard: Mapping[str, Any]) -> list[str]:
    by_id = {
        str(row.get("requested_model")): str(row.get("panel_key"))
        for row in leaderboard.get("results") or []
        if isinstance(row, Mapping)
    }
    sol_key = by_id.get("kc-gpt-5.6-sol")
    baseline_key = by_id.get(GPT_5_5_BASELINE_ID)
    if not sol_key or not baseline_key:
        return []
    target = None
    for test in leaderboard.get("pairwise_tests") or []:
        if not isinstance(test, Mapping):
            continue
        keys = {
            str(test.get("higher_panel_key")),
            str(test.get("lower_panel_key")),
        }
        if keys == {sol_key, baseline_key}:
            target = test
            break
    if target is None:
        return []

    mean = float(target.get("mean_difference") or 0.0)
    low = float(target.get("ci95_low") or 0.0)
    high = float(target.get("ci95_high") or 0.0)
    if str(target.get("higher_panel_key")) != sol_key:
        mean, low, high = -mean, -high, -low
    return [
        "## GPT-5.6 Sol versus GPT-5.5 baseline",
        "",
        (
            f"The paired operational-goodput effect for GPT-5.6 Sol minus the "
            f"GPT-5.5 baseline was {mean * 100:+.2f} percentage points "
            f"(95% interval {low * 100:+.2f} to {high * 100:+.2f}). The exact "
            f"randomization p-value was {float(target['randomization_p_value']):.3g}; "
            f"the Holm-adjusted p-value was {float(target['holm_adjusted_p_value']):.3g}."
        ),
        "",
        (
            "This narrow endpoint-as-served comparison does not establish that "
            "either model family is intrinsically or universally superior."
        ),
        "",
    ]


def render_markdown(
    bundle: Mapping[str, Any], leaderboard: Mapping[str, Any]
) -> str:
    rows = list(bundle["rows"])
    scored_candidates = sorted(
        (
            row
            for row in rows
            if row["role"] == "candidate"
            and row["claim_class"] == "general-availability"
            and row["benchmark_status"] == "scored"
        ),
        key=lambda row: int(row["rank"]),
    )
    baselines = [row for row in rows if row["role"] == "baseline"]
    not_measured_core = [
        row
        for row in rows
        if row["claim_class"] == "general-availability"
        and row["role"] == "candidate"
        and row["benchmark_status"] == "not_measured"
    ]
    preview = [
        row for row in rows if row["claim_class"] == "preview-or-limited-access"
    ]
    scope = bundle["scope"]
    sample = bundle["sample"]
    configuration = bundle["execution_configuration"]
    software = bundle["execution_software"]
    inference = bundle["pairwise_inference"]
    lines = [
        f"# Kendr current-frontier callable-subset leaderboard — {bundle.get('snapshot_date')}",
        "",
        f"**Matrix ID:** `{bundle.get('matrix_id')}`  ",
        f"**Profile:** `{bundle.get('profile_id')}`  ",
        f"**Execution software:** `{software['package']} {software['version']}`  ",
        f"**Source commit:** `{software['source_commit']}`  ",
        f"**Dirty worktree:** `{'yes' if software['source_worktree_dirty'] else 'no'}`  ",
        "**Status:** Descriptive endpoint-as-served engineering evidence",
        "",
        str(bundle["scientific_status"]),
        "",
        "## Frozen scope",
        "",
        _markdown_table(
            ["Field", "Value"],
            [
                ["Profile entries", scope["profile_entries"]],
                ["Core GA candidates", scope["core_ga_candidates"]],
                ["Scored GA candidates", scope["scored_core_ga_candidates"]],
                ["Not measured GA candidates", scope["not_measured_core_ga_candidates"]],
                ["Scored baselines", scope["scored_baselines"]],
                ["Preview companion entries", scope["preview_companion_entries"]],
                ["Questions per scored endpoint", sample["questions"]],
                ["Tasks", len(sample["tasks"])],
                ["Generations per endpoint-question", sample["generations_per_endpoint_question"]],
                ["Requested output cap", configuration["requested_max_output_tokens"]],
                ["Requested reasoning effort", configuration["requested_reasoning_effort"]],
                ["Benchmark package version", software["version"]],
                ["Execution source commit", f"`{software['source_commit']}`"],
                [
                    "Execution worktree dirty",
                    "yes" if software["source_worktree_dirty"] else "no",
                ],
            ],
        ),
        "",
        "## Scored GA candidates",
        "",
        _markdown_table(
            [
                "Rank",
                "Model",
                "Kendr endpoint",
                "Operational goodput",
                "95% interval",
                "Quality",
                "Conditional quality",
                "Availability",
                "p50 latency (ms)",
                "Observed cost",
            ],
            [
                [
                    row["rank"],
                    row["endpoint_label"],
                    f"`{row['endpoint_id']}`",
                    _percent(row["operational_goodput"]),
                    f"{_percent(row['operational_goodput_ci95_low'])}–{_percent(row['operational_goodput_ci95_high'])}",
                    _percent(row["quality_score"]),
                    _percent(row["conditional_quality_score"]),
                    _percent(row["availability"]),
                    _milliseconds(row["latency_p50_ms"]),
                    _money(row["cost_usd"], row["cost_is_lower_bound"]),
                ]
                for row in scored_candidates
            ],
        ),
        "",
        "`rank` excludes the declared GPT-5.5 baseline. `execution_rank` in the machine-readable bundle preserves the original scored matrix order.",
        "",
        "## Declared baseline",
        "",
        _markdown_table(
            [
                "Role",
                "Model",
                "Kendr endpoint",
                "Matrix order",
                "Operational goodput",
                "Quality",
                "Availability",
            ],
            [
                [
                    "Baseline",
                    row["endpoint_label"],
                    f"`{row['endpoint_id']}`",
                    row["execution_rank"],
                    _percent(row["operational_goodput"]),
                    _percent(row["quality_score"]),
                    _percent(row["availability"]),
                ]
                for row in baselines
            ],
        ),
        "",
        "## Core GA candidates reported as N/A",
        "",
        _markdown_table(
            [
                "Model",
                "Configured Kendr endpoint",
                "Coverage identity",
                "Catalog status",
                "Reason",
            ],
            [
                [
                    row["endpoint_label"],
                    (
                        f"`{row['endpoint_id']}`"
                        if row["endpoint_id"] is not None
                        else "N/A"
                    ),
                    (
                        f"`{row['vendor_model_id']}`"
                        if row["vendor_model_id"] is not None
                        else "N/A"
                    ),
                    row["catalog_status"],
                    row["n_a_reason"],
                ]
                for row in not_measured_core
            ],
        ),
        "",
        "N/A means not measured under this frozen execution. It is not a zero score. A scheduled endpoint with complete zero-goodput evidence would remain a scored zero.",
        "",
        "## Preview and limited-access companion",
        "",
        _markdown_table(
            ["Model", "Configured Kendr endpoint", "Status", "Reason"],
            [
                [
                    row["endpoint_label"],
                    f"`{row['endpoint_id']}`",
                    "N/A" if row["benchmark_status"] == "not_measured" else "Scored",
                    row["n_a_reason"] or "See companion result.",
                ]
                for row in preview
            ],
        ),
        "",
        "Preview and limited-access systems are not pooled into GA ranks or superiority claims.",
        "",
    ]
    lines.extend(_gpt_pairwise_note(leaderboard))
    lines.extend(
        [
            "## Inference and interpretation",
            "",
            f"The matrix contains {inference['comparisons']} paired comparisons; {inference['holm_rejections']} separated after the declared Holm family-wise correction. {inference['interpretation']}",
            "",
            f"The requested reasoning-effort field was `{configuration['requested_reasoning_effort']}`. {configuration['reasoning_effort_interpretation']}",
            "",
            (
                "The execution worktree contained uncommitted changes. The recorded "
                "commit identifies the base revision, but the commit alone cannot "
                "fully reconstruct those local changes."
                if software["source_worktree_dirty"]
                else "The execution worktree was clean at the recorded source commit."
            ),
            "",
            f"This campaign used a small, one-generation, {len(sample['tasks'])}-task objective slice. It did not measure multilingual breadth, multimodal behavior, long context, tool use, safety, fairness, regional load, human outcomes, or independent replication. Point-estimate order is therefore descriptive and may be unstable.",
            "",
            "## Privacy and reproducibility",
            "",
            "The public bundle contains aggregate measurements, exact public endpoint identifiers, source hashes, and N/A reasons. It excludes raw prompts, raw responses, provider request identifiers, error messages, credentials, and machine-local paths. The bundle-local `SHA256SUMS` detects byte drift but is not a digital signature.",
            "",
        ]
    )
    return "\n".join(lines)


def _write_lf(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def write_publication(
    *,
    bundle: Mapping[str, Any],
    leaderboard: Mapping[str, Any],
    output_dir: Path,
    stem: str,
) -> list[Path]:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", stem):
        raise FrontierPublicationError("Output stem contains unsafe characters")
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{stem}.json"
    csv_path = output_dir / f"{stem}.csv"
    markdown_path = output_dir / f"{stem}.md"
    checksum_path = output_dir / "SHA256SUMS"

    _write_lf(
        json_path,
        json.dumps(bundle, indent=2, ensure_ascii=False) + "\n",
    )
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=PUBLIC_CSV_FIELDS,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        for source in bundle["rows"]:
            row = dict(source)
            row["provider_error_distribution"] = json.dumps(
                row.get("provider_error_distribution") or {},
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            for field in PUBLIC_CSV_FIELDS:
                if row.get(field) is None:
                    row[field] = "N/A"
            writer.writerow(row)
    _write_lf(markdown_path, render_markdown(bundle, leaderboard))

    artifacts = sorted((csv_path, json_path, markdown_path), key=lambda path: path.name)
    checksum_lines = [f"{_sha256(path)}  {path.name}" for path in artifacts]
    _write_lf(checksum_path, "\n".join(checksum_lines) + "\n")
    return [json_path, csv_path, markdown_path, checksum_path]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix-root", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--execution-panel", type=Path, required=True)
    parser.add_argument("--coverage-audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--stem", default="kendr-frontier-leaderboard-2026-08-08"
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
            raise FrontierPublicationError(f"Required matrix artifact not found: {path}")

    manifest = _require_mapping(_read_json(manifest_path), "matrix manifest")
    leaderboard = _require_mapping(
        _read_json(leaderboard_path), "matrix leaderboard"
    )
    profile = _require_mapping(_read_json(args.profile), "frontier profile")
    execution_panel = _validated_execution_panel(_read_json(args.execution_panel))
    coverage_audit = _require_mapping(
        _read_json(args.coverage_audit), "frontier coverage audit"
    )
    catalog = _require_object_list(
        _read_json(catalog_path), "matrix Kendr catalog"
    )
    bundle = build_publication(
        manifest=manifest,
        leaderboard=leaderboard,
        profile=profile,
        execution_panel=execution_panel,
        coverage_audit=coverage_audit,
        catalog=catalog,
        source_hashes={
            "profile_sha256": _sha256(args.profile),
            "execution_panel_sha256": _sha256(args.execution_panel),
            "matrix_manifest_sha256": _sha256(manifest_path),
            "matrix_leaderboard_sha256": _sha256(leaderboard_path),
            "coverage_audit_sha256": _sha256(args.coverage_audit),
        },
    )
    for path in write_publication(
        bundle=bundle,
        leaderboard=leaderboard,
        output_dir=args.output,
        stem=args.stem,
    ):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
