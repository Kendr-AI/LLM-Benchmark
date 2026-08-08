from __future__ import annotations

import argparse
import csv
import hashlib
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
    KENDR_OUTPUT_CAP_COMPATIBILITY_PATCH,
    LIVEBENCH_PRICING_PATH,
    OPENAI_LIVEBENCH_REASONING_EFFORT,
    recovered_call_usage,
)
from .providers import KENDR_DEFAULT_USD_PER_CREDIT
from .livebench_worker import INSTRUCTION_FOLLOWING_COMPATIBILITY_PATCH
from .operations import compute_operational_metrics, group_call_attempts
from .scoring import (
    answer_failed,
    bootstrap_ci,
    category_scores,
    failed_question_ids,
    is_scored,
    normalized_scores,
    stable_seed,
)
from .resources import bundled_resource

LIVEBENCH_REPOSITORY = "https://github.com/LiveBench/LiveBench.git"
LIVEBENCH_REVISION = "4355e9b04222745ccc02a2661d1deebe767a85a2"
DEFAULT_LIVEBENCH_ROOT = Path(".vendor/LiveBench")
DEFAULT_LIVEBENCH_CONSTRAINTS = bundled_resource("livebench-constraints.txt")
DEFAULT_API_BASE = "https://kendr.org/v1"
OPENAI_API_BASE = "https://api.openai.com/v1"
DEFAULT_PRICING_PATH = bundled_resource("pricing.json")
DEFAULT_RELEASE = "2024-11-25"
LIVEBENCH_CATEGORIES = (
    "coding",
    "data_analysis",
    "instruction_following",
    "language",
    "math",
    "reasoning",
)
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
        "--deadline-ms",
        type=_positive_int,
        default=None,
        help=(
            "Optional final-answer deadline. Retries count toward this "
            "logical-request latency budget."
        ),
    )
    parser.add_argument(
        "--max-cost-usd-per-answer",
        type=_positive_decimal,
        default=None,
        help=(
            "Optional per-question USD budget. All retry attempts count."
        ),
    )
    parser.add_argument(
        "--allow-incomplete",
        action="store_true",
        help=(
            "Export an incomplete run instead of failing after artifacts are "
            "written. Missing planned questions still score zero."
        ),
    )
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
        prog="llm-benchmark-livebench",
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

    finalize = subparsers.add_parser(
        "finalize",
        help=(
            "Grade and export an interrupted run whose provider calls and "
            "LiveBench workspace answers already exist; inference is never "
            "replayed"
        ),
    )
    finalize.add_argument("run_dir", type=Path)
    finalize.add_argument(
        "--livebench-root",
        type=Path,
        default=DEFAULT_LIVEBENCH_ROOT,
    )
    finalize.add_argument(
        "--parallel-grading", type=_positive_int, default=4
    )
    finalize.add_argument(
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


def _iso_date_text(value: Any, *, field: str) -> str:
    """Normalize Arrow/Python LiveBench dates to canonical YYYY-MM-DD."""
    if value in (None, ""):
        return ""
    if hasattr(value, "date") and not isinstance(value, str):
        value = value.date()
    if hasattr(value, "isoformat") and not isinstance(value, str):
        value = value.isoformat()
    text = str(value)
    # Some dataset versions stringify midnight datetimes rather than dates.
    candidate = text[:10]
    try:
        datetime.strptime(candidate, "%Y-%m-%d")
    except ValueError as exc:
        raise RuntimeError(
            f"LiveBench {field} is not an ISO date: {text!r}"
        ) from exc
    return candidate


def _benchmark_selection(
    bench_names: Sequence[str],
) -> dict[str, set[str] | None]:
    """Parse LiveBench paths without the upstream multi-word-category bug."""
    selection: dict[str, set[str] | None] = {}
    for bench_name in bench_names:
        parts = bench_name.rstrip("/").split("/")
        if not parts or parts[0] != "live_bench" or len(parts) > 3:
            raise RuntimeError(f"Invalid LiveBench path: {bench_name!r}")
        categories = LIVEBENCH_CATEGORIES if len(parts) == 1 else (parts[1],)
        for category in categories:
            if category not in LIVEBENCH_CATEGORIES:
                raise RuntimeError(
                    f"Unsupported LiveBench category in {bench_name!r}: "
                    f"{category!r}"
                )
            task = parts[2] if len(parts) == 3 else None
            if task is None or selection.get(category) is None and category in selection:
                selection[category] = None
            else:
                selection.setdefault(category, set())
                selected_tasks = selection[category]
                if selected_tasks is not None:
                    selected_tasks.add(task)
    return selection


def load_livebench_question_records(
    bench_names: Sequence[str], release_option: str
) -> list[dict[str, Any]]:
    """Load the exact active cumulative LiveBench pool for preflight sampling.

    LiveBench's release option is cumulative.  Resolving the pool before any
    provider call lets callers freeze exact IDs, inspect actual question dates,
    and use the same sample for every endpoint.
    """
    try:
        from datasets import load_dataset
    except ImportError as exc:  # pragma: no cover - setup error path
        raise RuntimeError(
            "The LiveBench runtime is not installed; run `llm-benchmark-livebench "
            "setup` first."
        ) from exc

    cutoff = _iso_date_text(release_option, field="release option")
    selection = _benchmark_selection(bench_names)
    records: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for category, tasks in selection.items():
        dataset = load_dataset(f"livebench/{category}", split="test")
        for raw in dataset:
            record = dict(raw)
            task = str(record.get("task") or "")
            if tasks is not None and task not in tasks:
                continue
            released = _iso_date_text(
                record.get("livebench_release_date"),
                field="livebench_release_date",
            )
            removed = _iso_date_text(
                record.get("livebench_removal_date"),
                field="livebench_removal_date",
            )
            if not released or released > cutoff:
                continue
            if removed and removed <= cutoff:
                continue
            question_id = str(record.get("question_id") or "")
            if not question_id:
                raise RuntimeError(
                    f"LiveBench {category}/{task} contains an empty question ID"
                )
            if question_id in seen_ids:
                # Overlapping user paths may select the same row twice. The
                # benchmark unit is still one globally identified question.
                continue
            seen_ids.add(question_id)
            record["category"] = category
            record["task"] = task
            record["livebench_release_date"] = released
            record["livebench_removal_date"] = removed
            records.append(record)
    if not records:
        raise RuntimeError(
            "No active LiveBench questions matched the requested paths and "
            f"release {release_option}."
        )
    return records


def _planned_question_records(
    records: Sequence[Mapping[str, Any]],
    *,
    question_ids: Sequence[str] | None,
    question_begin: int | None,
    question_end: int | None,
) -> list[dict[str, Any]]:
    """Resolve LiveBench's per-task slice into an immutable question plan."""
    if question_ids:
        by_id = {str(record.get("question_id")): record for record in records}
        missing = [question_id for question_id in question_ids if question_id not in by_id]
        if missing:
            raise RuntimeError(
                "Requested question IDs are absent from the active pool: "
                + ", ".join(missing)
            )
        return [dict(by_id[question_id]) for question_id in question_ids]

    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for record in records:
        key = (str(record.get("category")), str(record.get("task")))
        grouped.setdefault(key, []).append(record)
    begin = question_begin or 0
    planned: list[dict[str, Any]] = []
    for rows in grouped.values():
        planned.extend(dict(record) for record in rows[begin:question_end])
    if not planned:
        raise RuntimeError("The requested per-task slice selected no questions.")
    return planned


def _planned_question_descriptors(
    records: Sequence[Mapping[str, Any]],
) -> list[dict[str, str]]:
    return [
        {
            "question_id": str(record.get("question_id")),
            "category": str(record.get("category") or "unknown"),
            "task": str(record.get("task") or "unknown"),
            "livebench_release_date": _iso_date_text(
                record.get("livebench_release_date"),
                field="livebench_release_date",
            ),
        }
        for record in records
    ]


def _json_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _write_artifact_hashes(root: Path) -> dict[str, dict[str, Any]]:
    """Write a compact integrity manifest for exported top-level artifacts."""
    records: dict[str, dict[str, Any]] = {}
    for path in sorted(root.iterdir()):
        if (
            not path.is_file()
            or path.name == "artifact_hashes.json"
        ):
            continue
        payload = path.read_bytes()
        records[path.name] = {
            "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
    document = {
        "schema_version": 1,
        "algorithm": "sha256",
        "files": records,
    }
    (root / "artifact_hashes.json").write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return records


def _credits_from_call(call: Mapping[str, Any]) -> Decimal | None:
    if call.get("retry_reason") == "no_credits_charged":
        return Decimal(0)
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


def _cost_from_call(call: Mapping[str, Any]) -> Decimal | None:
    value = call.get("cost_usd")
    if value is not None:
        return Decimal(str(value))
    if call.get("retry_reason") == "no_credits_charged":
        return Decimal(0)
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
    """Return answers linked to captured calls using failure-safe identity.

    Provider failures do not always have a request ID. The operational joiner
    also uses idempotency/logical IDs and an unambiguous canonical-message
    fallback, so completeness and operational metrics must share that exact
    association rule.
    """
    answer_question_ids = {
        str(answer.get("question_id"))
        for answer in answers
        if answer.get("question_id")
    }
    return {
        str(group["question_id"])
        for group in group_call_attempts(calls, answers=answers)
        if group.get("question_id") in answer_question_ids
    }


def _judgment_matches_answer(
    judgment: Mapping[str, Any], answer: Mapping[str, Any]
) -> bool:
    """Reject stale grades when either artifact carries an answer identity."""
    judgment_answer_id = str(judgment.get("answer_id") or "").strip()
    answer_id = str(answer.get("answer_id") or "").strip()
    if judgment_answer_id or answer_id:
        return bool(
            judgment_answer_id
            and answer_id
            and judgment_answer_id == answer_id
        )
    # Older LiveBench artifacts did not always expose answer_id. Preserve
    # rebuild compatibility only when neither side provides a stronger key.
    return True


def _missing_successful_judgment_ids(
    *,
    planned_ids: Sequence[str],
    answers: Sequence[Mapping[str, Any]],
    judgments: Sequence[Mapping[str, Any]],
) -> list[str]:
    """Return planned successful answers lacking a current scored judgment.

    Recovery is deliberately narrower than completeness scoring. Failed
    provider answers retain the protocol's zero normalization and are never
    sent back through the objective grader. A stale judgment whose answer ID
    does not match the current answer is also treated as missing.
    """

    answers_by_id = {
        str(answer.get("question_id")): answer
        for answer in answers
        if answer.get("question_id")
    }
    if any(question_id not in answers_by_id for question_id in planned_ids):
        return []
    planned_id_set = set(planned_ids)
    judged_ids = {
        question_id
        for judgment in judgments
        if (
            (question_id := str(judgment.get("question_id") or ""))
            in planned_id_set
            and is_scored(judgment)
            and _judgment_matches_answer(
                judgment, answers_by_id[question_id]
            )
        )
    }
    return [
        question_id
        for question_id in planned_ids
        if not answer_failed(answers_by_id[question_id])
        and question_id not in judged_ids
    ]


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
    operations = summary.get("operations") or {}
    retries = operations.get("retries") or {}
    cap_conformance = reliability.get(
        "operational_output_cap_conformance", {}
    )
    cap_attempt_conformance = (
        (operations.get("conformance") or {}).get(
            "output_cap_by_attempt", {}
        )
    )
    row = {
        "run_id": summary["run_id"],
        "provider": api.get("provider"),
        "model": summary["model"],
        "calls": api["calls"],
        "input_tokens": api["input_tokens"],
        "output_tokens": api["output_tokens"],
        "total_tokens": api["total_tokens"],
        "usage_records_reported": api.get("usage_records_reported"),
        "usage_records_missing": api.get("usage_records_missing"),
        "token_total_is_lower_bound": api.get(
            "token_total_is_lower_bound"
        ),
        "kendr_credits": api["kendr_credits"],
        "kendr_cost_usd": api["kendr_cost_usd"],
        "cost_usd": api.get("cost_usd"),
        "cost_records_reported": api.get("cost_records_reported"),
        "cost_records_missing": api.get("cost_records_missing"),
        "cost_total_is_lower_bound": api.get(
            "cost_total_is_lower_bound"
        ),
        "questions_matched": quality["questions_matched_to_current_calls"],
        "questions_scored": quality["questions_scored"],
        "questions_planned": quality.get("questions_planned"),
        "score_denominator": quality.get("score_denominator"),
        "complete": (summary.get("completeness") or {}).get("complete"),
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
        "attempt_latency_p50_ms": latency.get("attempt_ms", {}).get(
            "p50"
        ),
        "retry_attempt_amplification": retries.get(
            "observed_attempt_amplification"
        ),
        "retry_latency_amplification": retries.get(
            "latency_amplification"
        ),
        "router_latency_mean_ms": latency["router_ms"]["mean"],
        "answer_success_rate": reliability["answer_success_rate"],
        "scoring_coverage": reliability["scoring_coverage"],
        # Keep the established column name, but make its semantics consistent
        # with matrix exports: unknown planned questions count against the
        # conservative rate rather than disappearing from the denominator.
        "output_cap_compliance_rate": cap_conformance.get(
            "conservative_rate",
            reliability["output_cap_compliance_rate"],
        ),
        "output_cap_measured_rate": cap_conformance.get(
            "measured_rate", reliability["output_cap_compliance_rate"]
        ),
        "output_cap_unknown_questions": cap_conformance.get("unknown", 0),
        "output_cap_attempt_conservative_rate": (
            cap_attempt_conformance.get("conservative_rate")
        ),
        "output_cap_attempt_measured_rate": cap_attempt_conformance.get(
            "measured_rate"
        ),
        "output_cap_measured_attempts": reliability.get(
            "output_cap_measured_attempts"
        ),
        "output_cap_unknown_attempts": cap_attempt_conformance.get(
            "unknown", 0
        ),
        "deadline_conformance_rate": reliability.get(
            "deadline_conformance", {}
        ).get("conservative_rate"),
        "budget_conformance_rate": reliability.get(
            "budget_conformance", {}
        ).get("conservative_rate"),
        "operational_goodput_rate": reliability.get(
            "operational_goodput", {}
        ).get("conservative_rate"),
        "score_weighted_goodput": reliability.get(
            "score_weighted_goodput", {}
        ).get("conservative_mean"),
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
    malformed_cost_records: list[str] = []
    cost_records_reported = 0
    usage_records_reported = 0
    for call in calls:
        usage = recovered_call_usage(call)
        if usage:
            usage_records_reported += 1
        input_tokens += int(usage.get("prompt_tokens") or 0)
        output_tokens += int(usage.get("completion_tokens") or 0)
        details = usage.get("prompt_tokens_details") or {}
        cached_tokens += int(details.get("cached_tokens") or 0)
        call_credits = _credits_from_call(call)
        if call_credits is not None:
            credits += call_credits
            credits_available = True
        try:
            call_cost = _cost_from_call(call)
            if call_cost is not None:
                cost_usd += call_cost
                cost_usd_available = True
                cost_records_reported += 1
        except InvalidOperation:
            # Silently skipping this understated the published total with no
            # trace, so the count is surfaced in the summary instead.
            malformed_cost_records.append(
                str(call.get("request_id") or "unknown")
            )
        if call.get("latency_ms") is not None:
            target = (
                failed_request_latencies
                if call.get("error")
                else latencies
            )
            target.append(float(call["latency_ms"]))
    def _reported_output_tokens(call: Mapping[str, Any]) -> int:
        return int(
            recovered_call_usage(call).get("completion_tokens") or 0
        )

    # Cap compliance is measured over every attempt that reported output, not
    # only successful ones. A truncation rejection is the most flagrant possible
    # breach of the requested cap, so excluding it hid the violation that caused
    # the failure from both numerator and denominator.
    capped_calls = [
        call for call in calls if _reported_output_tokens(call) > 0
    ]
    output_cap_violations = sum(
        _reported_output_tokens(call) > args.max_tokens
        for call in capped_calls
    )
    maximum_output_tokens = max(
        (_reported_output_tokens(call) for call in calls),
        default=0,
    )
    failed_attempt_output_tokens = sum(
        _reported_output_tokens(call)
        for call in calls
        if call.get("error")
    )
    cost_records_missing = len(calls) - cost_records_reported
    usage_records_missing = len(calls) - usage_records_reported

    scores = [
        float(record["score"]) for record in judgments if is_scored(record)
    ]
    call_matched_question_ids = _current_run_question_ids(calls, answers)
    planned_descriptors = list(
        getattr(args, "planned_questions", None) or []
    )
    planned_question_ids = [
        str(record.get("question_id"))
        for record in planned_descriptors
        if record.get("question_id")
    ]
    if not planned_question_ids:
        planned_question_ids = [
            str(question_id)
            for question_id in (
                getattr(args, "planned_question_ids", None) or []
            )
        ]
    has_planned_contract = bool(planned_question_ids)
    score_question_ids = (
        planned_question_ids
        if has_planned_contract
        else sorted(call_matched_question_ids)
    )
    score_question_id_set = set(score_question_ids)
    current_answers = [
        record
        for record in answers
        if str(record.get("question_id")) in score_question_id_set
    ]
    answers_by_id = {
        str(record.get("question_id")): record for record in current_answers
    }
    candidate_judgments = [
        record
        for record in judgments
        if str(record.get("question_id")) in score_question_id_set
        and is_scored(record)
    ]
    current_judgments = [
        record
        for record in candidate_judgments
        if (
            (answer := answers_by_id.get(str(record.get("question_id"))))
            is not None
            and _judgment_matches_answer(record, answer)
        )
    ]
    judgments_by_id = {
        str(record.get("question_id")): record
        for record in current_judgments
    }
    failed_ids = failed_question_ids(current_answers)
    if has_planned_contract:
        # Missing answers, missing judgments, and provider failures are all zero
        # on the immutable planned denominator. Nothing can disappear merely
        # because an upstream file was absent.
        current_scores = [
            0.0
            if question_id not in answers_by_id
            or question_id not in judgments_by_id
            or question_id in failed_ids
            else float(judgments_by_id[question_id]["score"])
            for question_id in score_question_ids
        ]
    else:
        current_scores = normalized_scores(current_judgments, failed_ids)
    quality_points = sum(current_scores)
    # The interval must resample exactly the scores behind the point estimate.
    # Seeding from the requested model keeps it stable across panel subsets.
    quality_interval = bootstrap_ci(
        current_scores, seed=stable_seed(str(args.model))
    )
    current_failures = sum(
        answer_failed(record) for record in current_answers
    )
    missing_answer_ids = sorted(
        score_question_id_set - answers_by_id.keys()
    )
    missing_judgment_ids = sorted(
        score_question_id_set - judgments_by_id.keys()
    )
    mismatched_judgment_ids = sorted(
        {
            str(record.get("question_id"))
            for record in candidate_judgments
            if str(record.get("question_id")) not in judgments_by_id
        }
    )
    missing_call_ids = sorted(
        score_question_id_set - call_matched_question_ids
    )
    unexpected_answer_ids = sorted(
        {
            str(record.get("question_id"))
            for record in answers
            if record.get("question_id")
        }
        - score_question_id_set
    )
    completeness = {
        "contract": (
            "planned-question-ids-v1"
            if has_planned_contract
            else "legacy-observed-answers"
        ),
        "strict": bool(
            has_planned_contract
            and not getattr(args, "allow_incomplete", False)
        ),
        "planned_questions": len(score_question_ids),
        "answers_present": len(answers_by_id),
        "judgments_present": len(judgments_by_id),
        "calls_linked_to_answers": len(
            score_question_id_set & call_matched_question_ids
        ),
        "missing_answer_ids": missing_answer_ids,
        "missing_judgment_ids": missing_judgment_ids,
        "mismatched_answer_id_judgment_ids": mismatched_judgment_ids,
        "missing_call_link_ids": missing_call_ids,
        "unexpected_answer_ids": unexpected_answer_ids,
        "complete": bool(
            has_planned_contract
            and not missing_answer_ids
            and not missing_judgment_ids
            and not missing_call_ids
        )
        if has_planned_contract
        else None,
    }
    failed_answers = sum(answer_failed(record) for record in answers)
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
    operational = compute_operational_metrics(
        calls,
        answers=answers,
        judgments=current_judgments,
        planned_question_ids=(
            score_question_ids if has_planned_contract else ()
        ),
        deadline_ms=getattr(args, "deadline_ms", None),
        budget_usd=getattr(args, "max_cost_usd_per_answer", None),
        output_cap_tokens=args.max_tokens,
    )
    credits_float = float(credits) if credits_available else 0.0
    if not cost_usd_available and credits_available:
        cost_usd = credits * usd_per_credit
        cost_usd_available = True
    usd_float = float(cost_usd) if cost_usd_available else 0.0
    total_tokens = input_tokens + output_tokens
    final_answer_latency = operational["questions"][
        "cumulative_final_answer_latency_ms"
    ]
    total_latency_ms = sum(
        float(record.get("observed_cumulative_latency_ms") or 0)
        for record in operational["question_results"]
    )
    total_latency_seconds = total_latency_ms / 1000
    observed_scored_count = len(current_judgments)
    score_denominator = len(current_scores)
    successful_answer_count = max(
        0,
        score_denominator - current_failures - len(missing_answer_ids),
    )
    if has_planned_contract and planned_descriptors:
        metadata_by_id = {
            str(record.get("question_id")): record
            for record in planned_descriptors
        }
        category_values: dict[str, list[float]] = {}
        for question_id, score in zip(
            score_question_ids, current_scores, strict=True
        ):
            category = str(
                metadata_by_id.get(question_id, {}).get("category")
                or "unknown"
            )
            category_values.setdefault(category, []).append(score)
        planned_category_scores = {
            category: sum(values) / len(values)
            for category, values in sorted(category_values.items())
        }
    else:
        planned_category_scores = category_scores(
            current_judgments, failed_ids
        )
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
            "usage_records_reported": usage_records_reported,
            "usage_records_missing": usage_records_missing,
            "token_total_is_lower_bound": bool(usage_records_missing),
            "kendr_credits": format(credits, "f")
            if credits_available
            else None,
            "kendr_cost_usd": format(credits * usd_per_credit, "f")
            if credits_available
            else None,
            "cost_usd": format(cost_usd, "f")
            if cost_usd_available
            else None,
            "cost_records_reported": cost_records_reported,
            "cost_records_missing": cost_records_missing,
            "cost_total_is_lower_bound": bool(cost_records_missing),
            "usd_per_credit": format(usd_per_credit, "f"),
            "mean_latency_ms": (
                sum(latencies) / len(latencies) if latencies else None
            ),
            "mean_final_answer_latency_ms": final_answer_latency["mean"],
            "requested_max_output_tokens": args.max_tokens,
            "calls_exceeding_requested_output_cap": output_cap_violations,
            "maximum_output_tokens_observed": maximum_output_tokens,
            "failed_attempt_output_tokens": failed_attempt_output_tokens,
            "token_totals_include_failed_attempts": True,
        },
        "completeness": completeness,
        "current_run_quality": {
            "measurement": (
                "Official LiveBench objective ground-truth scores on the "
                "immutable planned-question denominator; missing work and "
                "provider failures score zero"
                if has_planned_contract
                else "Legacy observed-only LiveBench scores matched to request "
                "IDs; no immutable plan was recorded"
            ),
            "questions_matched_to_current_calls": len(
                call_matched_question_ids & score_question_id_set
            ),
            "questions_planned": score_denominator,
            "questions_with_judgment": observed_scored_count,
            "questions_scored": observed_scored_count,
            "score_denominator": score_denominator,
            "quality_points": quality_points,
            "objective_score_mean": (
                quality_points / score_denominator
                if score_denominator
                else None
            ),
            "perfect_score_rate": (
                sum(score >= 1.0 for score in current_scores)
                / score_denominator
                if score_denominator
                else None
            ),
            "nonzero_score_rate": (
                sum(score > 0 for score in current_scores)
                / score_denominator
                if score_denominator
                else None
            ),
            "quality_ci95": quality_interval,
            "category_scores": planned_category_scores,
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
                "Client-observed non-streaming latency. Final-answer latency "
                "is cumulative across retries and multi-turn calls; time to "
                "first token is unavailable."
            ),
            # Backward-compatible headline key, now corrected to describe what
            # the benchmark user actually waited for.
            "end_to_end_ms": final_answer_latency,
            "final_answer_ms": final_answer_latency,
            "logical_request_cumulative_ms": operational[
                "logical_requests"
            ]["cumulative_latency_ms"],
            "attempt_ms": operational["attempts"]["latency_ms"],
            "successful_attempt_ms": _distribution_stats(latencies),
            "failed_request_ms": _distribution_stats(
                failed_request_latencies
            ),
            "router_ms": _distribution_stats(router_latencies),
            "router_confidence": _distribution_stats(
                router_confidences
            ),
        },
        "reliability": {
            "successful_answers": successful_answer_count,
            "failed_answers": current_failures,
            "missing_answers": len(missing_answer_ids),
            "answer_success_rate": (
                successful_answer_count / score_denominator
                if score_denominator
                else None
            ),
            "scoring_coverage": (
                observed_scored_count / score_denominator
                if score_denominator
                else None
            ),
            # The headline is conservative question-level conformance. The
            # measured-only rate remains available explicitly for diagnostics.
            "output_cap_compliance_rate": operational["conformance"][
                "output_cap"
            ]["conservative_rate"],
            "output_cap_measured_rate": operational["conformance"][
                "output_cap"
            ]["measured_rate"],
            "output_cap_unknown_questions": operational["conformance"][
                "output_cap"
            ]["unknown"],
            "output_cap_measured_attempts": (
                operational["conformance"]["output_cap_by_attempt"]["pass"]
                + operational["conformance"]["output_cap_by_attempt"]["fail"]
            ),
            "output_cap_attempt_conformance": operational["conformance"][
                "output_cap_by_attempt"
            ],
            "calls_exceeding_requested_output_cap": (
                output_cap_violations
            ),
            "malformed_cost_records": malformed_cost_records,
            "route_distribution": dict(route_distribution),
            "router_task_distribution": dict(task_distribution),
            "provider_error_distribution": dict(
                provider_error_distribution
            ),
            "deadline_conformance": operational["conformance"][
                "deadline"
            ],
            "budget_conformance": operational["conformance"]["budget"],
            "operational_output_cap_conformance": operational[
                "conformance"
            ]["output_cap"],
            "operational_goodput": operational[
                "operational_goodput"
            ],
            "score_weighted_goodput": operational[
                "score_weighted_goodput"
            ],
        },
        "operations": operational,
        "relevance": {
            "separately_scored": False,
            "objective_task_score_proxy": (
                quality_points / score_denominator
                if score_denominator
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
            "integrity_manifest": "artifact_hashes.json",
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
    completeness = summary.get("completeness") or {}
    operations = summary.get("operations") or {}
    cap_conformance = reliability.get(
        "operational_output_cap_conformance", {}
    )
    cap_attempt_conformance = (
        (operations.get("conformance") or {}).get(
            "output_cap_by_attempt", {}
        )
    )

    def percent(value: Any) -> str:
        return f"{float(value) * 100:.2f}%" if value is not None else "n/a"

    def number(value: Any, digits: int = 3) -> str:
        return f"{float(value):.{digits}f}" if value is not None else "n/a"

    def bounded_number(
        value: Any, bound: str, digits: int = 3
    ) -> str:
        return f"{bound}{number(value, digits)}" if value is not None else "n/a"

    provider = str(api.get("provider") or "kendr")
    credits = api["kendr_credits"] or "n/a"
    tokens_are_lower_bound = bool(api.get("token_total_is_lower_bound"))
    cost_is_lower_bound = bool(api.get("cost_total_is_lower_bound"))
    token_bound = "≥" if tokens_are_lower_bound else ""
    cost_bound = "≥" if cost_is_lower_bound else ""
    cost = (
        f"{cost_bound}${Decimal(api['cost_usd']):f}"
        if api.get("cost_usd") is not None
        else "n/a"
    )
    latency = (
        f"{api['mean_final_answer_latency_ms']:.1f} ms"
        if api.get("mean_final_answer_latency_ms") is not None
        else "n/a"
    )
    unknown_cap_attempts = int(cap_attempt_conformance.get("unknown") or 0)
    unknown_cap_questions = int(cap_conformance.get("unknown") or 0)
    if api["calls_exceeding_requested_output_cap"]:
        cap_status = (
            "WARNING: provider output exceeded the requested "
            f"{api['requested_max_output_tokens']}-token cap; maximum "
            f"observed was {api['maximum_output_tokens_observed']}."
        )
    elif unknown_cap_attempts:
        cap_status = (
            "WARNING: no measured output exceeded the requested token cap, "
            f"but {unknown_cap_attempts} attempt(s) lacked usage telemetry; "
            f"{unknown_cap_questions} planned question(s) therefore have "
            "unknown cap conformance."
        )
    else:
        cap_status = (
            "Every captured attempt had enough usage telemetry to verify the "
            "requested token cap, and none exceeded it."
        )
    tokens_per_quality = bounded_number(
        efficiency["total_tokens_per_quality_point"], token_bound
    )
    quality_per_tokens = bounded_number(
        efficiency["quality_points_per_1000_tokens"],
        "≤" if tokens_are_lower_bound else "",
    )
    credits_per_quality = bounded_number(
        efficiency["credits_per_quality_point"], cost_bound, 6
    )
    usd_per_quality = bounded_number(
        efficiency["usd_per_quality_point"], cost_bound, 8
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
        f"- Tokens in/out: {token_bound}{api['input_tokens']} / "
        f"{token_bound}{api['output_tokens']}",
        f"- Usage telemetry reported/missing: "
        f"{api.get('usage_records_reported', 'n/a')} / "
        f"{api.get('usage_records_missing', 'n/a')}; totals are "
        f"{'captured lower bounds' if tokens_are_lower_bound else 'complete'}",
        f"- Kendr credits in this run: {credits}",
        f"- Cost in this run: {cost}",
        f"- Cost telemetry reported/missing: "
        f"{api.get('cost_records_reported', 'n/a')} / "
        f"{api.get('cost_records_missing', 'n/a')}; total is "
        f"{'a captured lower bound' if cost_is_lower_bound else 'complete'}",
        f"- Mean cumulative final-answer latency: {latency}",
        f"- Calls exceeding requested output cap: "
        f"{api['calls_exceeding_requested_output_cap']}",
        f"- Output-cap status: {cap_status}",
        "",
        "## Current-run quality",
        "",
        f"- Questions planned/matched/judged: "
        f"{quality.get('questions_planned', 'legacy')} / "
        f"{quality['questions_matched_to_current_calls']} / "
        f"{quality['questions_scored']}",
        f"- Completeness contract/status: "
        f"`{completeness.get('contract', 'legacy')}` / "
        f"{completeness.get('complete')}",
        f"- Objective score mean: "
        f"{percent(quality['objective_score_mean'])}",
        f"- Perfect-score rate: {percent(quality['perfect_score_rate'])}",
        f"- Nonzero-score rate: {percent(quality['nonzero_score_rate'])}",
        "",
        "Under a planned-question contract, missing answers or judgments stay "
        "in the denominator as zero. Legacy exports remain observed-only.",
        "",
        "## Efficiency",
        "",
        f"- Total tokens per quality point: {tokens_per_quality}",
        f"- Quality points per 1,000 tokens: {quality_per_tokens}",
        f"- Credits per quality point: {credits_per_quality}",
        f"- USD per quality point: {usd_per_quality}",
        f"- Output/input token ratio: "
        f"{number(efficiency['output_to_input_token_ratio'])}",
        f"- Output throughput: "
        f"{number(efficiency['output_tokens_per_second'])} tokens/s",
        f"- Latency per quality point: "
        f"{number(efficiency['latency_ms_per_quality_point'], 1)} ms",
        "",
        "## Latency and reliability",
        "",
        f"- Cumulative final-answer latency p50/p95/p99: "
        f"{number(latency_metrics['end_to_end_ms']['p50'], 1)} / "
        f"{number(latency_metrics['end_to_end_ms']['p95'], 1)} / "
        f"{number(latency_metrics['end_to_end_ms']['p99'], 1)} ms",
        f"- Attempt latency p50/p95: "
        f"{number(latency_metrics.get('attempt_ms', {}).get('p50'), 1)} / "
        f"{number(latency_metrics.get('attempt_ms', {}).get('p95'), 1)} ms",
        f"- Observed attempt amplification: "
        f"{number((operations.get('retries') or {}).get('observed_attempt_amplification'), 3)}x",
        f"- Retry latency amplification: "
        f"{number((operations.get('retries') or {}).get('latency_amplification'), 3)}x",
        f"- Mean router latency: "
        f"{number(latency_metrics['router_ms']['mean'], 1)} ms",
        f"- Answer success rate: "
        f"{percent(reliability['answer_success_rate'])}",
        f"- Scoring coverage: {percent(reliability['scoring_coverage'])}",
        f"- Output-cap compliance (conservative question-level): "
        f"{percent(cap_conformance.get('conservative_rate'))}",
        f"- Output-cap compliance (measured question-level): "
        f"{percent(cap_conformance.get('measured_rate'))}; "
        f"unknown questions: {unknown_cap_questions}",
        f"- Deadline conformance (conservative): "
        f"{percent((reliability.get('deadline_conformance') or {}).get('conservative_rate'))}",
        f"- Per-answer budget conformance (conservative): "
        f"{percent((reliability.get('budget_conformance') or {}).get('conservative_rate'))}",
        f"- Operational goodput (conservative): "
        f"{percent((reliability.get('operational_goodput') or {}).get('conservative_rate'))}",
        f"- Score-weighted goodput (conservative): "
        f"{percent((reliability.get('score_weighted_goodput') or {}).get('conservative_mean'))}",
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
        raise RuntimeError(
            f"{detail}. Run `llm-benchmark-livebench setup` first."
        )

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

    supplied_plan = getattr(args, "planned_questions", None)
    if supplied_plan is None:
        source_records = load_livebench_question_records(
            args.bench_name, args.livebench_release_option
        )
        planned_records = _planned_question_records(
            source_records,
            question_ids=args.question_id,
            question_begin=args.question_begin,
            question_end=args.question_end,
        )
    else:
        planned_records = [dict(record) for record in supplied_plan]
        if not planned_records:
            raise RuntimeError("The supplied benchmark plan is empty.")
    planned_questions = _planned_question_descriptors(planned_records)
    planned_question_ids = [
        record["question_id"] for record in planned_questions
    ]
    if len(planned_question_ids) != len(set(planned_question_ids)):
        raise RuntimeError("The benchmark plan contains duplicate question IDs.")
    sampling_provenance = getattr(args, "sampling_provenance", None)
    if sampling_provenance:
        sampled_ids = [
            str(question_id)
            for question_id in sampling_provenance.get("selected_ids", [])
        ]
        if sampled_ids != planned_question_ids:
            raise RuntimeError(
                "The supplied planned questions do not match the frozen "
                "sampling provenance selected IDs."
            )
    # Always hand LiveBench exact IDs. Its positional slice is tied to mutable
    # dataset order and therefore cannot be an auditable experiment contract.
    args.question_id = planned_question_ids
    args.question_begin = None
    args.question_end = None
    args.planned_questions = planned_questions
    args.planned_question_ids = planned_question_ids

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
        "deadline_ms": getattr(args, "deadline_ms", None),
        "max_cost_usd_per_answer": (
            format(args.max_cost_usd_per_answer, "f")
            if getattr(args, "max_cost_usd_per_answer", None) is not None
            else None
        ),
        "usd_per_credit": format(usd_per_credit, "f"),
        "planned_questions": planned_questions,
        "planned_question_ids": planned_question_ids,
        "planned_question_count": len(planned_question_ids),
        "planned_question_descriptor_sha256": _json_sha256(
            planned_questions
        ),
        "planned_question_content_sha256": _json_sha256(planned_records),
        "planned_question_content_hash_scope": "selected-full-records",
        "sampling": sampling_provenance,
        "completeness_policy": (
            "allow-incomplete"
            if getattr(args, "allow_incomplete", False)
            else "strict"
        ),
        "grading_recovery": {
            "policy": "single-serial-missing-successful-judgment-retry-v1",
            "maximum_attempts": 1,
            "attempted": False,
            "question_ids": [],
            "parallel_grading": None,
            "provider_inference_replayed": False,
        },
        "runtime": {
            "python": sys.version,
            "packages": _package_versions(),
        },
        "compatibility_patches": [
            "multi-word-category-path-runtime-shim-v1",
            INSTRUCTION_FOLLOWING_COMPATIBILITY_PATCH,
            KENDR_OUTPUT_CAP_COMPATIBILITY_PATCH,
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
    calls = _read_calls(call_log)
    current_answer_ids = _current_run_question_ids(calls, answers)
    all_planned_answers_are_current = set(planned_question_ids) <= (
        current_answer_ids
    )
    if not args.skip_grading and all_planned_answers_are_current:
        retry_question_ids = _missing_successful_judgment_ids(
            planned_ids=planned_question_ids,
            answers=answers,
            judgments=judgments,
        )
        if retry_question_ids:
            recovery = manifest["grading_recovery"]
            recovery.update(
                {
                    "attempted": True,
                    "question_ids": retry_question_ids,
                    "parallel_grading": 1,
                }
            )
            (run_dir / "manifest.json").write_text(
                json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
            )
            retry_args = argparse.Namespace(**vars(args))
            retry_args.question_id = retry_question_ids
            retry_args.parallel_grading = 1
            retry_args.resume = False
            _run_command(
                _grading_command(retry_args, root),
                cwd=work_dir,
                env=child_env,
            )
            judgment_paths = _paths_for_benches(
                work_dir,
                args.bench_name,
                "model_judgment/ground_truth_judgment.jsonl",
            )
            judgments = _model_judgments(
                _read_jsonl(judgment_paths), args.model_display_name
            )
    if not args.skip_grading:
        _run_command(
            _show_command(args, root),
            cwd=work_dir,
            env=child_env,
        )
    _write_jsonl(run_dir / "answers.jsonl", answers)
    _write_jsonl(run_dir / "judgments.jsonl", judgments)
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
    _write_artifact_hashes(run_dir)
    completeness = summary.get("completeness") or {}
    if (
        not getattr(args, "allow_incomplete", False)
        and completeness.get("complete") is False
    ):
        raise RuntimeError(
            "Run did not satisfy its planned-question contract; artifacts "
            f"were preserved at {run_dir}. Missing answers: "
            f"{len(completeness.get('missing_answer_ids') or [])}; missing "
            "judgments: "
            f"{len(completeness.get('missing_judgment_ids') or [])}."
        )
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
    planned_questions = manifest.get("planned_questions")
    expected_plan_hash = manifest.get(
        "planned_question_descriptor_sha256"
    )
    if planned_questions and expected_plan_hash:
        actual_plan_hash = _json_sha256(planned_questions)
        if actual_plan_hash != expected_plan_hash:
            raise RuntimeError(
                "Planned-question descriptors no longer match their manifest "
                "SHA-256; refusing to rebuild a mutated experiment."
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
        deadline_ms=manifest.get("deadline_ms"),
        max_cost_usd_per_answer=manifest.get(
            "max_cost_usd_per_answer"
        ),
        planned_questions=manifest.get("planned_questions"),
        planned_question_ids=manifest.get("planned_question_ids"),
        sampling_provenance=manifest.get("sampling"),
        allow_incomplete=(
            manifest.get("completeness_policy") == "allow-incomplete"
        ),
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
    _write_artifact_hashes(run_dir)
    return summary


def _normalize_missing_failed_judgments(
    *,
    judgments: list[dict[str, Any]],
    answers: list[dict[str, Any]],
    planned_questions: list[dict[str, Any]],
    planned_ids: list[str],
    model_display_name: str,
) -> list[str]:
    """Add explicit zero judgments only for provider-failed answers.

    Some pinned LiveBench objective graders do not emit a row when the model
    answer is ``$ERROR$``.  The matrix contract already assigns such outcomes
    zero.  Materializing that zero keeps the immutable denominator complete
    without inventing a score for a successful but ungraded answer.
    """
    present = {str(item.get("question_id") or "") for item in judgments}
    missing = [question_id for question_id in planned_ids if question_id not in present]
    if not missing:
        return []
    failed_ids = failed_question_ids(answers)
    unsafe = sorted(set(missing) - failed_ids)
    if unsafe:
        raise RuntimeError(
            "Official grading omitted successful answers; refusing to "
            "synthesize judgments for: " + ", ".join(unsafe)
        )
    plan_by_id = {
        str(item.get("question_id") or ""): item
        for item in planned_questions
    }
    answer_by_id = {
        str(item.get("question_id") or ""): item for item in answers
    }
    timestamp = datetime.now(timezone.utc).timestamp()
    for question_id in missing:
        plan = plan_by_id.get(question_id, {})
        answer = answer_by_id[question_id]
        judgments.append(
            {
                "_source_file": "protocol://failure-normalization-v1",
                "answer_id": answer.get("answer_id"),
                "category": plan.get("category"),
                "model": model_display_name,
                "normalization": (
                    "official grader emitted no row for provider-failed "
                    "$ERROR$ answer; zero required by frozen matrix policy"
                ),
                "question_id": question_id,
                "score": 0.0,
                "task": plan.get("task"),
                "tstamp": timestamp,
            }
        )
    return missing


def finalize_interrupted_run(
    run_dir: Path,
    *,
    livebench_root: Path,
    parallel_grading: int = 4,
    usd_per_credit: Decimal | None = None,
) -> dict[str, Any]:
    """Finish grading a captured first trial without replaying inference.

    LiveBench writes model answers to its workspace before the harness copies
    them into the run directory.  If orchestration is interrupted after all
    provider calls finish, silently preferring a later clean rerun creates
    survivorship bias.  This recovery path accepts only workspace answers that
    link back to every captured call and planned question in the original run.
    """
    root = livebench_root.resolve()
    valid, detail = _validate_checkout(root)
    if not valid:
        raise RuntimeError(
            f"{detail}. Run `llm-benchmark-livebench setup` first."
        )

    run_dir = run_dir.resolve()
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.is_file():
        raise RuntimeError(f"Manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("livebench_revision") != LIVEBENCH_REVISION:
        raise RuntimeError(
            "Interrupted run does not use the pinned LiveBench revision."
        )
    planned_questions = manifest.get("planned_questions") or []
    planned_ids = [
        str(question_id)
        for question_id in (manifest.get("planned_question_ids") or [])
    ]
    if not planned_ids or len(planned_ids) != len(set(planned_ids)):
        raise RuntimeError(
            "Interrupted run lacks a unique frozen planned-question list."
        )
    expected_plan_hash = manifest.get(
        "planned_question_descriptor_sha256"
    )
    if (
        not expected_plan_hash
        or _json_sha256(planned_questions) != expected_plan_hash
    ):
        raise RuntimeError(
            "Planned-question descriptors do not match the run manifest."
        )

    calls = _read_calls(run_dir / "calls.jsonl")
    if not calls:
        raise RuntimeError(
            "Interrupted run contains no captured provider calls."
        )
    run_id = str(manifest.get("run_id") or "")
    if any(str(call.get("run_id") or "") != run_id for call in calls):
        raise RuntimeError(
            "Captured calls do not all belong to the interrupted run ID."
        )

    work_dir = root / "livebench"
    model_display_name = str(manifest.get("model_display_name") or "")
    answer_paths = _paths_for_benches(
        work_dir,
        manifest.get("benchmarks") or [],
        f"model_answer/{model_display_name}.jsonl",
    )
    answers = _read_jsonl(answer_paths)
    answer_ids = [str(answer.get("question_id") or "") for answer in answers]
    if len(answers) != len(planned_ids) or set(answer_ids) != set(planned_ids):
        raise RuntimeError(
            "Workspace answers do not exactly match the interrupted run's "
            "frozen question plan."
        )
    linked_ids = _current_run_question_ids(calls, answers)
    if linked_ids != set(planned_ids):
        missing = sorted(set(planned_ids) - linked_ids)
        raise RuntimeError(
            "Workspace answers are not fully linked to the captured provider "
            f"calls; missing question IDs: {', '.join(missing)}"
        )

    args = argparse.Namespace(
        provider=manifest.get("provider", "kendr"),
        model=manifest["requested_model"],
        model_display_name=model_display_name,
        livebench_release_option=manifest["livebench_release"],
        bench_name=list(manifest["benchmarks"]),
        question_id=planned_ids,
        question_begin=None,
        question_end=None,
        parallel_grading=parallel_grading,
        resume=False,
        ignore_missing_answers=True,
        compare_model=[],
    )
    child_env = os.environ.copy()
    child_env["PYTHONUTF8"] = "1"
    child_env["PYTHONIOENCODING"] = "utf-8"
    child_env["PYTHONPATH"] = os.pathsep.join(
        filter(None, [str(root), child_env.get("PYTHONPATH", "")])
    )
    _run_command(
        _grading_command(args, root), cwd=work_dir, env=child_env
    )
    _run_command(_show_command(args, root), cwd=work_dir, env=child_env)

    judgment_paths = _paths_for_benches(
        work_dir,
        args.bench_name,
        "model_judgment/ground_truth_judgment.jsonl",
    )
    judgments = _model_judgments(
        _read_jsonl(judgment_paths), model_display_name
    )
    normalized_missing_ids = _normalize_missing_failed_judgments(
        judgments=judgments,
        answers=answers,
        planned_questions=planned_questions,
        planned_ids=planned_ids,
        model_display_name=model_display_name,
    )
    _write_jsonl(run_dir / "answers.jsonl", answers)
    _write_jsonl(run_dir / "judgments.jsonl", judgments)
    _copy_score_files(work_dir, run_dir)

    manifest["finalization"] = {
        "mode": "salvaged-interrupted-first-trial",
        "finalized_at": datetime.now(timezone.utc).isoformat(),
        "provider_inference_replayed": False,
        "captured_calls": len(calls),
        "linked_planned_questions": len(linked_ids),
        "workspace_answers_verified_against_calls": True,
        "failure_normalized_missing_judgment_ids": normalized_missing_ids,
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    summary = summarize_existing_run(
        run_dir,
        livebench_root=root,
        usd_per_credit=usd_per_credit,
    )
    completeness = summary.get("completeness") or {}
    if completeness.get("complete") is not True:
        raise RuntimeError(
            "Recovered run did not satisfy the strict planned-question "
            "contract; artifacts were preserved for diagnosis."
        )
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
        if args.command == "finalize":
            summary = finalize_interrupted_run(
                args.run_dir,
                livebench_root=args.livebench_root,
                parallel_grading=args.parallel_grading,
                usd_per_credit=args.kendr_usd_per_credit,
            )
            print(
                "Finalized without replaying inference: "
                f"{args.run_dir.resolve()} "
                f"({summary['current_run_quality']['questions_scored']} "
                "questions scored)"
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
        print(f"llm-benchmark-livebench failed: {exc}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
