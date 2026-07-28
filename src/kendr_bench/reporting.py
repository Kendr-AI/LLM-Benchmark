from __future__ import annotations

import csv
import json
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from statistics import mean, median
from typing import Any, Iterable

from .domain import BenchmarkRecord, decimal_text
from .pricing import RateCard


def _decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(value)
    except (InvalidOperation, TypeError):
        return None


def _ratio(numerator: Decimal | int, denominator: Decimal | int) -> str | None:
    if Decimal(denominator) == 0:
        return None
    return decimal_text(Decimal(numerator) / Decimal(denominator))


def _record_rate_card(record: BenchmarkRecord) -> RateCard | None:
    if not record.cost.rate_card:
        return None
    try:
        return RateCard.from_mapping(record.cost.rate_card)
    except (KeyError, TypeError, ValueError, InvalidOperation):
        return None


def build_summary(records: Iterable[BenchmarkRecord]) -> dict[str, Any]:
    record_list = list(records)
    by_provider: dict[str, list[BenchmarkRecord]] = defaultdict(list)
    for record in record_list:
        by_provider[record.provider].append(record)

    providers: dict[str, Any] = {}
    for provider, values in sorted(by_provider.items()):
        successful = [value for value in values if value.status == "ok"]
        total_usd = sum(
            (value.cost.amount_usd or Decimal("0") for value in successful),
            Decimal("0"),
        )
        total_credits = sum(
            (
                value.cost.amount or Decimal("0")
                for value in successful
                if value.cost.currency == "credits"
            ),
            Decimal("0"),
        )
        input_tokens = sum(value.usage.input_tokens for value in successful)
        output_tokens = sum(value.usage.output_tokens for value in successful)
        total_tokens = sum(value.usage.total_tokens for value in successful)
        latencies = [value.latency_ms for value in successful]
        providers[provider] = {
            "runs": len(values),
            "successful_runs": len(successful),
            "errors": len(values) - len(successful),
            "input_tokens": input_tokens,
            "cached_input_tokens": sum(
                value.usage.cached_input_tokens for value in successful
            ),
            "output_tokens": output_tokens,
            "reasoning_tokens": sum(
                value.usage.reasoning_tokens for value in successful
            ),
            "total_tokens": total_tokens,
            "cost_usd": decimal_text(total_usd) if total_usd else None,
            "credits": decimal_text(total_credits) if total_credits else None,
            "mean_latency_ms": round(mean(latencies), 3) if latencies else None,
            "p50_latency_ms": round(median(latencies), 3) if latencies else None,
            "total_tokens_per_usd": (
                _ratio(total_tokens, total_usd) if total_usd else None
            ),
            "output_tokens_per_usd": (
                _ratio(output_tokens, total_usd) if total_usd else None
            ),
        }

    paired: dict[tuple[str, int], dict[str, BenchmarkRecord]] = defaultdict(dict)
    for record in record_list:
        if record.status == "ok":
            paired[(record.case_id, record.repeat)][record.provider] = record

    comparisons: list[dict[str, Any]] = []
    for (case_id, repeat), values in sorted(paired.items()):
        if "openai" not in values or "kendr" not in values:
            continue
        openai = values["openai"]
        kendr = values["kendr"]
        openai_usd = openai.cost.amount_usd
        kendr_usd = kendr.cost.amount_usd
        comparison: dict[str, Any] = {
            "case_id": case_id,
            "repeat": repeat,
            "openai_total_tokens": openai.usage.total_tokens,
            "kendr_total_tokens": kendr.usage.total_tokens,
            "kendr_to_openai_token_ratio": _ratio(
                kendr.usage.total_tokens, openai.usage.total_tokens
            ),
            "openai_cost_usd": decimal_text(openai_usd),
            "kendr_cost_usd": decimal_text(kendr_usd),
            "kendr_credits": (
                decimal_text(kendr.cost.amount)
                if kendr.cost.currency == "credits"
                else None
            ),
            "openai_latency_ms": round(openai.latency_ms, 3),
            "kendr_latency_ms": round(kendr.latency_ms, 3),
        }
        if openai_usd is not None and kendr_usd is not None:
            comparison["kendr_to_openai_cost_ratio"] = _ratio(
                kendr_usd, openai_usd
            )
            comparison["kendr_cost_savings_percent"] = decimal_text(
                (Decimal("1") - (kendr_usd / openai_usd)) * Decimal("100")
            ) if openai_usd else None
            comparison["kendr_total_tokens_at_openai_spend"] = (
                decimal_text(
                    Decimal(kendr.usage.total_tokens)
                    * openai_usd
                    / kendr_usd
                )
                if kendr_usd
                else None
            )

        # Cross-apply each provider's rate card to the other provider's token
        # mix. This answers "what would the other provider charge for exactly
        # these reported input/output counts?" without assuming tokenizers are
        # identical.
        openai_card = _record_rate_card(openai)
        if openai_card is not None:
            openai_cost_for_kendr_usage = openai_card.calculate(kendr.usage)
            comparison["openai_cost_for_kendr_token_usage"] = decimal_text(
                openai_cost_for_kendr_usage
            )
            comparison["openai_same_token_cost_currency"] = openai_card.currency

        kendr_card = _record_rate_card(kendr)
        if kendr_card is not None:
            kendr_cost_for_openai_usage = kendr_card.calculate(openai.usage)
            comparison["kendr_cost_for_openai_token_usage"] = decimal_text(
                kendr_cost_for_openai_usage
            )
            comparison["kendr_same_token_cost_currency"] = kendr_card.currency
            usd_per_credit = _decimal(
                str(kendr.provider_metadata.get("usd_per_credit"))
                if kendr.provider_metadata.get("usd_per_credit") is not None
                else None
            )
            if (
                kendr_card.currency == "credits"
                and usd_per_credit is not None
            ):
                comparison[
                    "kendr_cost_for_openai_token_usage_usd"
                ] = decimal_text(kendr_cost_for_openai_usage * usd_per_credit)
        comparisons.append(comparison)

    return {
        "records": len(record_list),
        "providers": providers,
        "paired_comparisons": comparisons,
    }


