from __future__ import annotations

import copy
from decimal import Decimal

import pytest

from kendr_bench.operations import (
    FAIL,
    NOT_APPLICABLE,
    PASS,
    UNKNOWN,
    compute_operational_metrics,
    distribution_stats,
    group_call_attempts,
    operational_metrics,
)


def _call(
    request_id: str,
    prompt: str,
    *,
    latency_ms: float | None = 10,
    output_tokens: int | None = 5,
    cap: int | None = 10,
    cost_usd: str | None = "0.01",
    attempt_number: int | None = 1,
    retry_attempt_count: int | None = None,
    will_retry: bool | None = None,
    error: dict | None = None,
    **extra,
) -> dict:
    row = {
        "run_id": "run",
        "provider": "provider",
        "requested_model": "model",
        "request_id": request_id,
        "input_messages": [{"role": "user", "content": prompt}],
        "request_parameters": {"max_tokens": cap} if cap is not None else {},
        "output_text": "$ERROR$" if error else "answer",
        "error": error,
    }
    if latency_ms is not None:
        row["latency_ms"] = latency_ms
    if output_tokens is not None:
        row["usage"] = {"completion_tokens": output_tokens}
    if cost_usd is not None:
        row["cost_usd"] = cost_usd
    if attempt_number is not None:
        row["attempt_number"] = attempt_number
    if retry_attempt_count is not None:
        row["retry_attempt_count"] = retry_attempt_count
    if will_retry is not None:
        row["will_retry"] = will_retry
    row.update(extra)
    return row


def _answer(question_id: str, request_ids: list[str], *, failed=False) -> dict:
    return {
        "question_id": question_id,
        "choices": [{"turns": ["$ERROR$" if failed else "answer"]}],
        "api_info": {
            "benchmark_calls": [
                {"request_id": request_id} for request_id in request_ids
            ]
        },
    }


def _judgment(question_id: str, score: float | int | None) -> dict:
    return {"question_id": question_id, "score": score}


def _questions(metrics: dict) -> dict[str, dict]:
    return {
        row["question_id"]: row for row in metrics["question_results"]
    }


def test_group_call_attempts_joins_fresh_key_retries_and_links_answer():
    calls = [
        _call(
            "failed",
            "same",
            latency_ms=92,
            attempt_number=1,
            will_retry=True,
            error={"type": "Timeout"},
            idempotency_key="fresh-1",
        ),
        _call(
            "succeeded",
            "same",
            latency_ms=66,
            attempt_number=2,
            retry_attempt_count=1,
            idempotency_key="fresh-2",
        ),
    ]

    grouped = group_call_attempts(
        calls, answers=[_answer("q1", ["failed", "succeeded"])]
    )

    assert len(grouped) == 1
    assert grouped[0]["question_id"] == "q1"
    assert grouped[0]["identity_source"] == "retry_metadata_and_message"
    assert grouped[0]["request_ids"] == ["failed", "succeeded"]
    assert grouped[0]["attempt_count"] == 2
    assert grouped[0]["reported_attempt_count"] == 2
    assert grouped[0]["retry_count"] == 1


def test_group_call_attempts_does_not_merge_independent_identical_calls():
    calls = [_call("one", "repeat"), _call("two", "repeat")]

    grouped = group_call_attempts(calls)

    assert len(grouped) == 2
    assert [group["attempt_count"] for group in grouped] == [1, 1]


def test_group_call_attempts_uses_explicit_logical_id_without_messages():
    calls = [
        {
            "request_id": "one",
            "logical_request_id": "logical",
            "error": {"type": "error"},
            "will_retry": True,
        },
        {
            "request_id": "two",
            "logical_request_id": "logical",
            "output_text": "ok",
        },
    ]

    grouped = group_call_attempts(calls)

    assert len(grouped) == 1
    assert grouped[0]["identity_source"] == "logical_request_id"


