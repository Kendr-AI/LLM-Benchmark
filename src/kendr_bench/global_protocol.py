from __future__ import annotations

import hashlib
import importlib.resources
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from jsonschema import Draft202012Validator, FormatChecker


PROTOCOL_NAME = "LLM Benchmark Protocol (KGBP reference profile)"
PROTOCOL_VERSION = "KGBP-1.0"
DESIGN_THRESHOLD = 9.0


SYSTEM_TYPES = frozenset(
    {
        "base-model",
        "instruction-model",
        "reasoning-model",
        "specialist-model",
        "multimodal-model",
        "embedding-model",
        "reranker",
        "router",
        "ensemble",
        "agent",
        "application",
    }
)
DEPLOYMENT_SCOPES = frozenset(
    {"model", "endpoint", "routed-system", "agentic-system", "application"}
)
ACCESS_MODES = frozenset(
    {"first-party-api", "third-party-api", "managed", "open-weights", "local", "hybrid"}
)
CLAIM_TYPES = frozenset(
    {
        "controlled-comparison",
        "capability-under-strong-elicitation",
        "production-selection",
        "router-value",
        "safety-assurance",
    }
)

CORE_TRACKS = frozenset(
    {
        "reasoning",
        "knowledge",
        "factuality",
        "instruction-following",
        "coding",
        "long-context",
        "multilingual",
        "robustness",
        "safety",
        "efficiency",
        "reliability",
        "production-tasks",
    }
)


def _at(value: Mapping[str, Any], path: str, default: Any = None) -> Any:
    current: Any = value
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return default
        current = current[part]
    return current


def _nonempty(value: Any) -> bool:
    if value is None or value is False:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (Sequence, Mapping)):
        return len(value) > 0
    return True


def _number(value: Any) -> float | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _count(value: Any) -> int:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        return 0
    return len(value)


def _subset(required: set[str] | frozenset[str], actual: Any) -> bool:
    if not isinstance(actual, Sequence) or isinstance(actual, (str, bytes)):
        return False
    return required.issubset({str(item) for item in actual})


@dataclass(frozen=True)
class CheckResult:
    check_id: str
    title: str
    passed: bool
    weight: float
    critical: bool
    observed: Any
    requirement: str
    remediation: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DimensionResult:
    dimension: str
    score: float
    passed: bool
    checks: tuple[CheckResult, ...]

    @property
    def failed_checks(self) -> tuple[CheckResult, ...]:
        return tuple(check for check in self.checks if not check.passed)

    def to_dict(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension,
            "score": self.score,
            "passed": self.passed,
            "checks": [check.to_dict() for check in self.checks],
        }


@dataclass(frozen=True)
class ProtocolAudit:
    protocol_name: str
    protocol_version: str
    config_sha256: str
    dimensions: tuple[DimensionResult, ...]
    design_score: float
    minimum_dimension_score: float
    design_ready: bool
    execution_ready: bool
    evidence_bundle_structurally_complete: bool
    global_publication_candidate: bool
    execution_blockers: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "protocol_name": self.protocol_name,
            "protocol_version": self.protocol_version,
            "config_sha256": self.config_sha256,
            "threshold_policy": {
                "minimum_score_per_dimension_exclusive": DESIGN_THRESHOLD,
                "aggregation": "geometric mean; no compensation below the per-dimension gate",
            },
            "design_score": self.design_score,
            "minimum_dimension_score": self.minimum_dimension_score,
            "design_ready": self.design_ready,
            "execution_ready": self.execution_ready,
            "evidence_bundle_structurally_complete": self.evidence_bundle_structurally_complete,
            "global_publication_candidate": self.global_publication_candidate,
            "automated_assurance_scope": (
                "Configuration and evidence-reference structure only; the audit does "
                "not verify truth, adequacy, independence, accreditation, or conformity."
            ),
            "independent_evidence_review_required": True,
            "execution_blockers": list(self.execution_blockers),
            "dimensions": [dimension.to_dict() for dimension in self.dimensions],
        }


class _DimensionBuilder:
    def __init__(self, name: str) -> None:
        self.name = name
        self.checks: list[CheckResult] = []

    def add(
        self,
        check_id: str,
        title: str,
        passed: bool,
        *,
        observed: Any,
        requirement: str,
        remediation: str,
        weight: float = 1.0,
        critical: bool = False,
    ) -> None:
        self.checks.append(
            CheckResult(
                check_id=check_id,
                title=title,
                passed=bool(passed),
                weight=weight,
                critical=critical,
                observed=observed,
                requirement=requirement,
                remediation=remediation,
            )
        )

    def finish(self) -> DimensionResult:
        total = sum(check.weight for check in self.checks)
        earned = sum(check.weight for check in self.checks if check.passed)
        score = 10.0 * earned / total if total else 0.0
        if any(check.critical and not check.passed for check in self.checks):
            score = min(score, 8.9)
        score = round(score, 2)
        return DimensionResult(
            dimension=self.name,
            score=score,
            passed=score > DESIGN_THRESHOLD,
            checks=tuple(self.checks),
        )


