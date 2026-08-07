from __future__ import annotations

import pytest

from kendr_bench.routing import (
    compute_routing_benchmarks,
    extract_answer_routes,
)


def test_extract_answer_routes_prefers_the_final_successful_attempt():
    answers = [
        {
            "question_id": "q1",
            "api_info": {
                "benchmark_calls": [
                    {
                        "error": {"type": "Timeout"},
                        "kendr_routing": {
                            "selected_model_alias": "failed-model"
                        },
                    },
                    {
                        "kendr_routing": {
                            "selected_model_alias": "model-a",
                            "confidence": "0.8",
                        }
                    },
                ]
            },
        }
    ]

    assert extract_answer_routes(answers) == {
        "q1": {
            "selected_model_alias": "model-a",
            "confidence": "0.8",
            "task_category": None,
            "reason_code": None,
        }
    }


def test_routing_benchmarks_report_oracle_random_and_selection_regret():
    rows = [
        {
            "panel_key": "kendr-intelligent",
            "_question_scores": {"q1": 1.0, "q2": 0.5},
            "_routes": {
                "q1": {
                    "selected_model_alias": "model-a",
                    "confidence": 0.8,
                },
                "q2": {
                    "selected_model_alias": "not-in-panel",
                    "confidence": 0.6,
                },
            },
        },
        {
            "panel_key": "a",
            "model": "A",
            "requested_model": "model-a",
            "_question_scores": {"q1": 1.0, "q2": 0.0},
        },
        {
            "panel_key": "b",
            "model": "B",
            "requested_model": "model-b",
            "_question_scores": {"q1": 0.0, "q2": 1.0},
        },
    ]

    result = compute_routing_benchmarks(rows)

    assert result["available"] is True
    assert result["router"]["score"] == 0.75
    assert result["best_single_endpoint"]["score"] == 0.5
    assert result["random_endpoint_expected_score"] == 0.5
    assert result["panel_oracle_score"] == 1.0
    assert result["router"]["gap_to_panel_oracle"] == 0.25
    assert result["router"]["regret_to_panel_oracle"] is None
    assert result["router"]["regret_estimable"] is False
    assert result["router"]["uplift_over_best_single"] == 0.25
    selection = result["observed_selection_counterfactual"]
    assert selection["matched_to_panel_endpoint"] == 1
    assert selection["coverage_of_planned_questions"] == 0.5
    assert selection["selected_endpoint_score_on_matched_questions"] == 1.0
    assert result["confidence_calibration"]["measured_questions"] == 2


def test_routing_benchmarks_are_unavailable_without_router():
    result = compute_routing_benchmarks(
        [{"panel_key": "candidate", "_question_scores": {"q": 1.0}}]
    )

    assert result["available"] is False
    assert "absent" in result["reason"]


def test_full_coverage_regret_uses_selected_endpoint_counterfactuals():
    rows = [
        {
            "panel_key": "kendr-intelligent",
            # The routed service output can differ from the standalone model
            # result, so its panel gap is not route-selection regret.
            "_question_scores": {"q1": 0.9, "q2": 0.9},
            "_routes": {
                "q1": {"selected_model_alias": "model-a"},
                "q2": {"selected_model_alias": "model-a"},
            },
        },
        {
            "panel_key": "a",
            "model": "A",
            "requested_model": "model-a",
            "_question_scores": {"q1": 0.0, "q2": 0.0},
        },
        {
            "panel_key": "b",
            "model": "B",
            "requested_model": "model-b",
            "_question_scores": {"q1": 1.0, "q2": 1.0},
        },
    ]

    result = compute_routing_benchmarks(rows)

    assert result["router"]["gap_to_panel_oracle"] == pytest.approx(0.1)
    assert result["router"]["regret_to_panel_oracle"] == 1.0
    assert result["router"]["regret_estimable"] is True
    selection = result["observed_selection_counterfactual"]
    assert selection["complete_candidate_coverage"] is True
    assert selection["mean_regret_to_panel_oracle_on_matched_questions"] == 1.0