def test_group_call_attempts_falls_back_to_unique_message_identity():
    call = _call("raw", "identify me")
    answer = {
        "question_id": "q-message",
        "choices": [{"turns": ["answer"]}],
        "api_info": {
            "benchmark_calls": [
                {
                    "input_messages": copy.deepcopy(call["input_messages"]),
                }
            ]
        },
    }

    grouped = group_call_attempts([call], answers=[answer])

    assert grouped[0]["question_id"] == "q-message"


def test_group_call_attempts_refuses_ambiguous_message_fallback():
    call = _call("raw", "same question")
    embedded = {"input_messages": copy.deepcopy(call["input_messages"])}
    answers = [
        {
            "question_id": "q1",
            "api_info": {"benchmark_calls": [embedded]},
        },
        {
            "question_id": "q2",
            "api_info": {"benchmark_calls": [embedded]},
        },
    ]

    grouped = group_call_attempts([call], answers=answers)

    assert grouped[0]["question_id"] is None
    assert grouped[0]["question_id_candidates"] == []


def test_grouping_is_pure_and_does_not_mutate_input_rows():
    calls = [_call("one", "prompt")]
    original = copy.deepcopy(calls)

    grouped = group_call_attempts(calls)
    grouped[0]["attempts"][0]["request_id"] = "changed-copy"

    assert calls == original


def test_cumulative_request_and_final_answer_latency_include_retry():
    calls = [
        _call(
            "failed",
            "prompt",
            latency_ms=92,
            attempt_number=1,
            will_retry=True,
            error={"type": "Timeout"},
            retry_reason="no_credits_charged",
            cost_usd=None,
        ),
        _call(
            "ok",
            "prompt",
            latency_ms=66,
            attempt_number=2,
            retry_attempt_count=1,
            cost_usd="0.02",
        ),
    ]

    metrics = compute_operational_metrics(
        calls,
        answers=[_answer("q1", ["failed", "ok"])],
        judgments=[_judgment("q1", 1)],
        planned_question_ids=["q1"],
    )

    assert metrics["attempts"]["latency_ms"]["count"] == 2
    assert metrics["attempts"]["latency_ms"]["maximum"] == 92
    requests = metrics["logical_requests"]
    assert requests["cumulative_latency_ms"]["maximum"] == 158
    assert requests["final_attempt_latency_ms"]["maximum"] == 66
    questions = metrics["questions"]
    assert questions["cumulative_final_answer_latency_ms"]["maximum"] == 158
    assert _questions(metrics)["q1"]["cumulative_latency_ms"] == 158


def test_cumulative_latency_includes_retry_backoff_gap_when_timestamps_exist():
    calls = [
        _call(
            "failed",
            "prompt",
            latency_ms=100,
            attempt_number=1,
            will_retry=True,
            error={"type": "Timeout"},
            timestamp=1000.0,
        ),
        _call(
            "ok",
            "prompt",
            latency_ms=100,
            attempt_number=2,
            retry_attempt_count=1,
            timestamp=1000.3,
        ),
    ]

    metrics = compute_operational_metrics(
        calls,
        answers=[_answer("q1", ["failed", "ok"])],
        judgments=[_judgment("q1", 1)],
        planned_question_ids=["q1"],
    )

    request = metrics["logical_request_results"][0]
    question = _questions(metrics)["q1"]
    assert request["summed_attempt_latency_ms"] == 200
    assert request["wall_clock_span_ms"] == 400
    assert request["cumulative_latency_ms"] == 400
    assert request["latency_basis"] == "wall_clock_span_including_gaps"
    assert question["summed_logical_request_latency_ms"] == 400
    assert question["wall_clock_span_ms"] == 400
    assert question["cumulative_latency_ms"] == 400
    assert question["latency_basis"] == "summed_logical_request_latency"


