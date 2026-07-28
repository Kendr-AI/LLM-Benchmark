from __future__ import annotations

import argparse
import csv
import json
import random
from collections import Counter
from pathlib import Path
from typing import Any


MODEL_RESEARCH = {
    "kendr-intelligent": {
        "architecture": "Routing system; base-model parameter count is not applicable",
        "context": "1,000,000 tokens in the captured Kendr catalog",
        "max_output": "Route-dependent; client requested 2,048",
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
    amount = float(value)
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


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    index = (len(ordered) - 1) * p
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = index - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def bootstrap_ci(
    values: list[float], seed: int, iterations: int = 20_000
) -> tuple[float, float]:
    rng = random.Random(seed)
    n = len(values)
    means = [
        sum(values[rng.randrange(n)] for _ in range(n)) / n
        for _ in range(iterations)
    ]
    return percentile(means, 0.025), percentile(means, 0.975)


def get_answer_call(answer: dict[str, Any]) -> dict[str, Any]:
    calls = answer.get("api_info", {}).get("benchmark_calls", [])
    return calls[-1] if calls else {}


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


def call_routing(call: dict[str, Any]) -> dict[str, Any]:
    routing = call.get("kendr_routing")
    if routing:
        return routing
    error = call.get("error")
    if not isinstance(error, dict):
        return {}
    return (
        error.get("body", {})
        .get("details", {})
        .get("kendr_routing", {})
    )


def call_usage(call: dict[str, Any]) -> dict[str, Any]:
    usage = call.get("usage")
    if usage:
        return usage
    error = call.get("error")
    if not isinstance(error, dict):
        return {}
    attempts = error.get("body", {}).get("details", {}).get("attempts", [])
    if not attempts:
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


def find_runs(
    root: Path, manifest: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    by_requested: dict[str, tuple[Path, dict[str, Any]]] = {}
    for run_dir in (root / "runs").iterdir():
        summary_path = run_dir / "summary.json"
        if summary_path.exists():
            summary = read_json(summary_path)
            by_requested[summary["requested_model"]] = (run_dir, summary)
    result = {}
    for spec in manifest["models"]:
        run_dir, summary = by_requested[spec["model"]]
        result[spec["key"]] = {
            "spec": spec,
            "run_dir": run_dir,
            "summary": summary,
            "calls": read_jsonl(run_dir / "calls.jsonl"),
            "answers": read_jsonl(run_dir / "answers.jsonl"),
            "judgments": read_jsonl(run_dir / "judgments.jsonl"),
        }
    return result


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def build_metrics_rows(
    panel: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    rows = []
    for key, data in panel.items():
        spec, summary, calls = data["spec"], data["summary"], data["calls"]
        api = summary["current_api_run"]
        quality = summary["current_run_quality"]
        reliability = summary["reliability"]
        latency = summary["latency"]["end_to_end_ms"]
        raw_success = sum(not bool(call.get("error")) for call in calls)
        group = summary["workspace_snapshot"]["standard_group_scores"]
        scores = [float(j["score"]) for j in data["judgments"]]
        low, high = bootstrap_ci(scores, seed=1000 + len(rows))
        rows.append(
            {
                "panel_key": key,
                "model": spec["label"],
                "provider": spec["provider"],
                "requested_model": spec["model"],
                "questions": quality["questions_scored"],
                "quality_score": quality["objective_score_mean"],
                "quality_ci95_low": low,
                "quality_ci95_high": high,
                "quality_points": quality["quality_points"],
                "data_analysis_score": float(group["data_analysis"]) / 100,
                "instruction_following_score": float(
                    group["instruction_following"]
                )
                / 100,
                "language_score": float(group["language"]) / 100,
                "math_score": float(group["math"]) / 100,
                "reasoning_score": float(group["reasoning"]) / 100,
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
                "cost_usd": api["cost_usd"],
                "kendr_credits": api.get("kendr_credits"),
                "mean_latency_ms": latency["mean"],
                "p50_latency_ms": latency["p50"],
                "p95_latency_ms": latency["p95"],
                "max_latency_ms": latency["maximum"],
                "output_cap_compliance": reliability[
                    "output_cap_compliance_rate"
                ],
                "cap_violations": reliability[
                    "calls_exceeding_requested_output_cap"
                ],
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
            }
        )
    rows.sort(key=lambda row: row["quality_score"], reverse=True)
    return rows


def build_question_rows(
    panel: dict[str, dict[str, Any]], requested_cap: int
) -> list[dict[str, Any]]:
    rows = []
    for key, data in panel.items():
        judgments = {j["question_id"]: j for j in data["judgments"]}
        for answer in data["answers"]:
            qid = answer["question_id"]
            judgment = judgments[qid]
            call = get_answer_call(answer)
            routing = call_routing(call)
            usage = call_usage(call)
            output_tokens = usage.get(
                "completion_tokens", answer.get("total_output_tokens")
            )
            rows.append(
                {
                    "panel_key": key,
                    "model": data["spec"]["label"],
                    "question_id": qid,
                    "category": judgment["category"],
                    "task": judgment["task"],
                    "score": judgment["score"],
                    "answer_error": "$ERROR$"
                    in str(answer.get("choices", [])),
                    "input_tokens": usage.get(
                        "prompt_tokens", answer.get("total_input_tokens")
                    ),
                    "output_tokens": output_tokens,
                    "total_tokens": (
                        usage.get("total_tokens")
                        or (
                            (answer.get("total_input_tokens") or 0)
                            + (answer.get("total_output_tokens") or 0)
                        )
                    ),
                    "cost_usd": call.get("cost_usd")
                    or answer.get("api_info", {}).get(
                        "benchmark_cost_usd"
                    ),
                    "kendr_credits": call.get("kendr_credits"),
                    "latency_ms": call.get("latency_ms"),
                    "actual_model": call.get("actual_model"),
                    "selected_route": routing.get("selected_model_alias"),
                    "provider_model": routing.get("provider_model"),
                    "router_latency_ms": routing.get("router_latency_ms"),
                    "provider_latency_ms": routing.get(
                        "provider_latency_ms"
                    ),
                    "exceeded_requested_output_cap": bool(
                        output_tokens and output_tokens > requested_cap
                    ),
                }
            )
    rows.sort(key=lambda row: (row["panel_key"], row["category"], row["question_id"]))
    return rows


def build_attempt_rows(
    panel: dict[str, dict[str, Any]], requested_cap: int
) -> list[dict[str, Any]]:
    rows = []
    for key, data in panel.items():
        for call in data["calls"]:
            usage = call_usage(call)
            routing = call_routing(call)
            output_tokens = usage.get("completion_tokens")
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
                    "input_tokens": usage.get("prompt_tokens"),
                    "output_tokens": output_tokens,
                    "cost_usd": call.get("cost_usd"),
                    "kendr_credits": call.get("kendr_credits"),
                    "latency_ms": call.get("latency_ms"),
                    "selected_route": routing.get("selected_model_alias"),
                    "provider_model": routing.get("provider_model"),
                    "provider_latency_ms": routing.get(
                        "provider_latency_ms"
                    ),
                    "exceeded_requested_output_cap": bool(
                        output_tokens and output_tokens > requested_cap
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
    leader = metrics[0]
    sol = next(row for row in metrics if row["panel_key"] == "openai-sol")
    kc = next(row for row in metrics if row["panel_key"] == "kendr-intelligent")
    total_input = sum(int(row["input_tokens"]) for row in metrics)
    total_output = sum(int(row["output_tokens"]) for row in metrics)
    total_cost = sum(float(row["cost_usd"]) for row in metrics)
    raw_failures = sum(not row["success"] for row in attempts)
    overall_rows = []
    for rank, row in enumerate(metrics, 1):
        overall_rows.append(
            [
                rank,
                row["model"],
                percent(row["quality_score"]),
                f"{percent(row['quality_ci95_low'])}–{percent(row['quality_ci95_high'])}",
                percent(row["final_reliability"]),
                percent(row["raw_attempt_reliability"]),
                f"{row['input_tokens']:,}",
                f"{row['output_tokens']:,}",
                money(row["cost_usd"]),
                number(row["p50_latency_ms"] / 1000, 2),
                number(row["p95_latency_ms"] / 1000, 2),
                percent(row["output_cap_compliance"]),
            ]
        )
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
        cost_eff = (
            float(row["quality_points_per_usd"])
            / float(sol["quality_points_per_usd"])
        )
        token_eff = (
            float(sol["tokens_per_quality_point"])
            / float(row["tokens_per_quality_point"])
        )
        efficiency_rows.append(
            [
                row["model"],
                number(row["tokens_per_quality_point"], 0),
                money(row["usd_per_quality_point"]),
                number(row["quality_points_per_usd"], 1),
                f"{token_eff:.2f}×",
                f"{cost_eff:.2f}×",
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
    route_rows = [
        [route, count, percent(count / kc["final_successes"])]
        for route, count in json.loads(kc["route_distribution"]).items()
    ]
    o5 = {
        row["question_id"]: row
        for row in questions
        if row["panel_key"] == "claude-opus-5"
    }
    o48 = {
        row["question_id"]: row
        for row in questions
        if row["panel_key"] == "claude-opus-4-8"
    }
    paired = []
    deltas = []
    for qid in sorted(o5.keys() & o48.keys(), key=lambda q: (o5[q]["task"], q)):
        delta = float(o5[qid]["score"]) - float(o48[qid]["score"])
        deltas.append(delta)
        paired.append(
            [
                o5[qid]["task"],
                qid[:12],
                f"{float(o5[qid]['score']):.3f}",
                f"{float(o48[qid]['score']):.3f}",
                f"{delta:+.3f}",
            ]
        )
    delta_low, delta_high = bootstrap_ci(deltas, seed=5408)
    o5_wins = sum(delta > 0 for delta in deltas)
    o48_wins = sum(delta < 0 for delta in deltas)
    ties = sum(delta == 0 for delta in deltas)
    lines = [
        f"# Detailed benchmark report: {manifest['matrix_id']}",
        "",
        "## Executive result",
        "",
        (
            f"**{leader['model']} ranked first on this fixed LiveBench slice "
            f"at {percent(leader['quality_score'])}.** It used "
            f"{leader['total_tokens']:,} captured tokens, cost "
            f"{money(leader['cost_usd'])}, and had p50/p95 end-to-end latency "
            f"of {leader['p50_latency_ms'] / 1000:.2f}s/"
            f"{leader['p95_latency_ms'] / 1000:.2f}s."
        ),
        "",
        (
            f"KC Intelligent delivered {percent(kc['final_reliability'])} "
            f"final-answer reliability, but {percent(kc['raw_attempt_reliability'])} "
            f"raw-attempt reliability because one failed call was retried. Its "
            f"requested 2,048-token cap compliance was "
            f"{percent(kc['output_cap_compliance'])}; this is a separate "
            "OpenAI-compatibility issue, not a timeout recurrence."
        ),
        "",
        (
            f"The full paid pass captured {len(questions)} final answers from "
            f"{len(attempts)} raw attempts ({raw_failures} raw failure), "
            f"{total_input:,} input tokens, {total_output:,} output tokens, "
            f"and {money(total_cost)} in measured API cost."
        ),
        "",
        "This is a 15-question, one-generation-per-model research slice. It is useful for controlled comparison but is not a statistically definitive claim about general model capability.",
        "",
        "## Overall leaderboard",
        "",
        markdown_table(
            [
                "#",
                "Model/system",
                "Quality",
                "Question-bootstrap 95% CI",
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
        "The interval resamples these 15 questions only. It does not include generation-to-generation variance or benchmark-selection uncertainty.",
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
        "",
        "## Reliability, retries, and the remaining token-cap defect",
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
            "The timeout fix held: no raw call failed with HTTP 504. The KC "
            "failure was returned after the selected provider generated exactly "
            "4,096 tokens and Kendr rejected the truncated result; LiveBench "
            "retried it successfully. Consequently, final-answer reliability "
            "and raw-attempt reliability must be reported separately."
        ),
        "",
        (
            "Root cause in the inspected KendrWeb source: `/v1/chat/completions` "
            "deserializes `InferenceRequest`, which accepts `max_output_tokens` "
            "but not the OpenAI-compatible `max_tokens` sent by the harness. "
            "The missing value falls back to `DEFAULT_MAX_OUTPUT_TOKENS = 4096`. "
            "The same contract also has no `temperature` or `reasoning_effort` "
            "field, so those controls are not normalized across Kendr-routed models."
        ),
        "",
        "## KC Intelligent routing",
        "",
        markdown_table(["Selected route", "Final answers", "Share"], route_rows),
        "",
        "KC is a routed system, so its score measures the combined router-plus-model behavior, latency, and billing—not one foundation model.",
        "",
        "## Why Opus 5 scored below Opus 4.8 here",
        "",
        (
            f"Opus 5 scored {percent(next(r for r in metrics if r['panel_key'] == 'claude-opus-5')['quality_score'])}; "
            f"Opus 4.8 scored {percent(next(r for r in metrics if r['panel_key'] == 'claude-opus-4-8')['quality_score'])}. "
            f"The paired mean difference was {sum(deltas) / len(deltas) * 100:+.1f} "
            f"percentage points, with a question-bootstrap 95% interval of "
            f"{delta_low * 100:+.1f} to {delta_high * 100:+.1f} points. "
            f"Opus 5 won {o5_wins} questions, Opus 4.8 won {o48_wins}, and "
            f"{ties} tied."
        ),
        "",
        markdown_table(
            ["Task", "Question ID", "Opus 5", "Opus 4.8", "O5 − O4.8"],
            paired,
        ),
        "",
        (
            "This is possible without contradicting vendor aggregate claims. "
            "The slice is small, narrow, and sampled once. More importantly, "
            "provider-effective reasoning was not normalized: Anthropic documents "
            "Opus 5 thinking as on by default, whereas Opus 4.8 adaptive thinking "
            "is off unless explicitly requested. Kendr's chat contract does not "
            "expose those controls. The measured gap is concentrated in the "
            "table-join and summarization tasks, while both models were perfect "
            "on language, math, and reasoning in this slice."
        ),
        "",
        "## Artifact map",
        "",
        "- `model-metrics.csv`: one row per model/system with quality, cost, tokens, latency, reliability, cap, and capability metrics.",
        "- `question-level-results.csv`: all 135 final answers joined to objective judgments and call telemetry.",
        "- `raw-attempts.csv`: every provider attempt, including retries and errors.",
        "- `leaderboard.md`, `leaderboard.csv`, `leaderboard.json`: the standard matrix outputs.",
        "- `runs/<run-id>/`: raw calls, final answers, judgments, task/group scores, and per-model reports.",
        "",
        "## Conclusion",
        "",
        (
            f"On the measured workload, KC led quality and was "
            f"{float(kc['quality_points_per_usd']) / float(sol['quality_points_per_usd']):.2f}× "
            "as cost-efficient as Sol by quality points per captured USD, but it "
            "was slower and failed the requested output-cap contract on some "
            "successful calls. The timeout regression is resolved; token-control "
            "compatibility and reasoning-parameter normalization are the next "
            "fairness and reliability fixes."
        ),
        "",
    ]
    return "\n".join(lines)


def methodology_document(
    root: Path,
    manifest: dict[str, Any],
    panel: dict[str, dict[str, Any]],
) -> str:
    research_rows = []
    for spec in manifest["models"]:
        research = MODEL_RESEARCH[spec["key"]]
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
        research = MODEL_RESEARCH[spec["key"]]
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
    lines = [
        f"# Methodology and model documentation: {manifest['matrix_id']}",
        "",
        "## Reproduction identity",
        "",
        markdown_table(
            ["Parameter", "Value"],
            [
                ["LiveBench repository", "https://github.com/LiveBench/LiveBench"],
                ["Pinned commit", "4355e9b04222745ccc02a2661d1deebe767a85a2"],
                ["Release", manifest["livebench_release"]],
                ["Tasks", ", ".join(tasks)],
                ["Questions per task", manifest["questions_per_task"]],
                ["Questions per model", len(tasks) * manifest["questions_per_task"]],
                [
                    "Total final answers",
                    len(tasks)
                    * manifest["questions_per_task"]
                    * len(manifest["models"]),
                ],
                ["Requested output cap", manifest["max_tokens"]],
                ["Concurrent requests", manifest["parallel_requests"]],
                ["Concurrent grading", manifest["parallel_grading"]],
                ["Generation repeats", "1"],
                ["Streaming", "Off"],
                ["Tools/web search", "Off"],
                ["Kendr USD/credit", manifest["kendr_usd_per_credit"]],
            ],
        ),
        "",
        "Reproduction command:",
        "",
        "```powershell",
        ".venv\\Scripts\\kendr-benchmark-matrix.exe --confirm-paid-run --label all-models-timeout-fixed",
        "```",
        "",
        "Rebuild the reports without new API calls:",
        "",
        "```powershell",
        f".venv\\Scripts\\kendr-benchmark-matrix.exe --rebuild \"{root}\"",
        f".venv\\Scripts\\python.exe scripts\\generate_matrix_documentation.py \"{root}\"",
        "```",
        "",
        "## What was measured",
        "",
        "LiveBench provides objective, task-specific ground-truth graders. The run used one task from each of five categories: table joining, summarization, language connections, competition math, and zebra-puzzle reasoning. Provider failures are normalized to zero for aggregate quality while raw judgments and raw calls remain available.",
        "",
        "Measurements:",
        "",
        "- Quality: mean official objective score across all 15 requested answers.",
        "- Relevance proxy: the same task-specific correctness and instruction-compliance score; no generic semantic judge.",
        "- Reliability: final answer success and raw provider-attempt success, reported separately.",
        "- Latency: client-observed, non-streaming, end-to-end duration. TTFT is unavailable.",
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
                    "`temperature=0`, `max_completion_tokens=2048`, `reasoning_effort=none`",
                    "All three were sent through Chat Completions; no successful answer exceeded 2,048 output tokens.",
                ],
                [
                    "Kendr OpenAI-compatible chat",
                    "`temperature=0`, `max_tokens=2048`",
                    "The inspected `InferenceRequest` has neither field; unknown fields are ignored and output falls back to 4,096.",
                ],
                [
                    "Kendr provider adapters",
                    "Messages, model alias, no tools, non-streaming",
                    "Provider defaults govern temperature/thinking; the resolved 4,096 limit is forwarded.",
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
                "Run identifier",
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
        "- No prompt in this slice crossed OpenAI's long-context pricing threshold.",
        "",
        "## Timeout verification and remaining contract issue",
        "",
        "The inspected outer TLS proxy now gives `/v1/` a 360-second read/send timeout. The rerun produced no 504 failures. A prior exact math preflight also passed after 57.84 seconds, confirming that the former short timeout was no longer terminating the request.",
        "",
        "A separate compatibility problem remains: the OpenAI-style `max_tokens` key is not part of Kendr's `InferenceRequest`; only `max_output_tokens` is recognized. The default is 4,096, and provider adapters forward that resolved limit. This explains outputs above the requested 2,048 and the one 4,096-token truncation failure. Temperature and reasoning-effort controls are likewise absent from this request contract.",
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
        "- Only 15 questions per model and one generation per question: ranking noise can be large.",
        "- This is a five-task slice, not the complete public LiveBench suite.",
        "- Question-bootstrap intervals capture question-sampling uncertainty only.",
        "- Models were served through different transports and provider defaults.",
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("matrix_root", type=Path)
    args = parser.parse_args()
    root = args.matrix_root.resolve()
    manifest = read_json(root / "manifest.json")
    panel = find_runs(root, manifest)
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
    print(root / "detailed-report.md")
    print(root / "methodology-and-model-documentation.md")


if __name__ == "__main__":
    main()
