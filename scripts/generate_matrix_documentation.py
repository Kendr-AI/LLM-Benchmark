from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from kendr_bench.livebench_adapter import (
    KENDR_OUTPUT_CAP_COMPATIBILITY_PATCH,
)
from kendr_bench.livebench_cli import _write_artifact_hashes
from kendr_bench.scoring import (
    answer_failed,
    bootstrap_ci,
    category_scores,
    failed_question_ids,
    normalized_scores,
    paired_deltas,
    percentile,
    separation_tiers,
    stable_seed,
)


MODEL_RESEARCH = {
    "kendr-intelligent": {
        "architecture": "Routing system; base-model parameter count is not applicable",
        "context": "1,000,000 tokens in the captured Kendr catalog",
        "max_output": "Route-dependent; client cap recorded in the matrix manifest",
        "knowledge": "Route-dependent",
        "modes": "Text, vision, tools, structured output, reasoning, web search",
        "pricing": "Dynamic, based on the selected route",
        "source": "https://github.com/Kendr-AI/Kendr-PythonSDK",
        "notes": "Observed route mix is reported from response metadata.",
    },
    "claude-opus-5": {
        "architecture": "Undisclosed proprietary model",
        "context": "1,000,000 tokens",
        "max_output": "128,000 tokens",
        "knowledge": "May 2026 cutoff",
        "modes": "Adaptive reasoning on by default; effort low through max",
        "pricing": "$5/M input, $25/M output at Anthropic list price",
        "source": "https://platform.claude.com/docs/en/about-claude/models/whats-new-opus-5",
        "notes": "Kendr catalog equivalent is $6/M input and $30/M output at $0.002/credit.",
    },
    "claude-opus-4-8": {
        "architecture": "Undisclosed proprietary model",
        "context": "1,000,000 tokens",
        "max_output": "128,000 tokens",
        "knowledge": "January 2026 reliable-knowledge and training-data cutoff",
        "modes": "Adaptive thinking supported but off unless explicitly requested",
        "pricing": "$5/M input, $25/M output at Anthropic list price",
        "source": "https://platform.claude.com/docs/en/about-claude/models/whats-new-claude-4-8",
        "notes": "Kendr catalog equivalent is $6/M input and $30/M output at $0.002/credit.",
    },
    "openai-sol": {
        "architecture": "Undisclosed proprietary model",
        "context": "1,050,000 tokens",
        "max_output": "128,000 tokens",
        "knowledge": "February 16, 2026 cutoff",
        "modes": "Configurable reasoning; text and image input; tools",
        "pricing": "$5/M input, $0.50/M cached input, $30/M output",
        "source": "https://developers.openai.com/api/docs/models/gpt-5.6-sol",
        "notes": "Direct OpenAI API; reasoning effort was explicitly none in this run.",
    },
    "openai-terra": {
        "architecture": "Undisclosed proprietary model",
        "context": "1,050,000 tokens",
        "max_output": "128,000 tokens",
        "knowledge": "February 16, 2026 cutoff",
        "modes": "Configurable reasoning; text and image input; tools",
        "pricing": "$2.50/M input, $0.25/M cached input, $15/M output",
        "source": "https://developers.openai.com/api/docs/models/gpt-5.6-terra",
        "notes": "Direct OpenAI API; reasoning effort was explicitly none in this run.",
    },
    "glm-5": {
        "architecture": "744B total / 40B active MoE; 256 experts, 8 selected",
        "context": "200,000 advertised; config max positions 202,752",
        "max_output": "128,000 tokens in Z.ai documentation",
        "knowledge": "Not stated",
        "modes": "Text; long-horizon reasoning and agentic use",
        "pricing": "Kendr equivalent: $1.20/M input, $3.84/M output",
        "source": "https://github.com/zai-org/GLM-5",
        "notes": "Apache-2.0 in the official repository.",
    },
    "deepseek-v3-2": {
        "architecture": "685B total; V3 lineage reports 37B active MoE",
        "context": "163,840 positions in the official config",
        "max_output": "Route/provider-dependent",
        "knowledge": "Not stated",
        "modes": "Thinking and non-thinking; tool use",
        "pricing": "Kendr equivalent: $0.744/M input, $2.22/M output",
        "source": "https://huggingface.co/deepseek-ai/DeepSeek-V3.2",
        "notes": "MIT-licensed weights; official local guidance recommends temperature 1.0.",
    },
    "kimi-k2-5": {
        "architecture": "1T total / 32B active MoE; 384 experts, 8 selected plus shared",
        "context": "262,144 in Kendr; official repository describes 256K",
        "max_output": "Route/provider-dependent",
        "knowledge": "Not stated",
        "modes": "Native multimodal; thinking and instant modes; agents",
        "pricing": "Kendr equivalent: $0.72/M input, $3.60/M output",
        "source": "https://github.com/MoonshotAI/Kimi-K2.5",
        "notes": "Modified MIT with an attribution condition at stated scale thresholds.",
    },
    "llama-4-maverick": {
        "architecture": "400B total / 17B active MoE; 128 experts",
        "context": "1,000,000 tokens",
        "max_output": "Route/provider-dependent",
        "knowledge": "August 2024 cutoff",
        "modes": "Multilingual text and image input; text and code output",
        "pricing": "Kendr equivalent: $0.288/M input, $1.164/M output",
        "source": "https://github.com/meta-llama/llama-models/blob/main/models/llama4/MODEL_CARD.md",
        "notes": "Llama 4 Community License; trained on about 22T tokens.",
    },
}


# Current frontier panels use campaign-specific keys, so their research
# profiles must be bound to the exact requested endpoint ID instead of a
# display label or a conveniently similar panel key.  Keep this table
# deliberately literal: aliases and dated backends can have different serving
# behavior, limits, prices, and data-governance terms.
MODEL_RESEARCH_BY_REQUESTED_MODEL = {
    "kc-claude-opus-5": {
        "architecture": "Undisclosed proprietary model",
        "context": "1,000,000 tokens advertised by Anthropic",
        "max_output": "128,000 tokens advertised by Anthropic",
        "knowledge": "May 2026 cutoff",
        "modes": "Text and image input; adaptive reasoning; tools",
        "pricing": (
            "Kendr-managed Amazon Bedrock route; use captured Kendr call "
            "telemetry for campaign cost"
        ),
        "source": (
            "https://platform.claude.com/docs/en/about-claude/models/"
            "whats-new-opus-5"
        ),
        "notes": (
            "Exact Kendr canonical alias. Do not pool it with retired "
            "Bedrock aliases or a direct Anthropic endpoint."
        ),
    },
    "kc-gpt-5.6-sol": {
        "architecture": "Undisclosed proprietary model",
        "context": "1,050,000 tokens",
        "max_output": "128,000 tokens",
        "knowledge": "February 16, 2026 cutoff",
        "modes": "Configurable reasoning; text and image input; tools",
        "pricing": (
            "$5/M input, $0.50/M cached input, $30/M output at OpenAI "
            "list price"
        ),
        "source": (
            "https://developers.openai.com/api/docs/models/gpt-5.6-sol"
        ),
        "notes": (
            "Exact Kendr managed alias; report the campaign's explicit "
            "reasoning effort and captured route metadata."
        ),
    },
    "kc-grok-4.5": {
        "architecture": "Undisclosed proprietary model",
        "context": "500,000 tokens",
        "max_output": "Route-dependent; freeze the served endpoint limit",
        "knowledge": "Not stated in the cited model page",
        "modes": "Text and image input; reasoning effort low through high",
        "pricing": (
            "Kendr-managed xAI route; use captured Kendr call telemetry for "
            "campaign cost"
        ),
        "source": "https://docs.x.ai/developers/models/grok-4.5",
        "notes": (
            "Exact Kendr managed alias; reasoning effort is part of the "
            "benchmark configuration."
        ),
    },
    "kc-ollama-deepseek-v4-flash-0731": {
        "architecture": "Open-weight mixture-of-experts model",
        "context": "1,000,000 tokens advertised for DeepSeek V4 Flash",
        "max_output": "Up to 384,000 tokens on the vendor API path",
        "knowledge": "Not stated",
        "modes": "Text; thinking and non-thinking modes",
        "pricing": (
            "Kendr-managed dated Ollama route; use captured Kendr call "
            "telemetry for campaign cost"
        ),
        "source": "https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash",
        "notes": (
            "The 0731 suffix identifies the exact Kendr-served backend. Do "
            "not merge it with the rolling DeepSeek API alias without "
            "provider-returned identity evidence."
        ),
    },
    "kc-google-gemini-3-6-flash": {
        "architecture": "Undisclosed proprietary model",
        "context": "1,048,576 tokens",
        "max_output": "65,536 tokens",
        "knowledge": "Not stated in the cited model page",
        "modes": (
            "Text, image, video, audio, and PDF input; text output; tools"
        ),
        "pricing": (
            "Kendr-managed Google route; use captured Kendr call telemetry "
            "for campaign cost"
        ),
        "source": (
            "https://ai.google.dev/gemini-api/docs/models/"
            "gemini-3.6-flash"
        ),
        "notes": (
            "Exact Kendr Google alias; do not pool it with Gemini preview "
            "or rolling aliases."
        ),
    },
    "kc-openai-gpt-5-5": {
        "architecture": "Undisclosed proprietary model",
        "context": "Freeze from the exact served endpoint for the campaign",
        "max_output": "Freeze from the exact served endpoint for the campaign",
        "knowledge": "See the cited exact-model page",
        "modes": "Configurable reasoning from none through xhigh; tools",
        "pricing": (
            "Kendr-managed OpenAI route; use captured Kendr call telemetry "
            "for campaign cost"
        ),
        "source": "https://developers.openai.com/api/docs/models/gpt-5.5",
        "notes": (
            "Exact Kendr managed alias retained as a declared historical "
            "baseline, not a current-frontier candidate."
        ),
    },
}