def test_final_answer_latency_and_budget_include_all_multi_turn_requests():
    calls = [
        _call("turn-1", "first turn", latency_ms=10, cost_usd="0.01"),
        _call(
            "turn-2-failed",
            "second turn",
            latency_ms=20,
            cost_usd="0.02",
            will_retry=True,
            error={"type": "retryable"},
        ),
        _call(
            "turn-2-ok",
            "second turn",
            latency_ms=30,
            cost_usd="0.03",
            attempt_number=2,
            retry_attempt_count=1,
        ),
    ]

    metrics = compute_operational_metrics(
        calls,
        answers=[
            _answer("q1", ["turn-1", "turn-2-failed", "turn-2-ok"])
        ],
        judgments=[_judgment("q1", 1)],
        planned_question_ids=["q1"],
        budget_usd="0.055",
    )
    question = _questions(metrics)["q1"]

    assert metrics["logical_requests"]["count"] == 2
    assert question["logical_request_count"] == 2
    assert question["attempt_count"] == 3
    assert question["cumulative_latency_ms"] == 60
    assert question["cumulative_cost_usd"] == "0.06"
    assert question["budget"]["status"] == FAIL


def test_retry_amplification_counts_attempt_latency_and_cost():
    calls = [
        _call(
            "failed",
            "prompt",
            latency_ms=40,
            cost_usd="0.01",
            will_retry=True,
            error={"type": "Rejected"},
        ),
        _call(
            "ok",
            "prompt",
            latency_ms=60,
            cost_usd="0.02",
            attempt_number=2,
            retry_attempt_count=1,
        ),
        _call("plain", "other", latency_ms=50, cost_usd="0.02"),
    ]
    answers = [_answer("q1", ["failed", "ok"]), _answer("q2", ["plain"])]

    retry = compute_operational_metrics(calls, answers=answers)["retries"]

    assert retry["observed_extra_attempts"] == 1
    assert retry["reported_extra_attempts"] == 1
    assert retry["retried_logical_requests"] == 1
    assert retry["logical_request_retry_rate"] == 0.5
    assert retry["observed_attempt_amplification"] == 1.5
    assert retry["latency_amplification"] == pytest.approx(150 / 110)
    assert retry["cost_amplification"] == 1.25  # (.03 + .02) / (.02 + .02)


def test_explicit_no_credit_failure_is_known_zero_cost():
    calls = [
        _call(
            "failed",
            "prompt",
            cost_usd=None,
            will_retry=True,
            error={"type": "UpstreamFailure"},
            retry_reason="no_credits_charged",
        ),
        _call(
            "ok",
            "prompt",
            cost_usd="0.02",
            attempt_number=2,
            retry_attempt_count=1,
        ),
    ]

    metrics = compute_operational_metrics(
        calls,
        answers=[_answer("q1", ["failed", "ok"])],
        judgments=[_judgment("q1", 1)],
        planned_question_ids=["q1"],
        budget_usd="0.02",
    )

    request = metrics["logical_request_results"][0]
    question = _questions(metrics)["q1"]
    assert request["cumulative_cost_usd"] == "0.02"
    assert request["cost_complete"] is True
    assert question["cumulative_cost_usd"] == "0.02"
    assert question["budget"]["status"] == PASS


def test_reported_retry_without_prior_row_is_explicitly_incomplete():
    call = _call(
        "terminal",
        "prompt",
        latency_ms=20,
        attempt_number=3,
        retry_attempt_count=2,
    )

    metrics = compute_operational_metrics(
        [call],
        answers=[_answer("q1", ["terminal"])],
        judgments=[_judgment("q1", 1)],
        planned_question_ids=["q1"],
        deadline_ms=100,
    )

    request = metrics["logical_request_results"][0]
    question = _questions(metrics)["q1"]
    assert request["reported_attempt_count"] == 3
    assert request["missing_attempt_count"] == 2
    assert request["observed_latency_ms"] == 20
    assert request["cumulative_latency_ms"] is None
    assert metrics["retries"]["missing_attempts"] == 2
    assert question["deadline"]["status"] == UNKNOWN
    assert question["operational_goodput"] == UNKNOWN