def _construct_validity(config: Mapping[str, Any]) -> DimensionResult:
    builder = _DimensionBuilder("construct_validity")
    claim = _at(config, "study.claim_type")
    tracks = _at(config, "evaluation.tracks", [])
    metrics = _at(config, "evaluation.metrics", [])
    endpoints = _at(config, "study.primary_endpoints", [])
    builder.add(
        "CV01",
        "Explicit claim type",
        claim in CLAIM_TYPES,
        observed=claim,
        requirement=f"One of: {', '.join(sorted(CLAIM_TYPES))}",
        remediation="Declare the exact inference the benchmark is intended to support.",
        critical=True,
    )
    builder.add(
        "CV02",
        "Target population",
        _nonempty(_at(config, "study.target_population")),
        observed=_at(config, "study.target_population"),
        requirement="A bounded population of tasks, users, systems, and deployment contexts",
        remediation="Define what future tasks and environments the results should generalize to.",
    )
    builder.add(
        "CV03",
        "Primary endpoints and estimands",
        _count(endpoints) >= 2,
        observed=endpoints,
        requirement="At least two predeclared primary endpoints/estimands",
        remediation="Predeclare quality and operational primary outcomes separately.",
    )
    builder.add(
        "CV04",
        "Capability-separated tracks",
        _count(tracks) >= 10 and len(set(map(str, tracks))) == _count(tracks),
        observed=tracks,
        requirement="At least 10 unique, separately reported tracks",
        remediation="Add separate tracks instead of hiding heterogeneous abilities in one average.",
    )
    metric_valid = (
        isinstance(metrics, Sequence)
        and len(metrics) >= 8
        and all(
            isinstance(item, Mapping)
            and _nonempty(item.get("name"))
            and item.get("direction") in {"higher", "lower", "target"}
            and _nonempty(item.get("unit"))
            for item in metrics
        )
    )
    builder.add(
        "CV05",
        "Metric semantics",
        metric_valid,
        observed=len(metrics) if isinstance(metrics, Sequence) else metrics,
        requirement="At least 8 metrics with name, unit, and optimization direction",
        remediation="Define every metric's unit and whether higher, lower, or a target is better.",
    )
    builder.add(
        "CV06",
        "Decision thresholds",
        _nonempty(_at(config, "study.decision_thresholds")),
        observed=_at(config, "study.decision_thresholds"),
        requirement="Predeclared practical decision thresholds",
        remediation="State what score difference is operationally meaningful before running models.",
    )
    builder.add(
        "CV07",
        "Non-compensatory scorecards",
        _at(config, "evaluation.single_composite_is_primary") is False
        and _at(config, "evaluation.report_pareto_frontier") is True,
        observed={
            "single_composite_is_primary": _at(config, "evaluation.single_composite_is_primary"),
            "report_pareto_frontier": _at(config, "evaluation.report_pareto_frontier"),
        },
        requirement="Track scorecards are primary; a composite cannot hide a failed dimension",
        remediation="Make separate scorecards and the Pareto frontier primary outputs.",
        critical=True,
    )
    builder.add(
        "CV08",
        "Human or production anchors",
        _at(config, "evaluation.human_baselines") is True
        and _at(config, "evaluation.production_baselines") is True,
        observed={
            "human": _at(config, "evaluation.human_baselines"),
            "production": _at(config, "evaluation.production_baselines"),
        },
        requirement="Both qualified-human and incumbent-production baselines",
        remediation="Add baselines that make model scores interpretable in deployment terms.",
    )
    return builder.finish()


def _statistical_validity(config: Mapping[str, Any]) -> DimensionResult:
    builder = _DimensionBuilder("statistical_validity")
    items = _number(_at(config, "sampling.minimum_items"))
    repeats = _number(_at(config, "sampling.repeats_per_item"))
    strata = _at(config, "sampling.stratification_fields", [])
    builder.add(
        "ST01",
        "Adequate item count",
        items is not None and items >= 300,
        observed=items,
        requirement="At least 300 scored items, increased by prospective power analysis where needed",
        remediation="Increase the evaluation pool; do not infer global rankings from a tiny slice.",
        critical=True,
    )
    builder.add(
        "ST02",
        "Generation repeats",
        repeats is not None and repeats >= 3,
        observed=repeats,
        requirement="At least 3 independent generations per stochastic item/system",
        remediation="Run multiple epochs so generation variance can be separated from item variance.",
        critical=True,
    )
    builder.add(
        "ST03",
        "Prospective power analysis",
        _at(config, "statistics.prospective_power_analysis") is True
        and _nonempty(_at(config, "statistics.minimum_detectable_effect")),
        observed={
            "enabled": _at(config, "statistics.prospective_power_analysis"),
            "mde": _at(config, "statistics.minimum_detectable_effect"),
        },
        requirement="Pre-run power analysis with a minimum detectable effect",
        remediation="Size each primary track for its predeclared effect size.",
        critical=True,
    )
    builder.add(
        "ST04",
        "Representative stratification",
        _count(strata) >= 5,
        observed=strata,
        requirement="At least 5 design strata, including task and difficulty",
        remediation="Stratify the sample across capabilities, difficulty, language, modality, and source.",
    )
    builder.add(
        "ST05",
        "Hierarchical uncertainty",
        _at(config, "statistics.hierarchical_item_generation_model") is True
        and _at(config, "statistics.cluster_robust_uncertainty") is True,
        observed={
            "hierarchical": _at(config, "statistics.hierarchical_item_generation_model"),
            "cluster_robust": _at(config, "statistics.cluster_robust_uncertainty"),
        },
        requirement="Separate item, repeat, and cluster variance",
        remediation="Use hierarchical/cluster-aware estimation rather than treating every row as IID.",
        critical=True,
    )
    builder.add(
        "ST06",
        "Intervals and effect sizes",
        _at(config, "statistics.confidence_intervals") is True
        and _at(config, "statistics.effect_sizes") is True,
        observed={
            "ci": _at(config, "statistics.confidence_intervals"),
            "effects": _at(config, "statistics.effect_sizes"),
        },
        requirement="Confidence intervals and paired effect sizes for all primary comparisons",
        remediation="Report uncertainty and effect sizes, not only ranks and point estimates.",
    )
    builder.add(
        "ST07",
        "Multiplicity and equivalence",
        _at(config, "statistics.multiplicity_control") in {"holm", "hochberg", "closed-testing"}
        and _number(_at(config, "statistics.practical_equivalence_margin")) is not None,
        observed={
            "control": _at(config, "statistics.multiplicity_control"),
            "margin": _at(config, "statistics.practical_equivalence_margin"),
        },
        requirement="Family-wise error control plus a predeclared equivalence margin",
        remediation="Control leaderboard-wide comparisons and distinguish no evidence from equivalence.",
    )
    builder.add(
        "ST08",
        "Missingness and sensitivity analysis",
        _at(config, "statistics.failures_score_zero") is True
        and _at(config, "statistics.missingness_sensitivity_analysis") is True,
        observed={
            "failure_zero": _at(config, "statistics.failures_score_zero"),
            "sensitivity": _at(config, "statistics.missingness_sensitivity_analysis"),
        },
        requirement="Failure-aware primary scoring and sensitivity bounds for unknown data",
        remediation="Preserve the planned denominator and publish best/worst-case missing-data bounds.",
    )
    builder.add(
        "ST09",
        "Temporal replication",
        (_number(_at(config, "operations.measurement_days")) or 0) >= 3,
        observed=_at(config, "operations.measurement_days"),
        requirement="Measurements across at least 3 independent days/windows",
        remediation="Repeat across time to avoid treating a transient provider state as a model trait.",
    )
    return builder.finish()


