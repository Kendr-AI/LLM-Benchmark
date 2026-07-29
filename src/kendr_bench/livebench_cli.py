from __future__ import annotations

import argparse
import csv
import json
import math
import os
import shutil
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from secrets import token_hex
from typing import Any, Iterable, Mapping, Sequence

from .cli import load_environment
from .livebench_adapter import (
    KENDR_LIVEBENCH_CALL_LOG,
    KENDR_LIVEBENCH_RUN_ID,
    KENDR_LIVEBENCH_USD_PER_CREDIT,
    LIVEBENCH_PRICING_PATH,
    OPENAI_LIVEBENCH_REASONING_EFFORT,
)
from .providers import KENDR_DEFAULT_USD_PER_CREDIT
from .livebench_worker import INSTRUCTION_FOLLOWING_COMPATIBILITY_PATCH

LIVEBENCH_REPOSITORY = "https://github.com/LiveBench/LiveBench.git"
LIVEBENCH_REVISION = "4355e9b04222745ccc02a2661d1deebe767a85a2"
DEFAULT_LIVEBENCH_ROOT = Path(".vendor/LiveBench")
DEFAULT_LIVEBENCH_CONSTRAINTS = Path("config/livebench-constraints.txt")
DEFAULT_API_BASE = "https://kendr.org/v1"
OPENAI_API_BASE = "https://api.openai.com/v1"
DEFAULT_PRICING_PATH = Path("config/pricing.json")
DEFAULT_RELEASE = "2024-11-25"
DEFAULT_BENCHMARKS = (
    "live_bench/coding",
    "live_bench/data_analysis",
    "live_bench/instruction_following",
    "live_bench/language",
    "live_bench/math",
    "live_bench/reasoning",
)
GENERATED_SCORE_FILES = (
    "all_groups.csv",
    "all_tasks.csv",
    "df_raw.csv",
    "group_usage.csv",
    "task_usage.csv",
)


def _package_versions() -> dict[str, str | None]:
    packages = ("livebench", "openai", "datasets", "pandas", "litellm")
    versions: dict[str, str | None] = {}
    for package in packages:
        try:
            versions[package] = version(package)
        except PackageNotFoundError:
            versions[package] = None
    return versions


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def _positive_decimal(value: str) -> Decimal:
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise argparse.ArgumentTypeError("must be a decimal number") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def _safe_label(value: str) -> str:
    cleaned = "".join(
        character if character.isalnum() or character in "-_" else "-"
        for character in value.strip()
    ).strip("-_")
    return cleaned[:48]


