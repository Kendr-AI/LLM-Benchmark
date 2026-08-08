from __future__ import annotations

import argparse
import csv
import itertools
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import __version__
from .cli import load_environment
from .livebench_cli import (
    DEFAULT_LIVEBENCH_ROOT,
    DEFAULT_PRICING_PATH,
    _positive_decimal,
    _positive_int,
    _run_id,
    _safe_label,
    _write_artifact_hashes,
    load_livebench_question_records,
    run_livebench,
    summarize_existing_run,
)
from .providers import KENDR_DEFAULT_USD_PER_CREDIT
from .routing import compute_routing_benchmarks, extract_answer_routes
from .sampling import SamplingError, select_question_ids
from .scoring import (
    bootstrap_ci,
    category_scores,
    failed_question_ids,
    holm_adjust,
    paired_deltas,
    paired_randomization_test,
    separation_tiers,
    stable_seed,
)

DEFAULT_MATRIX_RELEASE = "2026-06-25"
DEFAULT_MATRIX_TASKS = (
    "live_bench/data_analysis/tablejoin",
    "live_bench/instruction_following/summarize",
    "live_bench/language/connections",
    "live_bench/math/math_comp",
    "live_bench/reasoning/zebra_puzzle",
)

SOURCE_PACKAGE = "llm-benchmark-protocol"
SOURCE_REPOSITORY = "https://github.com/Kendr-AI/LLM-Benchmark"


def _git_text(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _execution_software_provenance(root: Path | None = None) -> dict[str, Any]:
    """Capture the exact source revision and deterministic dirty-worktree bit.

    A dirty checkout is valid execution evidence and is recorded rather than
    rejected. A missing Git identity is different: without a commit the
    campaign cannot provide the required source lineage, so matrix creation
    fails before any provider calls are made.
    """

    candidates = [root] if root is not None else [
        Path(__file__).resolve().parents[2],
        Path.cwd(),
    ]
    inspected: set[Path] = set()
    failures: list[str] = []
    for candidate in candidates:
        if candidate is None:
            continue
        resolved = candidate.resolve()
        if resolved in inspected:
            continue
        inspected.add(resolved)
        try:
            repository_root = Path(
                _git_text(resolved, "rev-parse", "--show-toplevel")
            ).resolve()
            commit = _git_text(repository_root, "rev-parse", "HEAD")
            if not re.fullmatch(r"[0-9a-f]{40,64}", commit):
                raise RuntimeError(f"unexpected Git commit format {commit!r}")
            status = _git_text(
                repository_root,
                "status",
                "--porcelain=v1",
                "--untracked-files=normal",
            )
            return {
                "package": SOURCE_PACKAGE,
                "version": __version__,
                "source_repository": SOURCE_REPOSITORY,
                "source_commit": commit,
                "source_worktree_dirty": bool(status),
            }
        except (OSError, subprocess.CalledProcessError, RuntimeError) as exc:
            failures.append(f"{resolved}: {exc}")
    raise RuntimeError(
        "Unable to capture benchmark source commit before matrix execution. "
        + "; ".join(failures)
    )


def _unit_interval(value: str) -> float:
    parsed = float(value)
    if not 0 <= parsed <= 1:
        raise argparse.ArgumentTypeError("must be between zero and one")
    return parsed


@dataclass(frozen=True)
class ModelSpec:
    key: str
    provider: str
    model: str
    label: str
    access: str
    license: str
    license_source: str


DEFAULT_MODEL_PANEL = (
    ModelSpec(
        key="kendr-intelligent",
        provider="kendr",
        model="kendr-intelligent",
        label="Kendr Intelligent",
        access="Kendr routed system",
        license="Proprietary service",
        license_source="https://github.com/Kendr-AI/Kendr",
    ),
    ModelSpec(
        key="claude-opus-5",
        provider="kendr",
        model="kc-bedrock-anthropic-claude-opus-5",
        label="Claude Opus 5",
        access="Proprietary via Kendr (Amazon Bedrock)",
        license="Proprietary",
        license_source="https://www.anthropic.com/legal/commercial-terms",
    ),
    ModelSpec(
        key="claude-opus-4-8",
        provider="kendr",
        model="kc-claude-opus-4.8",
        label="Claude Opus 4.8",
        access="Proprietary via Kendr (Amazon Bedrock)",
        license="Proprietary",
        license_source="https://www.anthropic.com/legal/commercial-terms",
    ),
    ModelSpec(
        key="openai-sol",
        provider="openai",
        model="gpt-5.6-sol",
        label="OpenAI GPT-5.6 Sol",
        access="Direct proprietary API",
        license="Proprietary",
        license_source=(
            "https://developers.openai.com/api/docs/models/gpt-5.6-sol"
        ),
    ),
    ModelSpec(
        key="openai-terra",
        provider="openai",
        model="gpt-5.6-terra",
        label="OpenAI GPT-5.6 Terra",
        access="Direct proprietary API",
        license="Proprietary",
        license_source=(
            "https://developers.openai.com/api/docs/models/gpt-5.6-terra"
        ),
    ),
    ModelSpec(
        key="glm-5",
        provider="kendr",
        model="kc-glm-5",
        label="GLM-5",
        access="Open-weight via Kendr",
        license="Apache-2.0",
        license_source="https://github.com/zai-org/GLM-5",
    ),
    ModelSpec(
        key="deepseek-v3-2",
        provider="kendr",
        model="kc-deepseek-v3.2",
        label="DeepSeek V3.2",
        access="Open-weight via Kendr",
        license="MIT",
        license_source="https://huggingface.co/deepseek-ai/DeepSeek-V3.2",
    ),
    ModelSpec(
        key="kimi-k2-5",
        provider="kendr",
        model="kc-kimi-k2.5",
        label="Kimi K2.5",
        access="Open-weight via Kendr",
        license="Modified MIT",
        license_source="https://github.com/MoonshotAI/Kimi-K2.5",
    ),
    ModelSpec(
        key="llama-4-maverick",
        provider="kendr",
        model="kc-llama-4-maverick",
        label="Llama 4 Maverick",
        access="Open-weight via Kendr",
        license="Llama 4 Community",
        license_source=(
            "https://github.com/meta-llama/llama-models/"
            "blob/main/models/llama4/LICENSE"
        ),
    ),
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="llm-benchmark-matrix",
        description=(
            "Run the same LiveBench slice across Kendr, direct OpenAI, and "
            "Kendr-hosted open-weight models, then build a leaderboard."
        ),
    )
    parser.add_argument(
        "--livebench-root",
        type=Path,
        default=DEFAULT_LIVEBENCH_ROOT,
    )
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--no-env-file", action="store_true")
    parser.add_argument(
        "--output", type=Path, default=Path("results/matrix")
    )
    parser.add_argument(
        "--release", default=DEFAULT_MATRIX_RELEASE
    )
    parser.add_argument(
        "--task",
        action="append",
        dest="tasks",
        help="LiveBench task path; repeat to replace the default five tasks",
    )
    parser.add_argument(
        "--questions-per-task", type=_positive_int, default=3
    )
    parser.add_argument(
        "--sample-mode",
        choices=("seeded-random", "newest-first"),
        default="seeded-random",
        help=(
            "Deterministic within-task selection mode; never relies on "
            "dataset row order (default: seeded-random)"
        ),
    )
    parser.add_argument(
        "--sample-seed",
        type=int,
        default=20260801,
        help="Explicit deterministic sample seed (default: 20260801)",
    )
    parser.add_argument(
        "--minimum-release-date",
        default=None,
        help=(
            "Inclusive YYYY-MM-DD freshness floor. The release option itself "
            "is cumulative and does not imply this floor."
        ),
    )
    parser.add_argument("--max-tokens", type=_positive_int, default=2048)
    parser.add_argument(
        "--deadline-ms",
        type=_positive_int,
        default=120_000,
        help=(
            "Final-answer deadline including retries (default: 120000 ms)"
        ),
    )
    parser.add_argument(
        "--max-cost-usd-per-answer",
        type=_positive_decimal,
        default=None,
        help="Optional per-question USD budget including retries",
    )
    parser.add_argument(
        "--practical-equivalence-margin",
        type=_unit_interval,
        default=0.02,
        help=(
            "Absolute score margin used to identify practically equivalent "
            "paired effects (default: 0.02)"
        ),
    )
    parser.add_argument(
        "--parallel-requests", type=_positive_int, default=2
    )
    parser.add_argument(
        "--parallel-grading", type=_positive_int, default=4
    )
    parser.add_argument(
        "--include",
        action="append",
        choices=[model.key for model in DEFAULT_MODEL_PANEL],
        help="Panel key to include; repeat to select a subset",
    )
    parser.add_argument(
        "--panel-file",
        type=Path,
        help=(
            "JSON array of ModelSpec objects used instead of the built-in "
            "panel; enables a frozen provider-catalog campaign"
        ),
    )
    parser.add_argument(
        "--pricing", type=Path, default=DEFAULT_PRICING_PATH
    )
    parser.add_argument(
        "--kendr-usd-per-credit",
        type=_positive_decimal,
        default=KENDR_DEFAULT_USD_PER_CREDIT,
    )
    parser.add_argument(
        "--reasoning-effort",
        default="none",
        help="Reasoning effort for direct OpenAI baselines",
    )
    parser.add_argument("--label", default="popular-models")
    parser.add_argument(
        "--confirm-paid-run",
        action="store_true",
        help="Required because the default matrix makes chargeable API calls",
    )
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help=(
            "Resolve and persist the exact sampled IDs/provenance without "
            "making provider calls; does not require --confirm-paid-run"
        ),
    )
    parser.add_argument(
        "--rebuild",
        type=Path,
        help=(
            "Recompute summaries and leaderboard for an existing matrix "
            "without making API calls"
        ),
    )
    parser.add_argument(
        "--resume-matrix",
        type=Path,
        help=(
            "Continue an interrupted paid matrix in place. Completed trials "
            "with captured provider calls are reused; only panel identities "
            "with no captured trial are submitted."
        ),
    )
    return parser


