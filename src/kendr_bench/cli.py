from __future__ import annotations

import argparse
import os
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Sequence

from dotenv import load_dotenv

from .pricing import PricingCatalog
from .providers import (
    KENDR_DEFAULT_USD_PER_CREDIT,
    KendrProvider,
    OpenAIProvider,
)
from .runner import load_cases, run_benchmark


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kendr-bench",
        description="Benchmark OpenAI and Kendr token usage, cost, and latency.",
    )
    parser.add_argument(
        "--providers",
        default="openai,kendr",
        help="Comma-separated providers: openai,kendr (default: both)",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(".env"),
        help="Environment file to load (default: .env in the current directory)",
    )
    parser.add_argument(
        "--no-env-file",
        action="store_true",
        help="Do not load an environment file; use process variables only",
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path("benchmarks/cases.jsonl"),
        help="JSONL benchmark case file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results"),
        help="Root directory for timestamped result runs",
    )
    parser.add_argument(
        "--pricing",
        type=Path,
        default=Path("config/pricing.json"),
        help="Versioned provider pricing file",
    )
    parser.add_argument("--openai-model", default="gpt-5.6-sol")
    parser.add_argument("--kendr-model", default="kendr-intelligent")
    parser.add_argument(
        "--openai-reasoning-effort",
        choices=("none", "low", "medium", "high", "xhigh", "max"),
        default="none",
        help="Explicit effort keeps the OpenAI baseline reproducible",
    )
    parser.add_argument(
        "--max-output-tokens", type=_positive_int, default=512
    )
    parser.add_argument("--repeat", type=_positive_int, default=1)
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    parser.add_argument(
        "--kendr-usd-per-credit",
        type=_positive_decimal,
        default=None,
        help=(
            "USD value of one Kendr credit. Defaults to KendrWeb's 0.002; "
            "override when the admin billing setting differs"
        ),
    )
    parser.add_argument("--label", default="")
    parser.add_argument("--fail-fast", action="store_true")
    return parser


def load_environment(env_file: Path, *, disabled: bool) -> Path | None:
    if disabled or not env_file.is_file():
        return None
    resolved = env_file.resolve()
    # For this project-local CLI, the selected env file is explicit
    # configuration and therefore wins over stale inherited shell variables.
    load_dotenv(dotenv_path=resolved, override=True, encoding="utf-8")
    return resolved


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    loaded_env_file = load_environment(
        args.env_file, disabled=args.no_env_file
    )
    selected = [
        item.strip().lower()
        for item in args.providers.split(",")
        if item.strip()
    ]
    invalid = sorted(set(selected) - {"openai", "kendr"})
    if invalid:
        print(f"Unknown provider(s): {', '.join(invalid)}", file=sys.stderr)
        return 2
    if not selected:
        print("At least one provider is required.", file=sys.stderr)
        return 2
    if not args.cases.is_file():
        print(f"Cases file not found: {args.cases}", file=sys.stderr)
        return 2
    if not args.pricing.is_file():
        print(f"Pricing file not found: {args.pricing}", file=sys.stderr)
        return 2

    if "openai" in selected and not os.getenv("OPENAI_API_KEY"):
        print(
            "OPENAI_API_KEY is missing. Add it to the selected .env file or "
            "the process environment.",
            file=sys.stderr,
        )
        return 2
    if "kendr" in selected and not any(
        os.getenv(name)
        for name in (
            "KENDR_API_KEY",
            "KENDR_SESSION_TOKEN",
            "KENDR_SESSION_COOKIE",
        )
    ):
        print(
            "A Kendr credential is missing. Configure KENDR_API_KEY, "
            "KENDR_SESSION_TOKEN, or KENDR_SESSION_COOKIE.",
            file=sys.stderr,
        )
        return 2

    pricing = PricingCatalog.load(args.pricing)
    providers = []
    try:
        if "openai" in selected:
            providers.append(
                OpenAIProvider(
                    model=args.openai_model,
                    pricing=pricing,
                    reasoning_effort=args.openai_reasoning_effort,
                    timeout_seconds=args.timeout_seconds,
                )
            )
        if "kendr" in selected:
            usd_per_credit = args.kendr_usd_per_credit
            usd_conversion_source = "command_line"
            if usd_per_credit is None and os.getenv("KENDR_USD_PER_CREDIT"):
                usd_per_credit = _positive_decimal(
                    os.environ["KENDR_USD_PER_CREDIT"]
                )
                usd_conversion_source = "KENDR_USD_PER_CREDIT"
            elif usd_per_credit is None:
                usd_per_credit = KENDR_DEFAULT_USD_PER_CREDIT
                usd_conversion_source = "KendrWeb default"
            providers.append(
                KendrProvider(
                    model=args.kendr_model,
                    usd_per_credit=usd_per_credit,
                    usd_conversion_source=usd_conversion_source,
                    timeout_seconds=args.timeout_seconds,
                )
            )
    except Exception as exc:
        print(f"Provider setup failed: {exc}", file=sys.stderr)
        return 2

    cases = load_cases(args.cases)
    run_dir, records, paths = run_benchmark(
        providers=providers,
        cases=cases,
        output_root=args.output,
        max_output_tokens=args.max_output_tokens,
        repeat_count=args.repeat,
        pricing_file=args.pricing,
        pricing_as_of=pricing.as_of,
        fail_fast=args.fail_fast,
        label=args.label,
    )
    successful = sum(record.status == "ok" for record in records)
    errors = len(records) - successful
    if loaded_env_file is not None:
        print(f"Environment: {loaded_env_file}")
    print(f"Run: {run_dir.resolve()}")
    print(f"Records: {successful} successful, {errors} errors")
    print(f"Report: {paths['report'].resolve()}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
