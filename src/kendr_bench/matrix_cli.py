from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping, Sequence

from .cli import load_environment
from .livebench_cli import (
    DEFAULT_LIVEBENCH_ROOT,
    DEFAULT_PRICING_PATH,
    _positive_decimal,
    _positive_int,
    _run_id,
    _safe_label,
    run_livebench,
    summarize_existing_run,
)
from .providers import KENDR_DEFAULT_USD_PER_CREDIT
from .scoring import (
    bootstrap_ci,
    category_scores,
    failed_question_ids,
    paired_deltas,
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
        prog="kendr-benchmark-matrix",
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
    parser.add_argument("--max-tokens", type=_positive_int, default=2048)
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
        "--rebuild",
        type=Path,
        help=(
            "Recompute summaries and leaderboard for an existing matrix "
            "without making API calls"
        ),
    )
    return parser


def _selected_panel(keys: Sequence[str] | None) -> list[ModelSpec]:
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


def _question_scores(path: Path, answers_path: Path) -> dict[str, float]:
    """Per-question failure-normalized scores, for paired comparisons."""
    failed = _failed_question_ids(answers_path)
    scores: dict[str, float] = {}
    for record in _read_records(path):
        if record.get("score") in (None, -1):
            continue
        question_id = str(record.get("question_id"))
        scores[question_id] = (
            0.0 if question_id in failed else float(record["score"])
        )
    return scores


def _leaderboard_row(
    spec: ModelSpec,
    run_dir: Path,
    summary: Mapping[str, Any],
) -> dict[str, Any]:
    api = summary["current_api_run"]
    quality = summary["current_run_quality"]
    efficiency = summary["efficiency"]
    latency = summary["latency"]["end_to_end_ms"]
    failed_latency = summary["latency"].get("failed_request_ms", {})
    reliability = summary["reliability"]
    categories = _category_scores(
        run_dir / "judgments.jsonl", run_dir / "answers.jsonl"
    )
    interval = quality.get("quality_ci95") or {}
    successful_answers = reliability["successful_answers"]
    failed_answers = reliability["failed_answers"]
    attempted_answers = successful_answers + failed_answers
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
        "cost_usd": api.get("cost_usd"),
        "cost_per_successful_answer": cost_per_successful_answer,
        "kendr_credits": api.get("kendr_credits"),
        "latency_mean_ms": latency["mean"],
        "latency_p50_ms": latency["p50"],
        "latency_p95_ms": latency["p95"],
        "successful_latency_mean_ms": latency["mean"],
        "successful_latency_p50_ms": latency["p50"],
        "successful_latency_p95_ms": latency["p95"],
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
        "answer_success_rate": reliability["answer_success_rate"],
        "scoring_coverage": reliability["scoring_coverage"],
        "output_cap_compliance_rate": reliability[
            "output_cap_compliance_rate"
        ],
        "route_distribution": reliability["route_distribution"],
        "provider_error_distribution": reliability[
            "provider_error_distribution"
        ],
        "run_dir": str(run_dir),
        # Underscore-prefixed keys stay out of the published CSV/JSON; they only
        # feed tiering and paired comparisons.
        "_question_scores": _question_scores(
            run_dir / "judgments.jsonl", run_dir / "answers.jsonl"
        ),
        "_capability_keys": sorted(categories),
    }
    for category, score in categories.items():
        row[f"{category}_score"] = score
    return row


