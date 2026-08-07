from __future__ import annotations

import copy
import json
import os
import threading
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

KENDR_LIVEBENCH_CALL_LOG = "KENDR_LIVEBENCH_CALL_LOG"
KENDR_LIVEBENCH_RUN_ID = "KENDR_LIVEBENCH_RUN_ID"
KENDR_LIVEBENCH_USD_PER_CREDIT = "KENDR_LIVEBENCH_USD_PER_CREDIT"
KENDR_LIVEBENCH_SAFE_RETRIES = "KENDR_LIVEBENCH_SAFE_RETRIES"
KENDR_LIVEBENCH_RETRY_OPAQUE_5XX = "KENDR_LIVEBENCH_RETRY_OPAQUE_5XX"
KENDR_OUTPUT_CAP_COMPATIBILITY_PATCH = (
    "kendr-output-cap-field-compatibility-v1"
)
LIVEBENCH_PRICING_PATH = "KENDR_LIVEBENCH_PRICING_PATH"
OPENAI_LIVEBENCH_REASONING_EFFORT = (
    "KENDR_LIVEBENCH_OPENAI_REASONING_EFFORT"
)
KENDR_NO_CREDIT_MESSAGE = "No credits were charged"

_conversation_state = threading.local()
_call_log_lock = threading.Lock()


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        return _json_value(dump(mode="json"))
    return str(value)


def _exception_body(exc: BaseException) -> Mapping[str, Any]:
    body = getattr(exc, "body", None)
    body = _json_value(body)
    if isinstance(body, Mapping):
        return body
    response = getattr(exc, "response", None)
    response_json = getattr(response, "json", None)
    if callable(response_json):
        try:
            body = _json_value(response_json())
        except Exception:
            body = None
        if isinstance(body, Mapping):
            return body
    return {}


def _nested_mapping(
    value: Mapping[str, Any], *paths: tuple[str, ...]
) -> dict[str, Any]:
    for path in paths:
        current: Any = value
        for part in path:
            if not isinstance(current, Mapping):
                current = None
                break
            current = current.get(part)
        if isinstance(current, Mapping):
            return dict(current)
    return {}


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _failed_attempt_usage(details: Mapping[str, Any]) -> dict[str, Any]:
    """Recover provider-reported usage from a rejected Kendr attempt.

    A truncation rejection still generated (and forwarded) tokens. Reporting
    them as zero understates output volume and flatters tokens-per-quality-point
    for whichever endpoint failed.
    """
    attempts = details.get("attempts")
    if not isinstance(attempts, list):
        return {}
    for attempt in reversed(attempts):
        if not isinstance(attempt, Mapping):
            continue
        usage = attempt.get("usage")
        if not isinstance(usage, Mapping):
            continue
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
        if input_tokens is None and output_tokens is None:
            continue
        return {
            "prompt_tokens": int(input_tokens or 0),
            "completion_tokens": int(output_tokens or 0),
            "total_tokens": int(input_tokens or 0) + int(output_tokens or 0),
        }
    return {}


def recovered_call_usage(call: Mapping[str, Any]) -> dict[str, Any]:
    """Usage for a logged call, reconstructed from its failure body if absent.

    Lets ``summarize`` and ``--rebuild`` correct runs captured before failed
    attempts carried usage of their own, since the provider report was always
    preserved inside the persisted error body.
    """
    usage = call.get("usage")
    if isinstance(usage, Mapping) and usage:
        return dict(usage)
    error = call.get("error")
    if not isinstance(error, Mapping):
        return {}
    body = error.get("body")
    if not isinstance(body, Mapping):
        return {}
    return _failed_attempt_usage(
        _nested_mapping(body, ("details",), ("error", "details"))
    )


def _credits_from_usage(usage: Mapping[str, Any]) -> Decimal | None:
    for key in ("credits_charged", "total_credits"):
        credits = _decimal(usage.get(key))
        if credits is not None:
            return credits
    for key in (
        "credits_charged_micros",
        "credit_micros_charged",
        "total_credit_micros",
    ):
        micros = _decimal(usage.get(key))
        if micros is not None:
            return micros / Decimal(1_000_000)
    return None