def test_limit_breach_is_known_even_when_another_measurement_is_missing():
    call = _call(
        "one",
        "prompt",
        latency_ms=None,
        cost_usd="0.20",
    )

    question = _questions(
        compute_operational_metrics(
            [call],
            answers=[_answer("q1", ["one"])],
            judgments=[_judgment("q1", 1)],
            planned_question_ids=["q1"],
            budget_usd="0.10",
            deadline_ms=100,
        )
    )["q1"]

    assert question["budget"]["status"] == FAIL
    assert question["deadline"]["status"] == UNKNOWN
    assert question["operational_goodput"] == FAIL


def test_failed_retry_output_is_included_in_cap_conformance():
    calls = [
        _call(
            "failed",
            "prompt",
            output_tokens=20,
            cap=10,
            will_retry=True,
            error={"type": "Truncated"},
        ),
        _call(
            "ok",
            "prompt",
            output_tokens=5,
            cap=10,
            attempt_number=2,
            retry_attempt_count=1,
        ),
    ]

    metrics = compute_operational_metrics(
        calls,
        answers=[_answer("q1", ["failed", "ok"])],
        judgments=[_judgment("q1", 1)],
        planned_question_ids=["q1"],
    )
    question = _questions(metrics)["q1"]

    assert question["output_cap"]["status"] == FAIL
    assert question["output_cap"]["measured_attempts"] == 2
    assert question["output_cap"]["maximum_observed_output_tokens"] == 20
    assert metrics["conformance"]["output_cap"]["fail"] == 1
    by_attempt = metrics["conformance"]["output_cap_by_attempt"]
    assert by_attempt["pass"] == 1
    assert by_attempt["fail"] == 1
    assert by_attempt["measured_rate"] == 0.5


def test_failed_attempt_usage_can_be_recovered_from_error_body():
    failed = _call(
        "failed",
        "prompt",
        output_tokens=None,
        cap=10,
        will_retry=True,
        error={
            "body": {
                "details": {
                    "attempts": [{"usage": {"output_tokens": 11}}]
                }
            }
        },
    )
    ok = _call(
        "ok",
        "prompt",
        output_tokens=5,
        cap=10,
        attempt_number=2,
        retry_attempt_count=1,
    )

    question = _questions(
        compute_operational_metrics(
            [failed, ok],
            answers=[_answer("q1", ["failed", "ok"])],
            judgments=[_judgment("q1", 1)],
            planned_question_ids=["q1"],
        )
    )["q1"]

    assert question["output_cap"]["status"] == FAIL
    assert question["output_cap"]["maximum_observed_output_tokens"] == 11


def test_goodput_uses_full_planned_denominator_and_keeps_unknown_explicit():
    calls = [
        _call("q1-call", "one", cost_usd="0.01"),
        _call("q2-call", "two", cost_usd=None),
        _call("q3-call", "three", cost_usd="0.01"),
    ]
    answers = [
        _answer("q1", ["q1-call"]),
        _answer("q2", ["q2-call"]),
        _answer("q3", ["q3-call"]),
    ]
    judgments = [
        _judgment("q1", 1),
        _judgment("q2", 1),
        _judgment("q3", 0),
    ]

    metrics = compute_operational_metrics(
        calls,
        answers=answers,
        judgments=judgments,
        planned_question_ids=["q1", "q2", "q3", "q4"],
        deadline_ms=100,
        budget_usd="0.05",
        output_cap_tokens=10,
    )
    by_question = _questions(metrics)

    assert by_question["q1"]["operational_goodput"] == PASS
    assert by_question["q2"]["budget"]["status"] == UNKNOWN
    assert by_question["q2"]["operational_goodput"] == UNKNOWN
    assert by_question["q3"]["operational_goodput"] == FAIL
    assert by_question["q4"]["successful"] is False
    assert by_question["q4"]["operational_goodput"] == FAIL
    goodput = metrics["operational_goodput"]
    assert goodput["denominator"] == 4
    assert goodput["pass"] == 1
    assert goodput["fail"] == 2
    assert goodput["unknown"] == 1
    assert goodput["measured_rate"] == pytest.approx(1 / 3)
    assert goodput["conservative_rate"] == 0.25