def _coverage(config: Mapping[str, Any]) -> DimensionResult:
    builder = _DimensionBuilder("coverage_and_representativeness")
    tracks = {str(item) for item in _at(config, "evaluation.tracks", [])}
    modalities = {str(item) for item in _at(config, "coverage.modalities", [])}
    systems = _at(config, "systems", [])
    declared_modalities: set[str] = set()
    if isinstance(systems, Sequence):
        for system in systems:
            if isinstance(system, Mapping):
                declared_modalities.update(map(str, system.get("input_modalities", [])))
    checks = (
        ("CO01", "Core track coverage", CORE_TRACKS.issubset(tracks), sorted(tracks), "All 12 core tracks", "Add every core track or narrow the benchmark's claim."),
        ("CO02", "Production-shaped task share", (_number(_at(config, "coverage.production_task_fraction")) or 0) >= 0.25, _at(config, "coverage.production_task_fraction"), "At least 25% production-shaped tasks", "Add real, privacy-reviewed workflows weighted by deployment traffic."),
        ("CO03", "Language breadth", (_number(_at(config, "coverage.language_count")) or 0) >= 8, _at(config, "coverage.language_count"), "At least 8 languages", "Add languages representative of intended users."),
        ("CO04", "Language-family breadth", (_number(_at(config, "coverage.language_family_count")) or 0) >= 4, _at(config, "coverage.language_family_count"), "At least 4 language families", "Avoid counting only closely related high-resource languages."),
        ("CO05", "Locale and cultural review", _at(config, "coverage.native_speaker_review") is True and (_number(_at(config, "coverage.locale_count")) or 0) >= 8, {"review": _at(config, "coverage.native_speaker_review"), "locales": _at(config, "coverage.locale_count")}, "Native-speaker review across at least 8 locales", "Use local reviewers for translation, cultural validity, and harms."),
        ("CO06", "Advertised modality coverage", declared_modalities.issubset(modalities) and bool(modalities), {"declared": sorted(declared_modalities), "tested": sorted(modalities)}, "Every advertised input modality is tested", "Add modality-specific tasks or remove unsupported claims."),
        ("CO07", "Context-length curve", _count(_at(config, "coverage.context_length_buckets", [])) >= 5, _at(config, "coverage.context_length_buckets"), "At least 5 context-length buckets", "Measure a performance curve rather than a single context point."),
        ("CO08", "Difficulty calibration", _count(_at(config, "coverage.difficulty_bands", [])) >= 4, _at(config, "coverage.difficulty_bands"), "At least 4 calibrated difficulty bands", "Include non-saturated tasks and report results by difficulty."),
        ("CO09", "Multi-turn and tool workflows", _at(config, "coverage.multi_turn") is True and _at(config, "coverage.tool_use") is True, {"multi_turn": _at(config, "coverage.multi_turn"), "tool_use": _at(config, "coverage.tool_use")}, "Both multi-turn and tool-using tasks", "Add stateful, outcome-verified workflows."),
        ("CO10", "Worst-slice reporting", _at(config, "coverage.worst_slice_reporting") is True, _at(config, "coverage.worst_slice_reporting"), "Report worst slices and disparities", "Publish slice sample sizes, intervals, and worst-group performance."),
    )
    for check_id, title, passed, observed, requirement, remediation in checks:
        builder.add(check_id, title, passed, observed=observed, requirement=requirement, remediation=remediation, critical=check_id in {"CO01", "CO06"})
    return builder.finish()