def _run_id(label: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    parts = [timestamp]
    cleaned = _safe_label(label)
    if cleaned:
        parts.append(cleaned)
    parts.append(token_hex(4))
    return "-".join(parts)


def _run_command(
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> None:
    printable = subprocess.list2cmdline([str(item) for item in command])
    print(f"Running: {printable}")
    subprocess.run(
        [str(item) for item in command],
        cwd=cwd,
        env=dict(env) if env is not None else None,
        check=True,
    )


def _git_output(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _validate_checkout(root: Path) -> tuple[bool, str]:
    if not (root / ".git").is_dir():
        return False, f"LiveBench source checkout not found at {root}"
    try:
        revision = _git_output(root, "rev-parse", "HEAD")
    except (OSError, subprocess.CalledProcessError) as exc:
        return False, f"Could not inspect LiveBench checkout: {exc}"
    if revision != LIVEBENCH_REVISION:
        return (
            False,
            "LiveBench checkout is not at the benchmark pin "
            f"{LIVEBENCH_REVISION}; found {revision}",
        )
    if not (root / "livebench" / "gen_api_answer.py").is_file():
        return False, f"Invalid LiveBench source checkout at {root}"
    return True, revision


def setup_livebench(root: Path) -> None:
    root = root.resolve()
    if root.exists():
        valid, detail = _validate_checkout(root)
        if not valid:
            raise RuntimeError(
                f"{detail}. Existing files were left unchanged."
            )
        print(f"Using pinned LiveBench checkout: {root}")
    else:
        root.parent.mkdir(parents=True, exist_ok=True)
        _run_command(["git", "clone", LIVEBENCH_REPOSITORY, str(root)])
        _run_command(["git", "-C", str(root), "checkout", LIVEBENCH_REVISION])

    command = [sys.executable, "-m", "pip", "install"]
    if DEFAULT_LIVEBENCH_CONSTRAINTS.is_file():
        command.extend(
            ["--constraint", str(DEFAULT_LIVEBENCH_CONSTRAINTS.resolve())]
        )
    command.extend(["-e", str(root)])
    _run_command(command)
    print(f"LiveBench ready at {root}")


def _add_shared_run_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--livebench-root",
        type=Path,
        default=DEFAULT_LIVEBENCH_ROOT,
        help="Pinned LiveBench source checkout (default: .vendor/LiveBench)",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(".env"),
        help="Environment file to load (default: .env)",
    )
    parser.add_argument("--no-env-file", action="store_true")
    parser.add_argument(
        "--provider",
        choices=("kendr", "openai"),
        default="kendr",
        help="API provider to instrument (default: kendr)",
    )
    parser.add_argument("--model", default="kendr-intelligent")
    parser.add_argument(
        "--model-display-name",
        default="kendr-intelligent",
        help="Stable model name written into LiveBench result files",
    )
    parser.add_argument(
        "--api-base",
        default=None,
        help="Provider base URL; defaults to the selected provider endpoint",
    )
    parser.add_argument(
        "--reasoning-effort",
        default="none",
        help="Explicit reasoning effort for direct OpenAI models",
    )
    parser.add_argument(
        "--pricing",
        type=Path,
        default=DEFAULT_PRICING_PATH,
        help="Versioned pricing catalog used for direct OpenAI cost estimates",
    )
    parser.add_argument(
        "--bench-name",
        nargs="+",
        default=list(DEFAULT_BENCHMARKS),
        help="One or more official LiveBench category/task paths",
    )
    parser.add_argument(
        "--livebench-release-option",
        default=DEFAULT_RELEASE,
        help="Pinned public LiveBench release (default: 2024-11-25)",
    )
    parser.add_argument("--max-tokens", type=_positive_int, default=4096)
    parser.add_argument(
        "--parallel-requests", type=_positive_int, default=1
    )
    parser.add_argument("--parallel-grading", type=_positive_int, default=1)
    parser.add_argument("--question-begin", type=int)
    parser.add_argument("--question-end", type=int)
    parser.add_argument("--question-id", nargs="+")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--retry-failures", action="store_true")
    parser.add_argument("--skip-inference", action="store_true")
    parser.add_argument("--skip-grading", action="store_true")
    parser.add_argument("--ignore-missing-answers", action="store_true")
    parser.add_argument(
        "--kendr-usd-per-credit",
        type=_positive_decimal,
        default=None,
        help="USD value of one Kendr credit",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/livebench"),
    )
    parser.add_argument("--label", default="")
    parser.add_argument(
        "--confirm-full",
        action="store_true",
        help=(
            "Required for an unrestricted run of all six default categories; "
            "the suite is large and chargeable"
        ),
    )
    parser.add_argument(
        "--compare-model",
        action="append",
        default=[],
        help=(
            "Include a model already present in the LiveBench workspace in "
            "the standard score tables; repeat for multiple models"
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kendr-livebench",
        description=(
            "Run kendr-intelligent through pinned, unmodified LiveBench questions "
            "and graders while retaining Kendr cost and routing metadata."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    setup = subparsers.add_parser(
        "setup", help="Clone and install the pinned LiveBench source"
    )
    setup.add_argument(
        "--livebench-root",
        type=Path,
        default=DEFAULT_LIVEBENCH_ROOT,
    )

    status = subparsers.add_parser(
        "status", help="Check the LiveBench source pin"
    )
    status.add_argument(
        "--livebench-root",
        type=Path,
        default=DEFAULT_LIVEBENCH_ROOT,
    )

    summarize = subparsers.add_parser(
        "summarize",
        help="Rebuild derived metrics for an existing exported run",
    )
    summarize.add_argument("run_dir", type=Path)
    summarize.add_argument(
        "--livebench-root",
        type=Path,
        default=DEFAULT_LIVEBENCH_ROOT,
    )
    summarize.add_argument(
        "--kendr-usd-per-credit",
        type=_positive_decimal,
        default=None,
    )

    run = subparsers.add_parser(
        "run", help="Generate Kendr answers, grade them, and export artifacts"
    )
    _add_shared_run_arguments(run)
    return parser


def _generation_command(args: argparse.Namespace, root: Path) -> list[str]:
    command = [
        sys.executable,
        "-m",
        "kendr_bench.livebench_worker",
        "--livebench-root",
        str(root),
        "--adapter",
        getattr(args, "provider", "kendr"),
        "--model",
        args.model,
        "--model-display-name",
        args.model_display_name,
        "--api-base",
        args.api_base,
        "--question-source",
        "huggingface",
        "--bench-name",
        *args.bench_name,
        "--livebench-release-option",
        args.livebench_release_option,
        "--max-tokens",
        str(args.max_tokens),
        "--parallel",
        str(args.parallel_requests),
        "--num-choices",
        "1",
    ]
    if args.question_begin is not None:
        command.extend(["--question-begin", str(args.question_begin)])
    if args.question_end is not None:
        command.extend(["--question-end", str(args.question_end)])
    if args.question_id:
        command.extend(["--question-id", *args.question_id])
    if args.resume:
        command.append("--resume")
    if args.retry_failures:
        command.append("--retry-failures")
    return command


def _grading_command(args: argparse.Namespace, root: Path) -> list[str]:
    command = [
        sys.executable,
        "-m",
        "kendr_bench.livebench_worker",
        "--livebench-root",
        str(root),
        "--mode",
        "grading",
        "--model",
        args.model,
        "--model-display-name",
        args.model_display_name,
        "--question-source",
        "huggingface",
        "--bench-name",
        *args.bench_name,
        "--livebench-release-option",
        args.livebench_release_option,
        "--parallel",
        str(args.parallel_grading),
    ]
    if args.question_begin is not None:
        command.extend(["--question-begin", str(args.question_begin)])
    if args.question_end is not None:
        command.extend(["--question-end", str(args.question_end)])
    if args.question_id:
        command.extend(["--question-id", *args.question_id])
    if args.resume:
        command.append("--resume")
    if args.ignore_missing_answers:
        command.append("--ignore-missing-answers")
    return command


def _show_command(args: argparse.Namespace, root: Path) -> list[str]:
    models = [args.model_display_name, *args.compare_model]
    command = [
        sys.executable,
        "-m",
        "kendr_bench.livebench_worker",
        "--livebench-root",
        str(root),
        "--mode",
        "show",
        "--question-source",
        "huggingface",
        "--bench-name",
        *args.bench_name,
        "--model-list",
        *models,
        "--livebench-release-option",
        args.livebench_release_option,
        "--print-usage",
    ]
    if (
        args.question_begin is not None
        or args.question_end is not None
        or args.question_id
        or args.ignore_missing_answers
    ):
        command.append("--ignore-missing-judgments")
    return command


def _paths_for_benches(
    work_dir: Path, benches: Iterable[str], tail: str
) -> list[Path]:
    paths: set[Path] = set()
    for bench in benches:
        base = work_dir / "data"
        for component in bench.split("/"):
            base /= component
        if not base.exists():
            continue
        paths.update(base.rglob(tail))
    return sorted(paths)


def _read_jsonl(paths: Iterable[Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in paths:
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    record = json.loads(line)
                    record["_source_file"] = str(path)
                    records.append(record)
    return records


def _write_jsonl(path: Path, records: Iterable[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(
                json.dumps(record, ensure_ascii=False, sort_keys=True)
            )
            handle.write("\n")


def _read_calls(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return _read_jsonl([path])


def _credits_from_call(call: Mapping[str, Any]) -> Decimal | None:
    usage = call.get("kendr_usage")
    if not isinstance(usage, Mapping):
        return None
    for key in ("credits_charged", "total_credits"):
        value = usage.get(key)
        if value is not None:
            return Decimal(str(value))
    for key in (
        "credits_charged_micros",
        "credit_micros_charged",
        "total_credit_micros",
    ):
        value = usage.get(key)
        if value is not None:
            return Decimal(str(value)) / Decimal(1_000_000)
    return None


def _model_judgments(
    records: Iterable[Mapping[str, Any]], model: str
) -> list[dict[str, Any]]:
    expected = model.lower()
    return [
        dict(record)
        for record in records
        if str(record.get("model", "")).lower() == expected
    ]


def _copy_score_files(work_dir: Path, run_dir: Path) -> list[str]:
    copied: list[str] = []
    for name in GENERATED_SCORE_FILES:
        source = work_dir / name
        if source.is_file():
            shutil.copy2(source, run_dir / name)
            copied.append(name)
    return copied


def _standard_group_scores(path: Path, model: str) -> dict[str, str]:
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            row_model = row.get("model") or row.get("") or ""
            if row_model.lower() == model.lower():
                return {
                    key or "model": value
                    for key, value in row.items()
                    if value not in (None, "")
                }
    return {}


def _percentile(values: Sequence[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile / 100
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _distribution_stats(values: Sequence[float]) -> dict[str, float | None]:
    return {
        "minimum": min(values) if values else None,
        "mean": sum(values) / len(values) if values else None,
        "p50": _percentile(values, 50),
        "p95": _percentile(values, 95),
        "p99": _percentile(values, 99),
        "maximum": max(values) if values else None,
    }


def _current_run_question_ids(
    calls: Sequence[Mapping[str, Any]],
    answers: Sequence[Mapping[str, Any]],
) -> set[str]:
    request_ids = {
        str(call.get("request_id"))
        for call in calls
        if call.get("request_id")
    }
    question_ids: set[str] = set()
    for answer in answers:
        api_info = answer.get("api_info")
        if not isinstance(api_info, Mapping):
            continue
        answer_calls = api_info.get("benchmark_calls")
        if not isinstance(answer_calls, list):
            answer_calls = api_info.get("kendr_calls")
        if not isinstance(answer_calls, list):
            continue
        if any(
            isinstance(item, Mapping)
            and str(item.get("request_id")) in request_ids
            for item in answer_calls
        ):
            question_id = answer.get("question_id")
            if question_id:
                question_ids.add(str(question_id))
    return question_ids


def _safe_ratio(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator else None


def _write_metrics_csv(
    path: Path, summary: Mapping[str, Any]
) -> None:
    api = summary["current_api_run"]
    quality = summary["current_run_quality"]
    efficiency = summary["efficiency"]
    latency = summary["latency"]
    reliability = summary["reliability"]
    row = {
        "run_id": summary["run_id"],
        "provider": api.get("provider"),
        "model": summary["model"],
        "calls": api["calls"],
        "input_tokens": api["input_tokens"],
        "output_tokens": api["output_tokens"],
        "total_tokens": api["total_tokens"],
        "kendr_credits": api["kendr_credits"],
        "kendr_cost_usd": api["kendr_cost_usd"],
        "cost_usd": api.get("cost_usd"),
        "questions_matched": quality["questions_matched_to_current_calls"],
        "questions_scored": quality["questions_scored"],
        "objective_score_mean": quality["objective_score_mean"],
        "perfect_score_rate": quality["perfect_score_rate"],
        "nonzero_score_rate": quality["nonzero_score_rate"],
        "quality_points_per_1000_tokens": efficiency[
            "quality_points_per_1000_tokens"
        ],
        "total_tokens_per_quality_point": efficiency[
            "total_tokens_per_quality_point"
        ],
        "credits_per_quality_point": efficiency[
            "credits_per_quality_point"
        ],
        "usd_per_quality_point": efficiency["usd_per_quality_point"],
        "output_to_input_token_ratio": efficiency[
            "output_to_input_token_ratio"
        ],
        "output_tokens_per_second": efficiency[
            "output_tokens_per_second"
        ],
        "quality_points_per_second": efficiency[
            "quality_points_per_second"
        ],
        "latency_ms_per_quality_point": efficiency[
            "latency_ms_per_quality_point"
        ],
        "latency_mean_ms": latency["end_to_end_ms"]["mean"],
        "latency_p50_ms": latency["end_to_end_ms"]["p50"],
        "latency_p95_ms": latency["end_to_end_ms"]["p95"],
        "latency_p99_ms": latency["end_to_end_ms"]["p99"],
        "router_latency_mean_ms": latency["router_ms"]["mean"],
        "answer_success_rate": reliability["answer_success_rate"],
        "scoring_coverage": reliability["scoring_coverage"],
        "output_cap_compliance_rate": reliability[
            "output_cap_compliance_rate"
        ],
    }
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)


def _write_summary(
    *,
    args: argparse.Namespace,
    run_id: str,
    run_dir: Path,
    root: Path,
    calls: list[dict[str, Any]],
    answers: list[dict[str, Any]],
    judgments: list[dict[str, Any]],
    usd_per_credit: Decimal,
    copied_scores: list[str],
) -> dict[str, Any]:
    input_tokens = 0
    output_tokens = 0
    cached_tokens = 0
    credits = Decimal(0)
    credits_available = False
    cost_usd = Decimal(0)
    cost_usd_available = False
    latencies: list[float] = []
    failed_request_latencies: list[float] = []
    for call in calls:
        usage = call.get("usage") or {}
        input_tokens += int(usage.get("prompt_tokens") or 0)
        output_tokens += int(usage.get("completion_tokens") or 0)
        details = usage.get("prompt_tokens_details") or {}
        cached_tokens += int(details.get("cached_tokens") or 0)
        call_credits = _credits_from_call(call)
        if call_credits is not None:
            credits += call_credits
            credits_available = True
        if call.get("cost_usd") is not None:
            try:
                cost_usd += Decimal(str(call["cost_usd"]))
                cost_usd_available = True
            except InvalidOperation:
                pass
        if call.get("latency_ms") is not None:
            target = (
                failed_request_latencies
                if call.get("error")
                else latencies
            )
            target.append(float(call["latency_ms"]))
    successful_calls = [call for call in calls if not call.get("error")]
    output_cap_violations = sum(
        int((call.get("usage") or {}).get("completion_tokens") or 0)
        > args.max_tokens
        for call in successful_calls
    )
    maximum_output_tokens = max(
        (
            int((call.get("usage") or {}).get("completion_tokens") or 0)
            for call in successful_calls
        ),
        default=0,
    )

    scores = [
        float(record["score"])
        for record in judgments
        if record.get("score") not in (None, -1)
    ]
    current_question_ids = _current_run_question_ids(calls, answers)
    current_answers = [
        record
        for record in answers
        if str(record.get("question_id")) in current_question_ids
    ]
    current_judgments = [
        record
        for record in judgments
        if str(record.get("question_id")) in current_question_ids
        and record.get("score") not in (None, -1)
    ]
    failed_question_ids = {
        str(record.get("question_id"))
        for record in current_answers
        if bool(record.get("error"))
        or any(
            turn == "$ERROR$"
            for choice in record.get("choices", [])
            for turn in choice.get("turns", [])
        )
    }
    # Some instruction-following graders award format points to the literal
    # provider-failure sentinel. Provider failures are availability failures,
    # not low-quality answers, and are normalized to zero in current-run
    # quality while the raw official judgments remain in judgments.jsonl.
    current_scores = [
        0.0
        if str(record.get("question_id")) in failed_question_ids
        else float(record["score"])
        for record in current_judgments
    ]
    quality_points = sum(current_scores)
    current_failures = sum(
        bool(record.get("error"))
        or any(
            turn == "$ERROR$"
            for choice in record.get("choices", [])
            for turn in choice.get("turns", [])
        )
        for record in current_answers
    )
    failed_answers = sum(
        bool(record.get("error"))
        or any(
            turn == "$ERROR$"
            for choice in record.get("choices", [])
            for turn in choice.get("turns", [])
        )
        for record in answers
    )
    router_latencies = [
        float(routing["router_latency_ms"])
        for call in calls
        if isinstance((routing := call.get("kendr_routing")), Mapping)
        and routing.get("router_latency_ms") is not None
    ]
    router_confidences = [
        float(routing["confidence"])
        for call in calls
        if isinstance((routing := call.get("kendr_routing")), Mapping)
        and routing.get("confidence") is not None
    ]
    route_distribution = Counter(
        str(routing.get("selected_model_alias"))
        for call in calls
        if isinstance((routing := call.get("kendr_routing")), Mapping)
        and routing.get("selected_model_alias")
    )
    task_distribution = Counter(
        str(routing.get("task_category") or "unknown")
        for call in calls
        if isinstance((routing := call.get("kendr_routing")), Mapping)
        and routing.get("task_category")
    )
    provider_error_distribution = Counter(
        str((call.get("error") or {}).get("type") or "unknown")
        for call in calls
        if call.get("error")
    )
    credits_float = float(credits) if credits_available else 0.0
    if not cost_usd_available and credits_available:
        cost_usd = credits * usd_per_credit
        cost_usd_available = True
    usd_float = float(cost_usd) if cost_usd_available else 0.0
    total_tokens = input_tokens + output_tokens
    total_latency_ms = sum(latencies)
    total_latency_seconds = total_latency_ms / 1000
    current_answer_count = len(current_answers)
    current_scored_count = len(current_scores)
    summary = {
        "run_id": run_id,
        "model": args.model_display_name,
        "requested_model": args.model,
        "livebench": {
            "repository": LIVEBENCH_REPOSITORY,
            "revision": LIVEBENCH_REVISION,
            "source_root": str(root),
            "release": args.livebench_release_option,
            "benchmarks": args.bench_name,
        },
        "current_api_run": {
            "provider": getattr(args, "provider", "kendr"),
            "calls": len(calls),
            "input_tokens": input_tokens,
            "cached_input_tokens": cached_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "kendr_credits": format(credits, "f")
            if credits_available
            else None,
            "kendr_cost_usd": format(credits * usd_per_credit, "f")
            if credits_available
            else None,
            "cost_usd": format(cost_usd, "f")
            if cost_usd_available
            else None,
            "usd_per_credit": format(usd_per_credit, "f"),
            "mean_latency_ms": (
                sum(latencies) / len(latencies) if latencies else None
            ),
            "requested_max_output_tokens": args.max_tokens,
            "calls_exceeding_requested_output_cap": output_cap_violations,
            "maximum_output_tokens_observed": maximum_output_tokens,
        },
        "current_run_quality": {
            "measurement": (
                "Official LiveBench objective ground-truth scores matched to "
                "request IDs from this API invocation"
            ),
            "questions_matched_to_current_calls": len(
                current_question_ids
            ),
            "questions_scored": current_scored_count,
            "quality_points": quality_points,
            "objective_score_mean": (
                sum(current_scores) / current_scored_count
                if current_scored_count
                else None
            ),
            "perfect_score_rate": (
                sum(score >= 1.0 for score in current_scores)
                / current_scored_count
                if current_scored_count
                else None
            ),
            "nonzero_score_rate": (
                sum(score > 0 for score in current_scores)
                / current_scored_count
                if current_scored_count
                else None
            ),
        },
        "efficiency": {
            "measurement": (
                "Derived from current-run provider usage and matched official "
                "LiveBench quality points; not an official LiveBench score"
            ),
            "input_tokens_per_quality_point": _safe_ratio(
                input_tokens, quality_points
            ),
            "output_tokens_per_quality_point": _safe_ratio(
                output_tokens, quality_points
            ),
            "total_tokens_per_quality_point": _safe_ratio(
                total_tokens, quality_points
            ),
            "quality_points_per_1000_tokens": _safe_ratio(
                quality_points * 1000, total_tokens
            ),
            "credits_per_quality_point": _safe_ratio(
                credits_float, quality_points
            )
            if credits_available
            else None,
            "usd_per_quality_point": _safe_ratio(
                usd_float, quality_points
            )
            if cost_usd_available
            else None,
            "quality_points_per_usd": _safe_ratio(
                quality_points, usd_float
            )
            if cost_usd_available
            else None,
            "credits_per_call": _safe_ratio(
                credits_float, len(calls)
            )
            if credits_available
            else None,
            "usd_per_call": _safe_ratio(usd_float, len(calls))
            if cost_usd_available
            else None,
            "output_to_input_token_ratio": _safe_ratio(
                output_tokens, input_tokens
            ),
            "output_tokens_per_second": _safe_ratio(
                output_tokens, total_latency_seconds
            ),
            "quality_points_per_second": _safe_ratio(
                quality_points, total_latency_seconds
            ),
            "latency_ms_per_quality_point": _safe_ratio(
                total_latency_ms, quality_points
            ),
        },
        "latency": {
            "measurement": (
                "Client-observed non-streaming end-to-end latency; time to "
                "first token is unavailable"
            ),
            "end_to_end_ms": _distribution_stats(latencies),
            "failed_request_ms": _distribution_stats(
                failed_request_latencies
            ),
            "router_ms": _distribution_stats(router_latencies),
            "router_confidence": _distribution_stats(
                router_confidences
            ),
        },
        "reliability": {
            "successful_answers": current_answer_count - current_failures,
            "failed_answers": current_failures,
            "answer_success_rate": (
                (current_answer_count - current_failures)
                / current_answer_count
                if current_answer_count
                else None
            ),
            "scoring_coverage": (
                current_scored_count / len(current_question_ids)
                if current_question_ids
                else None
            ),
            "output_cap_compliance_rate": (
                (len(successful_calls) - output_cap_violations)
                / len(successful_calls)
                if successful_calls
                else None
            ),
            "calls_exceeding_requested_output_cap": (
                output_cap_violations
            ),
            "route_distribution": dict(route_distribution),
            "router_task_distribution": dict(task_distribution),
            "provider_error_distribution": dict(
                provider_error_distribution
            ),
        },
        "relevance": {
            "separately_scored": False,
            "objective_task_score_proxy": (
                sum(current_scores) / current_scored_count
                if current_scored_count
                else None
            ),
            "explanation": (
                "LiveBench tests correctness and instruction compliance with "
                "task-specific objective graders. It does not emit a generic "
                "semantic-relevance score; production relevance requires a "
                "separate domain rubric or judge."
            ),
        },
        "workspace_snapshot": {
            "answers": len(answers),
            "failed_answers": failed_answers,
            "judgments": len(judgments),
            "question_weighted_mean_score": (
                sum(scores) / len(scores) if scores else None
            ),
            "standard_group_scores": _standard_group_scores(
                run_dir / "all_groups.csv", args.model_display_name
            ),
        },
        "artifacts": {
            "calls": "calls.jsonl",
            "answers": "answers.jsonl",
            "judgments": "judgments.jsonl",
            "standard_score_files": copied_scores,
            "operational_metrics": "metrics.csv",
        },
    }
    (run_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    _write_metrics_csv(run_dir / "metrics.csv", summary)
    return summary


def _write_report(run_dir: Path, summary: Mapping[str, Any]) -> None:
    api = summary["current_api_run"]
    quality = summary["current_run_quality"]
    efficiency = summary["efficiency"]
    latency_metrics = summary["latency"]
    reliability = summary["reliability"]
    snapshot = summary["workspace_snapshot"]

    def percent(value: Any) -> str:
        return f"{float(value) * 100:.2f}%" if value is not None else "n/a"

    def number(value: Any, digits: int = 3) -> str:
        return f"{float(value):.{digits}f}" if value is not None else "n/a"

    provider = str(api.get("provider") or "kendr")
    credits = api["kendr_credits"] or "n/a"
    cost = (
        f"${Decimal(api['cost_usd']):f}"
        if api.get("cost_usd") is not None
        else "n/a"
    )
    latency = (
        f"{api['mean_latency_ms']:.1f} ms"
        if api["mean_latency_ms"] is not None
        else "n/a"
    )
    cap_status = (
        "WARNING: provider output exceeded the requested "
        f"{api['requested_max_output_tokens']}-token cap; maximum observed was "
        f"{api['maximum_output_tokens_observed']}."
        if api["calls_exceeding_requested_output_cap"]
        else "No provider-reported output exceeded the requested token cap."
    )
    mean_score = (
        f"{snapshot['question_weighted_mean_score'] * 100:.2f}%"
        if snapshot["question_weighted_mean_score"] is not None
        else "n/a"
    )
    lines = [
        f"# Instrumented LiveBench report: {summary['run_id']}",
        "",
        f"- Provider: `{provider}`",
        f"- Model: `{summary['model']}` (`{summary['requested_model']}`)",
        f"- LiveBench release: `{summary['livebench']['release']}`",
        f"- LiveBench revision: `{summary['livebench']['revision']}`",
        f"- API calls in this run: {api['calls']}",
        f"- Tokens in/out: {api['input_tokens']} / {api['output_tokens']}",
        f"- Kendr credits in this run: {credits}",
        f"- Cost in this run: {cost}",
        f"- Mean API latency: {latency}",
        f"- Calls exceeding requested output cap: "
        f"{api['calls_exceeding_requested_output_cap']}",
        f"- Output-cap status: {cap_status}",
        "",
        "## Current-run quality",
        "",
        f"- Questions matched/scored: "
        f"{quality['questions_matched_to_current_calls']} / "
        f"{quality['questions_scored']}",
        f"- Objective score mean: "
        f"{percent(quality['objective_score_mean'])}",
        f"- Perfect-score rate: {percent(quality['perfect_score_rate'])}",
        f"- Nonzero-score rate: {percent(quality['nonzero_score_rate'])}",
        "",
        "These are official LiveBench objective scores matched to the request "
        "IDs from this invocation.",
        "",
        "## Efficiency",
        "",
        f"- Total tokens per quality point: "
        f"{number(efficiency['total_tokens_per_quality_point'])}",
        f"- Quality points per 1,000 tokens: "
        f"{number(efficiency['quality_points_per_1000_tokens'])}",
        f"- Credits per quality point: "
        f"{number(efficiency['credits_per_quality_point'], 6)}",
        f"- USD per quality point: "
        f"{number(efficiency['usd_per_quality_point'], 8)}",
        f"- Output/input token ratio: "
        f"{number(efficiency['output_to_input_token_ratio'])}",
        f"- Output throughput: "
        f"{number(efficiency['output_tokens_per_second'])} tokens/s",
        f"- Latency per quality point: "
        f"{number(efficiency['latency_ms_per_quality_point'], 1)} ms",
        "",
        "## Latency and reliability",
        "",
        f"- End-to-end latency p50/p95/p99: "
        f"{number(latency_metrics['end_to_end_ms']['p50'], 1)} / "
        f"{number(latency_metrics['end_to_end_ms']['p95'], 1)} / "
        f"{number(latency_metrics['end_to_end_ms']['p99'], 1)} ms",
        f"- Mean router latency: "
        f"{number(latency_metrics['router_ms']['mean'], 1)} ms",
        f"- Answer success rate: "
        f"{percent(reliability['answer_success_rate'])}",
        f"- Scoring coverage: {percent(reliability['scoring_coverage'])}",
        f"- Output-cap compliance: "
        f"{percent(reliability['output_cap_compliance_rate'])}",
        f"- Selected-route distribution: "
        f"`{json.dumps(reliability['route_distribution'], sort_keys=True)}`",
        "",
        "Time to first token is not available because this reproducible path "
        "uses non-streaming requests.",
        "",
        "## Relevance",
        "",
        "LiveBench does not emit a separate generic relevance score. Its "
        "task-specific objective score measures correctness and, for the "
        "instruction-following category, compliance. Production relevance "
        "must be evaluated separately against a domain rubric or judge.",
        "",
        "## Workspace quality snapshot",
        "",
        f"- Answers present: {snapshot['answers']}",
        f"- Failed answers: {snapshot['failed_answers']}",
        f"- Judgments present: {snapshot['judgments']}",
        f"- Question-weighted mean score: {mean_score}",
        "",
        "LiveBench's official category/task weighting is preserved in "
        "`all_groups.csv` and `all_tasks.csv`. The question-weighted mean above "
        "is diagnostic only.",
        "",
        "## Captured artifacts",
        "",
        "- `calls.jsonl`: exact provider requests, outputs, usage, cost, "
        "request IDs, latency, and Kendr routing/optimization when present.",
        "- `answers.jsonl`: LiveBench-format model answers in the workspace.",
        "- `judgments.jsonl`: objective LiveBench judgments for this model.",
        "- `summary.json`: machine-readable totals and provenance.",
        "- `metrics.csv`: one-row operational and quality-adjusted metrics "
        "for cross-run/model comparison.",
        "",
    ]
    (run_dir / "report.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def run_livebench(args: argparse.Namespace) -> tuple[Path, dict[str, Any]]:
    root = args.livebench_root.resolve()
    valid, detail = _validate_checkout(root)
    if not valid:
        raise RuntimeError(f"{detail}. Run `kendr-livebench setup` first.")

    load_environment(args.env_file, disabled=args.no_env_file)
    provider = getattr(args, "provider", "kendr")
    api_key_env = (
        "KENDR_API_KEY" if provider == "kendr" else "OPENAI_API_KEY"
    )
    api_key = os.getenv(api_key_env)
    if not api_key:
        raise RuntimeError(
            f"{api_key_env} is missing from the selected .env file and process."
        )
    if args.api_base is None:
        args.api_base = (
            DEFAULT_API_BASE if provider == "kendr" else OPENAI_API_BASE
        )
    unrestricted_full_run = (
        tuple(args.bench_name) == DEFAULT_BENCHMARKS
        and args.question_begin is None
        and args.question_end is None
        and not args.question_id
        and not args.skip_inference
    )
    if unrestricted_full_run and not args.confirm_full:
        raise RuntimeError(
            "A full six-category LiveBench run is chargeable and requires "
            "--confirm-full. Run the documented one-question smoke first."
        )

    usd_per_credit = args.kendr_usd_per_credit
    if usd_per_credit is None and os.getenv("KENDR_USD_PER_CREDIT"):
        usd_per_credit = _positive_decimal(
            os.environ["KENDR_USD_PER_CREDIT"]
        )
    if usd_per_credit is None:
        usd_per_credit = KENDR_DEFAULT_USD_PER_CREDIT

    run_id = _run_id(args.label)
    run_dir = (args.output / run_id).resolve()
    run_dir.mkdir(parents=True, exist_ok=False)
    call_log = run_dir / "calls.jsonl"
    child_env = os.environ.copy()
    child_env["LIVEBENCH_API_KEY"] = api_key
    child_env[KENDR_LIVEBENCH_CALL_LOG] = str(call_log)
    child_env[KENDR_LIVEBENCH_RUN_ID] = run_id
    child_env[KENDR_LIVEBENCH_USD_PER_CREDIT] = format(
        usd_per_credit, "f"
    )
    pricing_path = args.pricing.resolve()
    if provider == "openai" and not pricing_path.is_file():
        raise RuntimeError(f"Pricing catalog not found: {pricing_path}")
    child_env[LIVEBENCH_PRICING_PATH] = str(pricing_path)
    child_env[OPENAI_LIVEBENCH_REASONING_EFFORT] = (
        args.reasoning_effort
    )
    # LiveBench's agentic runner prints Unicode symbols during import. Explicit
    # UTF-8 avoids Windows redirected-output failures under a CP-1252 locale.
    child_env["PYTHONUTF8"] = "1"
    child_env["PYTHONIOENCODING"] = "utf-8"
    child_env["PYTHONPATH"] = os.pathsep.join(
        filter(
            None,
            [str(root), child_env.get("PYTHONPATH", "")],
        )
    )
    work_dir = root / "livebench"

    manifest = {
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "livebench_repository": LIVEBENCH_REPOSITORY,
        "livebench_revision": LIVEBENCH_REVISION,
        "livebench_release": args.livebench_release_option,
        "benchmarks": args.bench_name,
        "provider": provider,
        "requested_model": args.model,
        "model_display_name": args.model_display_name,
        "api_base": args.api_base,
        "reasoning_effort": args.reasoning_effort,
        "pricing_catalog": str(pricing_path),
        "max_tokens": args.max_tokens,
        "parallel_requests": args.parallel_requests,
        "usd_per_credit": format(usd_per_credit, "f"),
        "runtime": {
            "python": sys.version,
            "packages": _package_versions(),
        },
        "compatibility_patches": [
            "multi-word-category-path-runtime-shim-v1",
            INSTRUCTION_FOLLOWING_COMPATIBILITY_PATCH,
        ],
    }
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    if not args.skip_inference:
        _run_command(
            _generation_command(args, root),
            cwd=work_dir,
            env=child_env,
        )
    if not args.skip_grading:
        _run_command(
            _grading_command(args, root),
            cwd=work_dir,
            env=child_env,
        )
        _run_command(
            _show_command(args, root),
            cwd=work_dir,
            env=child_env,
        )

    answer_paths = _paths_for_benches(
        work_dir,
        args.bench_name,
        f"model_answer/{args.model_display_name}.jsonl",
    )
    answers = _read_jsonl(answer_paths)
    judgment_paths = _paths_for_benches(
        work_dir,
        args.bench_name,
        "model_judgment/ground_truth_judgment.jsonl",
    )
    judgments = _model_judgments(
        _read_jsonl(judgment_paths), args.model_display_name
    )
    _write_jsonl(run_dir / "answers.jsonl", answers)
    _write_jsonl(run_dir / "judgments.jsonl", judgments)
    calls = _read_calls(call_log)
    copied_scores = _copy_score_files(work_dir, run_dir)
    summary = _write_summary(
        args=args,
        run_id=run_id,
        run_dir=run_dir,
        root=root,
        calls=calls,
        answers=answers,
        judgments=judgments,
        usd_per_credit=usd_per_credit,
        copied_scores=copied_scores,
    )
    _write_report(run_dir, summary)
    return run_dir, summary


def summarize_existing_run(
    run_dir: Path,
    *,
    livebench_root: Path,
    usd_per_credit: Decimal | None = None,
) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.is_file():
        raise RuntimeError(f"Manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    required = (
        "run_id",
        "requested_model",
        "model_display_name",
        "livebench_release",
        "benchmarks",
        "max_tokens",
    )
    missing = [key for key in required if key not in manifest]
    if missing:
        raise RuntimeError(
            f"Manifest is missing required fields: {', '.join(missing)}"
        )
    conversion = usd_per_credit
    if conversion is None:
        conversion = Decimal(
            str(
                manifest.get("usd_per_credit")
                or KENDR_DEFAULT_USD_PER_CREDIT
            )
        )
    args = argparse.Namespace(
        provider=manifest.get("provider", "kendr"),
        model=manifest["requested_model"],
        model_display_name=manifest["model_display_name"],
        livebench_release_option=manifest["livebench_release"],
        bench_name=list(manifest["benchmarks"]),
        max_tokens=int(manifest["max_tokens"]),
    )
    calls = _read_calls(run_dir / "calls.jsonl")
    answers = _read_jsonl([run_dir / "answers.jsonl"])
    judgments = _read_jsonl([run_dir / "judgments.jsonl"])
    copied_scores = [
        name for name in GENERATED_SCORE_FILES if (run_dir / name).is_file()
    ]
    summary = _write_summary(
        args=args,
        run_id=str(manifest["run_id"]),
        run_dir=run_dir,
        root=livebench_root.resolve(),
        calls=calls,
        answers=answers,
        judgments=judgments,
        usd_per_credit=conversion,
        copied_scores=copied_scores,
    )
    _write_report(run_dir, summary)
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "setup":
            setup_livebench(args.livebench_root)
            return 0
        if args.command == "status":
            valid, detail = _validate_checkout(
                args.livebench_root.resolve()
            )
            print(detail)
            return 0 if valid else 1
        if args.command == "summarize":
            summary = summarize_existing_run(
                args.run_dir,
                livebench_root=args.livebench_root,
                usd_per_credit=args.kendr_usd_per_credit,
            )
            print(
                "Updated: "
                f"{args.run_dir.resolve()} "
                f"({summary['current_run_quality']['questions_scored']} "
                "current-run questions scored)"
            )
            return 0
        if args.command == "run":
            run_dir, summary = run_livebench(args)
            current = summary["current_api_run"]
            snapshot = summary["workspace_snapshot"]
            print(f"Run: {run_dir}")
            print(
                f"{current.get('provider', 'kendr')} API: "
                f"{current['calls']} calls, "
                f"{current['input_tokens']} input tokens, "
                f"{current['output_tokens']} output tokens, "
                f"${current.get('cost_usd') or 'n/a'}"
            )
            print(
                "LiveBench snapshot: "
                f"{snapshot['answers']} answers, "
                f"{snapshot['judgments']} judgments, "
                f"{snapshot['failed_answers']} failed answers"
            )
            print(f"Report: {run_dir / 'report.md'}")
            return 1 if snapshot["failed_answers"] else 0
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"kendr-livebench failed: {exc}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
