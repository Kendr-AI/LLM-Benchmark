"""Counterfactual router evaluation over a shared question matrix."""

from __future__ import annotations

from collections import Counter
from typing import Any, Iterable, Mapping, Sequence


def extract_answer_routes(
    answers: Iterable[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Return the final observable Kendr routing decision per question."""
    routes: dict[str, dict[str, Any]] = {}
    for answer in answers:
        question_id = answer.get("question_id")
        api_info = answer.get("api_info")
        if not question_id or not isinstance(api_info, Mapping):
            continue
        calls = api_info.get("benchmark_calls")
        if not isinstance(calls, list):
            calls = api_info.get("kendr_calls")
        if not isinstance(calls, list):
            continue
        routed_calls = [
            call
            for call in calls
            if isinstance(call, Mapping)
            and isinstance(call.get("kendr_routing"), Mapping)
        ]
        if not routed_calls:
            continue
        # LiveBench records attempts in call order. Prefer the last successful
        # leg, falling back to the last routed failure for diagnostics.
        successful = [call for call in routed_calls if not call.get("error")]
        final_call = (successful or routed_calls)[-1]
        routing = final_call["kendr_routing"]
        routes[str(question_id)] = {
            "selected_model_alias": routing.get("selected_model_alias"),
            "confidence": routing.get("confidence"),
            "task_category": routing.get("task_category"),
            "reason_code": routing.get("reason_code"),
        }
    return routes


def _mean(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _confidence_calibration(
    question_ids: Sequence[str],
    router_scores: Mapping[str, float],
    routes: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    observations: list[tuple[float, float]] = []
    for question_id in question_ids:
        route = routes.get(question_id) or {}
        raw_confidence = route.get("confidence")
        try:
            confidence = float(raw_confidence)
        except (TypeError, ValueError):
            continue
        if not 0 <= confidence <= 1:
            continue
        observations.append((confidence, float(router_scores[question_id])))
    bins: list[dict[str, Any]] = []
    weighted_error = 0.0
    for index in range(5):
        low = index / 5
        high = (index + 1) / 5
        members = [
            item
            for item in observations
            if low <= item[0] < high
            or index == 4 and item[0] == high
        ]
        if not members:
            continue
        mean_confidence = _mean([item[0] for item in members])
        mean_score = _mean([item[1] for item in members])
        assert mean_confidence is not None and mean_score is not None
        weighted_error += len(members) * abs(mean_confidence - mean_score)
        bins.append(
            {
                "low": low,
                "high": high,
                "count": len(members),
                "mean_confidence": mean_confidence,
                "mean_realized_score": mean_score,
            }
        )
    return {
        "measured_questions": len(observations),
        "coverage": (
            len(observations) / len(question_ids) if question_ids else None
        ),
        "brier_score_against_realized_quality": _mean(
            [
                (confidence - score) ** 2
                for confidence, score in observations
            ]
        ),
        "expected_calibration_error": (
            weighted_error / len(observations) if observations else None
        ),
        "bins": bins,
        "warning": (
            "Router confidence is compared with realized objective score, not "
            "a vendor-defined probability of correctness."
        ),
    }


def compute_routing_benchmarks(
    rows: Sequence[Mapping[str, Any]],
    *,
    router_key: str = "kendr-intelligent",
) -> dict[str, Any]:
    """Compare a routed endpoint with best-single, random, and panel oracle.

    Candidate rows are endpoint-as-served counterfactuals on the same frozen
    questions. They are not necessarily the router's complete candidate set,
    so every oracle/regret field is explicitly panel-scoped.
    """
    router = next(
        (row for row in rows if row.get("panel_key") == router_key), None
    )
    if router is None:
        return {
            "available": False,
            "reason": f"router endpoint {router_key!r} is absent",
        }
    router_scores = router.get("_question_scores")
    if not isinstance(router_scores, Mapping) or not router_scores:
        return {
            "available": False,
            "reason": "router has no per-question scores",
        }
    question_ids = sorted(str(key) for key in router_scores)
    normalized_router_scores = {
        question_id: float(router_scores.get(question_id, 0.0))
        for question_id in question_ids
    }
    candidates = [
        row
        for row in rows
        if row.get("panel_key") != router_key
        and isinstance(row.get("_question_scores"), Mapping)
        and row.get("_question_scores")
    ]
    if not candidates:
        return {
            "available": False,
            "reason": "no counterfactual candidate endpoints have scores",
        }

    candidate_summaries: list[dict[str, Any]] = []
    candidate_scores: dict[str, dict[str, float]] = {}
    alias_to_key: dict[str, str] = {}
    for row in candidates:
        panel_key = str(row.get("panel_key"))
        raw_scores = row["_question_scores"]
        scores = {
            question_id: float(raw_scores.get(question_id, 0.0))
            for question_id in question_ids
        }
        candidate_scores[panel_key] = scores
        observed = sum(question_id in raw_scores for question_id in question_ids)
        candidate_summaries.append(
            {
                "panel_key": panel_key,
                "model": row.get("model"),
                "requested_model": row.get("requested_model"),
                "score": _mean(list(scores.values())),
                "observed_question_coverage": observed / len(question_ids),
            }
        )
        for alias in (
            panel_key,
            row.get("requested_model"),
            row.get("model"),
        ):
            if alias:
                alias_to_key[str(alias).lower()] = panel_key

    best_single = max(
        candidate_summaries,
        key=lambda item: (float(item["score"]), str(item["panel_key"])),
    )
    random_score = _mean(
        [float(item["score"]) for item in candidate_summaries]
    )
    oracle_by_question = {
        question_id: max(
            scores[question_id] for scores in candidate_scores.values()
        )
        for question_id in question_ids
    }
    oracle_score = _mean(list(oracle_by_question.values()))
    router_score = _mean(list(normalized_router_scores.values()))
    assert oracle_score is not None and router_score is not None

    routes = router.get("_routes")
    if not isinstance(routes, Mapping):
        routes = {}
    selected_scores: list[float] = []
    selected_regrets: list[float] = []
    routed_count = 0
    route_distribution: Counter[str] = Counter()
    for question_id in question_ids:
        route = routes.get(question_id)
        if not isinstance(route, Mapping):
            continue
        alias = route.get("selected_model_alias")
        if not alias:
            continue
        routed_count += 1
        route_distribution[str(alias)] += 1
        candidate_key = alias_to_key.get(str(alias).lower())
        if candidate_key is None:
            continue
        selected_score = candidate_scores[candidate_key][question_id]
        selected_scores.append(selected_score)
        selected_regrets.append(
            oracle_by_question[question_id] - selected_score
        )

    selected_coverage_complete = bool(
        routed_count == len(question_ids)
        and len(selected_scores) == len(question_ids)
    )
    panel_oracle_gap = oracle_score - router_score
    return {
        "available": True,
        "scope": (
            "Counterfactuals are limited to non-router endpoints in this "
            "matrix; this is a panel oracle, not an oracle over every model "
            "the production router could call."
        ),
        "questions": len(question_ids),
        "router": {
            "panel_key": router_key,
            "score": router_score,
            "gap_to_panel_oracle": panel_oracle_gap,
            "regret_to_panel_oracle": (
                _mean(selected_regrets)
                if selected_coverage_complete
                else None
            ),
            "regret_estimable": selected_coverage_complete,
            "regret_limitation": (
                None
                if selected_coverage_complete
                else "Not every observed route has a standalone endpoint in "
                "the panel, so the panel envelope is a comparison gap rather "
                "than a valid router-regret bound."
            ),
            "uplift_over_best_single": (
                router_score - float(best_single["score"])
            ),
            "uplift_over_random_endpoint": router_score - float(random_score),
        },
        "best_single_endpoint": best_single,
        "random_endpoint_expected_score": random_score,
        "panel_oracle_score": oracle_score,
        "candidate_endpoints": sorted(
            candidate_summaries, key=lambda item: str(item["panel_key"])
        ),
        "observed_selection_counterfactual": {
            "routed_questions": routed_count,
            "matched_to_panel_endpoint": len(selected_scores),
            "coverage_of_planned_questions": (
                len(selected_scores) / len(question_ids)
            ),
            "coverage_of_observed_routes": (
                len(selected_scores) / routed_count if routed_count else None
            ),
            "complete_candidate_coverage": selected_coverage_complete,
            "selected_endpoint_score_on_matched_questions": _mean(
                selected_scores
            ),
            "mean_regret_to_panel_oracle_on_matched_questions": _mean(
                selected_regrets
            ),
            "route_distribution": dict(route_distribution),
        },
        "confidence_calibration": _confidence_calibration(
            question_ids, normalized_router_scores, routes
        ),
    }
