"""Failure-aware operational metrics for benchmark call telemetry.

The quality scorer works at the question level, while provider telemetry is
written once per API attempt.  A safe retry therefore creates multiple call
rows for one logical request, and a multi-turn benchmark may create multiple
logical requests for one final answer.  This module joins those levels without
assuming that a provider request id survives a retry.

All public functions are pure and accept ordinary ``Mapping`` rows.  Missing
telemetry is never silently converted to zero: conformance is one of
``"pass"``, ``"fail"``, ``"unknown"``, or ``"not_applicable"``.  A known
breach or failure dominates unknown inputs, which is the normal truth table for
an AND predicate.  Thus a failed answer has failed operational goodput even if
its cost was not reported, while an otherwise correct answer with unknown cost
has unknown goodput when a cost budget applies.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Mapping, Sequence

PASS = "pass"
FAIL = "fail"
UNKNOWN = "unknown"
NOT_APPLICABLE = "not_applicable"

_QUESTION_ID_KEYS = (
    "question_id",
    "task_id",
    "case_id",
    "benchmark_case_id",
    "example_id",
)
_LOGICAL_REQUEST_ID_KEYS = (
    "logical_request_id",
    "request_group_id",
    "operation_id",
    "client_request_id",
    "invocation_id",
)
_SUCCESS_STATUSES = {"success", "succeeded", "ok", "completed", "complete"}
_FAILURE_STATUSES = {
    "error",
    "failed",
    "failure",
    "cancelled",
    "canceled",
    "timeout",
    "timed_out",
}
_ERROR_SENTINEL = "$ERROR$"


def _scalar_text(value: Any) -> str | None:
    if value is None or isinstance(value, (Mapping, list, tuple, set)):
        return None
    text = str(value).strip()
    return text or None


def _question_id(row: Mapping[str, Any]) -> str | None:
    for key in _QUESTION_ID_KEYS:
        value = _scalar_text(row.get(key))
        if value is not None:
            return value
    return None


def _nested(value: Any, *path: str) -> Any:
    current = value
    for part in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(part)
    return current


def _canonical(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {
            str(key): _canonical(item)
            for key, item in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    if isinstance(value, set):
        return sorted((_canonical(item) for item in value), key=repr)
    return str(value)


def _message_payload(row: Mapping[str, Any]) -> Any:
    for key in ("input_messages", "request_messages", "messages"):
        if key in row and row.get(key) is not None:
            return row.get(key)
    for key in ("input", "prompt"):
        if key in row and row.get(key) is not None:
            return [{"role": "user", "content": row.get(key)}]
    return None


def _message_fingerprint(row: Mapping[str, Any]) -> str | None:
    payload = _message_payload(row)
    if payload is None:
        return None
    encoded = json.dumps(
        _canonical(payload),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _request_context(row: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        _scalar_text(row.get("run_id")) or "",
        _scalar_text(row.get("provider")) or "",
        _scalar_text(row.get("requested_model") or row.get("model")) or "",
    )


def _identity_value(row: Mapping[str, Any], key: str) -> str | None:
    value = _scalar_text(row.get(key))
    if value is None:
        return None
    return "\x1f".join((*_request_context(row), key, value))


def _answer_call_rows(answer: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    api_info = answer.get("api_info")
    containers: list[Mapping[str, Any]] = []
    if isinstance(api_info, Mapping):
        containers.append(api_info)
    containers.append(answer)
    for container in containers:
        # benchmark_calls is provider-neutral and kendr_calls is its legacy
        # alias.  Prefer one rather than counting the duplicated list twice.
        for key in ("benchmark_calls", "kendr_calls", "calls"):
            rows = container.get(key)
            if isinstance(rows, (list, tuple)):
                return [row for row in rows if isinstance(row, Mapping)]
    return []


def _unique_lookup(
    values: Mapping[str, set[str]], key: str | None
) -> str | None:
    if key is None:
        return None
    matches = values.get(key, set())
    return next(iter(matches)) if len(matches) == 1 else None


def _call_question_ids(
    calls: Sequence[Mapping[str, Any]],
    answers: Sequence[Mapping[str, Any]],
) -> list[str | None]:
    """Associate call rows with answer questions using strongest evidence first."""

    request_ids: dict[str, set[str]] = defaultdict(set)
    idempotency_keys: dict[str, set[str]] = defaultdict(set)
    logical_ids: dict[str, set[str]] = defaultdict(set)
    fingerprints: dict[tuple[tuple[str, str, str], str], set[str]] = defaultdict(set)

    for answer in answers:
        question_id = _question_id(answer)
        if question_id is None:
            continue
        embedded = _answer_call_rows(answer)
        for row in embedded:
            request_id = _scalar_text(row.get("request_id"))
            if request_id is not None:
                request_ids[request_id].add(question_id)
            idempotency_key = _scalar_text(row.get("idempotency_key"))
            if idempotency_key is not None:
                idempotency_keys[idempotency_key].add(question_id)
            for key in _LOGICAL_REQUEST_ID_KEYS:
                logical_id = _identity_value(row, key)
                if logical_id is not None:
                    logical_ids[logical_id].add(question_id)
            fingerprint = _message_fingerprint(row)
            if fingerprint is not None:
                fingerprints[(_request_context(row), fingerprint)].add(question_id)

        # Older answer artifacts may preserve only request_messages.
        if not embedded:
            api_info = answer.get("api_info")
            if isinstance(api_info, Mapping):
                fingerprint = _message_fingerprint(api_info)
                if fingerprint is not None:
                    context = _request_context(api_info)
                    fingerprints[(context, fingerprint)].add(question_id)

    associated: list[str | None] = []
    for call in calls:
        direct = _question_id(call)
        if direct is not None:
            associated.append(direct)
            continue

        request_match = _unique_lookup(
            request_ids, _scalar_text(call.get("request_id"))
        )
        if request_match is not None:
            associated.append(request_match)
            continue
        idempotency_match = _unique_lookup(
            idempotency_keys, _scalar_text(call.get("idempotency_key"))
        )
        if idempotency_match is not None:
            associated.append(idempotency_match)
            continue

        logical_match = None
        for key in _LOGICAL_REQUEST_ID_KEYS:
            logical_match = _unique_lookup(logical_ids, _identity_value(call, key))
            if logical_match is not None:
                break
        if logical_match is not None:
            associated.append(logical_match)
            continue

        fingerprint = _message_fingerprint(call)
        fingerprint_match = _unique_lookup(
            fingerprints,
            (_request_context(call), fingerprint) if fingerprint is not None else None,
        )
        # Some embedded legacy rows omitted run/provider/model.  Fall back only
        # when the message itself identifies exactly one answer.
        if fingerprint_match is None and fingerprint is not None:
            candidates: set[str] = set()
            for (_, known_fingerprint), question_ids in fingerprints.items():
                if known_fingerprint == fingerprint:
                    candidates.update(question_ids)
            if len(candidates) == 1:
                fingerprint_match = next(iter(candidates))
        associated.append(fingerprint_match)
    return associated


def _integer(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if number >= 0 else None


class _DisjointSet:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))

    def find(self, item: int) -> int:
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, left: int, right: int) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def group_call_attempts(
    calls: Iterable[Mapping[str, Any]],
    *,
    answers: Iterable[Mapping[str, Any]] = (),
) -> list[dict[str, Any]]:
    """Group raw API attempts into logical requests.

    Explicit logical request ids and repeated idempotency keys are strongest.
    Fresh-key application retries are joined by retry metadata plus an exact,
    canonical message fingerprint.  Identical successful calls with no retry
    evidence remain separate, which avoids collapsing repeated generations.

    The returned attempt rows are shallow copies, and the input rows are never
    modified.  ``reported_attempt_count`` can exceed ``attempt_count`` when a
    terminal row says that earlier retries existed but those rows are absent.
    """

    call_rows = [dict(row) for row in calls]
    answer_rows = [dict(row) for row in answers]
    if not call_rows:
        return []

    associated_questions = _call_question_ids(call_rows, answer_rows)
    groups = _DisjointSet(len(call_rows))

    explicit: dict[str, int] = {}
    idempotency: dict[str, int] = {}
    for index, call in enumerate(call_rows):
        for key in _LOGICAL_REQUEST_ID_KEYS:
            identity = _identity_value(call, key)
            if identity is None:
                continue
            if identity in explicit:
                groups.union(explicit[identity], index)
            else:
                explicit[identity] = index
            break

        idempotency_key = _identity_value(call, "idempotency_key")
        if idempotency_key is not None:
            if idempotency_key in idempotency:
                groups.union(idempotency[idempotency_key], index)
            else:
                idempotency[idempotency_key] = index

    # Retry chains are sequential within a message identity even if unrelated
    # calls complete concurrently.  A chain stays open only when the previous
    # row explicitly promised a retry.
    open_retry: dict[tuple[Any, ...], int] = {}
    previous_for_base: dict[tuple[Any, ...], int] = {}
    for index, call in enumerate(call_rows):
        fingerprint = _message_fingerprint(call)
        if fingerprint is None:
            continue
        base = (*_request_context(call), associated_questions[index], fingerprint)
        attempt_number = _integer(call.get("attempt_number"))
        retry_count = _integer(call.get("retry_attempt_count"))
        continuation = bool(
            (attempt_number is not None and attempt_number > 1)
            or (retry_count is not None and retry_count > 0)
        )
        candidate = open_retry.get(base)
        if candidate is None and continuation:
            previous = previous_for_base.get(base)
            if previous is not None:
                previous_number = _integer(call_rows[previous].get("attempt_number"))
                if (
                    previous_number is None
                    or attempt_number is None
                    or attempt_number == previous_number + 1
                ):
                    candidate = previous
        if candidate is not None and (
            continuation or call_rows[candidate].get("will_retry") is True
        ):
            groups.union(candidate, index)

        if call.get("will_retry") is True:
            open_retry[base] = index
        else:
            open_retry.pop(base, None)
        previous_for_base[base] = index

    members: dict[int, list[int]] = defaultdict(list)
    for index in range(len(call_rows)):
        members[groups.find(index)].append(index)

    result: list[dict[str, Any]] = []
    seed_counts: dict[str, int] = defaultdict(int)
    for indexes in sorted(members.values(), key=lambda values: values[0]):
        component = [call_rows[index] for index in indexes]
        question_candidates = {
            associated_questions[index]
            for index in indexes
            if associated_questions[index] is not None
        }
        question_id = (
            next(iter(question_candidates))
            if len(question_candidates) == 1
            else None
        )

        explicit_keys = [
            (key, _identity_value(call, key))
            for call in component
            for key in _LOGICAL_REQUEST_ID_KEYS
            if _identity_value(call, key) is not None
        ]
        idempotency_values = {
            _identity_value(call, "idempotency_key") for call in component
        }
        idempotency_values.discard(None)
        if explicit_keys:
            identity_source = explicit_keys[0][0]
            identity_seed = explicit_keys[0][1] or ""
        elif len(component) > 1 and len(idempotency_values) == 1:
            identity_source = "idempotency_key"
            identity_seed = next(iter(idempotency_values)) or ""
        elif len(component) > 1:
            identity_source = "retry_metadata_and_message"
            identity_seed = _message_fingerprint(component[0]) or str(indexes[0])
        else:
            identity_source = "single_attempt"
            identity_seed = "\x1f".join(
                (
                    _scalar_text(component[0].get("request_id")) or "",
                    _message_fingerprint(component[0]) or "",
                    str(indexes[0]),
                )
            )
        seed_counts[identity_seed] += 1
        digest = hashlib.sha256(identity_seed.encode("utf-8")).hexdigest()[:16]
        logical_request_id = f"request-{digest}-{seed_counts[identity_seed]}"

        reported_counts = [len(component)]
        for call in component:
            attempt_number = _integer(call.get("attempt_number"))
            retry_count = _integer(call.get("retry_attempt_count"))
            if attempt_number is not None:
                reported_counts.append(attempt_number)
            if retry_count is not None:
                reported_counts.append(retry_count + 1)
        reported_attempt_count = max(reported_counts)
        result.append(
            {
                "logical_request_id": logical_request_id,
                "question_id": question_id,
                "question_id_candidates": sorted(question_candidates),
                "identity_source": identity_source,
                "attempt_indexes": indexes,
                "request_ids": [
                    _scalar_text(call.get("request_id")) for call in component
                ],
                "attempt_count": len(component),
                "reported_attempt_count": reported_attempt_count,
                "missing_attempt_count": reported_attempt_count - len(component),
                "retry_count": max(0, reported_attempt_count - 1),
                "attempts": component,
            }
        )
    return result


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(number) or number < 0:
        return None
    return number


def _decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not number.is_finite() or number < 0:
        return None
    return number


def _latency_ms(call: Mapping[str, Any]) -> float | None:
    for value in (
        call.get("latency_ms"),
        call.get("duration_ms"),
        _nested(call, "timing", "latency_ms"),
    ):
        parsed = _number(value)
        if parsed is not None:
            return parsed
    seconds = _number(call.get("latency_s") or call.get("duration_s"))
    return seconds * 1000 if seconds is not None else None


def _timestamp_ms(call: Mapping[str, Any]) -> float | None:
    """Return a completion timestamp in milliseconds when telemetry has one."""
    for key in ("timestamp", "tstamp", "completed_at", "ended_at"):
        parsed = _number(call.get(key))
        if parsed is None:
            continue
        # Unix seconds are currently around 1e9; millisecond epochs are 1e12.
        return parsed if parsed >= 100_000_000_000 else parsed * 1000
    return None


def _wall_clock_span_ms(
    attempts: Sequence[Mapping[str, Any]],
) -> float | None:
    """Elapsed first-start to final-completion, including retry/backoff gaps."""
    intervals: list[tuple[float, float]] = []
    for attempt in attempts:
        latency = _latency_ms(attempt)
        ended = _timestamp_ms(attempt)
        if latency is None or ended is None:
            return None
        intervals.append((ended - latency, ended))
    if not intervals:
        return None
    return max(end for _, end in intervals) - min(
        start for start, _ in intervals
    )


def _cost_usd(call: Mapping[str, Any]) -> Decimal | None:
    if call.get("retry_reason") == "no_credits_charged":
        return Decimal(0)
    for value in (
        call.get("cost_usd"),
        call.get("kendr_cost_usd"),
        _nested(call, "cost", "amount_usd"),
        _nested(call, "provider_metadata", "cost_usd"),
    ):
        parsed = _decimal(value)
        if parsed is not None:
            return parsed
    cost = call.get("cost")
    if isinstance(cost, Mapping):
        currency = str(cost.get("currency") or "").upper()
        if currency == "USD":
            parsed = _decimal(cost.get("amount"))
            if parsed is not None:
                return parsed

    # This retry reason is explicit provider evidence of a zero-dollar failed
    # attempt.  A generic missing cost on a failure remains unknown.
    if str(call.get("retry_reason") or "").lower() == "no_credits_charged":
        return Decimal(0)
    return None


def _usage_mappings(call: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    mappings: list[Mapping[str, Any]] = []
    for candidate in (
        call.get("usage"),
        call.get("kendr_usage"),
        _nested(call, "provider_metadata", "usage"),
    ):
        if isinstance(candidate, Mapping):
            mappings.append(candidate)

    attempts = _nested(call, "error", "body", "details", "attempts")
    if not isinstance(attempts, (list, tuple)):
        attempts = _nested(call, "error", "body", "error", "details", "attempts")
    if isinstance(attempts, (list, tuple)):
        for attempt in reversed(attempts):
            usage = attempt.get("usage") if isinstance(attempt, Mapping) else None
            if isinstance(usage, Mapping):
                mappings.append(usage)
    return mappings


def _output_tokens(call: Mapping[str, Any]) -> int | None:
    for usage in _usage_mappings(call):
        for key in (
            "completion_tokens",
            "output_tokens",
            "completionTokens",
            "outputTokens",
        ):
            if key in usage:
                return _integer(usage.get(key))
    for key in ("output_tokens", "completion_tokens"):
        if key in call:
            return _integer(call.get(key))
    return None


def _requested_cap(call: Mapping[str, Any]) -> int | None:
    parameters = call.get("request_parameters")
    containers = [parameters, call]
    if isinstance(parameters, Mapping):
        extra_body = parameters.get("extra_body")
        if isinstance(extra_body, Mapping):
            containers.insert(0, extra_body)
    for container in containers:
        if not isinstance(container, Mapping):
            continue
        for key in (
            "max_output_tokens",
            "max_completion_tokens",
            "max_tokens",
            "requested_max_output_tokens",
        ):
            if key in container:
                cap = _integer(container.get(key))
                if cap is not None:
                    return cap
    return None


def _attempt_success(call: Mapping[str, Any]) -> bool | None:
    if call.get("error"):
        return False
    status = str(call.get("status") or "").strip().lower()
    if status in _FAILURE_STATUSES:
        return False
    if status in _SUCCESS_STATUSES:
        return True
    for key in ("output_text", "output"):
        if key not in call:
            continue
        output = call.get(key)
        if output == _ERROR_SENTINEL:
            return False
        if output is not None and str(output) != "":
            return True
    return None


def _answer_success(answer: Mapping[str, Any]) -> bool | None:
    if answer.get("error"):
        return False
    status = str(answer.get("status") or "").strip().lower()
    if status in _FAILURE_STATUSES:
        return False
    if status in _SUCCESS_STATUSES:
        return True
    found_turn = False
    for choice in answer.get("choices") or []:
        if not isinstance(choice, Mapping):
            continue
        turns = choice.get("turns") or []
        for turn in turns:
            found_turn = True
            if turn == _ERROR_SENTINEL:
                return False
    return True if found_turn else None


def _percentile(values: Sequence[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * fraction
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def distribution_stats(values: Iterable[float]) -> dict[str, float | int | None]:
    """Return deterministic linear-interpolated distribution statistics."""

    measured = [float(value) for value in values]
    return {
        "count": len(measured),
        "minimum": min(measured) if measured else None,
        "mean": sum(measured) / len(measured) if measured else None,
        "p50": _percentile(measured, 0.50),
        "p95": _percentile(measured, 0.95),
        "p99": _percentile(measured, 0.99),
        "maximum": max(measured) if measured else None,
    }


def _resolve_limit(value: Any, question_id: str) -> Any:
    if not isinstance(value, Mapping):
        return value
    if question_id in value:
        return value[question_id]
    for default_key in ("*", "__default__", "default"):
        if default_key in value:
            return value[default_key]
    return None


def _limit_result(
    *,
    observed: float | None,
    limit: float | None,
    complete: bool,
    applicable: bool,
) -> str:
    if not applicable:
        return NOT_APPLICABLE
    if limit is None or observed is None:
        return UNKNOWN
    if observed > limit:
        return FAIL
    return PASS if complete else UNKNOWN


def _conjunction(states: Iterable[str | bool | None]) -> str:
    normalized: list[str] = []
    for state in states:
        if state is True:
            normalized.append(PASS)
        elif state is False:
            normalized.append(FAIL)
        elif state is None:
            normalized.append(UNKNOWN)
        elif state != NOT_APPLICABLE:
            normalized.append(str(state))
    if any(state == FAIL for state in normalized):
        return FAIL
    if normalized and all(state == PASS for state in normalized):
        return PASS
    return UNKNOWN


def _state_summary(states: Iterable[str]) -> dict[str, int | float | None]:
    values = list(states)
    passed = values.count(PASS)
    failed = values.count(FAIL)
    unknown = values.count(UNKNOWN)
    not_applicable = values.count(NOT_APPLICABLE)
    measured = passed + failed
    applicable = measured + unknown
    return {
        "pass": passed,
        "fail": failed,
        "unknown": unknown,
        "not_applicable": not_applicable,
        "measured_rate": passed / measured if measured else None,
        "conservative_rate": passed / applicable if applicable else None,
    }


def _score_by_question(
    judgments: Sequence[Mapping[str, Any]],
    answers_by_question: Mapping[str, list[Mapping[str, Any]]],
) -> dict[str, float]:
    scores: dict[str, list[float]] = defaultdict(list)
    for judgment in judgments:
        question_id = _question_id(judgment)
        value = judgment.get("score")
        if question_id is None or value in (None, -1):
            continue
        parsed = _number(value)
        if parsed is not None and parsed <= 1:
            scores[question_id].append(parsed)
    for question_id, answers in answers_by_question.items():
        if scores.get(question_id):
            continue
        for answer in answers:
            value = answer.get("score")
            if value in (None, -1):
                continue
            parsed = _number(value)
            if parsed is not None and parsed <= 1:
                scores[question_id].append(parsed)
    return {
        question_id: sum(values) / len(values)
        for question_id, values in scores.items()
        if values
    }


def _group_observations(group: Mapping[str, Any]) -> dict[str, Any]:
    attempts = [
        attempt
        for attempt in group.get("attempts") or []
        if isinstance(attempt, Mapping)
    ]
    latencies = [_latency_ms(attempt) for attempt in attempts]
    costs = [_cost_usd(attempt) for attempt in attempts]
    latency_known = all(value is not None for value in latencies)
    cost_known = all(value is not None for value in costs)
    history_complete = int(group.get("missing_attempt_count") or 0) == 0
    summed_attempt_latency = sum(value or 0 for value in latencies)
    wall_clock_span = _wall_clock_span_ms(attempts)
    # Timestamp precision can make a sequential span microscopically shorter
    # than the sum. Taking the maximum captures explicit backoff/queue gaps
    # without understating provider service time.
    observed_latency = max(
        summed_attempt_latency, wall_clock_span or 0
    )
    observed_cost = sum((value or Decimal(0) for value in costs), Decimal(0))
    final = attempts[-1] if attempts else None
    return {
        "observed_latency_ms": observed_latency if attempts else None,
        "cumulative_latency_ms": (
            observed_latency
            if attempts and latency_known and history_complete
            else None
        ),
        "latency_complete": latency_known and history_complete,
        "summed_attempt_latency_ms": (
            summed_attempt_latency if attempts else None
        ),
        "wall_clock_span_ms": wall_clock_span,
        "latency_basis": (
            "wall_clock_span_including_gaps"
            if wall_clock_span is not None
            and wall_clock_span > summed_attempt_latency
            else "summed_attempt_latency"
        )
        if attempts
        else "unavailable",
        "final_attempt_latency_ms": _latency_ms(final) if final else None,
        "observed_cost_usd": observed_cost if attempts else None,
        "cumulative_cost_usd": (
            observed_cost if attempts and cost_known and history_complete else None
        ),
        "cost_complete": cost_known and history_complete,
        "final_attempt_cost_usd": _cost_usd(final) if final else None,
        "successful": _attempt_success(final) if final else None,
    }


def compute_operational_metrics(
    calls: Iterable[Mapping[str, Any]],
    *,
    answers: Iterable[Mapping[str, Any]] = (),
    judgments: Iterable[Mapping[str, Any]] = (),
    planned_question_ids: Iterable[str] = (),
    deadline_ms: float | Mapping[str, float] | None = None,
    budget_usd: Decimal | float | str | Mapping[str, Any] | None = None,
    output_cap_tokens: int | Mapping[str, int] | None = None,
    correct_threshold: float = 1.0,
) -> dict[str, Any]:
    """Compute operational metrics over attempts, requests, and questions.

    ``deadline_ms`` and ``budget_usd`` are per-final-answer limits, either a
    scalar or a question-id mapping.  ``output_cap_tokens`` is checked against
    every attempt; when omitted, each attempt's request parameters are used.
    Limits are inclusive.  Cost, latency, and tokens from failed retries count.

    When ``planned_question_ids`` is non-empty it is the immutable denominator
    for goodput.  Missing planned questions are failures.  Otherwise the
    denominator is discovered from answers and associated call groups.
    """

    threshold = _number(correct_threshold)
    if threshold is None or threshold > 1:
        raise ValueError("correct_threshold must be between 0 and 1")

    call_rows = [dict(row) for row in calls]
    answer_rows = [dict(row) for row in answers]
    judgment_rows = [dict(row) for row in judgments]
    groups = group_call_attempts(call_rows, answers=answer_rows)
    group_observations = [_group_observations(group) for group in groups]

    answers_by_question: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for answer in answer_rows:
        question_id = _question_id(answer)
        if question_id is not None:
            answers_by_question[question_id].append(answer)

    groups_by_question: dict[str, list[int]] = defaultdict(list)
    for index, group in enumerate(groups):
        question_id = _scalar_text(group.get("question_id"))
        if question_id is not None:
            groups_by_question[question_id].append(index)

    planned = list(dict.fromkeys(str(value) for value in planned_question_ids))
    discovered = list(
        dict.fromkeys(
            [*answers_by_question.keys(), *groups_by_question.keys()]
        )
    )
    question_ids = planned if planned else discovered
    question_set = set(question_ids)
    scores = _score_by_question(judgment_rows, answers_by_question)

    question_results: list[dict[str, Any]] = []
    attempt_cap_states: list[str] = []
    for question_id in question_ids:
        group_indexes = groups_by_question.get(question_id, [])
        question_groups = [groups[index] for index in group_indexes]
        observations = [group_observations[index] for index in group_indexes]
        attempts = [
            attempt
            for group in question_groups
            for attempt in group.get("attempts") or []
            if isinstance(attempt, Mapping)
        ]

        summed_group_latency = (
            sum(float(item["observed_latency_ms"] or 0) for item in observations)
            if observations
            else None
        )
        question_wall_clock_span = _wall_clock_span_ms(attempts)
        observed_latency = (
            max(summed_group_latency, question_wall_clock_span or 0)
            if summed_group_latency is not None
            else None
        )
        latency_complete = bool(observations) and all(
            bool(item["latency_complete"]) for item in observations
        )
        cumulative_latency = observed_latency if latency_complete else None

        observed_cost_decimal = (
            sum(
                (item["observed_cost_usd"] or Decimal(0) for item in observations),
                Decimal(0),
            )
            if observations
            else None
        )
        cost_complete = bool(observations) and all(
            bool(item["cost_complete"]) for item in observations
        )
        cumulative_cost_decimal = (
            observed_cost_decimal if cost_complete else None
        )

        answer_statuses = [
            _answer_success(answer)
            for answer in answers_by_question.get(question_id, [])
        ]
        if answer_statuses:
            successful = answer_statuses[-1]
        elif observations:
            successful = observations[-1]["successful"]
        else:
            # The planned denominator makes an absent terminal result a known
            # availability failure rather than a silently omitted unknown.
            successful = False if planned else None

        score = scores.get(question_id)
        if successful is False:
            score = 0.0
        correct = score >= threshold if score is not None else None

        deadline_value = _number(_resolve_limit(deadline_ms, question_id))
        deadline_applicable = _resolve_limit(deadline_ms, question_id) is not None
        deadline_status = _limit_result(
            observed=observed_latency,
            limit=deadline_value,
            complete=latency_complete,
            applicable=deadline_applicable,
        )

        raw_budget = _resolve_limit(budget_usd, question_id)
        budget_value = _decimal(raw_budget)
        budget_applicable = raw_budget is not None
        budget_status = _limit_result(
            observed=(
                float(observed_cost_decimal)
                if observed_cost_decimal is not None
                else None
            ),
            limit=float(budget_value) if budget_value is not None else None,
            complete=cost_complete,
            applicable=budget_applicable,
        )

        raw_global_cap = _resolve_limit(output_cap_tokens, question_id)
        explicit_cap = output_cap_tokens is not None and raw_global_cap is not None
        global_cap = _integer(raw_global_cap)
        cap_pairs: list[tuple[int | None, int | None]] = []
        for attempt in attempts:
            cap = global_cap if explicit_cap else _requested_cap(attempt)
            cap_pairs.append((_output_tokens(attempt), cap))
        cap_applicable = explicit_cap or any(cap is not None for _, cap in cap_pairs)
        if not cap_applicable:
            cap_status = NOT_APPLICABLE
        elif any(
            output is not None and cap is not None and output > cap
            for output, cap in cap_pairs
        ):
            cap_status = FAIL
        elif cap_pairs and all(
            output is not None and cap is not None for output, cap in cap_pairs
        ):
            cap_status = PASS
        else:
            cap_status = UNKNOWN
        constraint_states = [deadline_status, budget_status, cap_status]
        goodput_status = _conjunction(
            [correct, successful, *constraint_states]
        )
        operational_eligibility = _conjunction(
            [successful, *constraint_states]
        )
        if operational_eligibility == FAIL:
            weighted_goodput: float | None = 0.0
        elif operational_eligibility == PASS and score is not None:
            weighted_goodput = score
        else:
            weighted_goodput = None

        cap_limits = sorted({cap for _, cap in cap_pairs if cap is not None})
        question_results.append(
            {
                "question_id": question_id,
                "logical_request_count": len(question_groups),
                "attempt_count": len(attempts),
                "reported_attempt_count": sum(
                    int(group.get("reported_attempt_count") or 0)
                    for group in question_groups
                ),
                "retry_count": sum(
                    int(group.get("retry_count") or 0) for group in question_groups
                ),
                "successful": successful,
                "objective_score": score,
                "correct_threshold": threshold,
                "correct": correct,
                "observed_cumulative_latency_ms": observed_latency,
                "cumulative_latency_ms": cumulative_latency,
                "latency_complete": latency_complete,
                "summed_logical_request_latency_ms": summed_group_latency,
                "wall_clock_span_ms": question_wall_clock_span,
                "latency_basis": (
                    "wall_clock_span_including_gaps"
                    if question_wall_clock_span is not None
                    and summed_group_latency is not None
                    and question_wall_clock_span > summed_group_latency
                    else "summed_logical_request_latency"
                )
                if observations
                else "unavailable",
                "observed_cumulative_cost_usd": (
                    format(observed_cost_decimal, "f")
                    if observed_cost_decimal is not None
                    else None
                ),
                "cumulative_cost_usd": (
                    format(cumulative_cost_decimal, "f")
                    if cumulative_cost_decimal is not None
                    else None
                ),
                "cost_complete": cost_complete,
                "deadline": {
                    "status": deadline_status,
                    "limit_ms": deadline_value,
                },
                "budget": {
                    "status": budget_status,
                    "limit_usd": (
                        format(budget_value, "f")
                        if budget_value is not None
                        else None
                    ),
                },
                "output_cap": {
                    "status": cap_status,
                    "limits_tokens": cap_limits,
                    "maximum_observed_output_tokens": max(
                        (output for output, _ in cap_pairs if output is not None),
                        default=None,
                    ),
                    "measured_attempts": sum(
                        output is not None and cap is not None
                        for output, cap in cap_pairs
                    ),
                },
                "operational_goodput": goodput_status,
                "score_weighted_goodput": weighted_goodput,
            }
        )

    # Attempt-level cap reporting covers every captured call, including
    # unexpected or unassigned telemetry that is intentionally outside a
    # frozen planned-question denominator.
    for group in groups:
        question_id = _scalar_text(group.get("question_id")) or ""
        raw_global_cap = _resolve_limit(output_cap_tokens, question_id)
        explicit_cap = output_cap_tokens is not None and raw_global_cap is not None
        global_cap = _integer(raw_global_cap)
        for attempt in group.get("attempts") or []:
            if not isinstance(attempt, Mapping):
                continue
            cap = global_cap if explicit_cap else _requested_cap(attempt)
            output = _output_tokens(attempt)
            if cap is None:
                attempt_cap_states.append(
                    UNKNOWN if explicit_cap else NOT_APPLICABLE
                )
            elif output is None:
                attempt_cap_states.append(UNKNOWN)
            elif output > cap:
                attempt_cap_states.append(FAIL)
            else:
                attempt_cap_states.append(PASS)

    attempt_latencies = [
        latency for call in call_rows if (latency := _latency_ms(call)) is not None
    ]
    request_cumulative_latencies = [
        float(item["cumulative_latency_ms"])
        for item in group_observations
        if item["cumulative_latency_ms"] is not None
    ]
    request_observed_latencies = [
        float(item["observed_latency_ms"])
        for item in group_observations
        if item["observed_latency_ms"] is not None
    ]
    final_attempt_latencies = [
        float(item["final_attempt_latency_ms"])
        for item in group_observations
        if item["final_attempt_latency_ms"] is not None
    ]
    question_latencies = [
        float(item["cumulative_latency_ms"])
        for item in question_results
        if item["cumulative_latency_ms"] is not None
    ]
    question_observed_latencies = [
        float(item["observed_cumulative_latency_ms"])
        for item in question_results
        if item["observed_cumulative_latency_ms"] is not None
    ]

    reported_attempts = sum(
        int(group.get("reported_attempt_count") or 0) for group in groups
    )
    retried_requests = sum(
        int(group.get("reported_attempt_count") or 0) > 1 for group in groups
    )
    complete_latency_pairs = [
        (
            float(item["cumulative_latency_ms"]),
            float(item["final_attempt_latency_ms"]),
        )
        for item in group_observations
        if item["cumulative_latency_ms"] is not None
        and item["final_attempt_latency_ms"] is not None
    ]
    latency_numerator = sum(left for left, _ in complete_latency_pairs)
    latency_denominator = sum(right for _, right in complete_latency_pairs)

    complete_cost_pairs = [
        (item["cumulative_cost_usd"], item["final_attempt_cost_usd"])
        for item in group_observations
        if item["cumulative_cost_usd"] is not None
        and item["final_attempt_cost_usd"] is not None
    ]
    cost_numerator = sum(
        (left for left, _ in complete_cost_pairs), Decimal(0)
    )
    cost_denominator = sum(
        (right for _, right in complete_cost_pairs), Decimal(0)
    )

    goodput_summary = _state_summary(
        item["operational_goodput"] for item in question_results
    )
    # Goodput is always applicable, so expose denominator language directly.
    goodput_summary["denominator"] = len(question_results)
    goodput_summary["conservative_rate"] = (
        int(goodput_summary["pass"]) / len(question_results)
        if question_results
        else None
    )
    weighted_values = [
        item["score_weighted_goodput"] for item in question_results
    ]
    known_weighted = [float(value) for value in weighted_values if value is not None]

    return {
        "schema_version": 1,
        "attempts": {
            "count": len(call_rows),
            "latency_ms": distribution_stats(attempt_latencies),
            "latency_unknown": len(call_rows) - len(attempt_latencies),
        },
        "logical_requests": {
            "count": len(groups),
            "cumulative_latency_ms": distribution_stats(
                request_cumulative_latencies
            ),
            "observed_latency_lower_bound_ms": distribution_stats(
                request_observed_latencies
            ),
            "final_attempt_latency_ms": distribution_stats(
                final_attempt_latencies
            ),
            "latency_unknown": len(groups) - len(request_cumulative_latencies),
        },
        "questions": {
            "count": len(question_results),
            "denominator_source": "planned" if planned else "discovered",
            "cumulative_final_answer_latency_ms": distribution_stats(
                question_latencies
            ),
            "observed_latency_lower_bound_ms": distribution_stats(
                question_observed_latencies
            ),
            "latency_unknown": len(question_results) - len(question_latencies),
        },
        "retries": {
            "observed_extra_attempts": max(0, len(call_rows) - len(groups)),
            "reported_extra_attempts": max(0, reported_attempts - len(groups)),
            "missing_attempts": max(0, reported_attempts - len(call_rows)),
            "retried_logical_requests": retried_requests,
            "logical_request_retry_rate": (
                retried_requests / len(groups) if groups else None
            ),
            "observed_attempt_amplification": (
                len(call_rows) / len(groups) if groups else None
            ),
            "reported_attempt_amplification": (
                reported_attempts / len(groups) if groups else None
            ),
            "latency_amplification": (
                latency_numerator / latency_denominator
                if latency_denominator
                else None
            ),
            "latency_amplification_measured_requests": len(
                complete_latency_pairs
            ),
            "cost_amplification": (
                float(cost_numerator / cost_denominator)
                if cost_denominator
                else None
            ),
            "cost_amplification_measured_requests": len(complete_cost_pairs),
        },
        "conformance": {
            "deadline": _state_summary(
                item["deadline"]["status"] for item in question_results
            ),
            "budget": _state_summary(
                item["budget"]["status"] for item in question_results
            ),
            "output_cap": _state_summary(
                item["output_cap"]["status"] for item in question_results
            ),
            "output_cap_by_attempt": _state_summary(attempt_cap_states),
        },
        "operational_goodput": goodput_summary,
        "score_weighted_goodput": {
            "known": len(known_weighted),
            "unknown": len(weighted_values) - len(known_weighted),
            "quality_points_delivered": sum(known_weighted),
            "measured_mean": (
                sum(known_weighted) / len(known_weighted)
                if known_weighted
                else None
            ),
            "conservative_mean": (
                sum(known_weighted) / len(weighted_values)
                if weighted_values
                else None
            ),
            "denominator": len(weighted_values),
        },
        "coverage": {
            "planned_questions": len(planned),
            "answers": sum(
                bool(answers_by_question.get(question_id))
                for question_id in question_ids
            ),
            "questions_with_call_telemetry": sum(
                bool(groups_by_question.get(question_id))
                for question_id in question_ids
            ),
            "questions_with_scores": sum(
                question_id in scores for question_id in question_ids
            ),
            "unexpected_question_ids": sorted(
                (set(discovered) - question_set) if planned else set()
            ),
            "unassigned_logical_requests": sum(
                group.get("question_id") is None for group in groups
            ),
        },
        "logical_request_results": [
            {
                **{key: value for key, value in group.items() if key != "attempts"},
                **{
                    key: (
                        format(value, "f") if isinstance(value, Decimal) else value
                    )
                    for key, value in observation.items()
                },
            }
            for group, observation in zip(groups, group_observations)
        ],
        "question_results": question_results,
    }


# A concise alias for callers that already use ``*_metrics`` naming.
operational_metrics = compute_operational_metrics


__all__ = [
    "FAIL",
    "NOT_APPLICABLE",
    "PASS",
    "UNKNOWN",
    "compute_operational_metrics",
    "distribution_stats",
    "group_call_attempts",
    "operational_metrics",
]
