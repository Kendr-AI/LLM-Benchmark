from __future__ import annotations

import importlib.metadata
import json
import platform
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Iterable

from . import __version__
from .domain import BenchmarkCase, BenchmarkRecord, Cost, ProviderResult, Usage
from .providers import (
    KENDR_SOURCE_REPOSITORY,
    KENDR_SOURCE_REVISION,
    BenchmarkProvider,
)
from .reporting import write_artifacts


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_cases(path: Path) -> list[BenchmarkCase]:
    cases: list[BenchmarkCase] = []
    seen: set[str] = set()
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            value = json.loads(line)
            case_id = str(value.get("id") or "").strip()
            input_text = value.get("input")
            if not case_id:
                raise ValueError(f"{path}:{line_number}: case id is required")
            if case_id in seen:
                raise ValueError(f"{path}:{line_number}: duplicate case id {case_id!r}")
            if not isinstance(input_text, str) or not input_text:
                raise ValueError(
                    f"{path}:{line_number}: non-empty string input is required"
                )
            seen.add(case_id)
            known = {"id", "input", "instructions", "category"}
            cases.append(
                BenchmarkCase(
                    id=case_id,
                    input=input_text,
                    instructions=str(value.get("instructions") or ""),
                    category=str(value.get("category") or "general"),
                    metadata={
                        key: item for key, item in value.items() if key not in known
                    },
                )
            )
    if not cases:
        raise ValueError(f"{path}: no benchmark cases found")
    return cases


def _package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def sanitize_error_message(message: str) -> str:
    """Remove credential-like values before an exception is persisted."""
    patterns = (
        r"(?i)\b(sk-(?:proj-|svcacct-)?)[A-Za-z0-9_*.\-=]{4,}",
        r"(?i)\b(kndr_(?:live|test)_)[A-Za-z0-9_*.\-=]{4,}",
        r"(?i)\b(Bearer\s+)[A-Za-z0-9._~+/\-=]{8,}",
    )
    sanitized = message
    for pattern in patterns:
        sanitized = re.sub(pattern, r"\1[REDACTED]", sanitized)
    return sanitized


def _record_success(
    run_id: str,
    case: BenchmarkCase,
    repeat: int,
    result: ProviderResult,
    started_at: str,
    finished_at: str,
    max_output_tokens: int,
) -> BenchmarkRecord:
    return BenchmarkRecord(
        run_id=run_id,
        case_id=case.id,
        repeat=repeat,
        provider=result.provider,
        requested_model=result.requested_model,
        actual_model=result.actual_model,
        input=case.input,
        instructions=case.instructions,
        output=result.output_text,
        usage=result.usage,
        cost=result.cost,
        latency_ms=result.latency_ms,
        request_id=result.request_id,
        status="ok",
        started_at=started_at,
        finished_at=finished_at,
        request_parameters={"max_output_tokens": max_output_tokens},
        provider_metadata=result.metadata,
    )


def _record_error(
    run_id: str,
    case: BenchmarkCase,
    repeat: int,
    provider: BenchmarkProvider,
    error: Exception,
    latency_ms: float,
    started_at: str,
    finished_at: str,
    max_output_tokens: int,
) -> BenchmarkRecord:
    return BenchmarkRecord(
        run_id=run_id,
        case_id=case.id,
        repeat=repeat,
        provider=provider.name,
        requested_model=provider.model,
        actual_model="",
        input=case.input,
        instructions=case.instructions,
        output="",
        usage=Usage(),
        cost=Cost(None, None, "unavailable"),
        latency_ms=latency_ms,
        request_id="",
        status="error",
        started_at=started_at,
        finished_at=finished_at,
        request_parameters={"max_output_tokens": max_output_tokens},
        error={
            "type": type(error).__name__,
            "message": sanitize_error_message(str(error)),
        },
    )


def run_benchmark(
    *,
    providers: Iterable[BenchmarkProvider],
    cases: list[BenchmarkCase],
    output_root: Path,
    max_output_tokens: int,
    repeat_count: int,
    pricing_file: Path,
    pricing_as_of: str,
    fail_fast: bool = False,
    label: str = "",
) -> tuple[Path, list[BenchmarkRecord], dict[str, Path]]:
    providers_list = list(providers)
    started_at = utc_now()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = uuid.uuid4().hex[:8]
    safe_label = "".join(
        character if character.isalnum() or character in "-_" else "-"
        for character in label.strip()
    ).strip("-")
    run_id = f"{stamp}-{safe_label + '-' if safe_label else ''}{suffix}"
    records: list[BenchmarkRecord] = []

    for repeat in range(1, repeat_count + 1):
        for case in cases:
            for provider in providers_list:
                call_started_at = utc_now()
                timer = perf_counter()
                try:
                    result = provider.generate(
                        case,
                        max_output_tokens=max_output_tokens,
                        run_id=run_id,
                        repeat=repeat,
                    )
                    call_finished_at = utc_now()
                    records.append(
                        _record_success(
                            run_id,
                            case,
                            repeat,
                            result,
                            call_started_at,
                            call_finished_at,
                            max_output_tokens,
                        )
                    )
                except Exception as exc:
                    call_finished_at = utc_now()
                    records.append(
                        _record_error(
                            run_id,
                            case,
                            repeat,
                            provider,
                            exc,
                            (perf_counter() - timer) * 1000,
                            call_started_at,
                            call_finished_at,
                            max_output_tokens,
                        )
                    )
                    if fail_fast:
                        raise

    manifest: dict[str, Any] = {
        "schema_version": 1,
        "run_id": run_id,
        "started_at": started_at,
        "finished_at": utc_now(),
        "label": label,
        "providers": [
            {"provider": provider.name, "model": provider.model}
            for provider in providers_list
        ],
        "case_ids": [case.id for case in cases],
        "repeat_count": repeat_count,
        "max_output_tokens": max_output_tokens,
        "fairness_controls": {
            "same_input": True,
            "same_instructions": True,
            "same_max_output_tokens": True,
            "web_search": False,
            "openai_service_tier": "default",
        },
        "pricing": {
            "file": str(pricing_file.resolve()),
            "as_of": pricing_as_of,
        },
        "runtime": {
            "python": sys.version,
            "platform": platform.platform(),
            "kendr_bench": __version__,
            "openai_sdk": _package_version("openai"),
            "kendr_sdk": _package_version("kendr"),
        },
        "kendr_source": {
            "repository": KENDR_SOURCE_REPOSITORY,
            "revision": KENDR_SOURCE_REVISION,
        },
    }
    run_dir = output_root / run_id
    paths = write_artifacts(run_dir, records, manifest)
    return run_dir, records, paths