def _freshness(config: Mapping[str, Any]) -> DimensionResult:
    builder = _DimensionBuilder("freshness_and_contamination_control")
    max_age = _number(_at(config, "freshness.maximum_item_age_days"))
    private_fraction = _number(_at(config, "freshness.private_holdout_fraction"))
    entries = (
        ("FR01", "Fresh item ceiling", max_age is not None and max_age <= 180, max_age, "Maximum item age of 180 days", "Use a continuously refreshed pool and record actual item dates.", True),
        ("FR02", "Private holdout", private_fraction is not None and private_fraction >= 0.2, private_fraction, "At least 20% private or access-controlled holdout", "Maintain a secure holdout unavailable during model development.", True),
        ("FR03", "Rolling refresh", _at(config, "freshness.rolling_refresh") is True, _at(config, "freshness.rolling_refresh"), "Versioned rolling refresh policy", "Define item retirement, replacement, and re-evaluation cadence.", False),
        ("FR04", "Contamination audit", _at(config, "freshness.contamination_audit") is True, _at(config, "freshness.contamination_audit"), "Lexical, semantic, and answer-reproduction checks", "Audit training/test leakage and publish the audit method.", True),
        ("FR05", "Canary items", _at(config, "freshness.canary_items") is True, _at(config, "freshness.canary_items"), "Canaries for leakage and benchmark awareness", "Seed trackable items and define an incident threshold.", False),
        ("FR06", "Cross-source deduplication", _at(config, "freshness.semantic_deduplication") is True, _at(config, "freshness.semantic_deduplication"), "Exact and semantic deduplication across splits/sources", "Remove paraphrases and shared-answer leakage across datasets.", False),
        ("FR07", "Leakage response policy", _nonempty(_at(config, "freshness.leakage_response_policy")), _at(config, "freshness.leakage_response_policy"), "Predeclared quarantine, invalidation, and rerun policy", "State how contaminated results are corrected and versioned.", False),
        ("FR08", "Plan frozen before inference", _at(config, "freshness.freeze_before_inference") is True, _at(config, "freshness.freeze_before_inference"), "Content-addressed plan frozen before provider calls", "Freeze IDs, graders, weights, and exclusions before inference.", True),
        ("FR09", "Broken-item review", _at(config, "freshness.blind_broken_item_review") is True, _at(config, "freshness.blind_broken_item_review"), "Blind review and predeclared exclusion rules", "Review ambiguous/broken tasks without seeing model identity.", False),
    )
    for check_id, title, passed, observed, requirement, remediation, critical in entries:
        builder.add(check_id, title, passed, observed=observed, requirement=requirement, remediation=remediation, critical=critical)
    return builder.finish()


def _fairness(config: Mapping[str, Any]) -> DimensionResult:
    builder = _DimensionBuilder("fairness_and_comparability")
    regimes = _at(config, "fairness.elicitation_regimes", [])
    entries = (
        ("FA01", "Dual elicitation regimes", _subset({"controlled", "provider-optimized"}, regimes), regimes, "Controlled and provider-optimized regimes", "Publish equal-budget and credible maximum-elicitation results separately.", True),
        ("FA02", "Equal resource budgets", _at(config, "fairness.equal_resource_budgets") is True, _at(config, "fairness.equal_resource_budgets"), "Turns, tokens, time, tools, attempts, and cost budgets are explicit", "Fix resource budgets for controlled comparisons.", True),
        ("FA03", "Provider-recommended settings", _at(config, "fairness.provider_recommended_settings") is True, _at(config, "fairness.provider_recommended_settings"), "Documented provider settings in optimized regime", "Record settings and sources without mixing them into controlled results.", False),
        ("FA04", "Reasoning and sampling disclosure", _at(config, "fairness.reasoning_and_sampling_disclosed") is True, _at(config, "fairness.reasoning_and_sampling_disclosed"), "Reasoning effort, temperature, seed, caps, and hidden-token treatment", "Capture effective—not merely requested—generation parameters.", False),
        ("FA05", "Order randomization", _at(config, "fairness.randomized_interleaving") is True, _at(config, "fairness.randomized_interleaving"), "Blocked randomization/interleaving across systems", "Avoid sequential provider blocks.", True),
        ("FA06", "Tokenizer-normalized efficiency", _at(config, "fairness.normalized_token_measure") is True, _at(config, "fairness.normalized_token_measure"), "Provider-native billing plus a common text/token unit", "Report native billing and standardized output volume separately.", False),
        ("FA07", "Exact system identity", _at(config, "fairness.immutable_system_snapshots") is True, _at(config, "fairness.immutable_system_snapshots"), "Immutable model/endpoint/version/region/safeguard identity", "Reject mutable aliases as the only identity.", True),
        ("FA08", "Refusal and safety-policy handling", _nonempty(_at(config, "fairness.refusal_policy")), _at(config, "fairness.refusal_policy"), "Predeclared refusal, block, and policy-conflict scoring", "Separate capability failures from expected safeguard behavior.", False),
        ("FA09", "Open and closed divisions", _subset({"closed", "open"}, _at(config, "fairness.divisions", [])), _at(config, "fairness.divisions"), "Closed comparable and open optimized divisions", "Borrow MLPerf-style divisions to preserve both fairness and innovation.", False),
    )
    for check_id, title, passed, observed, requirement, remediation, critical in entries:
        builder.add(check_id, title, passed, observed=observed, requirement=requirement, remediation=remediation, critical=critical)
    return builder.finish()


def _reproducibility(config: Mapping[str, Any]) -> DimensionResult:
    builder = _DimensionBuilder("reproducibility_and_traceability")
    entries = (
        ("RE01", "Pinned code and harness", _at(config, "reproducibility.pinned_code") is True and _at(config, "reproducibility.pinned_harness") is True, {"code": _at(config, "reproducibility.pinned_code"), "harness": _at(config, "reproducibility.pinned_harness")}, "Content-addressed code and harness", "Record immutable commits and patches.", True),
        ("RE02", "Pinned environment", _at(config, "reproducibility.container_or_lockfile") is True and _at(config, "reproducibility.hardware_and_region_manifest") is True, {"environment": _at(config, "reproducibility.container_or_lockfile"), "hardware": _at(config, "reproducibility.hardware_and_region_manifest")}, "Rebuildable dependencies plus hardware/region manifest", "Publish lockfiles/container digests and infrastructure description.", False),
        ("RE03", "Dataset and plan hashes", _at(config, "reproducibility.content_hashes") is True, _at(config, "reproducibility.content_hashes"), "Hashes for eligible pool, plan, prompts, graders, and artifacts", "Hash content rather than relying only on filenames or release labels.", True),
        ("RE04", "Machine-readable schemas", _at(config, "reproducibility.machine_readable_schemas") is True, _at(config, "reproducibility.machine_readable_schemas"), "Versioned schemas for systems, calls, answers, judgments, and reports", "Publish validation schemas and reject invalid submissions.", False),
        ("RE05", "Raw artifact access", _at(config, "reproducibility.public_raw_artifacts") is True, _at(config, "reproducibility.public_raw_artifacts"), "Privacy-reviewed prompts, outputs, calls, and judgments", "Publish artifacts or provide controlled auditor access where privacy forbids release.", True),
        ("RE06", "One-command replay", _at(config, "reproducibility.one_command_replay") is True, _at(config, "reproducibility.one_command_replay"), "Offline report reconstruction and documented inference replay", "Make every table reproducible without editing source.", False),
        ("RE07", "Signed transparency log", _at(config, "reproducibility.signed_append_only_log") is True, _at(config, "reproducibility.signed_append_only_log"), "Signed append-only run and correction log", "Sign manifests and retain superseded/invalidated results.", True),
        ("RE08", "End-to-end lineage", _at(config, "reproducibility.answer_judgment_call_lineage") is True, _at(config, "reproducibility.answer_judgment_call_lineage"), "Unique lineage from plan to attempts, answer, judgment, and report", "Enforce referential integrity and deny incomplete publication.", True),
        ("RE09", "Software and data bill of materials", _at(config, "reproducibility.sbom_and_data_provenance") is True, _at(config, "reproducibility.sbom_and_data_provenance"), "SBOM, licenses, data origin, transformations, and grader provenance", "Record the complete evaluation supply chain.", False),
    )
    for check_id, title, passed, observed, requirement, remediation, critical in entries:
        builder.add(check_id, title, passed, observed=observed, requirement=requirement, remediation=remediation, critical=critical)
    return builder.finish()