def _ranking_key(row: Mapping[str, Any]) -> tuple[float, float, float]:
    quality = row.get("quality_score")
    cost = row.get("cost_usd")
    latency = row.get("latency_p50_ms")
    return (
        -float(quality) if quality is not None else float("inf"),
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
) -> None:
    ordered = sorted(rows, key=_ranking_key)
    for rank, row in enumerate(ordered, 1):
        row["rank"] = rank

    tiers = separation_tiers(
        [
            (
                row["panel_key"],
                {
                    "low": row.get("quality_ci95_low"),
                    "high": row.get("quality_ci95_high"),
                },
            )
            for row in ordered
        ]
    )
    for row in ordered:
        row["tier"] = tiers.get(row["panel_key"])

    # Marginal intervals are the weakest test available on paired data. Each
    # adjacent pair answered the same questions, so the paired bootstrap is what
    # actually says whether one outranked the other.
    adjacent: list[dict[str, Any]] = []
    for higher, lower in zip(ordered, ordered[1:]):
        deltas = paired_deltas(
            higher.get("_question_scores") or {},
            lower.get("_question_scores") or {},
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
        adjacent.append(
            {
                "higher_ranked": higher["model"],
                "lower_ranked": lower["model"],
                "questions_compared": len(deltas),
                "mean_difference": sum(deltas) / len(deltas),
                "ci95_low": low,
                "ci95_high": high,
                "separates_at_95": bool(
                    low is not None
                    and high is not None
                    and (low > 0 or high < 0)
                ),
                "wins_higher_ranked": sum(delta > 0 for delta in deltas),
                "wins_lower_ranked": sum(delta < 0 for delta in deltas),
                "ties": sum(delta == 0 for delta in deltas),
            }
        )

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
            "Official question-weighted LiveBench objective score descending; "
            "estimated/reported USD then p50 latency ascending as tie-breakers. "
            "Rank order is finer than the sample resolves: use `tier` and "
            "`adjacent_pair_tests` to judge which gaps are real."
        ),
        "results": published,
        "adjacent_pair_tests": adjacent,
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
        "Ranks are printed in full for traceability, but adjacent ranks are "
        "routinely closer than this sample can resolve. Models sharing a tier "
        "are not separated at 95% confidence.",
        "",
        "| Rank | Tier | Model | Access | E2E quality | 95% CI | "
        "Conditional quality | "
        "Availability | Scored | Cost | p50 success latency | "
        "p50 failed latency | Total tokens | Tokens / quality point | "
        "Cap compliance |",
        "|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in ordered:
        ci_low = row.get("quality_ci95_low")
        ci_high = row.get("quality_ci95_high")
        ci_text = (
            f"{_percent(ci_low)}–{_percent(ci_high)}"
            + ("*" if row.get("quality_ci95_degenerate") else "")
            if ci_low is not None and ci_high is not None
            else "n/a"
        )
        lines.append(
            f"| {row['rank']} | {row.get('tier') or 'n/a'} | {row['model']} | "
            f"{row['access']} | "
            f"{_percent(row.get('end_to_end_quality_score', row.get('quality_score')))} | "
            f"{ci_text} | "
            f"{_percent(row.get('conditional_quality_score'))} | "
            f"{_percent(row.get('availability', row.get('answer_success_rate')))} | "
            f"{row['questions_scored']} | {_money(row['cost_usd'])} | "
            f"{_number(row['latency_p50_ms'])} ms | "
            f"{_number(row.get('failed_latency_p50_ms'))} ms | "
            f"{row['total_tokens']:,} | "
            f"{_number(row['tokens_per_quality_point'])} | "
            f"{_percent(row['output_cap_compliance_rate'])} |"
        )

    if any(row.get("quality_ci95_degenerate") for row in ordered):
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
                "## Does each rank gap survive a paired test?",
                "",
                "Each row resamples the per-question differences between two "
                "adjacent ranks, which is the only test that uses the fact "
                "that both answered the same questions.",
                "",
                "| Higher rank | Lower rank | Mean difference | 95% CI | "
                "W/L/T | Separated at 95%? |",
                "|---|---|---:|---:|---:|---|",
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
                f"{'yes' if item['separates_at_95'] else 'no'} |"
            )
        separated = sum(item["separates_at_95"] for item in adjacent)
        lines.extend(
            [
                "",
                f"{separated} of {len(adjacent)} adjacent gaps are separated "
                "at 95% confidence. Unseparated gaps are ordering noise, not "
                "measured differences.",
            ]
        )

    baseline = next(
        (row for row in ordered if row["panel_key"] == "openai-sol"),
        None,
    )
    baseline_usd_per_quality = (
        baseline.get("usd_per_quality_point") if baseline else None
    )
    baseline_tokens_per_quality = (
        baseline.get("tokens_per_quality_point") if baseline else None
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
        token_index = (
            float(baseline_tokens_per_quality)
            / float(tokens_per_quality)
            if reliable
            and baseline_tokens_per_quality is not None
            and tokens_per_quality not in (None, 0)
            else None
        )
        lines.append(
            f"| {row['model']} | "
            f"{_number(row.get('quality_points'), 3)} | "
            f"{_money(row['cost_usd'])} | "
            f"{_number(row.get('kendr_credits'), 6)} | "
            f"{_money(usd_per_quality)} | "
            f"{_number(tokens_per_quality)} | "
            f"{_multiplier(cost_index)} | "
            f"{_multiplier(token_index)} |"
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
    by_key = {model.key: model for model in DEFAULT_MODEL_PANEL}
    for row in ordered:
        spec = by_key[row["panel_key"]]
        lines.append(
            f"| {spec.label} | `{spec.model}` | {spec.access} | "
            f"[{spec.license}]({spec.license_source}) |"
        )

    lines.extend(
        [
            "",
            "## Endpoint reliability",
            "",
            "| Model | Successful / attempted | Provider errors | "
            "Selected routes |",
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
            "measured under load and is higher than a single-request "
            "measurement would be. The load is the same for every model, so "
            "ordering is comparable while absolute values are not.",
            "- Cap compliance below 100% means that endpoint was not held to "
            "the requested output budget. Token and cost comparisons against a "
            "fully compliant endpoint are biased in favor of whichever one was "
            "allowed to generate more.",
            "- Time to first token is unavailable because the instrumented "
            "path is non-streaming. Latency is client-observed end-to-end.",
            "- Retry visibility differs by provider: Kendr retries are "
            "explicit and logged as separate attempts, while the OpenAI client "
            "retries inside the transport. Raw-attempt reliability is therefore "
            "not comparable across the two paths.",
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


def run_matrix(args: argparse.Namespace) -> Path:
    if not args.confirm_paid_run:
        raise RuntimeError(
            "The multi-model matrix is chargeable. Re-run with "
            "--confirm-paid-run after reviewing the selected panel and sample."
        )
    load_environment(args.env_file, disabled=args.no_env_file)
    panel = _selected_panel(args.include)
    tasks = tuple(args.tasks or DEFAULT_MATRIX_TASKS)
    matrix_id = _run_id(args.label)
    matrix_root = (args.output / matrix_id).resolve()
    matrix_root.mkdir(parents=True, exist_ok=False)
    runs_root = matrix_root / "runs"
    runs_root.mkdir()

    manifest = {
        "matrix_id": matrix_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "models": [asdict(model) for model in panel],
        "livebench_release": args.release,
        "tasks": tasks,
        "questions_per_task": args.questions_per_task,
        "max_tokens": args.max_tokens,
        "parallel_requests": args.parallel_requests,
        "parallel_grading": args.parallel_grading,
        "reasoning_effort": args.reasoning_effort,
        "pricing_catalog": str(args.pricing.resolve()),
        "kendr_usd_per_credit": format(
            args.kendr_usd_per_credit, "f"
        ),
    }
    (matrix_root / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
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
            parallel_grading=args.parallel_grading,
            question_begin=0,
            question_end=args.questions_per_task,
            question_id=None,
            resume=False,
            retry_failures=False,
            skip_inference=False,
            skip_grading=False,
            ignore_missing_answers=True,
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
        )

    _publish_latest(matrix_root)
    return matrix_root


def rebuild_matrix(matrix_root: Path, livebench_root: Path) -> Path:
    matrix_root = matrix_root.resolve()
    manifest_path = matrix_root / "manifest.json"
    if not manifest_path.is_file():
        raise RuntimeError(f"Matrix manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    specs = [ModelSpec(**item) for item in manifest["models"]]
    run_dirs = sorted((matrix_root / "runs").glob("*"))
    by_identity: dict[tuple[str, str], Path] = {}
    for run_dir in run_dirs:
        run_manifest_path = run_dir / "manifest.json"
        if not run_manifest_path.is_file():
            continue
        run_manifest = json.loads(
            run_manifest_path.read_text(encoding="utf-8")
        )
        by_identity[
            (
                str(run_manifest.get("provider") or "kendr"),
                str(run_manifest.get("requested_model")),
            )
        ] = run_dir

    rows: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    usd_per_credit = Decimal(
        str(
            manifest.get("kendr_usd_per_credit")
            or KENDR_DEFAULT_USD_PER_CREDIT
        )
    )
    for spec in specs:
        run_dir = by_identity.get((spec.provider, spec.model))
        if run_dir is None:
            failures.append(
                {"model": spec.label, "error": "Run directory not found"}
            )
            continue
        try:
            summary = summarize_existing_run(
                run_dir,
                livebench_root=livebench_root,
                usd_per_credit=usd_per_credit,
            )
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
        tasks=manifest["tasks"],
        release=str(manifest["livebench_release"]),
        questions_per_task=int(manifest["questions_per_task"]),
        max_tokens=int(manifest["max_tokens"]),
        parallel_requests=int(manifest["parallel_requests"]),
    )
    _publish_latest(matrix_root)
    return matrix_root


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        root = (
            rebuild_matrix(args.rebuild, args.livebench_root)
            if args.rebuild
            else run_matrix(args)
        )
    except (OSError, RuntimeError) as exc:
        print(f"kendr-benchmark-matrix failed: {exc}", file=sys.stderr)
        return 1
    print(f"\nLeaderboard: {root / 'leaderboard.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