def _flat_record(record: BenchmarkRecord) -> dict[str, Any]:
    return {
        "run_id": record.run_id,
        "case_id": record.case_id,
        "repeat": record.repeat,
        "provider": record.provider,
        "requested_model": record.requested_model,
        "actual_model": record.actual_model,
        "status": record.status,
        "input": record.input,
        "instructions": record.instructions,
        "output": record.output,
        "input_tokens": record.usage.input_tokens,
        "cached_input_tokens": record.usage.cached_input_tokens,
        "cache_write_input_tokens": record.usage.cache_write_input_tokens,
        "output_tokens": record.usage.output_tokens,
        "reasoning_tokens": record.usage.reasoning_tokens,
        "total_tokens": record.usage.total_tokens,
        "cost_amount": decimal_text(record.cost.amount),
        "cost_currency": record.cost.currency,
        "cost_usd": decimal_text(record.cost.amount_usd),
        "cost_source": record.cost.source,
        "latency_ms": round(record.latency_ms, 3),
        "request_id": record.request_id,
        "started_at": record.started_at,
        "finished_at": record.finished_at,
        "error_type": (record.error or {}).get("type"),
        "error_message": (record.error or {}).get("message"),
    }


def write_artifacts(
    run_dir: Path,
    records: list[BenchmarkRecord],
    manifest: dict[str, Any],
) -> dict[str, Path]:
    run_dir.mkdir(parents=True, exist_ok=False)
    paths = {
        "manifest": run_dir / "manifest.json",
        "records_jsonl": run_dir / "records.jsonl",
        "records_csv": run_dir / "records.csv",
        "summary": run_dir / "summary.json",
        "report": run_dir / "report.md",
    }
    paths["manifest"].write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    with paths["records_jsonl"].open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(
                json.dumps(record.to_dict(), ensure_ascii=False, default=str)
                + "\n"
            )

    flat = [_flat_record(record) for record in records]
    with paths["records_csv"].open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(flat[0]) if flat else [])
        if flat:
            writer.writeheader()
            writer.writerows(flat)

    summary = build_summary(records)
    summary["run_id"] = manifest["run_id"]
    summary["started_at"] = manifest["started_at"]
    paths["summary"].write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    paths["report"].write_text(
        render_markdown_report(summary), encoding="utf-8"
    )
    return paths


def render_markdown_report(summary: dict[str, Any]) -> str:
    lines = [
        f"# Benchmark report: {summary.get('run_id', '')}",
        "",
        "| Provider | Successful | Errors | Input tokens | Output tokens | Cost USD | Credits | Mean latency (ms) |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for provider, value in summary.get("providers", {}).items():
        lines.append(
            f"| {provider} | {value['successful_runs']} | {value['errors']} | "
            f"{value['input_tokens']} | {value['output_tokens']} | "
            f"{value['cost_usd'] or 'n/a'} | {value['credits'] or 'n/a'} | "
            f"{value['mean_latency_ms'] if value['mean_latency_ms'] is not None else 'n/a'} |"
        )
    lines.extend(
        [
            "",
            "## Paired comparisons",
            "",
            "| Case | Repeat | OpenAI tokens | Kendr tokens | OpenAI USD | Kendr USD | Kendr credits |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for value in summary.get("paired_comparisons", []):
        lines.append(
            f"| {value['case_id']} | {value['repeat']} | "
            f"{value['openai_total_tokens']} | {value['kendr_total_tokens']} | "
            f"{value['openai_cost_usd'] or 'n/a'} | "
            f"{value['kendr_cost_usd'] or 'n/a'} | "
            f"{value['kendr_credits'] or 'n/a'} |"
        )
    lines.extend(
        [
            "",
            "USD-normalized comparisons use KendrWeb's default credit conversion unless it is "
            "overridden through `--kendr-usd-per-credit` or `KENDR_USD_PER_CREDIT`.",
            "",
        ]
    )
    return "\n".join(lines)