def _operations(config: Mapping[str, Any]) -> DimensionResult:
    builder = _DimensionBuilder("operational_realism")
    streaming = set(map(str, _at(config, "operations.streaming_metrics", [])))
    load = set(map(str, _at(config, "operations.load_scenarios", [])))
    entries = (
        ("OP01", "Temporal and regional spread", (_number(_at(config, "operations.measurement_days")) or 0) >= 3 and (_number(_at(config, "operations.regions")) or 0) >= 3, {"days": _at(config, "operations.measurement_days"), "regions": _at(config, "operations.regions")}, "At least 3 days and 3 regions", "Measure service behavior across independent times and regions.", True),
        ("OP02", "Load scenarios", {"offline", "interactive", "server"}.issubset(load), sorted(load), "Offline, interactive, and server scenarios", "Use scenario-specific latency/throughput constraints.", False),
        ("OP03", "Concurrency curve", _count(_at(config, "operations.concurrency_levels", [])) >= 3, _at(config, "operations.concurrency_levels"), "At least 3 concurrency/load levels", "Measure saturation rather than a single concurrency setting.", False),
        ("OP04", "Streaming latency", {"ttft", "ttfa", "tpot", "e2e"}.issubset(streaming), sorted(streaming), "TTFT, first-answer token, TPOT, and end-to-end latency", "Use streaming instrumentation and separate reasoning from answer latency.", False),
        ("OP05", "Tail sample adequacy", (_number(_at(config, "operations.minimum_requests_per_system")) or 0) >= 1000, _at(config, "operations.minimum_requests_per_system"), "At least 1,000 requests/system for operational tails", "Collect enough observations before reporting p95/p99/SLO rates.", True),
        ("OP06", "Retry-inclusive accounting", _at(config, "operations.retry_inclusive") is True and _at(config, "operations.transport_retries_disabled_or_observed") is True, {"retry_inclusive": _at(config, "operations.retry_inclusive"), "transport_observed": _at(config, "operations.transport_retries_disabled_or_observed")}, "All attempts, hidden transport retries, time, tokens, and cost are observed", "Disable opaque SDK retries or instrument them.", True),
        ("OP07", "Error taxonomy and availability", _at(config, "operations.error_taxonomy") is True and _at(config, "operations.availability_and_goodput") is True, {"taxonomy": _at(config, "operations.error_taxonomy"), "goodput": _at(config, "operations.availability_and_goodput")}, "Versioned errors plus failure-aware availability/goodput", "Keep failures in the denominator and distinguish provider/model/policy/harness failures.", False),
        ("OP08", "Cost and successful-outcome economics", _at(config, "operations.cost_per_success") is True and _at(config, "operations.budget_qualified_goodput") is True, {"cost_per_success": _at(config, "operations.cost_per_success"), "goodput": _at(config, "operations.budget_qualified_goodput")}, "Cost per successful outcome and cost-budget goodput", "Use observed billed cost and sensitivity ranges for modeled prices.", False),
        ("OP09", "Energy and environmental metrics", _at(config, "operations.energy_and_carbon") is True, _at(config, "operations.energy_and_carbon"), "Measured or supplier-attested energy and carbon with boundaries", "Report energy/request and carbon assumptions separately from price.", False),
        ("OP10", "Longitudinal drift", _at(config, "operations.drift_monitoring") is True, _at(config, "operations.drift_monitoring"), "Scheduled re-runs, change-point detection, and alias drift alerts", "Treat managed endpoints as changing systems.", False),
    )
    for check_id, title, passed, observed, requirement, remediation, critical in entries:
        builder.add(check_id, title, passed, observed=observed, requirement=requirement, remediation=remediation, critical=critical)
    return builder.finish()