def _selected_panel(
    keys: Sequence[str] | None,
    panel_file: Path | None = None,
) -> list[ModelSpec]:
    if panel_file is not None:
        if keys:
            raise RuntimeError("--include cannot be combined with --panel-file")
        try:
            raw = json.loads(panel_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Invalid panel JSON: {exc}") from exc
        if not isinstance(raw, list) or not raw:
            raise RuntimeError("Panel file must contain a non-empty JSON array")
        try:
            panel = [ModelSpec(**item) for item in raw]
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"Invalid ModelSpec in panel file: {exc}") from exc
        keys_seen = [model.key for model in panel]
        identities = [(model.provider, model.model) for model in panel]
        if len(set(keys_seen)) != len(keys_seen):
            raise RuntimeError("Panel model keys must be unique")
        if len(set(identities)) != len(identities):
            raise RuntimeError("Panel provider/model identities must be unique")
        return panel
    if not keys:
        return list(DEFAULT_MODEL_PANEL)
    selected = set(keys)
    return [
        model for model in DEFAULT_MODEL_PANEL if model.key in selected
    ]


def _read_records(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
    return records


def _failed_question_ids(path: Path) -> set[str]:
    return failed_question_ids(_read_records(path))


def _category_scores(
    path: Path, answers_path: Path | None = None
) -> dict[str, float]:
    failed = (
        _failed_question_ids(answers_path)
        if answers_path is not None
        else set()
    )
    return category_scores(_read_records(path), failed)


def _question_scores(
    path: Path,
    answers_path: Path,
    planned_question_ids: Sequence[str] | None = None,
) -> dict[str, float]:
    """Per-question failure-normalized scores, for paired comparisons."""
    failed = _failed_question_ids(answers_path)
    answer_ids = {
        str(record.get("question_id"))
        for record in _read_records(answers_path)
        if record.get("question_id")
    }
    planned = {
        str(question_id): 0.0
        for question_id in (planned_question_ids or [])
    }
    scores: dict[str, float] = dict(planned)
    for record in _read_records(path):
        if record.get("score") in (None, -1):
            continue
        question_id = str(record.get("question_id"))
        if planned and question_id not in planned:
            continue
        scores[question_id] = (
            0.0
            if question_id in failed or question_id not in answer_ids
            else float(record["score"])
        )
    return scores


def _planned_ids(run_dir: Path) -> list[str]:
    path = run_dir / "manifest.json"
    if not path.is_file():
        return []
    manifest = json.loads(path.read_text(encoding="utf-8"))
    return [
        str(question_id)
        for question_id in (manifest.get("planned_question_ids") or [])
    ]


def _leaderboard_row(
    spec: ModelSpec,
    run_dir: Path,
    summary: Mapping[str, Any],
) -> dict[str, Any]:
    api = summary["current_api_run"]
    quality = summary["current_run_quality"]
    efficiency = summary["efficiency"]
    latency = summary["latency"]["end_to_end_ms"]
    successful_attempt_latency = summary["latency"].get(
        "successful_attempt_ms", latency
    )
    attempt_latency = summary["latency"].get("attempt_ms", {})
    failed_latency = summary["latency"].get("failed_request_ms", {})
    reliability = summary["reliability"]
    cap_conformance = reliability.get(
        "operational_output_cap_conformance", {}
    )
    operations = summary.get("operations") or {}
    retries = operations.get("retries") or {}
    operational_question_scores = {
        str(item["question_id"]): float(
            item.get("score_weighted_goodput") or 0.0
        )
        for item in (operations.get("question_results") or [])
        if item.get("question_id")
    }
    operational_interval = (
        bootstrap_ci(
            list(operational_question_scores.values()),
            seed=stable_seed(f"{spec.key}|operational-goodput"),
        )
        if operational_question_scores
        else {}
    )
    categories = dict(
        quality.get("category_scores")
        or _category_scores(
            run_dir / "judgments.jsonl", run_dir / "answers.jsonl"
        )
    )
    interval = quality.get("quality_ci95") or {}
    successful_answers = reliability["successful_answers"]
    failed_answers = reliability["failed_answers"]
    attempted_answers = int(
        quality.get("score_denominator")
        or successful_answers + failed_answers
    )
    end_to_end_quality_score = quality["objective_score_mean"]
    conditional_quality_score = _safe_divide(
        quality["quality_points"], successful_answers
    )
    cost_per_successful_answer = _safe_divide(
        api.get("cost_usd"), successful_answers
    )
    row: dict[str, Any] = {
        "rank": None,
        "model": spec.label,
        "panel_key": spec.key,
        "provider": spec.provider,
        "requested_model": spec.model,
        "access": spec.access,
        "license": spec.license,
        "license_source": spec.license_source,
        "questions_scored": quality["questions_scored"],
        "quality_points": quality["quality_points"],
        "quality_score": end_to_end_quality_score,
        "score_weighted_operational_goodput": reliability.get(
            "score_weighted_goodput", {}
        ).get("conservative_mean"),
        "binary_operational_goodput": reliability.get(
            "operational_goodput", {}
        ).get("conservative_rate"),
        "operational_goodput_ci95_low": operational_interval.get("low"),
        "operational_goodput_ci95_high": operational_interval.get("high"),
        "operational_goodput_ci95_degenerate": operational_interval.get(
            "degenerate"
        ),
        "quality_ci95_low": interval.get("low"),
        "quality_ci95_high": interval.get("high"),
        "quality_ci95_degenerate": interval.get("degenerate"),
        "tier": None,
        "end_to_end_quality_score": end_to_end_quality_score,
        "conditional_quality_score": conditional_quality_score,
        "availability": reliability["answer_success_rate"],
        "perfect_score_rate": quality["perfect_score_rate"],
        "nonzero_score_rate": quality["nonzero_score_rate"],
        "input_tokens": api["input_tokens"],
        "output_tokens": api["output_tokens"],
        "total_tokens": api["total_tokens"],
        "token_total_is_lower_bound": bool(
            api.get("token_total_is_lower_bound")
        ),
        "cost_usd": api.get("cost_usd"),
        "cost_total_is_lower_bound": bool(
            api.get("cost_total_is_lower_bound")
        ),
        "cost_per_successful_answer": cost_per_successful_answer,
        "kendr_credits": api.get("kendr_credits"),
        "latency_mean_ms": latency["mean"],
        "latency_p50_ms": latency["p50"],
        "latency_p95_ms": latency["p95"],
        "successful_latency_mean_ms": successful_attempt_latency["mean"],
        "successful_latency_p50_ms": successful_attempt_latency["p50"],
        "successful_latency_p95_ms": successful_attempt_latency["p95"],
        "attempt_latency_p50_ms": attempt_latency.get("p50"),
        "attempt_latency_p95_ms": attempt_latency.get("p95"),
        "retry_attempt_amplification": retries.get(
            "observed_attempt_amplification"
        ),
        "retry_latency_amplification": retries.get(
            "latency_amplification"
        ),
        "failed_latency_mean_ms": failed_latency.get("mean"),
        "failed_latency_p50_ms": failed_latency.get("p50"),
        "failed_latency_p95_ms": failed_latency.get("p95"),
        "output_tokens_per_second": efficiency[
            "output_tokens_per_second"
        ],
        "tokens_per_quality_point": efficiency[
            "total_tokens_per_quality_point"
        ],
        "quality_points_per_1000_tokens": efficiency[
            "quality_points_per_1000_tokens"
        ],
        "usd_per_quality_point": efficiency[
            "usd_per_quality_point"
        ],
        "quality_points_per_usd": efficiency[
            "quality_points_per_usd"
        ],
        "attempted_answers": attempted_answers,
        "successful_answers": successful_answers,
        "failed_answers": failed_answers,
        "missing_answers": reliability.get("missing_answers", 0),
        "answer_success_rate": reliability["answer_success_rate"],
        "scoring_coverage": reliability["scoring_coverage"],
        "output_cap_compliance_rate": cap_conformance.get(
            "conservative_rate",
            reliability["output_cap_compliance_rate"],
        ),
        "output_cap_measured_rate": cap_conformance.get(
            "measured_rate", reliability["output_cap_compliance_rate"]
        ),
        "output_cap_unknown_questions": cap_conformance.get("unknown", 0),
        "deadline_conformance_rate": reliability.get(
            "deadline_conformance", {}
        ).get("conservative_rate"),
        "budget_conformance_rate": reliability.get(
            "budget_conformance", {}
        ).get("conservative_rate"),
        "complete": (summary.get("completeness") or {}).get("complete"),
        "route_distribution": reliability["route_distribution"],
        "provider_error_distribution": reliability[
            "provider_error_distribution"
        ],
        "run_dir": str(run_dir),
        # Underscore-prefixed keys stay out of the published CSV/JSON; they only
        # feed tiering and paired comparisons.
        "_question_scores": _question_scores(
            run_dir / "judgments.jsonl",
            run_dir / "answers.jsonl",
            _planned_ids(run_dir),
        ),
        "_ranking_question_scores": (
            operational_question_scores
            or _question_scores(
                run_dir / "judgments.jsonl",
                run_dir / "answers.jsonl",
                _planned_ids(run_dir),
            )
        ),
        "_routes": extract_answer_routes(
            _read_records(run_dir / "answers.jsonl")
        ),
        "_capability_keys": sorted(categories),
    }
    for category, score in categories.items():
        row[f"{category}_score"] = score
    return row


def _ranking_key(
    row: Mapping[str, Any],
) -> tuple[float, float, float, float]:
    objective_quality = row.get("quality_score")
    goodput = row.get("score_weighted_operational_goodput")
    if goodput is None:
        goodput = objective_quality
    cost = (
        None
        if row.get("cost_total_is_lower_bound")
        else row.get("cost_usd")
    )
    latency = row.get("latency_p50_ms")
    return (
        -float(goodput) if goodput is not None else float("inf"),
        -float(objective_quality)
        if objective_quality is not None
        else float("inf"),
        float(cost) if cost is not None else float("inf"),
        float(latency) if latency is not None else float("inf"),
    )


def _percent(value: Any) -> str:
    return f"{float(value) * 100:.1f}%" if value is not None else "n/a"


def _number(value: Any, digits: int = 1) -> str:
    return f"{float(value):,.{digits}f}" if value is not None else "n/a"


def _money(value: Any) -> str:
    return f"${Decimal(str(value)):.6f}" if value is not None else "n/a"


def _multiplier(value: Any) -> str:
    return f"{float(value):.2f}×" if value is not None else "n/a"


def _safe_divide(numerator: Any, denominator: Any) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return float(numerator) / float(denominator)


def _write_leaderboard(
    root: Path,
    *,
    matrix_id: str,
    rows: list[dict[str, Any]],
    failures: list[dict[str, str]],
    tasks: Sequence[str],
    release: str,
    questions_per_task: int,
    max_tokens: int,
    parallel_requests: int,
    practical_equivalence_margin: float = 0.02,
) -> None:
    if not 0 <= practical_equivalence_margin <= 1:
        raise ValueError(
            "practical_equivalence_margin must be between zero and one"
        )
    ordered = sorted(rows, key=_ranking_key)
    for rank, row in enumerate(ordered, 1):
        row["rank"] = rank

    tiers = separation_tiers(
        [
            (
                row["panel_key"],
                {
                    "low": (
                        row.get("operational_goodput_ci95_low")
                        if row.get("score_weighted_operational_goodput")
                        is not None
                        else row.get("quality_ci95_low")
                    ),
                    "high": (
                        row.get("operational_goodput_ci95_high")
                        if row.get("score_weighted_operational_goodput")
                        is not None
                        else row.get("quality_ci95_high")
                    ),
                },
            )
            for row in ordered
        ]
    )
    for row in ordered:
        row["tier"] = tiers.get(row["panel_key"])

    # Pre-specify the full family. Testing only whichever endpoints happen to
    # land adjacent after observing results is post-selection and ignores the
    # many comparisons readers naturally make from a leaderboard.
    pairwise: list[dict[str, Any]] = []
    raw_p_values: dict[str, float | None] = {}
    for higher, lower in itertools.combinations(ordered, 2):
        pair_metric = (
            "score_weighted_operational_goodput"
            if higher.get("score_weighted_operational_goodput") is not None
            and lower.get("score_weighted_operational_goodput") is not None
            else "objective_score"
        )
        deltas = paired_deltas(
            higher.get("_ranking_question_scores")
            or higher.get("_question_scores")
            or {},
            lower.get("_ranking_question_scores")
            or lower.get("_question_scores")
            or {},
        )
        if not deltas:
            continue
        interval = bootstrap_ci(
            deltas,
            seed=stable_seed(
                f"{higher['panel_key']}|{lower['panel_key']}"
            ),
        )
        low, high = interval["low"], interval["high"]
        pair_key = f"{higher['panel_key']}|{lower['panel_key']}"
        randomization = paired_randomization_test(
            deltas, seed=stable_seed(pair_key)
        )
        raw_p_values[pair_key] = randomization["p_value"]
        pairwise.append(
            {
                "comparison_id": pair_key,
                "metric": pair_metric,
                "higher_ranked": higher["model"],
                "lower_ranked": lower["model"],
                "higher_panel_key": higher["panel_key"],
                "lower_panel_key": lower["panel_key"],
                "questions_compared": len(deltas),
                "mean_difference": sum(deltas) / len(deltas),
                "ci95_low": low,
                "ci95_high": high,
                "separates_at_95": bool(
                    low is not None
                    and high is not None
                    and (low > 0 or high < 0)
                ),
                "practical_equivalence_margin": (
                    practical_equivalence_margin
                ),
                "practically_equivalent_at_95": bool(
                    low is not None
                    and high is not None
                    and low >= -practical_equivalence_margin
                    and high <= practical_equivalence_margin
                ),
                "randomization_p_value": randomization["p_value"],
                "randomization_method": randomization["method"],
                "randomization_permutations": randomization[
                    "permutations"
                ],
                "nonzero_pairs": randomization["nonzero_pairs"],
                "wins_higher_ranked": sum(delta > 0 for delta in deltas),
                "wins_lower_ranked": sum(delta < 0 for delta in deltas),
                "ties": sum(delta == 0 for delta in deltas),
            }
        )
    adjusted = holm_adjust(raw_p_values)
    for item in pairwise:
        adjusted_p = adjusted[item["comparison_id"]]
        item["holm_adjusted_p_value"] = adjusted_p
        item["separates_at_fwer_05"] = bool(
            adjusted_p is not None and adjusted_p <= 0.05
        )
    adjacent_keys = {
        f"{higher['panel_key']}|{lower['panel_key']}"
        for higher, lower in zip(ordered, ordered[1:])
    }
    adjacent = [
        item for item in pairwise if item["comparison_id"] in adjacent_keys
    ]

    # Discover capabilities from what each run actually graded. Scanning for a
    # "_score" suffix also swept up the two overall-quality columns and rendered
    # them as if they were capabilities.
    categories = sorted(
        {
            key
            for row in ordered
            for key in (row.get("_capability_keys") or [])
        }
    )
    routing_benchmarks = compute_routing_benchmarks(ordered)
    published = [
        {
            key: value
            for key, value in row.items()
            if not key.startswith("_")
        }
        for row in ordered
    ]
    json_document = {
        "matrix_id": matrix_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "livebench_release": release,
        "tasks": list(tasks),
        "questions_per_task": questions_per_task,
        "requested_max_output_tokens": max_tokens,
        "parallel_requests": parallel_requests,
        "ranking_rule": (
            "Conservative score-weighted operational goodput descending when "
            "available, otherwise official question-weighted objective score; "
            "objective quality, complete estimated/reported USD, then cumulative "
            "final-answer p50 latency are tie-breakers. "
            "Rank order is finer than the sample resolves. `tier` is a "
            "descriptive marginal-interval grouping only; inferential claims "
            "use paired randomization tests with Holm family-wise correction."
        ),
        "results": published,
        "pairwise_test_family": {
            "comparisons": len(pairwise),
            "test": "two-sided paired sign-randomization",
            "multiplicity_correction": "Holm family-wise error rate",
            "alpha": 0.05,
            "practical_equivalence_margin": practical_equivalence_margin,
        },
        "pairwise_tests": pairwise,
        "adjacent_pair_tests": adjacent,
        "routing_benchmarks": routing_benchmarks,
        "failures": failures,
    }
    (root / "leaderboard.json").write_text(
        json.dumps(json_document, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    fieldnames: list[str] = []
    for row in published:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with (root / "leaderboard.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in published:
            writer.writerow(
                {
                    key: json.dumps(value, sort_keys=True)
                    if isinstance(value, (dict, list))
                    else value
                    for key, value in row.items()
                }
            )

    lines = [
        f"# Popular-model LiveBench leaderboard: {matrix_id}",
        "",
        "This is an observed endpoint-as-served run, not a table of vendor "
        "claims. Every model received the same question slice and the same "
        "*requested* output cap; check the cap-compliance column before reading "
        "the token and cost axes as controlled.",
        "",
        "## Overall leaderboard",
        "",
        "Ranks are printed in full for traceability. Tiers only group "
        "overlapping marginal intervals; they neither prove a difference nor "
        "prove equivalence. The paired tests below are the inferential result.",
        "",
        "| Rank | Tier | Model | Access | Goodput | E2E quality | Ranking "
        "95% CI | "
        "Conditional quality | "
        "Availability | Scored | Cost | p50 final-answer latency | "
        "p50 failed latency | Total tokens | Tokens / quality point | "
        "Cap compliance |",
        "|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in ordered:
        has_goodput = row.get("score_weighted_operational_goodput") is not None
        ci_low = (
            row.get("operational_goodput_ci95_low")
            if has_goodput
            else row.get("quality_ci95_low")
        )
        ci_high = (
            row.get("operational_goodput_ci95_high")
            if has_goodput
            else row.get("quality_ci95_high")
        )
        ci_degenerate = (
            row.get("operational_goodput_ci95_degenerate")
            if has_goodput
            else row.get("quality_ci95_degenerate")
        )
        ci_text = (
            f"{_percent(ci_low)}–{_percent(ci_high)}"
            + ("*" if ci_degenerate else "")
            if ci_low is not None and ci_high is not None
            else "n/a"
        )
        lines.append(
            f"| {row['rank']} | {row.get('tier') or 'n/a'} | {row['model']} | "
            f"{row['access']} | "
            f"{_percent(row.get('score_weighted_operational_goodput'))} | "
            f"{_percent(row.get('end_to_end_quality_score', row.get('quality_score')))} | "
            f"{ci_text} | "
            f"{_percent(row.get('conditional_quality_score'))} | "
            f"{_percent(row.get('availability', row.get('answer_success_rate')))} | "
            f"{row['questions_scored']} | "
            f"{'≥' if row.get('cost_total_is_lower_bound') else ''}"
            f"{_money(row['cost_usd'])} | "
            f"{_number(row['latency_p50_ms'])} ms | "
            f"{_number(row.get('failed_latency_p50_ms'))} ms | "
            f"{'≥' if row.get('token_total_is_lower_bound') else ''}"
            f"{row['total_tokens']:,} | "
            f"{'≥' if row.get('token_total_is_lower_bound') else ''}"
            f"{_number(row['tokens_per_quality_point'])} | "
            f"{_percent(row['output_cap_compliance_rate'])} |"
        )

    if any(
        row.get("operational_goodput_ci95_degenerate")
        if row.get("score_weighted_operational_goodput") is not None
        else row.get("quality_ci95_degenerate")
        for row in ordered
    ):
        lines.extend(
            [
                "",
                "`*` marks an interval whose bound is censored by the score "
                "scale or built from too few distinct resample values to read "
                "as a real limit. At this sample size a bound printed as "
                "`100.0%` means the resampled mean hit the ceiling, not that "
                "the endpoint is estimated to reach it.",
            ]
        )

    if adjacent:
        lines.extend(
            [
                "",
                "## Do adjacent rank gaps survive the pre-specified test family?",
                "",
                "All endpoint pairs are tested with a two-sided paired sign-"
                "randomization test, then corrected together with Holm's "
                "family-wise procedure. This table shows the adjacent subset; "
                "`leaderboard.json` contains the complete family.",
                "",
                "| Higher rank | Lower rank | Mean difference | 95% CI | "
                "W/L/T | Raw p | Holm p | FWER 5%? | Equivalent? |",
                "|---|---|---:|---:|---:|---:|---:|---|---|",
            ]
        )

        for item in adjacent:
            lines.append(
                f"| {item['higher_ranked']} | {item['lower_ranked']} | "
                f"{_percent(item['mean_difference'])} | "
                f"{_percent(item['ci95_low'])}–"
                f"{_percent(item['ci95_high'])} | "
                f"{item['wins_higher_ranked']}/"
                f"{item['wins_lower_ranked']}/{item['ties']} | "
                f"{_number(item['randomization_p_value'], 4)} | "
                f"{_number(item['holm_adjusted_p_value'], 4)} | "
                f"{'yes' if item['separates_at_fwer_05'] else 'no'} | "
                f"{'yes' if item['practically_equivalent_at_95'] else 'no'} |"
            )
        separated = sum(
            item["separates_at_fwer_05"] for item in adjacent
        )
        equivalent = sum(
            item["practically_equivalent_at_95"] for item in adjacent
        )
        lines.extend(
            [
                "",
                f"{separated} of {len(adjacent)} adjacent gaps are separated "
                "at family-wise 5%; "
                f"{equivalent} are contained within the predeclared +/-"
                f"{practical_equivalence_margin:.3f} practical margin. A gap "
                "that is neither significant nor equivalent is unresolved, "
                "not a tie.",
            ]
        )

    if routing_benchmarks.get("available"):
        router_metrics = routing_benchmarks["router"]
        best_single = routing_benchmarks["best_single_endpoint"]
        selection = routing_benchmarks[
            "observed_selection_counterfactual"
        ]
        calibration = routing_benchmarks["confidence_calibration"]
        lines.extend(
            [
                "",
                "## Router counterfactuals",
                "",
                routing_benchmarks["scope"],
                "",
                "| Routed score | Best single | Random endpoint | Panel "
                "oracle | Panel-oracle gap | Uplift vs best single |",
                "|---:|---:|---:|---:|---:|---:|",
                f"| {_percent(router_metrics['score'])} | "
                f"{best_single['model']} "
                f"({_percent(best_single['score'])}) | "
                f"{_percent(routing_benchmarks['random_endpoint_expected_score'])} | "
                f"{_percent(routing_benchmarks['panel_oracle_score'])} | "
                f"{_percent(router_metrics['gap_to_panel_oracle'])} | "
                f"{_percent(router_metrics['uplift_over_best_single'])} |",
                "",
                f"Observed selected-model counterfactual coverage: "
                f"{selection['matched_to_panel_endpoint']}/"
                f"{routing_benchmarks['questions']} planned questions "
                f"({_percent(selection['coverage_of_planned_questions'])}). "
                "Unmatched routes are not silently imputed.",
                "",
                f"Router-confidence calibration coverage: "
                f"{calibration['measured_questions']}/"
                f"{routing_benchmarks['questions']}; Brier score against "
                "realized objective quality: "
                f"{_number(calibration['brier_score_against_realized_quality'], 4)}; "
                "expected calibration error: "
                f"{_number(calibration['expected_calibration_error'], 4)}. "
                f"{calibration['warning']} With only this small set of soft "
                "objective-score targets, these values diagnose confidence–"
                "score mismatch rather than establish general calibration.",
            ]
        )

    baseline = next(
        (row for row in ordered if row["panel_key"] == "openai-sol"),
        None,
    )
    baseline_usd_per_quality = (
        baseline.get("usd_per_quality_point") if baseline else None
    )
    baseline_cost_is_lower_bound = bool(
        baseline and baseline.get("cost_total_is_lower_bound")
    )
    baseline_tokens_per_quality = (
        baseline.get("tokens_per_quality_point") if baseline else None
    )
    baseline_tokens_are_lower_bound = bool(
        baseline and baseline.get("token_total_is_lower_bound")
    )
    lines.extend(
        [
            "",
            "## Cost- and token-normalized efficiency",
            "",
            "Efficiency indices use direct OpenAI Sol as 1.00× and are shown "
            "only for endpoints with at least 80% answer success. Higher is "
            "better.",
            "",
            "| Model | Quality points | Total USD | Kendr credits | "
            "USD / quality point | Tokens / quality point | Cost efficiency "
            "vs Sol | Token efficiency vs Sol |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in ordered:
        reliable = (
            row.get("answer_success_rate") is not None
            and float(row["answer_success_rate"]) >= 0.8
        )
        usd_per_quality = row.get("usd_per_quality_point")
        tokens_per_quality = row.get("tokens_per_quality_point")
        cost_index = (
            float(baseline_usd_per_quality) / float(usd_per_quality)
            if reliable
            and baseline_usd_per_quality is not None
            and usd_per_quality not in (None, 0)
            else None
        )
        row_cost_is_lower_bound = bool(
            row.get("cost_total_is_lower_bound")
        )
        if row_cost_is_lower_bound and baseline_cost_is_lower_bound:
            cost_index_text = "n/a"
        elif row_cost_is_lower_bound:
            cost_index_text = f"≤{_multiplier(cost_index)}"
        elif baseline_cost_is_lower_bound:
            cost_index_text = f"≥{_multiplier(cost_index)}"
        else:
            cost_index_text = _multiplier(cost_index)
        token_index = (
            float(baseline_tokens_per_quality)
            / float(tokens_per_quality)
            if reliable
            and baseline_tokens_per_quality is not None
            and tokens_per_quality not in (None, 0)
            else None
        )
        row_tokens_are_lower_bound = bool(
            row.get("token_total_is_lower_bound")
        )
        if row_tokens_are_lower_bound and baseline_tokens_are_lower_bound:
            token_index_text = "n/a"
        elif row_tokens_are_lower_bound:
            token_index_text = f"≤{_multiplier(token_index)}"
        elif baseline_tokens_are_lower_bound:
            token_index_text = f"≥{_multiplier(token_index)}"
        else:
            token_index_text = _multiplier(token_index)
        lines.append(
            f"| {row['model']} | "
            f"{_number(row.get('quality_points'), 3)} | "
            f"{'≥' if row.get('cost_total_is_lower_bound') else ''}"
            f"{_money(row['cost_usd'])} | "
            f"{_number(row.get('kendr_credits'), 6)} | "
            f"{'≥' if row_cost_is_lower_bound else ''}"
            f"{_money(usd_per_quality)} | "
            f"{'≥' if row_tokens_are_lower_bound else ''}"
            f"{_number(tokens_per_quality)} | "
            f"{cost_index_text} | "
            f"{token_index_text} |"
        )

    if categories:
        lines.extend(
            [
                "",
                "## Quality by capability",
                "",
                "| Model | "
                + " | ".join(category.replace("_", " ").title() for category in categories)
                + " |",
                "|---|" + "|".join("---:" for _ in categories) + "|",
            ]
        )
        for row in ordered:
            lines.append(
                f"| {row['model']} | "
                + " | ".join(
                    _percent(row.get(f"{category}_score"))
                    for category in categories
                )
                + " |"
            )

    lines.extend(
        [
            "",
            "## Model panel",
            "",
            "| Model | Requested ID | Provider path | License / terms |",
            "|---|---|---|---|",
        ]
    )
    for row in ordered:
        lines.append(
            f"| {row['model']} | `{row['requested_model']}` | "
            f"{row['access']} | "
            f"[{row['license']}]({row['license_source']}) |"
        )

    lines.extend(
        [
            "",
            "## Endpoint reliability",
            "",
            "| Model | Final successes / planned | Attempt-level provider errors | "
            "Attempt-level selected routes |",
            "|---|---:|---|---|",
        ]
    )
    for row in ordered:
        errors = json.dumps(
            row.get("provider_error_distribution") or {}, sort_keys=True
        )
        routes = json.dumps(
            row.get("route_distribution") or {}, sort_keys=True
        )
        lines.append(
            f"| {row['model']} | "
            f"{row.get('successful_answers', 'n/a')} / "
            f"{row.get('attempted_answers', row['questions_scored'])} | "
            f"`{errors}` | `{routes}` |"
        )

    lines.extend(
        [
            "",
            "## Methodology and limits",
            "",
            f"- LiveBench release: `{release}`.",
            f"- Tasks: `{', '.join(tasks)}`.",
            f"- Sample: {questions_per_task} questions per task "
            f"({questions_per_task * len(tasks)} planned per model).",
            f"- Requested maximum output: {max_tokens} tokens per call.",
            f"- Request concurrency: {parallel_requests}.",
            "- Quality is the official task-specific objective LiveBench "
            "score. It is also the available relevance/correctness proxy; "
            "LiveBench does not produce a separate generic relevance score.",
            "- End-to-end quality includes availability failures in the "
            "denominator. Conditional quality divides the same quality points "
            "by successful answers only, so it answers how good the model was "
            "when it returned an answer.",
            "- A provider-failed `$ERROR$` answer is normalized to zero even "
            "if an instruction-format grader awards it incidental partial "
            "credit. Raw official judgments remain preserved per run.",
            "- Cost is provider-reported credits converted at the configured "
            "USD/credit rate for Kendr, and token-estimated standard API cost "
            "for direct OpenAI. These are different price bases: the Kendr "
            "figure is what was actually billed, including any service margin, "
            "while the OpenAI figure is undiscounted list price. Read cost "
            "ratios as what a buyer pays, not as inference-cost ratios.",
            "- Kendr Intelligent's router consumes tokens of its own on every "
            "request. Those tokens are inside the reported credits, and "
            "therefore inside its cost, but they are not in its token counts. "
            "Its tokens-per-quality-point is understated relative to a direct "
            "endpoint's.",
            f"- Requests ran at concurrency {parallel_requests}, so latency is "
            "measured under load rather than as isolated single requests. "
            "Endpoints ran in sequential blocks with one generation per "
            "question, so latency ordering is descriptive and may include "
            "time-of-run effects.",
            "- The cap column is conservative question-level conformance: "
            "unknown failed-attempt usage counts against the rate. A value "
            "below 100% means the output budget was violated or could not be "
            "verified, so token and cost comparisons need qualification.",
            "- `≥` and `≤` mark one-sided bounds when failed attempts lack "
            "usage or cost telemetry. Derived token/cost efficiency inherits "
            "the corresponding bound rather than being printed as exact.",
            "- Time to first token is unavailable because the instrumented "
            "path is non-streaming. Latency is client-observed end-to-end.",
            "- The current direct-OpenAI adapter disables hidden SDK retries; "
            "Kendr application retries and any benchmark-layer OpenAI retries "
            "are logged as separate attempts. Historical artifacts created "
            "before this policy may not have comparable attempt visibility.",
            "- Open-weight means model weights are available under the linked "
            "upstream terms. It does not imply every license is OSI-approved.",
            "- The latest classic LiveBench release has no active classic "
            "coding questions. Agentic coding is intentionally excluded "
            "because it requires a separate Docker/repository execution "
            "pipeline and should be reported independently.",
            "- A small stratified sample is useful for engineering decisions "
            "but is not a statistically definitive public leaderboard.",
        ]
    )
    if failures:
        lines.extend(["", "## Failures", ""])
        lines.extend(
            f"- `{item['model']}`: {item['error']}" for item in failures
        )
    (root / "leaderboard.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    _write_artifact_hashes(root)


def _catalog_snapshot(path: Path) -> None:
    try:
        import kendr

        records = kendr.Client().list_models()
    except Exception as exc:
        records = [{"catalog_error": f"{type(exc).__name__}: {exc}"}]
    path.write_text(
        json.dumps(records, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )


def _publish_latest(matrix_root: Path) -> None:
    parent = matrix_root.parent
    (parent / "latest.txt").write_text(
        str(matrix_root) + os.linesep, encoding="utf-8"
    )
    for suffix in ("md", "csv", "json"):
        shutil.copy2(
            matrix_root / f"leaderboard.{suffix}",
            parent / f"latest-leaderboard.{suffix}",
        )


def _require_complete_panel(
    *,
    rows: Sequence[Mapping[str, Any]],
    failures: Sequence[Mapping[str, Any]],
    expected_count: int,
    matrix_root: Path,
) -> None:
    """Prevent a partial matrix from becoming the successful latest result."""
    explicitly_incomplete = [
        row for row in rows if row.get("complete") is False
    ]
    if (
        not failures
        and not explicitly_incomplete
        and len(rows) == expected_count
    ):
        return
    eligible_count = len(rows) - len(explicitly_incomplete)
    raise RuntimeError(
        "Matrix is incomplete: "
        f"{eligible_count}/{expected_count} endpoints produced eligible results; "
        f"{len(failures)} failed. Partial artifacts were preserved at "
        f"{matrix_root}; latest was not updated."
    )


def _select_rebuild_run(
    run_dirs: Sequence[Path],
) -> tuple[Path | None, list[Path]]:
    """Select the first provider trial, never the cleanest later rerun.

    Manifest-only starts have no model outcome and may be skipped. Once a run
    has captured at least one provider call, it is the experiment for that
    endpoint. Choosing a later successful rerun after observing those calls is
    survivorship bias; an interrupted first trial must instead be finalized or
    remain an explicit matrix failure.
    """
    attempted: list[Path] = []
    for run_dir in sorted(run_dirs):
        call_log = run_dir / "calls.jsonl"
        if call_log.is_file() and call_log.stat().st_size > 0:
            attempted.append(run_dir)
    return (attempted[0] if attempted else None), attempted


def run_matrix(args: argparse.Namespace) -> Path:
    if not args.confirm_paid_run and not getattr(
        args, "preflight_only", False
    ):
        raise RuntimeError(
            "The multi-model matrix is chargeable. Re-run with "
            "--confirm-paid-run after reviewing the selected panel and sample."
        )
    execution_software = _execution_software_provenance()
    load_environment(args.env_file, disabled=args.no_env_file)
    panel = _selected_panel(args.include, getattr(args, "panel_file", None))
    tasks = tuple(args.tasks or DEFAULT_MATRIX_TASKS)
    try:
        source_questions = load_livebench_question_records(
            tasks, args.release
        )
        sampling = select_question_ids(
            source_questions,
            questions_per_stratum=args.questions_per_task,
            stratify_by=("category", "task"),
            seed=args.sample_seed,
            minimum_release_date=args.minimum_release_date,
            mode=args.sample_mode,
        )
    except SamplingError as exc:
        raise RuntimeError(f"Sample preflight failed: {exc}") from exc
    source_by_id = {
        str(record["question_id"]): record for record in source_questions
    }
    planned_questions = [
        source_by_id[question_id] for question_id in sampling.selected_ids
    ]
    matrix_id = _run_id(args.label)
    matrix_root = (args.output / matrix_id).resolve()
    matrix_root.mkdir(parents=True, exist_ok=False)
    runs_root = matrix_root / "runs"
    runs_root.mkdir()

    manifest = {
        "matrix_id": matrix_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "execution_software": execution_software,
        "models": [asdict(model) for model in panel],
        "livebench_release": args.release,
        "tasks": tasks,
        "questions_per_task": args.questions_per_task,
        "sampling": sampling.to_dict(),
        "max_tokens": args.max_tokens,
        "deadline_ms": args.deadline_ms,
        "max_cost_usd_per_answer": (
            format(args.max_cost_usd_per_answer, "f")
            if args.max_cost_usd_per_answer is not None
            else None
        ),
        "practical_equivalence_margin": (
            args.practical_equivalence_margin
        ),
        "parallel_requests": args.parallel_requests,
        "parallel_grading": args.parallel_grading,
        "reasoning_effort": args.reasoning_effort,
        "pricing_catalog": str(args.pricing.resolve()),
        "kendr_usd_per_credit": format(
            args.kendr_usd_per_credit, "f"
        ),
        "preflight_only": bool(getattr(args, "preflight_only", False)),
        "panel_file": (
            str(args.panel_file.resolve())
            if getattr(args, "panel_file", None) is not None
            else None
        ),
    }
    (matrix_root / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    if getattr(args, "preflight_only", False):
        (matrix_root / "sample-plan.json").write_text(
            json.dumps(
                {
                    "matrix_id": matrix_id,
                    "livebench_release": args.release,
                    "tasks": list(tasks),
                    "sampling": sampling.to_dict(),
                    "planned_questions": [
                        {
                            "question_id": str(record["question_id"]),
                            "category": str(record.get("category")),
                            "task": str(record.get("task")),
                            "livebench_release_date": str(
                                record.get("livebench_release_date")
                            ),
                        }
                        for record in planned_questions
                    ],
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        _write_artifact_hashes(matrix_root)
        return matrix_root

    _catalog_snapshot(matrix_root / "kendr_model_catalog.json")

    rows: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    suffix = _safe_label(matrix_id)[-12:]
    for index, spec in enumerate(panel, 1):
        print(
            f"\n[{index}/{len(panel)}] {spec.label} "
            f"({spec.provider}:{spec.model})"
        )
        run_args = argparse.Namespace(
            livebench_root=args.livebench_root,
            env_file=args.env_file,
            no_env_file=args.no_env_file,
            provider=spec.provider,
            model=spec.model,
            model_display_name=_safe_label(f"{spec.key}-{suffix}"),
            api_base=None,
            reasoning_effort=args.reasoning_effort,
            pricing=args.pricing,
            bench_name=list(tasks),
            livebench_release_option=args.release,
            max_tokens=args.max_tokens,
            parallel_requests=args.parallel_requests,
            practical_equivalence_margin=(
                args.practical_equivalence_margin
            ),
            parallel_grading=args.parallel_grading,
            question_begin=None,
            question_end=None,
            question_id=list(sampling.selected_ids),
            planned_questions=planned_questions,
            planned_question_ids=list(sampling.selected_ids),
            sampling_provenance=sampling.to_dict(),
            resume=False,
            retry_failures=False,
            skip_inference=False,
            skip_grading=False,
            ignore_missing_answers=True,
            deadline_ms=args.deadline_ms,
            max_cost_usd_per_answer=args.max_cost_usd_per_answer,
            allow_incomplete=False,
            kendr_usd_per_credit=args.kendr_usd_per_credit,
            output=runs_root,
            label=spec.key,
            confirm_full=False,
            compare_model=[],
        )
        try:
            run_dir, summary = run_livebench(run_args)
            rows.append(_leaderboard_row(spec, run_dir, summary))
        except Exception as exc:
            failures.append(
                {
                    "model": spec.label,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
        _write_leaderboard(
            matrix_root,
            matrix_id=matrix_id,
            rows=rows,
            failures=failures,
            tasks=tasks,
            release=args.release,
            questions_per_task=args.questions_per_task,
            max_tokens=args.max_tokens,
            parallel_requests=args.parallel_requests,
            practical_equivalence_margin=(
                args.practical_equivalence_margin
            ),
        )

    _require_complete_panel(
        rows=rows,
        failures=failures,
        expected_count=len(panel),
        matrix_root=matrix_root,
    )
    _publish_latest(matrix_root)
    return matrix_root


def rebuild_matrix(matrix_root: Path, livebench_root: Path) -> Path:
    matrix_root = matrix_root.resolve()
    manifest_path = matrix_root / "manifest.json"
    if not manifest_path.is_file():
        raise RuntimeError(f"Matrix manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_sampling = manifest.get("sampling") or {}
    specs = [ModelSpec(**item) for item in manifest["models"]]
    run_dirs = sorted((matrix_root / "runs").glob("*"))
    by_identity: dict[tuple[str, str], list[Path]] = {}
    for run_dir in run_dirs:
        run_manifest_path = run_dir / "manifest.json"
        if not run_manifest_path.is_file():
            continue
        run_manifest = json.loads(
            run_manifest_path.read_text(encoding="utf-8")
        )
        run_sampling = run_manifest.get("sampling") or {}
        if expected_sampling and (
            run_sampling.get("content_hash")
            != expected_sampling.get("content_hash")
            or run_sampling.get("selected_ids")
            != expected_sampling.get("selected_ids")
        ):
            raise RuntimeError(
                f"Run {run_dir.name} does not match the matrix sampling "
                "content hash and selected IDs."
            )
        by_identity.setdefault(
            (
                str(run_manifest.get("provider") or "kendr"),
                str(run_manifest.get("requested_model")),
            ),
            [],
        ).append(run_dir)

    rows: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    usd_per_credit = Decimal(
        str(
            manifest.get("kendr_usd_per_credit")
            or KENDR_DEFAULT_USD_PER_CREDIT
        )
    )
    for spec in specs:
        candidates = by_identity.get((spec.provider, spec.model)) or []
        run_dir, attempted_runs = _select_rebuild_run(candidates)
        if run_dir is None:
            failures.append(
                {
                    "model": spec.label,
                    "error": "No run with captured provider calls found",
                }
            )
            continue
        try:
            summary = summarize_existing_run(
                run_dir,
                livebench_root=livebench_root,
                usd_per_credit=usd_per_credit,
            )
            if (summary.get("completeness") or {}).get("complete") is False:
                raise RuntimeError(
                    "Earliest captured provider trial is incomplete; a later "
                    "rerun was not substituted. Finalize or diagnose the "
                    "first trial."
                )
            row = _leaderboard_row(spec, run_dir, summary)
            row["run_selection_policy"] = "earliest-captured-provider-trial"
            row["captured_trial_count"] = len(attempted_runs)
            row["excluded_later_trial_run_ids"] = [
                candidate.name for candidate in attempted_runs[1:]
            ]
            rows.append(row)
        except Exception as exc:
            failures.append(
                {
                    "model": spec.label,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    _write_leaderboard(
        matrix_root,
        matrix_id=str(manifest["matrix_id"]),
        rows=rows,
        failures=failures,
        tasks=manifest["tasks"],
        release=str(manifest["livebench_release"]),
        questions_per_task=int(manifest["questions_per_task"]),
        max_tokens=int(manifest["max_tokens"]),
        parallel_requests=int(manifest["parallel_requests"]),
        practical_equivalence_margin=float(
            manifest.get("practical_equivalence_margin", 0.02)
        ),
    )
    _require_complete_panel(
        rows=rows,
        failures=failures,
        expected_count=len(specs),
        matrix_root=matrix_root,
    )
    _publish_latest(matrix_root)
    return matrix_root


def resume_matrix(
    matrix_root: Path,
    livebench_root: Path,
    *,
    env_file: Path,
    no_env_file: bool,
) -> Path:
    """Continue a frozen matrix without replacing captured provider trials."""
    load_environment(env_file, disabled=no_env_file)
    matrix_root = matrix_root.resolve()
    manifest_path = matrix_root / "manifest.json"
    if not manifest_path.is_file():
        raise RuntimeError(f"Matrix manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("preflight_only"):
        raise RuntimeError("A preflight-only matrix cannot be resumed in place")

    specs = [ModelSpec(**item) for item in manifest["models"]]
    runs_root = matrix_root / "runs"
    runs_root.mkdir(exist_ok=True)
    expected_sampling = manifest.get("sampling") or {}
    expected_ids = list(expected_sampling.get("selected_ids") or [])
    if not expected_ids:
        raise RuntimeError("Frozen matrix manifest has no selected question IDs")

    planned_questions: list[dict[str, Any]] | None = None
    for candidate in sorted(runs_root.glob("*")):
        candidate_manifest_path = candidate / "manifest.json"
        if not candidate_manifest_path.is_file():
            continue
        candidate_manifest = json.loads(
            candidate_manifest_path.read_text(encoding="utf-8")
        )
        candidate_sampling = candidate_manifest.get("sampling") or {}
        if (
            candidate_sampling.get("content_hash")
            == expected_sampling.get("content_hash")
            and candidate_sampling.get("selected_ids") == expected_ids
            and candidate_manifest.get("planned_questions")
        ):
            planned_questions = list(candidate_manifest["planned_questions"])
            break
    if planned_questions is None:
        raise RuntimeError(
            "No matching captured run contains the frozen question descriptors; "
            "resume cannot safely reconstruct the study."
        )

    def captured_candidates(spec: ModelSpec) -> list[Path]:
        matches: list[Path] = []
        for candidate in sorted(runs_root.glob("*")):
            candidate_manifest_path = candidate / "manifest.json"
            call_log = candidate / "calls.jsonl"
            if (
                not candidate_manifest_path.is_file()
                or not call_log.is_file()
                or call_log.stat().st_size <= 0
            ):
                continue
            candidate_manifest = json.loads(
                candidate_manifest_path.read_text(encoding="utf-8")
            )
            candidate_sampling = candidate_manifest.get("sampling") or {}
            if (
                str(candidate_manifest.get("provider") or "kendr") == spec.provider
                and str(candidate_manifest.get("requested_model")) == spec.model
                and candidate_sampling.get("content_hash")
                == expected_sampling.get("content_hash")
                and candidate_sampling.get("selected_ids") == expected_ids
            ):
                matches.append(candidate)
        return matches

    usd_per_credit = Decimal(
        str(
            manifest.get("kendr_usd_per_credit")
            or KENDR_DEFAULT_USD_PER_CREDIT
        )
    )
    max_cost = manifest.get("max_cost_usd_per_answer")
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    suffix = _safe_label(str(manifest["matrix_id"]))[-12:]
    tasks = tuple(manifest["tasks"])

    for index, spec in enumerate(specs, 1):
        candidates = captured_candidates(spec)
        selected, attempted = _select_rebuild_run(candidates)
        if selected is not None:
            print(
                f"\n[{index}/{len(specs)}] Reusing captured trial for "
                f"{spec.label} ({selected.name})"
            )
            try:
                summary = summarize_existing_run(
                    selected,
                    livebench_root=livebench_root,
                    usd_per_credit=usd_per_credit,
                )
                if (summary.get("completeness") or {}).get("complete") is False:
                    raise RuntimeError(
                        "Earliest captured provider trial is incomplete; it "
                        "was preserved and not replaced by a clean rerun."
                    )
                row = _leaderboard_row(spec, selected, summary)
                row["run_selection_policy"] = (
                    "earliest-captured-provider-trial"
                )
                row["captured_trial_count"] = len(attempted)
                row["excluded_later_trial_run_ids"] = [
                    path.name for path in attempted[1:]
                ]
                rows.append(row)
            except Exception as exc:
                failures.append(
                    {
                        "model": spec.label,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
        else:
            print(
                f"\n[{index}/{len(specs)}] Resuming with new trial for "
                f"{spec.label} ({spec.provider}:{spec.model})"
            )
            run_args = argparse.Namespace(
                livebench_root=livebench_root,
                env_file=env_file,
                no_env_file=no_env_file,
                provider=spec.provider,
                model=spec.model,
                model_display_name=_safe_label(f"{spec.key}-{suffix}"),
                api_base=None,
                reasoning_effort=manifest.get("reasoning_effort", "none"),
                pricing=Path(manifest["pricing_catalog"]),
                bench_name=list(tasks),
                livebench_release_option=str(manifest["livebench_release"]),
                max_tokens=int(manifest["max_tokens"]),
                parallel_requests=int(manifest["parallel_requests"]),
                practical_equivalence_margin=float(
                    manifest.get("practical_equivalence_margin", 0.02)
                ),
                parallel_grading=int(manifest["parallel_grading"]),
                question_begin=None,
                question_end=None,
                question_id=list(expected_ids),
                planned_questions=planned_questions,
                planned_question_ids=list(expected_ids),
                sampling_provenance=expected_sampling,
                resume=False,
                retry_failures=False,
                skip_inference=False,
                skip_grading=False,
                ignore_missing_answers=True,
                deadline_ms=int(manifest["deadline_ms"]),
                max_cost_usd_per_answer=(
                    Decimal(str(max_cost)) if max_cost is not None else None
                ),
                allow_incomplete=False,
                kendr_usd_per_credit=usd_per_credit,
                output=runs_root,
                label=spec.key,
                confirm_full=False,
                compare_model=[],
            )
            try:
                run_dir, summary = run_livebench(run_args)
                rows.append(_leaderboard_row(spec, run_dir, summary))
            except Exception as exc:
                failures.append(
                    {
                        "model": spec.label,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )

        _write_leaderboard(
            matrix_root,
            matrix_id=str(manifest["matrix_id"]),
            rows=rows,
            failures=failures,
            tasks=tasks,
            release=str(manifest["livebench_release"]),
            questions_per_task=int(manifest["questions_per_task"]),
            max_tokens=int(manifest["max_tokens"]),
            parallel_requests=int(manifest["parallel_requests"]),
            practical_equivalence_margin=float(
                manifest.get("practical_equivalence_margin", 0.02)
            ),
        )

    _require_complete_panel(
        rows=rows,
        failures=failures,
        expected_count=len(specs),
        matrix_root=matrix_root,
    )
    _publish_latest(matrix_root)
    return matrix_root


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.rebuild and args.resume_matrix:
        print(
            "llm-benchmark-matrix failed: --rebuild and --resume-matrix "
            "are mutually exclusive",
            file=sys.stderr,
        )
        return 1
    try:
        if args.rebuild:
            root = rebuild_matrix(args.rebuild, args.livebench_root)
        elif args.resume_matrix:
            root = resume_matrix(
                args.resume_matrix,
                args.livebench_root,
                env_file=args.env_file,
                no_env_file=args.no_env_file,
            )
        else:
            root = run_matrix(args)
    except (OSError, RuntimeError) as exc:
        print(f"llm-benchmark-matrix failed: {exc}", file=sys.stderr)
        return 1
    if args.preflight_only and not args.rebuild and not args.resume_matrix:
        print(f"\nSample plan: {root / 'sample-plan.json'}")
    else:
        print(f"\nLeaderboard: {root / 'leaderboard.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
