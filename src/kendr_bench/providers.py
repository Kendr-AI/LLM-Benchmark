from __future__ import annotations

import time
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Protocol

from .domain import BenchmarkCase, Cost, ProviderResult, Usage, decimal_text
from .pricing import PricingCatalog, RateCard

KENDR_SOURCE_REPOSITORY = "https://github.com/Kendr-AI/Kendr"
KENDR_SOURCE_REVISION = "2a07a08b266f43593d10843ddf213c3ab7b801c5"
KENDR_DEFAULT_USD_PER_CREDIT = Decimal("0.002")


class BenchmarkProvider(Protocol):
    name: str
    model: str

    def generate(
        self,
        case: BenchmarkCase,
        *,
        max_output_tokens: int,
        run_id: str,
        repeat: int,
    ) -> ProviderResult: ...


def _mapping(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        return dict(dump(mode="json"))
    return {}


def _nested(value: Mapping[str, Any], *paths: tuple[str, ...]) -> Any:
    for path in paths:
        current: Any = value
        for part in path:
            if not isinstance(current, Mapping):
                current = None
                break
            current = current.get(part)
        if current is not None:
            return current
    return None


def _decimal_or_none(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


class OpenAIProvider:
    name = "openai"

    def __init__(
        self,
        *,
        model: str,
        pricing: PricingCatalog,
        reasoning_effort: str = "none",
        timeout_seconds: float = 120.0,
        client: Any | None = None,
    ) -> None:
        self.model = model
        self.pricing = pricing
        self.reasoning_effort = reasoning_effort
        if client is None:
            from openai import OpenAI

            client = OpenAI(timeout=timeout_seconds, max_retries=2)
        self.client = client

    def generate(
        self,
        case: BenchmarkCase,
        *,
        max_output_tokens: int,
        run_id: str,
        repeat: int,
    ) -> ProviderResult:
        request: dict[str, Any] = {
            "model": self.model,
            "input": case.input,
            "max_output_tokens": max_output_tokens,
            "reasoning": {"effort": self.reasoning_effort},
            "service_tier": "default",
            "store": False,
            "metadata": {
                "benchmark_run_id": run_id,
                "benchmark_case_id": case.id,
                "benchmark_repeat": str(repeat),
            },
        }
        if case.instructions:
            request["instructions"] = case.instructions

        started = time.perf_counter()
        response = self.client.responses.create(**request)
        latency_ms = (time.perf_counter() - started) * 1000
        usage_raw = _mapping(getattr(response, "usage", None))
        usage = Usage.from_provider(usage_raw)
        actual_model = str(getattr(response, "model", None) or self.model)
        cost = self.pricing.estimate(
            self.name, self.model, actual_model, usage
        )
        return ProviderResult(
            provider=self.name,
            requested_model=self.model,
            actual_model=actual_model,
            output_text=str(getattr(response, "output_text", "") or ""),
            usage=usage,
            cost=cost,
            latency_ms=latency_ms,
            request_id=str(getattr(response, "id", "") or ""),
            metadata={
                "raw_usage": usage_raw,
                "status": getattr(response, "status", None),
                "service_tier": getattr(response, "service_tier", None),
                "incomplete_details": _mapping(
                    getattr(response, "incomplete_details", None)
                ),
            },
        )


class KendrProvider:
    name = "kendr"

    def __init__(
        self,
        *,
        model: str,
        usd_per_credit: Decimal | None = None,
        usd_conversion_source: str = "",
        timeout_seconds: float = 120.0,
        client: Any | None = None,
    ) -> None:
        self.model = model
        self.usd_per_credit = usd_per_credit
        self.usd_conversion_source = usd_conversion_source
        self.timeout_seconds = timeout_seconds
        if client is None:
            try:
                import kendr
            except ImportError as exc:
                raise RuntimeError(
                    "Kendr SDK is not installed. Install the pinned source "
                    'dependency with: python -m pip install -e ".[kendr]"'
                ) from exc
            client = kendr.Client()
        self.client = client
        self._catalog: list[dict[str, Any]] | None = None

    def _models(self) -> list[dict[str, Any]]:
        if self._catalog is None:
            self._catalog = [
                dict(item)
                for item in self.client.list_models()
                if isinstance(item, Mapping)
            ]
        return self._catalog

    def _catalog_model(self, aliases: list[str]) -> dict[str, Any] | None:
        for alias in aliases:
            for model in self._models():
                if str(model.get("alias") or model.get("id") or "") == alias:
                    return model
        return None

    def generate(
        self,
        case: BenchmarkCase,
        *,
        max_output_tokens: int,
        run_id: str,
        repeat: int,
    ) -> ProviderResult:
        # Load the governed catalog before the charged request so the exact
        # rate card visible to this credential is captured.
        self._models()
        started = time.perf_counter()
        response = self.client.create_response(
            model=self.model,
            input=case.input,
            instructions=case.instructions or None,
            max_output_tokens=max_output_tokens,
            web_search=False,
            metadata={
                "benchmark_run_id": run_id,
                "benchmark_case_id": case.id,
                "benchmark_repeat": repeat,
            },
            timeout_seconds=self.timeout_seconds,
        )
        latency_ms = (time.perf_counter() - started) * 1000
        usage_raw = dict(response.usage or {})
        usage = Usage.from_provider(usage_raw)
        raw = dict(response.raw or {})
        kendr_usage = dict(response.kendr_usage or {})
        routing = dict(response.kendr_routing or {})
        optimization = dict(response.kendr_optimization or {})
        selected_alias = str(
            _nested(
                routing,
                ("selected_model_alias",),
                ("selected_alias",),
                ("model_alias",),
            )
            or raw.get("provider_model")
            or response.model
            or self.model
        )
        actual_model = selected_alias
        catalog_model = self._catalog_model(
            [selected_alias, str(response.model or ""), self.model]
        )
        rate_card = (
            RateCard.from_kendr_catalog(catalog_model)
            if catalog_model is not None
            else None
        )

        credit_micros = _decimal_or_none(
            _nested(
                raw,
                ("credit_micros_charged",),
                ("kendr_usage", "credit_micros_charged"),
            )
            or _nested(
                kendr_usage,
                ("credit_micros_charged",),
                ("total_credit_micros",),
            )
        )
        reported_credits = _decimal_or_none(
            _nested(
                raw,
                ("credits_charged",),
                ("kendr_usage", "credits_charged"),
            )
            or _nested(
                kendr_usage,
                ("credits_charged",),
                ("total_credits",),
            )
        )
        if credit_micros is not None:
            credits = credit_micros / Decimal(1_000_000)
            cost_source = "provider_reported_credit_micros"
        elif reported_credits is not None:
            credits = reported_credits
            cost_source = "provider_reported_credits"
        elif rate_card is not None:
            credits = rate_card.calculate(usage)
            cost_source = "estimated_kendr_catalog"
        else:
            credits = None
            cost_source = "unavailable"
        amount_usd = (
            credits * self.usd_per_credit
            if credits is not None and self.usd_per_credit is not None
            else None
        )
        cost = Cost(
            amount=credits,
            currency="credits" if credits is not None else None,
            amount_usd=amount_usd,
            source=cost_source,
            rate_card=rate_card.to_dict() if rate_card else None,
        )

        return ProviderResult(
            provider=self.name,
            requested_model=self.model,
            actual_model=actual_model,
            output_text=response.output_text,
            usage=usage,
            cost=cost,
            latency_ms=latency_ms,
            request_id=str(response.request_id or raw.get("request_id") or ""),
            metadata={
                "raw_usage": usage_raw,
                "kendr_usage": kendr_usage,
                "kendr_routing": routing,
                "kendr_optimization": optimization,
                "catalog_model": catalog_model,
                "credit_micros_charged": decimal_text(credit_micros),
                "usd_per_credit": decimal_text(self.usd_per_credit),
                "usd_conversion_source": self.usd_conversion_source,
                "source_repository": KENDR_SOURCE_REPOSITORY,
                "source_revision": KENDR_SOURCE_REVISION,
            },
        )