def _trustworthiness(config: Mapping[str, Any]) -> DimensionResult:
    builder = _DimensionBuilder("safety_security_and_trustworthiness")
    required = {
        "harmful-content",
        "jailbreak-robustness",
        "privacy",
        "bias-and-fairness",
        "factuality",
        "cybersecurity",
        "overrefusal",
        "deception",
    }
    domains = set(map(str, _at(config, "trustworthiness.domains", [])))
    entries = (
        ("TR01", "Trustworthiness domain coverage", required.issubset(domains), sorted(domains), "Eight core trustworthiness domains", "Add missing risk domains and publish separate results.", True),
        ("TR02", "Threat models", _nonempty(_at(config, "trustworthiness.threat_models")), _at(config, "trustworthiness.threat_models"), "Explicit actors, capabilities, assets, and harm thresholds", "Tie each safety evaluation to a concrete threat model.", True),
        ("TR03", "Independent red team", _at(config, "trustworthiness.independent_red_team") is True, _at(config, "trustworthiness.independent_red_team"), "Independent, conflict-disclosed red teaming", "Include external domain experts and preserve negative findings.", False),
        ("TR04", "Adaptive adversarial testing", _at(config, "trustworthiness.adaptive_attacks") is True, _at(config, "trustworthiness.adaptive_attacks"), "Multi-turn, tool-aware, adaptive attacks under defined budgets", "Test realistic adversaries, not only static prompt lists.", False),
        ("TR05", "Multilingual and multimodal safety", _at(config, "trustworthiness.cross_language_modality") is True, _at(config, "trustworthiness.cross_language_modality"), "Safety coverage across claimed languages/modalities", "Probe policy consistency outside English text.", False),
        ("TR06", "Human escalation outcomes", _at(config, "trustworthiness.human_escalation") is True, _at(config, "trustworthiness.human_escalation"), "Escalation precision, recall, burden, and resolution quality", "Evaluate the socio-technical system, not only model output.", False),
        ("TR07", "Privacy and legal review", _at(config, "trustworthiness.privacy_legal_review") is True, _at(config, "trustworthiness.privacy_legal_review"), "Documented privacy, consent, retention, and jurisdiction review", "Review test data and artifact publication before execution.", True),
        ("TR08", "Uncertainty and abstention", _at(config, "trustworthiness.calibration_and_abstention") is True, _at(config, "trustworthiness.calibration_and_abstention"), "Calibration, selective risk, and appropriate abstention", "Measure confidence/abstention against hard outcomes on adequate samples.", False),
        ("TR09", "Incident simulation", _at(config, "trustworthiness.incident_and_failover_tests") is True, _at(config, "trustworthiness.incident_and_failover_tests"), "Stateful incidents, degraded dependencies, failover, and recovery", "Test operational safety under realistic failures.", False),
    )
    for check_id, title, passed, observed, requirement, remediation, critical in entries:
        builder.add(check_id, title, passed, observed=observed, requirement=requirement, remediation=remediation, critical=critical)
    return builder.finish()


def _system_evaluation(config: Mapping[str, Any]) -> DimensionResult:
    builder = _DimensionBuilder("system_classification_and_specialized_evaluation")
    systems = _at(config, "systems", [])
    valid_profiles = isinstance(systems, Sequence) and len(systems) >= 2
    required_fields = {
        "system_id",
        "provider",
        "system_type",
        "deployment_scope",
        "access_mode",
        "version",
        "input_modalities",
        "output_modalities",
        "declared_capabilities",
    }
    if valid_profiles:
        valid_profiles = all(
            isinstance(system, Mapping)
            and required_fields.issubset(system)
            and system.get("system_type") in SYSTEM_TYPES
            and system.get("deployment_scope") in DEPLOYMENT_SCOPES
            and system.get("access_mode") in ACCESS_MODES
            and _nonempty(system.get("version"))
            for system in systems
        )
    system_types = {
        str(system.get("system_type"))
        for system in systems
        if isinstance(system, Mapping)
    } if isinstance(systems, Sequence) else set()
    router_present = bool(system_types & {"router", "ensemble"})
    agent_present = bool(system_types & {"agent", "application"})
    embedding_present = "embedding-model" in system_types or "reranker" in system_types
    router_ok = not router_present or (
        _at(config, "specialized.router.full_candidate_counterfactuals") is True
        and _subset(
            {"best-single", "uniform-random", "oracle"},
            _at(config, "specialized.router.baselines", []),
        )
        and _at(config, "specialized.router.regret_calibration_stability") is True
    )
    agent_ok = not agent_present or (
        _at(config, "specialized.agent.outcome_state_verification") is True
        and _at(config, "specialized.agent.long_horizon_trajectories") is True
    )
    retrieval_ok = not embedding_present or (
        _at(config, "specialized.retrieval.ir_metrics") is True
        and _at(config, "specialized.retrieval.hard_negatives") is True
    )
    entries = (
        ("SY01", "Complete system taxonomy", valid_profiles, len(systems) if isinstance(systems, Sequence) else systems, "At least 2 fully classified immutable systems", "Populate the system card fields and validate enum values.", True),
        ("SY02", "Scope-appropriate comparisons", _at(config, "specialized.no_cross_scope_ranking") is True, _at(config, "specialized.no_cross_scope_ranking"), "Models, endpoints, routers, and applications are not silently mixed", "Publish separate divisions or explicitly label system-to-system comparisons.", True),
        ("SY03", "Router/ensemble evaluation", router_ok, {"required": router_present, "configured": router_ok}, "Full candidate counterfactuals, baselines, regret, calibration, and stability", "Benchmark every possible route and repeat routing decisions.", router_present),
        ("SY04", "Agent/application evaluation", agent_ok, {"required": agent_present, "configured": agent_ok}, "Long-horizon outcome/state verification", "Grade environment outcomes, side effects, and trajectory budgets.", agent_present),
        ("SY05", "Embedding/reranker evaluation", retrieval_ok, {"required": embedding_present, "configured": retrieval_ok}, "IR metrics, hard negatives, multilingual and domain slices", "Use nDCG/MRR/recall and calibrated retrieval datasets.", embedding_present),
        ("SY06", "Modality-specific graders", _at(config, "specialized.modality_specific_graders") is True, _at(config, "specialized.modality_specific_graders"), "Validated graders for each advertised modality", "Do not force non-text outputs through a generic text judge.", False),
        ("SY07", "Judge validation", _at(config, "specialized.judge_human_validation") is True and (_number(_at(config, "specialized.minimum_judge_human_agreement")) or 0) >= 0.8, {"validated": _at(config, "specialized.judge_human_validation"), "agreement": _at(config, "specialized.minimum_judge_human_agreement")}, "Blind human validation with >=0.80 agreement target", "Validate automated graders by task, language, model family, and score band.", True),
        ("SY08", "Judge-bias controls", _at(config, "specialized.multi_family_judge_panel") is True and _at(config, "specialized.blinded_and_randomized_judging") is True, {"panel": _at(config, "specialized.multi_family_judge_panel"), "blind": _at(config, "specialized.blinded_and_randomized_judging")}, "Multi-family panel, blind labels, randomized order, position-bias checks", "Use objective graders where possible and audited panels otherwise.", False),
        ("SY09", "Capability saturation policy", _at(config, "specialized.saturation_retirement_threshold") is not None, _at(config, "specialized.saturation_retirement_threshold"), "Predeclared task retirement/replacement threshold", "Retire tracks that no longer discriminate systems.", False),
    )
    for check_id, title, passed, observed, requirement, remediation, critical in entries:
        builder.add(check_id, title, passed, observed=observed, requirement=requirement, remediation=remediation, critical=critical)
    return builder.finish()