UNKNOWN_MODEL_RESEARCH = {
    "architecture": "Not researched",
    "context": "Not researched",
    "max_output": "Not researched",
    "knowledge": "Not researched",
    "modes": "Not researched",
    "pricing": "Not researched",
    "source": "n/a",
    "notes": "No curated research entry for this panel key.",
}


def model_research_for_spec(spec: dict[str, Any]) -> dict[str, str]:
    """Resolve research without guessing across model identities.

    Current frontier entries are selected only by an exact requested-model
    match.  The panel-key fallback preserves reports for the historical pilot,
    whose curated profiles predate exact endpoint-ID mappings.  Deliberately do
    not normalize case, trim suffixes, or perform fuzzy matching here.
    """

    exact = MODEL_RESEARCH_BY_REQUESTED_MODEL.get(str(spec.get("model", "")))
    if exact is not None:
        return exact
    return MODEL_RESEARCH.get(
        str(spec.get("key", "")), UNKNOWN_MODEL_RESEARCH
    )


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def percent(value: Any, digits: int = 1) -> str:
    if value is None:
        return "n/a"
    return f"{float(value) * 100:.{digits}f}%"


def number(value: Any, digits: int = 2) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):,.{digits}f}"


def money(value: Any) -> str:
    if value in (None, ""):
        return "n/a"
    amount = Decimal(str(value))
    return f"${amount:.6f}" if amount < 1 else f"${amount:,.2f}"


def markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    def clean(value: Any) -> str:
        return str(value).replace("|", "\\|").replace("\n", " ")

    lines = [
        "| " + " | ".join(map(clean, headers)) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend(
        "| " + " | ".join(clean(value) for value in row) + " |"
        for row in rows
    )
    return "\n".join(lines)


def ratio(numerator: Any, denominator: Any) -> float | None:
    """Guarded division. A model that scored zero quality points produces a
    ``None`` efficiency metric, which used to crash the whole report."""
    if numerator is None or denominator is None:
        return None
    try:
        divisor = float(denominator)
    except (TypeError, ValueError):
        return None
    if divisor == 0:
        return None
    try:
        return float(numerator) / divisor
    except (TypeError, ValueError):
        return None


def multiplier(value: float | None) -> str:
    return f"{value:.2f}×" if value is not None else "n/a"


def interval_text(interval: dict[str, Any]) -> str:
    low, high = interval.get("low"), interval.get("high")
    if low is None or high is None:
        return "n/a"
    marker = "*" if interval.get("degenerate") else ""
    return f"{percent(low)}–{percent(high)}{marker}"


def get_answer_call(answer: dict[str, Any]) -> dict[str, Any]:
    calls = get_answer_calls(answer)
    return calls[-1] if calls else {}


def get_answer_calls(answer: dict[str, Any]) -> list[dict[str, Any]]:
    calls = answer.get("api_info", {}).get("benchmark_calls", [])
    return [call for call in calls if isinstance(call, dict)]


def call_error(call: dict[str, Any]) -> str:
    error = call.get("error")
    if isinstance(error, dict):
        return str(
            error.get("message")
            or error.get("code")
            or error.get("type")
            or error
        )
    return str(error or "")


def error_details(call: dict[str, Any]) -> dict[str, Any]:
    """Failure detail block, tolerating both error-body shapes.

    The live OpenAI SDK hands back an already-unwrapped body, while older
    captures keep the outer ``error`` envelope.
    """
    error = call.get("error")
    if not isinstance(error, dict):
        return {}
    body = error.get("body")
    if not isinstance(body, dict):
        return {}
    for candidate in (
        body.get("details"),
        (body.get("error") or {}).get("details")
        if isinstance(body.get("error"), dict)
        else None,
    ):
        if isinstance(candidate, dict):
            return candidate
    return {}


def call_routing(call: dict[str, Any]) -> dict[str, Any]:
    routing = call.get("kendr_routing")
    if routing:
        return routing
    routing = error_details(call).get("kendr_routing")
    return routing if isinstance(routing, dict) else {}


def call_usage(call: dict[str, Any]) -> dict[str, Any]:
    usage = call.get("usage")
    if usage:
        return usage
    attempts = error_details(call).get("attempts")
    if not isinstance(attempts, list) or not attempts:
        return {}
    provider_usage = attempts[-1].get("usage", {})
    return {
        "prompt_tokens": provider_usage.get("input_tokens"),
        "completion_tokens": provider_usage.get("output_tokens"),
        "total_tokens": (
            (provider_usage.get("input_tokens") or 0)
            + (provider_usage.get("output_tokens") or 0)
        ),
    }


def call_cost_usd(call: dict[str, Any]) -> tuple[Decimal, bool]:
    """Return captured cost and whether it is known for this attempt."""
    if str(call.get("retry_reason") or "").lower() == "no_credits_charged":
        return Decimal(0), True
    for value in (call.get("cost_usd"), call.get("kendr_cost_usd")):
        if value is None:
            continue
        try:
            parsed = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return Decimal(0), False
        if parsed.is_finite() and parsed >= 0:
            return parsed, True
        return Decimal(0), False
    return Decimal(0), False


def call_kendr_credits(call: dict[str, Any]) -> tuple[Decimal, bool]:
    """Return billed Kendr credits, recognizing explicit no-charge failures."""
    if str(call.get("retry_reason") or "").lower() == "no_credits_charged":
        return Decimal(0), True
    value = call.get("kendr_credits")
    if value is None and isinstance(call.get("kendr_usage"), dict):
        value = call["kendr_usage"].get("credits_charged")
    if value is None:
        return Decimal(0), False
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(0), False
    return (parsed, True) if parsed.is_finite() and parsed >= 0 else (Decimal(0), False)


def find_runs(
    root: Path, manifest: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    runs_root = (root / "runs").resolve()
    canonical_path = root / "leaderboard.json"
    canonical = read_json(canonical_path) if canonical_path.is_file() else {}
    canonical_by_key = {
        str(row.get("panel_key")): row
        for row in (canonical.get("results") or [])
        if row.get("panel_key") and row.get("run_dir")
    }
    fallback_by_requested: dict[str, list[Path]] = {}
    for run_dir in sorted(runs_root.iterdir()):
        summary_path = run_dir / "summary.json"
        if not summary_path.is_file():
            continue
        summary = read_json(summary_path)
        fallback_by_requested.setdefault(
            str(summary["requested_model"]), []
        ).append(run_dir)
    result = {}
    missing: list[str] = []
    for spec in manifest["models"]:
        canonical_row = canonical_by_key.get(str(spec["key"]))
        if canonical_row is not None:
            run_dir = Path(str(canonical_row["run_dir"])).resolve()
            try:
                run_dir.relative_to(runs_root)
            except ValueError as exc:
                raise RuntimeError(
                    f"Canonical run for {spec['label']} is outside the "
                    "matrix runs directory."
                ) from exc
        else:
            candidates = fallback_by_requested.get(str(spec["model"])) or []
            attempted = [
                candidate
                for candidate in candidates
                if (candidate / "calls.jsonl").is_file()
                and (candidate / "calls.jsonl").stat().st_size > 0
            ]
            run_dir = (attempted or candidates or [None])[0]
        if run_dir is None or not (run_dir / "summary.json").is_file():
            missing.append(spec["label"])
            continue
        summary = read_json(run_dir / "summary.json")
        if str(summary.get("requested_model")) != str(spec["model"]):
            raise RuntimeError(
                f"Selected run {run_dir.name} does not match "
                f"{spec['label']} ({spec['model']})."
            )
        result[spec["key"]] = {
            "spec": spec,
            "run_dir": run_dir,
            "summary": summary,
            "calls": read_jsonl(run_dir / "calls.jsonl"),
            "answers": read_jsonl(run_dir / "answers.jsonl"),
            "judgments": read_jsonl(run_dir / "judgments.jsonl"),
        }
    if missing:
        print(
            "Skipping models with no run directory: "
            + ", ".join(missing),
            file=sys.stderr,
        )
    return result


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    # Underscore-prefixed keys are intermediates (per-question score maps) used
    # for paired tests, not published columns.
    published = [
        {key: value for key, value in row.items() if not key.startswith("_")}
        for row in rows
    ]
    fieldnames: list[str] = []
    for row in published:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, restval="")
        writer.writeheader()
        writer.writerows(published)


def build_metrics_rows(
    panel: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    rows = []
    for key, data in panel.items():
        spec, summary, calls = data["spec"], data["summary"], data["calls"]
        api = summary["current_api_run"]
        quality = summary["current_run_quality"]
        reliability = summary["reliability"]
        cap_conformance = reliability.get(
            "operational_output_cap_conformance", {}
        )
        latency = summary["latency"]["end_to_end_ms"]
        raw_success = sum(not bool(call.get("error")) for call in calls)
        # Resample the same failure-normalized scores that produced
        # quality_score. Bootstrapping the raw judgments instead described a
        # different dataset, because some graders award format credit to the
        # literal $ERROR$ sentinel.
        failed_ids = failed_question_ids(data["answers"])
        scores = normalized_scores(data["judgments"], failed_ids)
        interval = bootstrap_ci(scores, seed=stable_seed(key))
        capabilities = quality.get("category_scores") or category_scores(
            data["judgments"], failed_ids
        )
        operations = summary.get("operations") or {}
        operational_scores = {
            str(item["question_id"]): float(
                item.get("score_weighted_goodput") or 0.0
            )
            for item in (operations.get("question_results") or [])
            if item.get("question_id")
        }
        operational_interval = (
            bootstrap_ci(
                list(operational_scores.values()),
                seed=stable_seed(f"{key}|operational-goodput"),
            )
            if operational_scores
            else interval
        )
        retries = operations.get("retries") or {}
        final_latency = summary["latency"]["end_to_end_ms"]
        attempt_latency = summary["latency"].get("attempt_ms", {})
        score_weighted_goodput = reliability.get(
            "score_weighted_goodput", {}
        ).get("conservative_mean")
        rows.append(
            {
                "panel_key": key,
                "model": spec["label"],
                "provider": spec["provider"],
                "requested_model": spec["model"],
                "questions": quality["questions_scored"],
                "questions_planned": quality.get("score_denominator"),
                "quality_score": quality["objective_score_mean"],
                "quality_ci95_low": interval["low"],
                "quality_ci95_high": interval["high"],
                "quality_ci95_degenerate": interval["degenerate"],
                "quality_ci95_distinct_resample_means": interval[
                    "distinct_resample_means"
                ],
                "tier": None,
                "quality_points": quality["quality_points"],
                "score_weighted_operational_goodput": (
                    score_weighted_goodput
                ),
                "binary_operational_goodput": reliability.get(
                    "operational_goodput", {}
                ).get("conservative_rate"),
                "ranking_ci95_low": operational_interval["low"],
                "ranking_ci95_high": operational_interval["high"],
                "ranking_ci95_degenerate": operational_interval[
                    "degenerate"
                ],
                # Computed from normalized judgments, not LiveBench's raw
                # group CSV, so this table cannot disagree with the overall
                # quality column the way the two published tables used to.
                "data_analysis_score": capabilities.get("data_analysis"),
                "instruction_following_score": capabilities.get(
                    "instruction_following"
                ),
                "language_score": capabilities.get("language"),
                "math_score": capabilities.get("math"),
                "reasoning_score": capabilities.get("reasoning"),
                "final_successes": reliability["successful_answers"],
                "final_failures": reliability["failed_answers"],
                "final_reliability": reliability["answer_success_rate"],
                "raw_attempts": len(calls),
                "raw_attempt_successes": raw_success,
                "raw_attempt_failures": len(calls) - raw_success,
                "raw_attempt_reliability": (
                    raw_success / len(calls) if calls else None
                ),
                "input_tokens": api["input_tokens"],
                "output_tokens": api["output_tokens"],
                "total_tokens": api["total_tokens"],
                "token_total_is_lower_bound": bool(
                    api.get("token_total_is_lower_bound")
                ),
                "cost_usd": api["cost_usd"],
                "cost_total_is_lower_bound": bool(
                    api.get("cost_total_is_lower_bound")
                ),
                "kendr_credits": api.get("kendr_credits"),
                "mean_latency_ms": final_latency["mean"],
                "p50_latency_ms": final_latency["p50"],
                "p95_latency_ms": final_latency["p95"],
                "max_latency_ms": final_latency["maximum"],
                "attempt_p50_latency_ms": attempt_latency.get("p50"),
                "attempt_p95_latency_ms": attempt_latency.get("p95"),
                "retry_attempt_amplification": retries.get(
                    "observed_attempt_amplification"
                ),
                "retry_latency_amplification": retries.get(
                    "latency_amplification"
                ),
                "output_cap_compliance": cap_conformance.get(
                    "conservative_rate",
                    reliability["output_cap_compliance_rate"],
                ),
                "output_cap_measured_rate": cap_conformance.get(
                    "measured_rate",
                    reliability["output_cap_compliance_rate"],
                ),
                "output_cap_unknown_questions": cap_conformance.get(
                    "unknown", 0
                ),
                "cap_violations": reliability[
                    "calls_exceeding_requested_output_cap"
                ],
                "deadline_conformance": reliability.get(
                    "deadline_conformance", {}
                ).get("conservative_rate"),
                "budget_conformance": reliability.get(
                    "budget_conformance", {}
                ).get("conservative_rate"),
                "complete": (summary.get("completeness") or {}).get(
                    "complete"
                ),
                "max_output_tokens_observed": api[
                    "maximum_output_tokens_observed"
                ],
                "tokens_per_quality_point": summary["efficiency"][
                    "total_tokens_per_quality_point"
                ],
                "usd_per_quality_point": summary["efficiency"][
                    "usd_per_quality_point"
                ],
                "quality_points_per_usd": summary["efficiency"][
                    "quality_points_per_usd"
                ],
                "route_distribution": json.dumps(
                    reliability.get("route_distribution", {}),
                    sort_keys=True,
                ),
                "provider_error_distribution": json.dumps(
                    reliability.get("provider_error_distribution", {}),
                    sort_keys=True,
                ),
                "run_dir": str(data["run_dir"]),
                "_question_scores": {
                    str(judgment.get("question_id")): (
                        0.0
                        if str(judgment.get("question_id")) in failed_ids
                        else float(judgment["score"])
                    )
                    for judgment in data["judgments"]
                    if judgment.get("score") not in (None, -1)
                },
                "_ranking_question_scores": operational_scores,
            }
        )

    def order_key(
        row: dict[str, Any],
    ) -> tuple[float, float, float, float]:
        quality = row.get("quality_score")
        goodput = row.get("score_weighted_operational_goodput")
        if goodput is None:
            goodput = quality
        cost = (
            None
            if row.get("cost_total_is_lower_bound")
            else row.get("cost_usd")
        )
        return (
            -float(goodput) if goodput is not None else float("inf"),
            -float(quality) if quality is not None else float("inf"),
            float(cost) if cost is not None else float("inf"),
            (
                float(row["p50_latency_ms"])
                if row.get("p50_latency_ms") is not None
                else float("inf")
            ),
        )

    # Same rule as the leaderboard writer. These two artifacts used to sort by
    # different keys and could print different rank orders on a tie.
    rows.sort(key=order_key)
    tiers = separation_tiers(
        [
            (
                row["panel_key"],
                {
                    "low": row["ranking_ci95_low"],
                    "high": row["ranking_ci95_high"],
                },
            )
            for row in rows
        ]
    )
    for row in rows:
        row["tier"] = tiers.get(row["panel_key"])
    return rows


def build_question_rows(
    panel: dict[str, dict[str, Any]], requested_cap: int
) -> list[dict[str, Any]]:
    rows = []
    for key, data in panel.items():
        judgments = {j["question_id"]: j for j in data["judgments"]}
        operations_by_question = {
            str(item["question_id"]): item
            for item in (
                (data["summary"].get("operations") or {}).get(
                    "question_results"
                )
                or []
            )
            if item.get("question_id")
        }
        for answer in data["answers"]:
            qid = answer["question_id"]
            # An answer with no judgment is exactly what a silently-dropped
            # provider failure looks like, so it is recorded rather than raising.
            judgment = judgments.get(qid, {})
            calls = get_answer_calls(answer)
            final_call = calls[-1] if calls else {}
            routing = call_routing(final_call)
            usages = [call_usage(call) for call in calls]
            if calls:
                input_tokens = sum(
                    int(usage.get("prompt_tokens") or 0)
                    for usage in usages
                )
                output_tokens = sum(
                    int(usage.get("completion_tokens") or 0)
                    for usage in usages
                )
                token_usage_complete = all(
                    usage.get("prompt_tokens") is not None
                    and usage.get("completion_tokens") is not None
                    for usage in usages
                )
            else:
                input_tokens = answer.get("total_input_tokens")
                output_tokens = answer.get("total_output_tokens")
                token_usage_complete = (
                    input_tokens is not None and output_tokens is not None
                )

            observed_cost = Decimal(0)
            cost_observed = False
            fallback_cost_complete = bool(calls)
            observed_credits = Decimal(0)
            credits_observed = False
            credits_complete = bool(calls)
            credits_applicable = data["spec"].get("provider") == "kendr"
            for attempt in calls:
                attempt_cost, cost_known = call_cost_usd(attempt)
                observed_cost += attempt_cost
                cost_observed = cost_observed or cost_known
                fallback_cost_complete = fallback_cost_complete and cost_known
                if credits_applicable:
                    attempt_credits, credits_known = call_kendr_credits(attempt)
                    observed_credits += attempt_credits
                    credits_observed = credits_observed or credits_known
                    credits_complete = credits_complete and credits_known

            operation = operations_by_question.get(str(qid), {})
            operation_cost = operation.get("observed_cumulative_cost_usd")
            if operation_cost is not None:
                observed_cost = Decimal(str(operation_cost))
                cost_observed = True
            elif not calls:
                answer_cost = (answer.get("api_info") or {}).get(
                    "benchmark_cost_usd"
                )
                if answer_cost is not None:
                    observed_cost = Decimal(str(answer_cost))
                    cost_observed = True
                    fallback_cost_complete = True
            cost_complete = bool(
                operation.get("cost_complete", fallback_cost_complete)
            )
            observed_latency = operation.get(
                "observed_cumulative_latency_ms"
            )
            if observed_latency is None and calls:
                known_latencies = [
                    float(call["latency_ms"])
                    for call in calls
                    if call.get("latency_ms") is not None
                ]
                observed_latency = sum(known_latencies)
            latency_complete = bool(
                operation.get(
                    "latency_complete",
                    bool(calls)
                    and all(call.get("latency_ms") is not None for call in calls),
                )
            )
            cumulative_latency = operation.get("cumulative_latency_ms")
            if cumulative_latency is None and latency_complete:
                cumulative_latency = observed_latency
            cap = operation.get("output_cap") or {}
            max_attempt_output = max(
                (
                    int(usage["completion_tokens"])
                    for usage in usages
                    if usage.get("completion_tokens") is not None
                ),
                default=None,
            )
            rows.append(
                {
                    "panel_key": key,
                    "model": data["spec"]["label"],
                    "question_id": qid,
                    "category": judgment.get("category"),
                    "task": judgment.get("task"),
                    "score": judgment.get("score"),
                    "graded": bool(judgment)
                    and judgment.get("score") not in (None, -1),
                    "answer_error": answer_failed(answer),
                    "attempt_count": operation.get(
                        "attempt_count", len(calls)
                    ),
                    "retry_count": operation.get(
                        "retry_count", max(0, len(calls) - 1)
                    ),
                    "reported_cumulative_input_tokens": input_tokens,
                    "reported_cumulative_output_tokens": output_tokens,
                    "reported_cumulative_total_tokens": (
                        (input_tokens or 0) + (output_tokens or 0)
                        if input_tokens is not None or output_tokens is not None
                        else None
                    ),
                    "token_usage_complete": token_usage_complete,
                    "token_totals_are_lower_bounds": not token_usage_complete,
                    "observed_cumulative_cost_usd": (
                        format(observed_cost, "f") if cost_observed else None
                    ),
                    "cumulative_cost_usd": operation.get(
                        "cumulative_cost_usd",
                        format(observed_cost, "f")
                        if cost_observed and cost_complete
                        else None,
                    ),
                    "cost_complete": cost_complete,
                    "observed_cost_is_lower_bound": not cost_complete,
                    "observed_cumulative_kendr_credits": (
                        format(observed_credits, "f")
                        if credits_observed
                        else None
                    ),
                    "kendr_credits_complete": (
                        credits_complete
                        if credits_applicable and calls
                        else None
                    ),
                    "observed_cumulative_latency_ms": observed_latency,
                    "cumulative_latency_ms": cumulative_latency,
                    "latency_complete": latency_complete,
                    "final_attempt_actual_model": final_call.get(
                        "actual_model"
                    ),
                    "final_attempt_selected_route": routing.get(
                        "selected_model_alias"
                    ),
                    "final_attempt_provider_model": routing.get(
                        "provider_model"
                    ),
                    "final_attempt_router_latency_ms": routing.get(
                        "router_latency_ms"
                    ),
                    "final_attempt_provider_latency_ms": routing.get(
                        "provider_latency_ms"
                    ),
                    "output_cap_status": cap.get("status"),
                    "maximum_attempt_output_tokens": cap.get(
                        "maximum_observed_output_tokens", max_attempt_output
                    ),
                    "measured_attempt_exceeded_requested_output_cap": bool(
                        max_attempt_output is not None
                        and max_attempt_output > requested_cap
                    ),
                }
            )
    rows.sort(
        key=lambda row: (
            row["panel_key"],
            str(row["category"] or ""),
            row["question_id"],
        )
    )
    return rows


def build_attempt_rows(
    panel: dict[str, dict[str, Any]], requested_cap: int
) -> list[dict[str, Any]]:
    rows = []
    for key, data in panel.items():
        credits_applicable = data["spec"].get("provider") == "kendr"
        for call in data["calls"]:
            usage = call_usage(call)
            routing = call_routing(call)
            output_tokens = usage.get("completion_tokens")
            input_tokens = usage.get("prompt_tokens")
            token_usage_complete = (
                input_tokens is not None and output_tokens is not None
            )
            cost, cost_complete = call_cost_usd(call)
            credits, credits_complete = call_kendr_credits(call)
            cap_status = (
                "unknown"
                if output_tokens is None
                else "fail"
                if int(output_tokens) > requested_cap
                else "pass"
            )
            rows.append(
                {
                    "panel_key": key,
                    "model": data["spec"]["label"],
                    "request_id": call.get("request_id"),
                    "attempt_number": call.get("attempt_number"),
                    "success": not bool(call.get("error")),
                    "error_type": (call.get("error") or {}).get("type")
                    if isinstance(call.get("error"), dict)
                    else "",
                    "error_code": (call.get("error") or {}).get("code")
                    if isinstance(call.get("error"), dict)
                    else "",
                    "error_message": call_error(call),
                    "reported_input_tokens": input_tokens,
                    "reported_output_tokens": output_tokens,
                    "reported_total_tokens": (
                        int(input_tokens) + int(output_tokens)
                        if token_usage_complete
                        else None
                    ),
                    "token_usage_complete": token_usage_complete,
                    "observed_cost_usd": (
                        format(cost, "f") if cost_complete else None
                    ),
                    "cost_complete": cost_complete,
                    "observed_kendr_credits": (
                        format(credits, "f")
                        if credits_applicable and credits_complete
                        else None
                    ),
                    "kendr_credits_complete": (
                        credits_complete if credits_applicable else None
                    ),
                    "latency_ms": call.get("latency_ms"),
                    "selected_route": routing.get("selected_model_alias"),
                    "provider_model": routing.get("provider_model"),
                    "provider_latency_ms": routing.get(
                        "provider_latency_ms"
                    ),
                    "output_cap_status": cap_status,
                    "measured_output_exceeded_requested_cap": bool(
                        output_tokens is not None
                        and int(output_tokens) > requested_cap
                    ),
                }
            )
    return rows


def detailed_report(
    root: Path,
    manifest: dict[str, Any],
    panel: dict[str, dict[str, Any]],
    metrics: list[dict[str, Any]],
    questions: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
) -> str:
    def find(panel_key: str) -> dict[str, Any] | None:
        return next(
            (row for row in metrics if row["panel_key"] == panel_key), None
        )

    leader = metrics[0]
    canonical_path = root / "leaderboard.json"
    canonical = read_json(canonical_path) if canonical_path.is_file() else {}
    trial_rows: list[list[Any]] = []
    for canonical_row in canonical.get("results") or []:
        panel_key = str(canonical_row.get("panel_key") or "")
        data = panel.get(panel_key)
        selected_manifest = (
            read_json(data["run_dir"] / "manifest.json")
            if data and (data["run_dir"] / "manifest.json").is_file()
            else {}
        )
        finalization = selected_manifest.get("finalization") or {}
        captured_trials = int(canonical_row.get("captured_trial_count") or 1)
        excluded = canonical_row.get("excluded_later_trial_run_ids") or []
        if captured_trials <= 1 and not finalization:
            continue
        excluded_cost = 0.0
        excluded_cost_is_lower_bound = False
        for run_id in excluded:
            excluded_summary_path = root / "runs" / str(run_id) / "summary.json"
            if not excluded_summary_path.is_file():
                continue
            excluded_summary = read_json(excluded_summary_path)
            excluded_api = excluded_summary.get("current_api_run") or {}
            if excluded_api.get("cost_usd") is not None:
                excluded_cost += float(excluded_api["cost_usd"])
            excluded_cost_is_lower_bound = (
                excluded_cost_is_lower_bound
                or bool(excluded_api.get("cost_total_is_lower_bound"))
            )
        trial_rows.append(
            [
                canonical_row.get("model"),
                Path(str(canonical_row.get("run_dir"))).name,
                captured_trials,
                ", ".join(map(str, excluded)) or "none",
                (
                    ("≥" if excluded_cost_is_lower_bound else "")
                    + money(excluded_cost)
                    if excluded
                    else "$0.000000"
                ),
                (
                    f"{finalization.get('mode')} (inference replayed: "
                    f"{'yes' if finalization.get('provider_inference_replayed') else 'no'})"
                    if finalization
                    else "none"
                ),
            ]
        )
    trial_section: list[str] = []
    if trial_rows:
        trial_section = [
            "## Trial selection and interrupted-run recovery",
            "",
            markdown_table(
                [
                    "Model",
                    "Selected first trial",
                    "Captured trials",
                    "Excluded later trials",
                    "Excluded captured cost",
                    "Recovery",
                ],
                trial_rows,
            ),
            "",
            "The canonical rebuild selects the earliest run with captured "
            "provider calls. Manifest-only starts may be skipped, but a later "
            "outcome-bearing rerun is never substituted after observing the "
            "first trial. Interrupted first-trial answers may be graded "
            "offline only after every planned question is linked back to its "
            "captured call; provider inference is not replayed.",
            "Excluded later trials do not enter canonical quality, reliability, "
            "latency, token, or cost totals, but their spend remains part of "
            "the overall benchmarking campaign.",
            "",
        ]
    sol = find("openai-sol")
    kendr = find("kendr-intelligent")
    total_input = sum(int(row["input_tokens"] or 0) for row in metrics)
    total_output = sum(int(row["output_tokens"] or 0) for row in metrics)
    total_cost = sum(
        float(row["cost_usd"]) for row in metrics if row["cost_usd"] is not None
    )
    raw_failures = sum(not row["success"] for row in attempts)
    final_successes = sum(int(row["final_successes"] or 0) for row in metrics)
    final_failures = sum(int(row["final_failures"] or 0) for row in metrics)
    kendr_cost_ratio = (
        ratio(
            kendr["quality_points_per_usd"],
            sol["quality_points_per_usd"],
        )
        if kendr
        and sol
        and float(kendr.get("final_reliability") or 0) >= 0.8
        and float(sol.get("final_reliability") or 0) >= 0.8
        else None
    )
    seconds = lambda value: (
        number(float(value) / 1000, 2) if value is not None else "n/a"
    )
    overall_rows = []
    for rank, row in enumerate(metrics, 1):
        overall_rows.append(
            [
                rank,
                row["tier"] or "n/a",
                row["model"],
                percent(row.get("score_weighted_operational_goodput")),
                percent(row["quality_score"]),
                interval_text(
                    {
                        "low": row["ranking_ci95_low"],
                        "high": row["ranking_ci95_high"],
                        "degenerate": row["ranking_ci95_degenerate"],
                    }
                ),
                percent(row["final_reliability"]),
                percent(row["raw_attempt_reliability"]),
                ("≥" if row.get("token_total_is_lower_bound") else "")
                + f"{row['input_tokens']:,}",
                ("≥" if row.get("token_total_is_lower_bound") else "")
                + f"{row['output_tokens']:,}",
                (
                    "≥" if row.get("cost_total_is_lower_bound") else ""
                )
                + money(row["cost_usd"]),
                seconds(row["p50_latency_ms"]),
                seconds(row["p95_latency_ms"]),
                percent(row["output_cap_compliance"]),
            ]
        )
    pair_rows = []
    canonical_adjacent = canonical.get("adjacent_pair_tests") or []
    for item in canonical_adjacent:
        pair_rows.append(
            [
                item["higher_ranked"],
                item["lower_ranked"],
                f"{float(item['mean_difference']) * 100:+.1f} pp",
                f"{float(item['ci95_low']) * 100:+.1f} to "
                f"{float(item['ci95_high']) * 100:+.1f} pp",
                f"{item['wins_higher_ranked']}/"
                f"{item['wins_lower_ranked']}/{item['ties']}",
                number(item.get("randomization_p_value"), 4),
                number(item.get("holm_adjusted_p_value"), 4),
                "yes" if item.get("separates_at_fwer_05") else "no",
                "yes"
                if item.get("practically_equivalent_at_95")
                else "no",
            ]
        )
    if not canonical_adjacent:
        for higher, lower in zip(metrics, metrics[1:]):
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
            separated = low is not None and high is not None and (
                low > 0 or high < 0
            )
            pair_rows.append(
                [
                    higher["model"],
                    lower["model"],
                    f"{sum(deltas) / len(deltas) * 100:+.1f} pp",
                    f"{low * 100:+.1f} to {high * 100:+.1f} pp",
                    f"{sum(d > 0 for d in deltas)}/"
                    f"{sum(d < 0 for d in deltas)}/"
                    f"{sum(d == 0 for d in deltas)}",
                    "n/a",
                    "n/a",
                    "yes" if separated else "no",
                    "not tested",
                ]
            )
    separated_pairs = sum(row[7] == "yes" for row in pair_rows)
    capability_rows = [
        [
            row["model"],
            percent(row["data_analysis_score"]),
            percent(row["instruction_following_score"]),
            percent(row["language_score"]),
            percent(row["math_score"]),
            percent(row["reasoning_score"]),
        ]
        for row in metrics
    ]
    efficiency_rows = []
    for row in metrics:
        relative_efficiency_eligible = bool(
            row.get("final_reliability") is not None
            and float(row["final_reliability"]) >= 0.8
            and sol
            and sol.get("final_reliability") is not None
            and float(sol["final_reliability"]) >= 0.8
        )
        cost_eff = (
            ratio(
                row["quality_points_per_usd"], sol["quality_points_per_usd"]
            )
            if relative_efficiency_eligible
            else None
        )
        token_eff = (
            ratio(
                sol["tokens_per_quality_point"],
                row["tokens_per_quality_point"],
            )
            if relative_efficiency_eligible
            else None
        )
        row_tokens_are_lower_bound = bool(
            row.get("token_total_is_lower_bound")
        )
        sol_tokens_are_lower_bound = bool(
            sol and sol.get("token_total_is_lower_bound")
        )
        if not relative_efficiency_eligible:
            token_efficiency = "n/a"
        elif row_tokens_are_lower_bound and sol_tokens_are_lower_bound:
            token_efficiency = "n/a"
        elif row_tokens_are_lower_bound:
            token_efficiency = f"≤{multiplier(token_eff)}"
        elif sol_tokens_are_lower_bound:
            token_efficiency = f"≥{multiplier(token_eff)}"
        else:
            token_efficiency = multiplier(token_eff)
        row_cost_is_lower_bound = bool(
            row.get("cost_total_is_lower_bound")
        )
        sol_cost_is_lower_bound = bool(
            sol and sol.get("cost_total_is_lower_bound")
        )
        if not relative_efficiency_eligible:
            cost_efficiency = "n/a"
        elif row_cost_is_lower_bound and sol_cost_is_lower_bound:
            cost_efficiency = "n/a"
        elif row_cost_is_lower_bound:
            cost_efficiency = f"≤{multiplier(cost_eff)}"
        elif sol_cost_is_lower_bound:
            cost_efficiency = f"≥{multiplier(cost_eff)}"
        else:
            cost_efficiency = multiplier(cost_eff)
        efficiency_rows.append(
            [
                row["model"],
                ("≥" if row_tokens_are_lower_bound else "")
                + number(row["tokens_per_quality_point"], 0),
                ("≥" if row_cost_is_lower_bound else "")
                + money(row["usd_per_quality_point"]),
                ("≤" if row_cost_is_lower_bound else "")
                + number(row["quality_points_per_usd"], 1),
                token_efficiency,
                cost_efficiency,
            ]
        )
    error_rows = []
    for row in attempts:
        if not row["success"]:
            error_rows.append(
                [
                    row["model"],
                    row["request_id"],
                    number(float(row["latency_ms"]) / 1000, 2)
                    if row["latency_ms"]
                    else "n/a",
                    row["selected_route"] or "n/a",
                    row["error_code"] or row["error_type"] or "n/a",
                    row["error_message"][:180] or "n/a",
                ]
            )
    if not error_rows:
        error_rows = [["None", "—", "—", "—", "—", "No raw failures"]]
    # Share is over routed attempts, not final answers. Dividing a per-call
    # counter by an answer count only summed to 100% while failed calls were
    # being discarded.
    route_counts = (
        json.loads(kendr["route_distribution"]) if kendr else {}
    )
    routed_total = sum(route_counts.values())
    route_rows = [
        [route, count, percent(ratio(count, routed_total))]
        for route, count in sorted(route_counts.items())
    ]
    opus_section = _same_family_section(
        metrics, questions, "claude-opus-5", "claude-opus-4-8"
    )
    lines = [
        f"# Detailed benchmark report: {manifest['matrix_id']}",
        "",
        "## Executive result",
        "",
        (
            f"**{leader['model']} placed first by conservative score-weighted "
            f"operational goodput at "
            f"{percent(leader.get('score_weighted_operational_goodput'))}; "
            f"its unconstrained objective quality was "
            f"{percent(leader['quality_score'])}"
            f" ({interval_text({'low': leader['ranking_ci95_low'], 'high': leader['ranking_ci95_high'], 'degenerate': leader['ranking_ci95_degenerate']})} ranking-metric CI).** "
            f"It used "
            f"{'at least ' if leader.get('token_total_is_lower_bound') else ''}"
            f"{leader['total_tokens']:,} captured tokens, had "
            f"{'at least ' if leader.get('cost_total_is_lower_bound') else ''}"
            f"{money(leader['cost_usd'])} in captured cost, and had p50/p95 "
            f"end-to-end latency "
            f"of {seconds(leader['p50_latency_ms'])}s/"
            f"{seconds(leader['p95_latency_ms'])}s."
        ),
        "",
        (
            f"Of {len(pair_rows)} adjacent rank gaps, {separated_pairs} survive "
            "the paired randomization family at Holm-adjusted 5%. A gap that "
            "is neither significant nor practically equivalent is unresolved, "
            "not a tie."
            if pair_rows
            else "Only one endpoint was measured, so no ranking claim is made."
        ),
        "",
        (
            (
                f"{kendr['model']} delivered "
                f"{percent(kendr['final_reliability'])} final-answer "
                f"reliability against "
                f"{percent(kendr['raw_attempt_reliability'])} raw-attempt "
                f"reliability across {kendr['raw_attempts']} captured "
                "attempts. Its conservative compliance with the requested "
                f"{manifest['max_tokens']:,}-token cap was "
                f"{percent(kendr['output_cap_compliance'])}. "
                + (
                    "Because cap compliance was incomplete, its token and "
                    "cost figures require qualification."
                    if float(kendr["output_cap_compliance"] or 0) < 1
                    else (
                        "Cap conformance did not imply availability: some "
                        "capped outputs were rejected before an answer was "
                        "returned."
                        if float(kendr["final_reliability"] or 0) < 1
                        else "All captured attempts had verifiable cap data."
                    )
                )
            )
            if kendr
            else "Kendr Intelligent was not part of this panel."
        ),
        "",
        (
            f"The full paid pass captured {len(questions)} final records "
            f"({final_successes} successful and {final_failures} failed) from "
            f"{len(attempts)} raw attempts ({raw_failures} raw "
            f"{'failure' if raw_failures == 1 else 'failures'}), "
            f"{'at least ' if any(row.get('token_total_is_lower_bound') for row in metrics) else ''}"
            f"{total_input:,} input tokens, "
            f"{'at least ' if any(row.get('token_total_is_lower_bound') for row in metrics) else ''}"
            f"{total_output:,} output tokens, "
            f"and {'at least ' if any(row.get('cost_total_is_lower_bound') for row in metrics) else ''}"
            f"{money(total_cost)} in measured API cost."
        ),
        "",
        "This is a one-generation-per-model research slice. It is useful for controlled comparison but is not a statistically definitive claim about general model capability.",
        "Endpoints ran in sequential blocks rather than an interleaved order, so latency rankings are descriptive and may include backend or network time-of-run effects.",
        "",
        "## Overall leaderboard",
        "",
        markdown_table(
            [
                "#",
                "Tier",
                "Model/system",
                "Score-weighted goodput",
                "Quality",
                "Ranking-metric bootstrap 95% CI",
                "Final reliability",
                "Raw reliability",
                "Input tok.",
                "Output tok.",
                "Cost",
                "p50 s",
                "p95 s",
                "Cap compliance",
            ],
            overall_rows,
        ),
        "",
        "The interval resamples this question set only. It does not include generation-to-generation variance or benchmark-selection uncertainty. A `*` marks an interval whose bound is censored by the score scale or built from too few distinct resample values to read as an estimated limit — at this sample size a bound printed as `100.0%` means the resampled mean reached the ceiling, not that the endpoint is estimated to score perfectly.",
        "",
        "Tiers are descriptive overlap groups for marginal intervals. They do not establish either difference or equivalence.",
        "",
        "## Does each rank gap survive a paired test?",
        "",
        markdown_table(
            [
                "Higher rank",
                "Lower rank",
                "Mean difference",
                "95% CI",
                "W/L/T",
                "Raw p",
                "Holm p",
                "FWER 5%?",
                "Equivalent?",
            ],
            pair_rows
            or [["n/a"] * 8 + ["no pairs to compare"]],
        ),
        "",
        "The canonical leaderboard tests every endpoint pair with a two-sided paired sign-randomization test, then applies Holm family-wise correction. This table is the adjacent subset.",
        "",
        "## Quality by capability",
        "",
        markdown_table(
            [
                "Model/system",
                "Data analysis",
                "Instruction following",
                "Language",
                "Math",
                "Reasoning",
            ],
            capability_rows,
        ),
        "",
        "LiveBench task correctness and instruction compliance are the relevance proxy here. No separate generic semantic-relevance judge was used.",
        "",
        "## Efficiency",
        "",
        "Relative efficiency indices use direct OpenAI Sol as 1.00× and are shown only for endpoints with at least 80% final-answer reliability. Absolute captured ratios remain visible below that gate.",
        "",
        markdown_table(
            [
                "Model/system",
                "Tokens / quality point",
                "USD / quality point",
                "Quality points / USD",
                "Token efficiency vs Sol",
                "Cost efficiency vs Sol",
            ],
            efficiency_rows,
        ),
        "",
        "A quality point is one point on the 0–1 task scale, summed over questions. Token counts are provider-reported and tokenizer-specific, so cross-family token efficiency is directional rather than physically identical.",
        "`≥` and `≤` mark one-sided bounds inherited from missing failed-attempt usage or cost telemetry.",
        "",
        "## Reliability, retries, and output-cap telemetry",
        "",
        markdown_table(
            [
                "Model",
                "Request ID",
                "Latency s",
                "Route",
                "Error",
                "Message",
            ],
            error_rows,
        ),
        "",
        (
            f"Retried attempts are logged separately from final answers, so "
            f"final-answer and raw-attempt reliability are reported as distinct "
            f"numbers. The largest observed output across the panel was "
            f"{max((int(row['max_output_tokens_observed'] or 0) for row in metrics), default=0):,} "
            f"tokens against a requested cap of {manifest['max_tokens']:,}. "
            "A rejected over-cap generation counts as a violation even when "
            "it produces no answer; missing failure usage counts as unknown "
            "and reduces conservative cap conformance."
        ),
        "",
        (
            "Known contract gap in the inspected KendrWeb source: "
            "`/v1/chat/completions` deserializes `InferenceRequest`, which "
            "accepts `max_output_tokens` but not the OpenAI-compatible "
            "`max_tokens`, and an absent value falls back to "
            "`DEFAULT_MAX_OUTPUT_TOKENS = 4096`. The harness now sends both "
            "keys so the requested cap binds on either contract. Runs recorded "
            "before that change show cap compliance below 100% and must be "
            "re-measured before their token and cost axes are treated as "
            "controlled. `temperature` and `reasoning_effort` are still absent "
            "from the contract, so those controls remain unnormalized across "
            "Kendr-routed models."
        ),
        "",
        *trial_section,
        "## Kendr Intelligent routing",
        "",
        markdown_table(
            ["Selected route", "Routed attempts", "Share"], route_rows
        ),
        "",
        "Kendr is a routed system, so its score measures the combined router-plus-model behavior, latency, and billing—not one foundation model. The router also consumes tokens of its own on every request; those are inside the reported credits and therefore inside the cost, but they are not counted in its token totals.",
        "",
        *opus_section,
        "## Artifact map",
        "",
        "- `model-metrics.csv`: one row per model/system with quality, cost, tokens, latency, reliability, cap, and capability metrics.",
        f"- `question-level-results.csv`: all {len(questions)} final records joined to objective judgments and cumulative retry-inclusive tokens, observed cost, latency, and cap status; completeness flags identify one-sided telemetry bounds.",
        "- `raw-attempts.csv`: every provider attempt, including retries and errors.",
        "- `leaderboard.md`, `leaderboard.csv`, `leaderboard.json`: the standard matrix outputs.",
        "- `runs/<run-id>/`: raw calls, final records, judgments, task/group scores, and per-model reports.",
        "",
        "## Conclusion",
        "",
        (
            f"On the measured workload, {leader['model']} placed first on "
            "quality"
            + (
                f" and {kendr['model']} was "
                f"{multiplier(kendr_cost_ratio)} as cost-efficient as Sol by "
                "quality points per measured USD"
                if kendr_cost_ratio is not None
                else ""
            )
            + ". "
            + (
                "That cost ratio compares a Kendr invoice against OpenAI list "
                "price, so it is a buyer-facing ratio rather than an "
                "inference-cost ratio. "
                if kendr_cost_ratio is not None
                else "Relative efficiency is not promoted for endpoints below "
                "the 80% final-answer reliability gate. "
            )
            + "All measured output usage conformed to the requested output "
            "cap, but failed attempts without usage are conservatively "
            "unknown. Sampling and reasoning parameters remain "
            "provider-effective rather than normalized, so this is an "
            "endpoint-as-served comparison."
        ),
        "",
    ]
    return "\n".join(lines)


def _same_family_section(
    metrics: list[dict[str, Any]],
    questions: list[dict[str, Any]],
    left_key: str,
    right_key: str,
) -> list[str]:
    """Paired write-up for two related models, emitted only if both ran.

    Kept deliberately non-causal: with a handful of informative questions the
    honest statement is where the difference appeared, not why.
    """
    left = next((row for row in metrics if row["panel_key"] == left_key), None)
    right = next(
        (row for row in metrics if row["panel_key"] == right_key), None
    )
    if left is None or right is None:
        return []
    left_scores = left.get("_question_scores") or {}
    right_scores = right.get("_question_scores") or {}
    deltas = paired_deltas(left_scores, right_scores)
    if not deltas:
        return []
    interval = bootstrap_ci(
        deltas, seed=stable_seed(f"{left_key}|{right_key}")
    )
    low, high = interval["low"], interval["high"]
    separated = low > 0 or high < 0
    tasks = {
        row["question_id"]: row.get("task")
        for row in questions
        if row["panel_key"] in {left_key, right_key}
    }
    rows = []
    for question_id in sorted(
        left_scores.keys() & right_scores.keys(),
        key=lambda q: (str(tasks.get(q) or ""), q),
    ):
        delta = left_scores[question_id] - right_scores[question_id]
        rows.append(
            [
                tasks.get(question_id) or "n/a",
                question_id[:12],
                f"{left_scores[question_id]:.3f}",
                f"{right_scores[question_id]:.3f}",
                f"{delta:+.3f}",
            ]
        )
    informative = sum(delta != 0 for delta in deltas)
    differing_tasks = sorted(
        {
            str(tasks.get(question_id) or "unknown")
            for question_id in left_scores.keys() & right_scores.keys()
            if left_scores[question_id] != right_scores[question_id]
        }
    )
    return [
        f"## {left['model']} versus {right['model']}",
        "",
        (
            f"{left['model']} scored {percent(left['quality_score'])} and "
            f"{right['model']} scored {percent(right['quality_score'])}. The "
            f"paired mean difference was {sum(deltas) / len(deltas) * 100:+.1f} "
            f"percentage points with a 95% interval of {low * 100:+.1f} to "
            f"{high * 100:+.1f} points, so the two are "
            + (
                "separated at 95% confidence."
                if separated
                else "**not separated at 95% confidence**."
            )
            + f" {informative} of {len(deltas)} questions distinguished them at "
            f"all ({sum(d > 0 for d in deltas)} to "
            f"{sum(d < 0 for d in deltas)}), so this comparison rests on a very "
            "small number of informative items."
        ),
        "",
        markdown_table(
            [
                "Task",
                "Question ID",
                left["model"],
                right["model"],
                "Difference",
            ],
            rows,
        ),
        "",
        (
            "The difference appeared in "
            + (", ".join(differing_tasks) if differing_tasks else "no task")
            + ". No cause is attributed here: reasoning and sampling "
            "parameters were not normalized across these endpoints, the slice "
            "is small and sampled once, and an unseparated interval cannot "
            "support a claim about which model is stronger in general."
        ),
        "",
    ]


def methodology_document(
    root: Path,
    manifest: dict[str, Any],
    panel: dict[str, dict[str, Any]],
) -> str:
    research_rows = []
    for spec in manifest["models"]:
        research = model_research_for_spec(spec)
        research_rows.append(
            [
                spec["label"],
                spec["model"],
                research["architecture"],
                research["context"],
                research["max_output"],
                research["pricing"],
                spec["license"],
            ]
        )
    profile_sections = []
    for spec in manifest["models"]:
        research = model_research_for_spec(spec)
        profile_sections.extend(
            [
                f"### {spec['label']}",
                "",
                f"- Requested identifier: `{spec['model']}`",
                f"- Architecture/parameters: {research['architecture']}.",
                f"- Context: {research['context']}.",
                f"- Maximum output: {research['max_output']}.",
                f"- Knowledge: {research['knowledge']}.",
                f"- Modes: {research['modes']}.",
                f"- Price basis: {research['pricing']}.",
                f"- License/access: {spec['license']}; {spec['access']}.",
                f"- Research note: {research['notes']}",
                f"- Primary source: {research['source']}",
                "",
            ]
        )
    tasks = [task.rsplit("/", 1)[-1] for task in manifest["tasks"]]
    sampling = manifest.get("sampling") or {}
    sampling_dates = sampling.get("selected_date_distribution") or {}
    sampled_ids = sampling.get("selected_ids") or []
    planned_question_count = (
        len(sampled_ids)
        if sampled_ids
        else len(tasks) * int(manifest["questions_per_task"])
    )
    final_successes = sum(
        int(
            (data["summary"].get("reliability") or {}).get(
                "successful_answers", 0
            )
        )
        for data in panel.values()
    )
    final_failures = sum(
        int(
            (data["summary"].get("reliability") or {}).get(
                "failed_answers", 0
            )
        )
        for data in panel.values()
    )
    final_missing = sum(
        int(
            (data["summary"].get("reliability") or {}).get(
                "missing_answers", 0
            )
        )
        for data in panel.values()
    )
    final_record_detail = (
        f"{final_successes + final_failures} "
        f"({final_successes} successful, {final_failures} failed"
        + (f", {final_missing} missing" if final_missing else "")
        + ")"
    )
    finalizations: list[str] = []
    for data in panel.values():
        run_manifest_path = data["run_dir"] / "manifest.json"
        run_manifest = (
            read_json(run_manifest_path)
            if run_manifest_path.is_file()
            else {}
        )
        finalization = run_manifest.get("finalization") or {}
        if finalization:
            finalizations.append(
                f"{data['spec']['label']}: {data['run_dir'].name}, "
                f"{finalization.get('mode')}, provider inference replayed="
                f"{bool(finalization.get('provider_inference_replayed'))}"
            )
    kendr_entries = [
        data
        for data in panel.values()
        if data["spec"].get("provider") == "kendr"
    ]
    kendr_cap_patch_recorded = bool(kendr_entries) and all(
        KENDR_OUTPUT_CAP_COMPATIBILITY_PATCH
        in (
            read_json(data["run_dir"] / "manifest.json").get(
                "compatibility_patches", []
            )
            if (data["run_dir"] / "manifest.json").is_file()
            else []
        )
        for data in kendr_entries
    )
    requested_cap = int(manifest["max_tokens"])
    if kendr_cap_patch_recorded:
        kendr_chat_requested = (
            f"`temperature=0`, `max_tokens={requested_cap}`, and "
            f"`max_output_tokens={requested_cap}`"
        )
        kendr_chat_interpretation = (
            "The run manifests record the dual-field compatibility patch; "
            "`max_output_tokens` is the service-recognized limit. Observed "
            "cap compliance still determines whether the endpoint honored it."
        )
        kendr_provider_interpretation = (
            "Provider defaults govern temperature/thinking; the requested "
            "resolved output limit is forwarded."
        )
        cap_contract_summary = (
            "These runs record the compatibility patch that sends both the "
            "OpenAI-style `max_tokens` field and Kendr's recognized "
            "`max_output_tokens` field. Any observed over-cap output is "
            "therefore endpoint nonconformance, not an omitted client field. "
            "Temperature and reasoning-effort controls remain absent from "
            "Kendr's request contract."
        )
    else:
        kendr_chat_requested = (
            f"Historical run: `temperature=0`, `max_tokens={requested_cap}`"
        )
        kendr_chat_interpretation = (
            "The run manifests do not record the dual-field compatibility "
            "patch. Kendr recognizes `max_output_tokens`, so this legacy "
            "matrix may have fallen back to the service default."
        )
        kendr_provider_interpretation = (
            "Provider defaults governed temperature/thinking and the resolved "
            "service output limit in this legacy matrix."
        )
        cap_contract_summary = (
            "This matrix predates the recorded dual-field compatibility patch. "
            "Kendr's request contract recognizes `max_output_tokens`, not "
            "only the OpenAI-style `max_tokens` field, and defaults to 4,096 "
            "when the recognized field is absent. The current harness sends "
            "both fields, but these historical token and cost axes require a "
            "new run before they can be treated as controlled. Temperature "
            "and reasoning-effort controls likewise remain unnormalized."
        )
    # Read the pin from what the runs actually recorded rather than repeating a
    # literal that can drift away from the code.
    revision = next(
        (
            str(data["summary"]["livebench"]["revision"])
            for data in panel.values()
            if data["summary"].get("livebench", {}).get("revision")
        ),
        "unrecorded",
    )
    lines = [
        f"# Methodology and model documentation: {manifest['matrix_id']}",
        "",
        "## Reproduction identity",
        "",
        markdown_table(
            ["Parameter", "Value"],
            [
                ["LiveBench repository", "https://github.com/LiveBench/LiveBench"],
                ["Pinned commit", revision],
                ["Release", manifest["livebench_release"]],
                ["Tasks", ", ".join(tasks)],
                ["Questions per task", manifest["questions_per_task"]],
                ["Questions per model", planned_question_count],
                [
                    "Sampling",
                    (
                        f"{sampling.get('mode')} seed={sampling.get('seed')}"
                        if sampling
                        else "Legacy positional slice; exact preflight not recorded"
                    ),
                ],
                [
                    "Minimum release date",
                    sampling.get("minimum_release_date") or "None",
                ],
                [
                    "Selected question dates",
                    json.dumps(sampling_dates, sort_keys=True)
                    if sampling_dates
                    else "Not recorded in legacy manifest",
                ],
                [
                    "Eligible-pool SHA-256",
                    sampling.get("content_hash") or "Not recorded",
                ],
                ["Final records", final_record_detail],
                ["Requested output cap", manifest["max_tokens"]],
                [
                    "Final-answer deadline",
                    manifest.get("deadline_ms") or "Not configured",
                ],
                [
                    "Per-answer USD budget",
                    manifest.get("max_cost_usd_per_answer")
                    or "Not configured",
                ],
                ["Concurrent requests", manifest["parallel_requests"]],
                ["Concurrent grading", manifest["parallel_grading"]],
                ["Generation repeats", "1"],
                [
                    "Trial selection",
                    "Earliest run with captured provider calls; manifest-only "
                    "starts may be skipped and later outcome-bearing reruns "
                    "are excluded",
                ],
                [
                    "Interrupted-run finalization",
                    "; ".join(finalizations) if finalizations else "None",
                ],
                ["Streaming", "Off"],
                ["Tools/web search", "Off"],
                ["Kendr USD/credit", manifest["kendr_usd_per_credit"]],
            ],
        ),
        "",
        "Reproduction command:",
        "",
        "```powershell",
        (
            ".venv\\Scripts\\llm-benchmark-matrix.exe "
            f"--release {manifest['livebench_release']} "
            f"--questions-per-task {manifest['questions_per_task']} "
            f"--sample-mode {sampling.get('mode', 'seeded-random')} "
            f"--sample-seed {sampling.get('seed', 20260801)} "
            f"--max-tokens {manifest['max_tokens']} "
            f"--deadline-ms {manifest.get('deadline_ms', 120000)} "
            f"--parallel-requests {manifest['parallel_requests']} "
            f"--parallel-grading {manifest['parallel_grading']} "
            f"--reasoning-effort {manifest.get('reasoning_effort', 'none')} "
            "--confirm-paid-run --label all-models-final-protocol"
        ),
        "```",
        "",
        "Rebuild the reports without new API calls:",
        "",
        "```powershell",
        f".venv\\Scripts\\llm-benchmark-matrix.exe --rebuild \"{root}\"",
        f".venv\\Scripts\\python.exe scripts\\generate_matrix_documentation.py \"{root}\"",
        "```",
        "",
        "## What was measured",
        "",
        "LiveBench provides objective, task-specific ground-truth graders. New runs resolve the cumulative release pool before inference, select deterministic exact IDs per category/task, and persist both IDs and an eligible-pool content hash. Provider failures and missing planned work are normalized to zero while raw judgments and calls remain available.",
        "",
        "For matrix rebuilds, the first directory containing provider calls is the endpoint trial. A later rerun cannot replace it after outcomes are visible. If orchestration stopped after LiveBench wrote its answers, `llm-benchmark-livebench finalize` can grade and export that original trial without making another inference request, but only after all frozen question IDs link to captured calls.",
        "",
        "Measurements:",
        "",
        "- Quality: mean official objective score on the immutable planned-question denominator; provider failures and missing work count as zero.",
        "- Operational goodput: objective score delivered only when the answer succeeds and satisfies the retry-inclusive deadline, USD budget, and per-attempt output cap. Unknown required telemetry is zero in the conservative rate.",
        "- Relevance proxy: the same task-specific correctness and instruction-compliance score; no generic semantic judge.",
        "- Reliability: final answer success and raw provider-attempt success, reported separately.",
        "- Latency: cumulative final-answer service time across failed attempts, retries, and multi-turn calls. Attempt latency is retained separately; TTFT is unavailable.",
        "- Usage: provider-reported input, cached-input, reasoning, and output tokens when supplied.",
        "- Cost: direct OpenAI usage multiplied by the pinned local price catalog; Kendr uses provider-reported credits multiplied by $0.002/credit.",
        "- Efficiency: tokens and USD divided by accumulated quality points; these are derived research metrics, not official LiveBench fields.",
        "",
        "## Requested versus provider-effective parameters",
        "",
        markdown_table(
            ["Surface", "Requested", "Accepted/effective interpretation"],
            [
                [
                    "Direct OpenAI",
                    f"`temperature=0`, `max_completion_tokens={requested_cap}`, `reasoning_effort=none`",
                    "All three are sent through Chat Completions; observed cap compliance is reported per endpoint.",
                ],
                [
                    "Kendr OpenAI-compatible chat",
                    kendr_chat_requested,
                    kendr_chat_interpretation,
                ],
                [
                    "Kendr provider adapters",
                    "Messages, model alias, no tools, non-streaming",
                    kendr_provider_interpretation,
                ],
                [
                    "Opus 5 via Kendr",
                    "No explicit thinking/effort control",
                    "Anthropic documents thinking on by default and effort high by default.",
                ],
                [
                    "Opus 4.8 via Kendr",
                    "No explicit thinking/effort control",
                    "Anthropic documents adaptive thinking as off unless requested.",
                ],
                [
                    "Open-weight models via Kendr",
                    "No family-specific sampling controls",
                    "Provider defaults apply; this differs from some official local-serving recommendations.",
                ],
            ],
        ),
        "",
        "Because effective reasoning and sampling modes differ, this is an endpoint-as-served comparison. It is not a perfectly controlled foundation-model ablation.",
        "",
        "## Model parameter and commercial research table",
        "",
        markdown_table(
            [
                "Model/system",
                "Requested endpoint ID",
                "Architecture/size",
                "Context",
                "Advertised max output",
                "Price basis",
                "License",
            ],
            research_rows,
        ),
        "",
        "Undisclosed values are stated as undisclosed rather than estimated. Kendr credit equivalents use the run's $0.002-per-credit conversion and the captured model-catalog snapshot.",
        "",
        "## Model research profiles",
        "",
        *profile_sections,
        "## Cost and token interpretation",
        "",
        "- OpenAI Sol catalog: $5/M input, $0.50/M cached input, $30/M output.",
        "- OpenAI Terra catalog: $2.50/M input, $0.25/M cached input, $15/M output.",
        "- Kendr charges are the actual credits reported in each response, converted at the configured $0.002/credit.",
        "- Kendr Intelligent has no single static rate because routing is dynamic.",
        "- Cross-provider token counts are not tokenizer-normalized. Compare costs directly and treat raw token ratios as directional.",
        "- Human-readable USD values use decimal round-half-even to six places; JSON and CSV retain the captured precision.",
        "- No prompt in this slice crossed OpenAI's long-context pricing threshold.",
        "",
        "## Timeout and request-contract verification",
        "",
        "Transport behavior is reported from captured client attempts and error metadata. External proxy configuration is not inferred from benchmark responses; verify deployed timeouts separately when diagnosing 5xx or timeout failures.",
        "",
        cap_contract_summary,
        "",
        "Relevant inspected source:",
        "",
        "- `KendrWeb/cloud/services/model-api/src/main.rs`: `/v1/chat/completions` deserializes `InferenceRequest`.",
        "- `KendrWeb/cloud/crates/kendr-contracts/src/lib.rs`: `max_output_tokens` and the 4,096 default.",
        "- `KendrWeb/cloud/crates/kendr-providers/src/lib.rs`: resolved output limit forwarded to providers.",
        "- `KendrWeb/deploy/nginx/kendr-tls.conf.template`: `/v1/` timeout is 360 seconds.",
        "",
        "## Statistical and practical limitations",
        "",
        f"- Only {planned_question_count} planned questions per model and one generation per question: ranking noise can be large.",
        f"- This is a {len(tasks)}-task slice, not the complete public LiveBench suite.",
        "- Question-bootstrap intervals capture question-sampling uncertainty only. All endpoint pairs use paired sign-randomization with Holm family-wise correction; non-significance is not called a tie unless the interval also fits the declared practical-equivalence margin.",
        "- The LiveBench release option is cumulative. Freshness comes from the recorded selected-date distribution and optional minimum-release-date floor, not from the release label alone.",
        "- Models were served through different transports and provider defaults.",
        "- Endpoint blocks were sequential rather than interleaved, so latency ordering is descriptive and may include backend or network time-of-run effects.",
        "- Kendr Intelligent includes routing overhead and may select different models over time.",
        "- Non-streaming latency omits time-to-first-token and perceived streaming responsiveness.",
        "- The run did not test tool use, vision, long context, multi-turn behavior, safety, or production domain relevance.",
        "- Prices, aliases, model implementations, and endpoint defaults can change; use the captured manifest, catalog, commit, and raw responses for auditability.",
        "",
        "## Source index",
        "",
        "- LiveBench methodology and repository: https://github.com/LiveBench/LiveBench",
        "- OpenAI GPT-5.6 Sol: https://developers.openai.com/api/docs/models/gpt-5.6-sol",
        "- OpenAI GPT-5.6 Terra: https://developers.openai.com/api/docs/models/gpt-5.6-terra",
        "- Claude Opus 5: https://platform.claude.com/docs/en/about-claude/models/whats-new-opus-5",
        "- Claude Opus 4.8: https://platform.claude.com/docs/en/about-claude/models/whats-new-claude-4-8",
        "- GLM-5: https://github.com/zai-org/GLM-5",
        "- DeepSeek V3.2: https://huggingface.co/deepseek-ai/DeepSeek-V3.2",
        "- Kimi K2.5: https://github.com/MoonshotAI/Kimi-K2.5",
        "- Llama 4 Maverick: https://github.com/meta-llama/llama-models/blob/main/models/llama4/MODEL_CARD.md",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Rebuild the detailed report and methodology document for a "
            "completed matrix. Makes no API calls."
        )
    )
    parser.add_argument("matrix_root", type=Path)
    args = parser.parse_args()
    root = args.matrix_root.resolve()
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        print(f"Matrix manifest not found: {manifest_path}", file=sys.stderr)
        return 1
    manifest = read_json(manifest_path)
    if not (root / "runs").is_dir():
        print(f"No runs directory under {root}", file=sys.stderr)
        return 1
    panel = find_runs(root, manifest)
    if not panel:
        print(
            f"No usable runs found under {root / 'runs'}", file=sys.stderr
        )
        return 1
    metrics = build_metrics_rows(panel)
    questions = build_question_rows(panel, manifest["max_tokens"])
    attempts = build_attempt_rows(panel, manifest["max_tokens"])
    write_csv(root / "model-metrics.csv", metrics)
    write_csv(root / "question-level-results.csv", questions)
    write_csv(root / "raw-attempts.csv", attempts)
    (root / "detailed-report.md").write_text(
        detailed_report(root, manifest, panel, metrics, questions, attempts),
        encoding="utf-8",
    )
    (root / "methodology-and-model-documentation.md").write_text(
        methodology_document(root, manifest, panel),
        encoding="utf-8",
    )
    _write_artifact_hashes(root)
    print(root / "detailed-report.md")
    print(root / "methodology-and-model-documentation.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
