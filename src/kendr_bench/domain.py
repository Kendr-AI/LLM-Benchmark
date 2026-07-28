from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal
from typing import Any, Mapping


def _read(value: Any, *path: str) -> Any:
    current = value
    for part in path:
        if current is None:
            return None
        if isinstance(current, Mapping):
            current = current.get(part)
        else:
            current = getattr(current, part, None)
    return current


def _first_int(value: Any, paths: tuple[tuple[str, ...], ...]) -> int:
    for path in paths:
        found = _read(value, *path)
        if found is not None:
            try:
                return int(found)
            except (TypeError, ValueError):
                continue
    return 0


def decimal_text(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value, "f")


@dataclass(frozen=True)
class BenchmarkCase:
    id: str
    input: str
    instructions: str = ""
    category: str = "general"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    cached_input_tokens: int = 0
    cache_write_input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    total_tokens: int = 0

    @classmethod
    def from_provider(cls, raw: Any) -> "Usage":
        input_tokens = _first_int(
            raw,
            (
                ("input_tokens",),
                ("prompt_tokens",),
                ("inputTokens",),
                ("promptTokens",),
            ),
        )
        output_tokens = _first_int(
            raw,
            (
                ("output_tokens",),
                ("completion_tokens",),
                ("outputTokens",),
                ("completionTokens",),
            ),
        )
        total_tokens = _first_int(
            raw,
            (("total_tokens",), ("totalTokens",)),
        )
        if not total_tokens:
            total_tokens = input_tokens + output_tokens
        return cls(
            input_tokens=input_tokens,
            cached_input_tokens=_first_int(
                raw,
                (
                    ("input_tokens_details", "cached_tokens"),
                    ("prompt_tokens_details", "cached_tokens"),
                    ("cached_input_tokens",),
                    ("cache_read_input_tokens",),
                ),
            ),
            cache_write_input_tokens=_first_int(
                raw,
                (
                    ("input_tokens_details", "cache_write_tokens"),
                    ("cache_creation_input_tokens",),
                    ("cache_write_input_tokens",),
                ),
            ),
            output_tokens=output_tokens,
            reasoning_tokens=_first_int(
                raw,
                (
                    ("output_tokens_details", "reasoning_tokens"),
                    ("completion_tokens_details", "reasoning_tokens"),
                    ("reasoning_tokens",),
                ),
            ),
            total_tokens=total_tokens,
        )

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass(frozen=True)
class Cost:
    amount: Decimal | None
    currency: str | None
    source: str
    amount_usd: Decimal | None = None
    rate_card: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "amount": decimal_text(self.amount),
            "currency": self.currency,
            "source": self.source,
            "amount_usd": decimal_text(self.amount_usd),
            "rate_card": self.rate_card,
        }


@dataclass(frozen=True)
class ProviderResult:
    provider: str
    requested_model: str
    actual_model: str
    output_text: str
    usage: Usage
    cost: Cost
    latency_ms: float
    request_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BenchmarkRecord:
    run_id: str
    case_id: str
    repeat: int
    provider: str
    requested_model: str
    actual_model: str
    input: str
    instructions: str
    output: str
    usage: Usage
    cost: Cost
    latency_ms: float
    request_id: str
    status: str
    started_at: str
    finished_at: str
    request_parameters: dict[str, Any] = field(default_factory=dict)
    provider_metadata: dict[str, Any] = field(default_factory=dict)
    error: dict[str, str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "case_id": self.case_id,
            "repeat": self.repeat,
            "provider": self.provider,
            "requested_model": self.requested_model,
            "actual_model": self.actual_model,
            "input": self.input,
            "instructions": self.instructions,
            "output": self.output,
            "usage": self.usage.to_dict(),
            "cost": self.cost.to_dict(),
            "latency_ms": round(self.latency_ms, 3),
            "request_id": self.request_id,
            "status": self.status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "request_parameters": self.request_parameters,
            "provider_metadata": self.provider_metadata,
            "error": self.error,
        }