def _governance(config: Mapping[str, Any]) -> DimensionResult:
    builder = _DimensionBuilder("governance_and_external_auditability")
    entries = (
        ("GO01", "Versioned public protocol", _nonempty(_at(config, "governance.protocol_version")) and _at(config, "governance.public_protocol") is True, {"version": _at(config, "governance.protocol_version"), "public": _at(config, "governance.public_protocol")}, "Public semantic version, scope, and normative rules", "Publish the protocol and preserve every superseded version.", True),
        ("GO02", "Preregistration", _at(config, "governance.preregistration_required") is True, _at(config, "governance.preregistration_required"), "Timestamped hypotheses, endpoints, exclusions, and analysis plan", "Preregister before revealing model identities/results.", True),
        ("GO03", "Independent review plan", (_number(_at(config, "governance.minimum_independent_reviewers")) or 0) >= 2 and (_number(_at(config, "governance.minimum_replicating_organizations")) or 0) >= 2, {"reviewers": _at(config, "governance.minimum_independent_reviewers"), "replications": _at(config, "governance.minimum_replicating_organizations")}, "At least 2 external reviewers and 2 independent replications", "Create a neutral review board and fund independent replication.", True),
        ("GO04", "Conflict and funding disclosure", _at(config, "governance.conflict_disclosure") is True and _at(config, "governance.funding_disclosure") is True, {"conflicts": _at(config, "governance.conflict_disclosure"), "funding": _at(config, "governance.funding_disclosure")}, "Public conflicts, funding, credits, and vendor participation", "Disclose incentives and prohibit result-contingent compensation.", False),
        ("GO05", "Public change process", _at(config, "governance.public_comment_and_change_control") is True, _at(config, "governance.public_comment_and_change_control"), "Public RFC, change log, compatibility policy, and deprecation window", "Use open multistakeholder governance for normative changes.", False),
        ("GO06", "Appeals and corrections", _at(config, "governance.appeals_and_corrections") is True, _at(config, "governance.appeals_and_corrections"), "Time-bounded appeal, adjudication, correction, and invalidation process", "Let providers and researchers challenge broken items or identities transparently.", False),
        ("GO07", "Benchmark card", _at(config, "governance.benchmark_card") is True, _at(config, "governance.benchmark_card"), "Claim, population, construction, limitations, risks, and intended use", "Publish a benchmark card with every release.", False),
        ("GO08", "Inclusive governance", (_number(_at(config, "governance.stakeholder_groups")) or 0) >= 4 and (_number(_at(config, "governance.geographic_regions")) or 0) >= 3, {"stakeholders": _at(config, "governance.stakeholder_groups"), "regions": _at(config, "governance.geographic_regions")}, "At least 4 stakeholder groups across 3 world regions", "Include academia, industry, civil society, deployers, and affected communities.", False),
        ("GO09", "Ethics, accessibility, and licensing", _at(config, "governance.ethics_accessibility_license_review") is True, _at(config, "governance.ethics_accessibility_license_review"), "Ethics, accessibility, data rights, licenses, and participant protections", "Complete review before data collection or publication.", True),
        ("GO10", "Standards crosswalk", _subset({"NIST-AI-RMF", "ISO-IEC-25059", "ISO-IEC-23894", "ISO-IEC-42001", "MLPerf-principles"}, _at(config, "governance.standards_crosswalk", [])), _at(config, "governance.standards_crosswalk"), "Crosswalk to NIST, ISO quality/risk/governance, and MLPerf principles", "Maintain a clause-level, versioned standards mapping.", False),
    )
    for check_id, title, passed, observed, requirement, remediation, critical in entries:
        builder.add(check_id, title, passed, observed=observed, requirement=requirement, remediation=remediation, critical=critical)
    return builder.finish()


DIMENSION_BUILDERS: tuple[Callable[[Mapping[str, Any]], DimensionResult], ...] = (
    _construct_validity,
    _statistical_validity,
    _coverage,
    _freshness,
    _fairness,
    _reproducibility,
    _operations,
    _trustworthiness,
    _system_evaluation,
    _governance,
)