def test_score_weighted_goodput_is_separate_from_binary_threshold():
    call = _call("one", "prompt")

    metrics = compute_operational_metrics(
        [call],
        answers=[_answer("q1", ["one"])],
        judgments=[_judgment("q1", 0.8)],
        planned_question_ids=["q1"],
        correct_threshold=0.9,
    )
    question = _questions(metrics)["q1"]

    assert question["correct"] is False
    assert question["operational_goodput"] == FAIL
    assert question["score_weighted_goodput"] == 0.8
    assert metrics["score_weighted_goodput"]["conservative_mean"] == 0.8


def test_no_configured_constraint_is_not_applicable_not_unknown():
    call = _call("one", "prompt", cap=None)

    question = _questions(
        compute_operational_metrics(
            [call],
            answers=[_answer("q1", ["one"])],
            judgments=[_judgment("q1", 1)],
            planned_question_ids=["q1"],
        )
    )["q1"]

    assert question["deadline"]["status"] == NOT_APPLICABLE
    assert question["budget"]["status"] == NOT_APPLICABLE
    assert question["output_cap"]["status"] == NOT_APPLICABLE
    assert question["operational_goodput"] == PASS


def test_question_specific_limits_and_defaults_are_supported():
    calls = [_call("one", "one"), _call("two", "two")]
    answers = [_answer("q1", ["one"]), _answer("q2", ["two"])]
    judgments = [_judgment("q1", 1), _judgment("q2", 1)]

    metrics = compute_operational_metrics(
        calls,
        answers=answers,
        judgments=judgments,
        planned_question_ids=["q1", "q2"],
        deadline_ms={"q1": 5, "*": 20},
        budget_usd={"q1": Decimal("0.005"), "default": "0.02"},
    )
    by_question = _questions(metrics)

    assert by_question["q1"]["deadline"]["status"] == FAIL
    assert by_question["q1"]["budget"]["status"] == FAIL
    assert by_question["q2"]["deadline"]["status"] == PASS
    assert by_question["q2"]["budget"]["status"] == PASS


def test_unscored_success_is_unknown_but_failed_answer_is_zero():
    calls = [_call("one", "one"), _call("two", "two")]
    answers = [
        _answer("q1", ["one"]),
        _answer("q2", ["two"], failed=True),
    ]

    metrics = compute_operational_metrics(
        calls,
        answers=answers,
        judgments=[_judgment("q1", -1), _judgment("q2", None)],
        planned_question_ids=["q1", "q2"],
    )
    by_question = _questions(metrics)

    assert by_question["q1"]["correct"] is None
    assert by_question["q1"]["operational_goodput"] == UNKNOWN
    assert by_question["q2"]["objective_score"] == 0
    assert by_question["q2"]["correct"] is False
    assert by_question["q2"]["operational_goodput"] == FAIL


def test_unmatched_and_unexpected_telemetry_is_reported():
    calls = [
        _call("planned", "planned"),
        _call("unexpected", "unexpected", question_id="other"),
        _call("unassigned", "unassigned"),
    ]
    answers = [_answer("q1", ["planned"])]

    coverage = compute_operational_metrics(
        calls,
        answers=answers,
        judgments=[_judgment("q1", 1)],
        planned_question_ids=["q1"],
    )["coverage"]

    assert coverage["unexpected_question_ids"] == ["other"]
    assert coverage["unassigned_logical_requests"] == 1


def test_invalid_correct_threshold_is_rejected():
    with pytest.raises(ValueError, match="between 0 and 1"):
        compute_operational_metrics([], correct_threshold=1.1)


def test_distribution_stats_and_alias_are_stable():
    assert distribution_stats([1, 2, 3, 4])["p50"] == 2.5
    assert distribution_stats([])["mean"] is None
    assert operational_metrics is compute_operational_metrics