def _append_call_log(record: Mapping[str, Any]) -> None:
    configured = os.getenv(KENDR_LIVEBENCH_CALL_LOG)
    if not configured:
        return
    path = Path(configured)
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(_json_value(record), ensure_ascii=False)
    with _call_log_lock:
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(serialized)
            handle.write("\n")


def _cumulative_metadata(
    messages: list[dict[str, Any]],
    call: Mapping[str, Any],
    prior_calls: list[Mapping[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], Decimal | None, Decimal | None]:
    # LiveBench invokes one conversation sequentially on one worker thread.
    # A request with no assistant turn starts a new choice/question.
    starts_conversation = not any(
        message.get("role") == "assistant" for message in messages
    )
    if starts_conversation or not hasattr(_conversation_state, "calls"):
        _conversation_state.calls = []
    for prior_call in prior_calls or []:
        _conversation_state.calls.append(copy.deepcopy(dict(prior_call)))
    _conversation_state.calls.append(copy.deepcopy(dict(call)))
    calls = copy.deepcopy(_conversation_state.calls)
    credits = Decimal(0)
    credits_found = False
    cost_usd = Decimal(0)
    cost_found = False
    for item in calls:
        usage = item.get("kendr_usage")
        if isinstance(usage, Mapping):
            item_credits = _credits_from_usage(usage)
            if item_credits is not None:
                credits += item_credits
                credits_found = True
        item_cost = _decimal(item.get("cost_usd"))
        if item_cost is not None:
            cost_usd += item_cost
            cost_found = True
    return (
        calls,
        credits if credits_found else None,
        cost_usd if cost_found else None,
    )


def _int_env(name: str, default: int) -> int:
    try:
        return max(0, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def _truthy_env(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _exception_status_code(exc: BaseException) -> int | None:
    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int):
        return status_code
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    if isinstance(status_code, int):
        return status_code
    return None


def _exception_request_id(
    exc: BaseException, error_body: Mapping[str, Any]
) -> str:
    request_id = getattr(exc, "request_id", None)
    if request_id:
        return str(request_id)

    nested_error = _nested_mapping(error_body, ("error",))
    request_id = error_body.get("request_id") or nested_error.get(
        "request_id"
    )
    if request_id:
        return str(request_id)

    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    get_header = getattr(headers, "get", None)
    if callable(get_header):
        request_id = get_header("x-request-id")
        if request_id:
            return str(request_id)
    return ""


def _exception_messages(
    exc: BaseException, error_body: Mapping[str, Any]
) -> list[str]:
    messages: list[str] = []
    error = error_body.get("error")
    if isinstance(error, Mapping):
        message = error.get("message")
        if isinstance(message, str):
            messages.append(message)
    message = error_body.get("message")
    if isinstance(message, str):
        messages.append(message)
    messages.append(str(exc))
    return messages


def _kendr_retry_reason(
    exc: BaseException, error_body: Mapping[str, Any]
) -> str | None:
    status_code = _exception_status_code(exc)
    messages = _exception_messages(exc, error_body)
    if any(KENDR_NO_CREDIT_MESSAGE in message for message in messages):
        return "no_credits_charged"
    if (
        _truthy_env(KENDR_LIVEBENCH_RETRY_OPAQUE_5XX)
        and status_code in {502, 503, 504}
    ):
        return "opaque_5xx"
    return None


def kendr_chat_completion(
    model: str,
    messages: list[dict[str, Any]],
    temperature: float,
    max_tokens: int,
    model_api_kwargs: dict[str, Any] | None = None,
    api_dict: dict[str, str] | None = None,
    stream: bool = False,
) -> tuple[str, int, dict[str, Any]]:
    """LiveBench completion function for Kendr's OpenAI-compatible endpoint.

    LiveBench's generic client does not send the idempotency header required by
    Kendr chargeable requests and drops provider-specific billing metadata.
    This adapter supplies the header and preserves the exact request, response,
    token, credit, routing, and optimization fields.
    """

    if stream:
        raise ValueError(
            "The Kendr LiveBench adapter currently requires non-streaming calls."
        )
    if api_dict is None or not api_dict.get("api_key"):
        raise ValueError("Kendr LiveBench requires an API key.")
    api_base = api_dict.get("api_base", "")
    if not api_base:
        raise ValueError("Kendr LiveBench requires an API base URL.")

    from openai import OpenAI

    request_kwargs: dict[str, Any] = {"temperature": temperature}
    if model_api_kwargs:
        request_kwargs.update(model_api_kwargs)
    if (
        "max_tokens" not in request_kwargs
        and "max_completion_tokens" not in request_kwargs
    ):
        request_kwargs["max_tokens"] = max_tokens
    request_kwargs = {
        key: value for key, value in request_kwargs.items() if value is not None
    }
    # Kendr's InferenceRequest recognizes `max_output_tokens`, not the
    # OpenAI-compatible `max_tokens`, and silently falls back to its 4,096
    # default. Sending both makes the requested cap bind on either contract, so
    # the panel is actually held to one output budget.
    effective_cap = request_kwargs.get(
        "max_tokens", request_kwargs.get("max_completion_tokens", max_tokens)
    )
    extra_body = dict(request_kwargs.pop("extra_body", None) or {})
    extra_body.setdefault("max_output_tokens", effective_cap)

    client = OpenAI(
        api_key=api_dict["api_key"],
        base_url=api_base,
        timeout=1200,
        # A transport retry reuses the explicit idempotency key while the
        # original request may still be active, which Kendr correctly rejects
        # with HTTP 409. Safe application-level retries use a fresh key below.
        max_retries=0,
    )
    safe_retries = _int_env(KENDR_LIVEBENCH_SAFE_RETRIES, 1)
    prior_calls: list[dict[str, Any]] = []
    attempt_number = 1
    while True:
        idempotency_key = str(uuid4())
        started = time.perf_counter()
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                stream=False,
                extra_headers={"Idempotency-Key": idempotency_key},
                extra_body=extra_body,
                **request_kwargs,
            )
            break
        except Exception as exc:
            latency_ms = (time.perf_counter() - started) * 1000
            error_body = _exception_body(exc)
            # The OpenAI SDK already unwraps the outer "error" envelope, so the
            # live body is flat. Older captures and some proxies keep the
            # envelope, so both shapes are accepted; reading only the nested one
            # silently discarded all failure telemetry.
            error_details = _nested_mapping(
                error_body, ("details",), ("error", "details")
            )
            kendr_routing = _nested_mapping(
                error_body,
                ("kendr_routing",),
                ("error", "kendr_routing"),
            ) or _nested_mapping(error_details, ("kendr_routing",))
            kendr_optimization = _nested_mapping(
                error_body,
                ("kendr_optimization",),
                ("error", "kendr_optimization"),
            ) or _nested_mapping(error_details, ("kendr_optimization",))
            request_id = str(
                getattr(exc, "request_id", None)
                or error_details.get("request_id")
                or _nested_mapping(error_body, ("error",)).get("request_id")
                or error_body.get("request_id")
                or idempotency_key
            )
            retry_reason = _kendr_retry_reason(exc, error_body)
            explicitly_uncharged = retry_reason == "no_credits_charged"
            will_retry = (
                retry_reason is not None and len(prior_calls) < safe_retries
            )
            failed_usage = _failed_attempt_usage(error_details)
            call = {
                "run_id": os.getenv(KENDR_LIVEBENCH_RUN_ID),
                "provider": "kendr",
                "request_id": request_id,
                "requested_model": model,
                "actual_model": None,
                "input_messages": copy.deepcopy(messages),
                "request_parameters": {
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    **copy.deepcopy(request_kwargs),
                    **copy.deepcopy(extra_body),
                },
                "output_text": "$ERROR$",
                "usage": failed_usage,
                "usage_source": (
                    "failed_attempt_provider_report"
                    if failed_usage
                    else "unavailable"
                ),
                "kendr_usage": (
                    {"credits_charged": "0"}
                    if explicitly_uncharged
                    else {}
                ),
                "kendr_credits": "0" if explicitly_uncharged else None,
                "kendr_cost_usd": "0" if explicitly_uncharged else None,
                "cost_usd": "0" if explicitly_uncharged else None,
                "cost_source": (
                    "provider_explicit_no_charge"
                    if explicitly_uncharged
                    else "unavailable_failed_request"
                ),
                "kendr_routing": kendr_routing,
                "kendr_optimization": kendr_optimization,
                "latency_ms": latency_ms,
                "idempotency_key": idempotency_key,
                "timestamp": time.time(),
                "attempt_number": attempt_number,
                "will_retry": will_retry,
                "retry_reason": retry_reason,
                "error": {
                    "type": type(exc).__name__,
                    "message": str(exc),
                    "body": dict(error_body) if error_body else None,
                    "status_code": _exception_status_code(exc),
                },
            }
            _append_call_log(call)
            if will_retry:
                prior_calls.append(call)
                attempt_number += 1
                continue
            calls, _, _ = _cumulative_metadata(
                messages, call, prior_calls=prior_calls
            )
            return (
                "$ERROR$",
                0,
                {
                    "input_tokens": 0,
                    "cached_tokens": 0,
                    "request_messages": copy.deepcopy(messages),
                    "actual_model": None,
                    "benchmark_calls": calls,
                    "kendr_calls": calls,
                    "benchmark_error": call["error"],
                },
            )
    latency_ms = (time.perf_counter() - started) * 1000

    if not response.choices:
        raise RuntimeError("Kendr returned no completion choices.")
    output = response.choices[0].message.content
    if not output:
        raise RuntimeError("Kendr returned an empty completion.")

    usage = _json_value(getattr(response, "usage", None)) or {}
    completion_tokens = int(usage.get("completion_tokens") or 0)
    completion_details = usage.get("completion_tokens_details") or {}
    completion_tokens += int(completion_details.get("reasoning_tokens") or 0)
    input_tokens = int(usage.get("prompt_tokens") or 0)
    prompt_details = usage.get("prompt_tokens_details") or {}
    cached_tokens = int(prompt_details.get("cached_tokens") or 0)

    kendr_usage = _json_value(getattr(response, "kendr_usage", None)) or {}
    credits = _credits_from_usage(kendr_usage)
    usd_per_credit = _decimal(
        os.getenv(KENDR_LIVEBENCH_USD_PER_CREDIT)
    )
    call = {
        "run_id": os.getenv(KENDR_LIVEBENCH_RUN_ID),
        "provider": "kendr",
        "request_id": str(getattr(response, "id", "") or ""),
        "requested_model": model,
        "actual_model": str(getattr(response, "model", "") or model),
        "input_messages": copy.deepcopy(messages),
        "request_parameters": {
            "temperature": temperature,
            "max_tokens": max_tokens,
            **copy.deepcopy(request_kwargs),
            **copy.deepcopy(extra_body),
        },
        "output_text": output,
        "usage": usage,
        "kendr_usage": kendr_usage,
        "kendr_credits": format(credits, "f")
        if credits is not None
        else None,
        "kendr_cost_usd": format(credits * usd_per_credit, "f")
        if credits is not None and usd_per_credit is not None
        else None,
        "cost_usd": format(credits * usd_per_credit, "f")
        if credits is not None and usd_per_credit is not None
        else None,
        "cost_source": "provider_reported_credits",
        "usd_per_credit": format(usd_per_credit, "f")
        if usd_per_credit is not None
        else None,
        "kendr_routing": _json_value(
            getattr(response, "kendr_routing", None)
        )
        or {},
        "kendr_optimization": _json_value(
            getattr(response, "kendr_optimization", None)
        )
        or {},
        "latency_ms": latency_ms,
        "idempotency_key": idempotency_key,
        "timestamp": time.time(),
        "attempt_number": attempt_number,
        "retry_attempt_count": len(prior_calls),
    }
    _append_call_log(call)
    calls, cumulative_credits, cumulative_cost_usd = _cumulative_metadata(
        messages, call, prior_calls=prior_calls
    )

    metadata: dict[str, Any] = {
        "input_tokens": input_tokens,
        "cached_tokens": cached_tokens,
        "request_messages": copy.deepcopy(messages),
        "actual_model": call["actual_model"],
        "benchmark_calls": calls,
        "kendr_calls": calls,
    }
    if cumulative_credits is not None:
        metadata["kendr_credits_charged"] = format(
            cumulative_credits, "f"
        )
    if cumulative_cost_usd is not None:
        metadata["benchmark_cost_usd"] = format(
            cumulative_cost_usd, "f"
        )
    return output, completion_tokens, metadata


def openai_chat_completion(
    model: str,
    messages: list[dict[str, Any]],
    temperature: float,
    max_tokens: int,
    model_api_kwargs: dict[str, Any] | None = None,
    api_dict: dict[str, str] | None = None,
    stream: bool = False,
) -> tuple[str, int, dict[str, Any]]:
    """LiveBench completion function with direct OpenAI usage/cost capture."""

    if stream:
        raise ValueError(
            "The instrumented OpenAI adapter currently requires "
            "non-streaming calls."
        )
    if api_dict is None or not api_dict.get("api_key"):
        raise ValueError("The OpenAI LiveBench adapter requires an API key.")

    from openai import OpenAI

    request_kwargs: dict[str, Any] = {}
    if model_api_kwargs:
        request_kwargs.update(model_api_kwargs)
    if (
        "max_tokens" not in request_kwargs
        and "max_completion_tokens" not in request_kwargs
    ):
        request_kwargs["max_completion_tokens"] = max_tokens
    reasoning_effort = request_kwargs.pop(
        "reasoning_effort",
        os.getenv(OPENAI_LIVEBENCH_REASONING_EFFORT, "none"),
    )
    if reasoning_effort:
        request_kwargs["reasoning_effort"] = reasoning_effort
    # GPT-5.6 supports temperature at effective reasoning effort "none".
    if reasoning_effort == "none" and "temperature" not in request_kwargs:
        request_kwargs["temperature"] = temperature
    request_kwargs = {
        key: value for key, value in request_kwargs.items() if value is not None
    }

    api_base = api_dict.get("api_base") or None
    started = time.perf_counter()
    response: Any | None = None
    try:
        client = OpenAI(
            api_key=api_dict["api_key"],
            base_url=api_base,
            timeout=1200,
            # Hidden SDK retries make raw-attempt reliability and latency
            # incomparable with Kendr. Keep retries at the benchmark layer so
            # every transport attempt can produce its own call-log record.
            max_retries=0,
        )
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            stream=False,
            **request_kwargs,
        )
        if not response.choices:
            raise RuntimeError("OpenAI returned no completion choices.")
        output = response.choices[0].message.content
        if not output:
            raise RuntimeError("OpenAI returned an empty completion.")
    except Exception as exc:
        latency_ms = (time.perf_counter() - started) * 1000
        error_body = _exception_body(exc)
        response_usage = (
            _json_value(getattr(response, "usage", None)) if response else {}
        )
        usage = (
            dict(response_usage)
            if isinstance(response_usage, Mapping)
            else {}
        )
        prompt_details = usage.get("prompt_tokens_details") or {}
        input_tokens = int(usage.get("prompt_tokens") or 0)
        cached_tokens = int(prompt_details.get("cached_tokens") or 0)
        actual_model = (
            str(getattr(response, "model", "") or model)
            if response is not None
            else None
        )
        request_id = (
            str(getattr(response, "id", "") or "")
            if response is not None
            else ""
        ) or _exception_request_id(exc, error_body)
        error = {
            "type": type(exc).__name__,
            "message": str(exc),
            "body": dict(error_body) if error_body else None,
            "status_code": _exception_status_code(exc),
        }
        call = {
            "run_id": os.getenv(KENDR_LIVEBENCH_RUN_ID),
            "provider": "openai",
            "request_id": request_id,
            "requested_model": model,
            "actual_model": actual_model,
            "input_messages": copy.deepcopy(messages),
            "request_parameters": copy.deepcopy(request_kwargs),
            "output_text": "$ERROR$",
            "usage": usage,
            "usage_source": (
                "provider_response" if usage else "unavailable"
            ),
            "cost_usd": None,
            "cost_source": "unavailable_failed_request",
            "rate_card": None,
            "latency_ms": latency_ms,
            "timestamp": time.time(),
            "attempt_number": 1,
            "will_retry": False,
            "retry_reason": None,
            "transport_max_retries": 0,
            "transport_retry_attempt_count": 0,
            "transport_attempt_visibility": (
                "one_logged_call_per_sdk_attempt"
            ),
            "error": error,
        }
        _append_call_log(call)
        calls, _, _ = _cumulative_metadata(messages, call)
        return (
            "$ERROR$",
            0,
            {
                "input_tokens": input_tokens,
                "cached_tokens": cached_tokens,
                "request_messages": copy.deepcopy(messages),
                "actual_model": actual_model,
                "benchmark_calls": calls,
                "benchmark_error": error,
            },
        )
    latency_ms = (time.perf_counter() - started) * 1000

    usage = _json_value(getattr(response, "usage", None)) or {}
    input_tokens = int(usage.get("prompt_tokens") or 0)
    output_tokens = int(usage.get("completion_tokens") or 0)
    prompt_details = usage.get("prompt_tokens_details") or {}
    cached_tokens = int(prompt_details.get("cached_tokens") or 0)
    actual_model = str(getattr(response, "model", "") or model)

    cost_usd: Decimal | None = None
    rate_card: dict[str, Any] | None = None
    pricing_path = os.getenv(LIVEBENCH_PRICING_PATH)
    if pricing_path:
        from .domain import Usage
        from .pricing import PricingCatalog

        catalog = PricingCatalog.load(Path(pricing_path))
        estimated = catalog.estimate(
            "openai",
            model,
            actual_model,
            Usage.from_provider(usage),
        )
        cost_usd = estimated.amount_usd
        rate_card = estimated.rate_card

    call = {
        "run_id": os.getenv(KENDR_LIVEBENCH_RUN_ID),
        "provider": "openai",
        "request_id": str(getattr(response, "id", "") or ""),
        "requested_model": model,
        "actual_model": actual_model,
        "input_messages": copy.deepcopy(messages),
        "request_parameters": copy.deepcopy(request_kwargs),
        "output_text": output,
        "usage": usage,
        "cost_usd": format(cost_usd, "f")
        if cost_usd is not None
        else None,
        "cost_source": "estimated_openai_standard_rate_card"
        if cost_usd is not None
        else "unavailable",
        "rate_card": rate_card,
        "latency_ms": latency_ms,
        "timestamp": time.time(),
        "attempt_number": 1,
        "retry_attempt_count": 0,
        "transport_max_retries": 0,
        "transport_retry_attempt_count": 0,
        "transport_attempt_visibility": "one_logged_call_per_sdk_attempt",
    }
    _append_call_log(call)
    calls, _, cumulative_cost_usd = _cumulative_metadata(messages, call)
    metadata: dict[str, Any] = {
        "input_tokens": input_tokens,
        "cached_tokens": cached_tokens,
        "request_messages": copy.deepcopy(messages),
        "actual_model": actual_model,
        "benchmark_calls": calls,
    }
    if cumulative_cost_usd is not None:
        metadata["benchmark_cost_usd"] = format(
            cumulative_cost_usd, "f"
        )
    return output, output_tokens, metadata