def _config_hash(config: Mapping[str, Any]) -> str:
    serialized = json.dumps(config, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _execution_blockers(config: Mapping[str, Any]) -> list[str]:
    if _at(config, "study.status") != "executed":
        return ["Study status is not 'executed'; design readiness is not result validity."]
    requirements = {
        "evidence.preregistration_uri": "Timestamped preregistration evidence is missing.",
        "evidence.raw_artifact_bundle_uri": "Privacy-reviewed raw artifact bundle is missing.",
        "evidence.signed_manifest_uri": "Signed run manifest/transparency-log evidence is missing.",
        "evidence.independent_review_uri": "Independent review report is missing.",
        "evidence.replication_reports": "Independent replication reports are missing.",
        "evidence.benchmark_card_uri": "Public benchmark card is missing.",
        "evidence.standards_crosswalk_uri": "Published standards crosswalk is missing.",
    }
    blockers = [message for path, message in requirements.items() if not _nonempty(_at(config, path))]
    replications = _at(config, "evidence.replication_reports", [])
    if _count(replications) < 2:
        blockers.append("At least two independent replication reports are required.")
    if _at(config, "evidence.protocol_deviations_resolved") is not True:
        blockers.append("Protocol deviations are unresolved or not documented.")
    if _at(config, "evidence.all_primary_tracks_adequately_powered") is not True:
        blockers.append("Not all primary tracks have demonstrated adequate statistical power.")
    return blockers


def audit_protocol(config: Mapping[str, Any]) -> ProtocolAudit:
    dimensions = tuple(builder(config) for builder in DIMENSION_BUILDERS)
    scores = [dimension.score for dimension in dimensions]
    if any(score <= 0 for score in scores):
        design_score = 0.0
    else:
        design_score = math.exp(sum(math.log(score) for score in scores) / len(scores))
    design_score = round(design_score, 2)
    minimum = min(scores, default=0.0)
    design_ready = bool(dimensions) and all(dimension.passed for dimension in dimensions)
    blockers = _execution_blockers(config)
    execution_ready = design_ready and not blockers
    return ProtocolAudit(
        protocol_name=PROTOCOL_NAME,
        protocol_version=PROTOCOL_VERSION,
        config_sha256=_config_hash(config),
        dimensions=dimensions,
        design_score=design_score,
        minimum_dimension_score=minimum,
        design_ready=design_ready,
        execution_ready=execution_ready,
        evidence_bundle_structurally_complete=execution_ready,
        # Software can verify declarations, schemas, hashes, and internal
        # consistency. It cannot award international legitimacy or certify the
        # substantive adequacy and independence of external evidence.
        global_publication_candidate=False,
        execution_blockers=tuple(blockers),
    )


def load_protocol(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Protocol configuration must be a JSON object")
    repository_schema = (
        Path(__file__).resolve().parents[2]
        / "config"
        / "global-protocol-v1.schema.json"
    )
    if repository_schema.is_file():
        schema = json.loads(repository_schema.read_text(encoding="utf-8"))
    else:
        resource = importlib.resources.files("kendr_bench").joinpath(
            "schemas/global-protocol-v1.schema.json"
        )
        schema = json.loads(resource.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    failures = sorted(validator.iter_errors(value), key=lambda error: list(error.path))
    if failures:
        messages = []
        for error in failures[:20]:
            location = ".".join(str(part) for part in error.absolute_path) or "<root>"
            messages.append(f"{location}: {error.message}")
        if len(failures) > 20:
            messages.append(f"... and {len(failures) - 20} more schema errors")
        raise ValueError("Protocol schema validation failed:\n" + "\n".join(messages))
    return value


def render_audit_markdown(audit: ProtocolAudit) -> str:
    state = (
        "DESIGN READY; EVIDENCE REFERENCES STRUCTURALLY COMPLETE; EXTERNAL REVIEW REQUIRED"
        if audit.evidence_bundle_structurally_complete
        else "DESIGN READY; EXECUTION EVIDENCE REQUIRED"
        if audit.design_ready
        else "PILOT / NOT DESIGN READY"
    )
    lines = [
        f"# {audit.protocol_name} audit",
        "",
        f"- Protocol: `{audit.protocol_version}`",
        f"- Configuration SHA-256: `{audit.config_sha256}`",
        f"- State: **{state}**",
        f"- Geometric design score: **{audit.design_score:.2f}/10**",
        f"- Minimum dimension: **{audit.minimum_dimension_score:.2f}/10**",
        f"- Rule: every dimension must be strictly above {DESIGN_THRESHOLD:.1f}; averaging cannot compensate for a weak dimension.",
        "",
        "## Dimension scorecard",
        "",
        "| Dimension | Score | Gate | Failed checks |",
        "| --- | ---: | --- | ---: |",
    ]
    for dimension in audit.dimensions:
        lines.append(
            f"| {dimension.dimension.replace('_', ' ').title()} | "
            f"{dimension.score:.2f} | {'PASS' if dimension.passed else 'FAIL'} | "
            f"{len(dimension.failed_checks)} |"
        )
    failed = [
        (dimension.dimension, check)
        for dimension in audit.dimensions
        for check in dimension.failed_checks
    ]
    lines.extend(["", "## Required improvements", ""])
    if failed:
        for dimension, check in failed:
            critical = " **[critical]**" if check.critical else ""
            lines.extend(
                [
                    f"### {check.check_id}: {check.title}{critical}",
                    "",
                    f"- Dimension: `{dimension}`",
                    f"- Requirement: {check.requirement}",
                    f"- Observed: `{json.dumps(check.observed, ensure_ascii=False, default=str)}`",
                    f"- Action: {check.remediation}",
                    "",
                ]
            )
    else:
        lines.append("No design-gate failures.")
    lines.extend(["", "## Execution/publication blockers", ""])
    if audit.execution_blockers:
        lines.extend(f"- {blocker}" for blocker in audit.execution_blockers)
    else:
        lines.append(
            "No structural evidence-reference blockers. This software does not "
            "validate the substantive adequacy, independence, or authority of the evidence."
        )
    lines.extend(
        [
            "",
            "> Passing this automated audit is necessary, not sufficient. The audit evaluates "
            "declarations and structural evidence references, not truth or "
            "conformity. It never awards global-publication, certification, or international-acceptance "
            "status. Independent replication, multistakeholder governance, peer review, and authorized "
            "standards or conformity-assessment processes remain external.",
            "",
        ]
    )
    return "\n".join(lines)
