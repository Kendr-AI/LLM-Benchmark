from __future__ import annotations

from kendr_bench.scoring import (
    answer_failed,
    bootstrap_ci,
    category_scores,
    failed_question_ids,
    normalized_scores,
    paired_deltas,
    percentile,
    separation_tiers,
    stable_seed,
)


def test_answer_failed_detects_sentinel_and_error_flag():
    assert answer_failed({"choices": [{"turns": ["$ERROR$"]}]})
    assert answer_failed({"error": "boom"})
    assert not answer_failed({"choices": [{"turns": ["a real answer"]}]})
    assert not answer_failed({})


def test_failed_question_ids_collects_only_failures():
    answers = [
        {"question_id": "a", "choices": [{"turns": ["$ERROR$"]}]},
        {"question_id": "b", "choices": [{"turns": ["fine"]}]},
        {"question_id": "c", "error": {"type": "Timeout"}},
    ]
    assert failed_question_ids(answers) == {"a", "c"}


def test_normalized_scores_zero_out_grader_credit_for_provider_failure():
    """A format grader can award credit to the literal failure sentinel."""
    judgments = [
        {"question_id": "a", "score": 0.1667},
        {"question_id": "b", "score": 1.0},
        {"question_id": "c", "score": -1},
    ]
    assert normalized_scores(judgments, {"a"}) == [0.0, 1.0]
    assert normalized_scores(judgments, set()) == [0.1667, 1.0]


def test_category_scores_average_normalized_scores_per_category():
    judgments = [
        {"question_id": "a", "category": "math", "score": 1.0},
        {"question_id": "b", "category": "math", "score": 0.0},
        {"question_id": "c", "category": "language", "score": 0.5},
        {"question_id": "d", "category": "language", "score": -1},
    ]
    assert category_scores(judgments, set()) == {
        "language": 0.5,
        "math": 0.5,
    }
    assert category_scores(judgments, {"a"})["math"] == 0.0


def test_stable_seed_is_identity_based_not_positional():
    assert stable_seed("kendr-intelligent") == stable_seed(
        "kendr-intelligent"
    )
    assert stable_seed("kendr-intelligent") != stable_seed("openai-sol")


def test_bootstrap_ci_is_reproducible_for_a_given_seed():
    values = [0.2, 0.5, 1.0, 1.0, 1.0]
    first = bootstrap_ci(values, seed=stable_seed("m"), iterations=2_000)
    second = bootstrap_ci(values, seed=stable_seed("m"), iterations=2_000)
    assert first["low"] == second["low"]
    assert first["high"] == second["high"]
    assert first["low"] <= sum(values) / len(values) <= first["high"]


def test_bootstrap_ci_flags_a_bound_censored_by_the_score_scale():
    """An upper bound of 1.0 is the ceiling, not an estimated limit."""
    interval = bootstrap_ci(
        [1.0] * 12 + [0.2, 0.5, 0.67], seed=stable_seed("kendr"),
    )
    assert interval["high"] == 1.0
    assert interval["high_at_bound"] is True
    assert interval["degenerate"] is True


def test_bootstrap_ci_reports_resample_granularity():
    interval = bootstrap_ci([0.0, 1.0], seed=1, iterations=500)
    # Two questions can only ever produce three distinct means.
    assert interval["distinct_resample_means"] <= 3
    assert interval["degenerate"] is True


def test_bootstrap_ci_handles_no_scores_without_raising():
    interval = bootstrap_ci([], seed=1)
    assert interval["low"] is None
    assert interval["high"] is None
    assert interval["n"] == 0
    assert interval["degenerate"] is True


def test_percentile_interpolates_and_tolerates_empty_input():
    assert percentile([], 0.5) is None
    assert percentile([5.0], 0.9) == 5.0
    assert percentile([0.0, 1.0], 0.5) == 0.5


def test_paired_deltas_uses_only_shared_questions():
    left = {"a": 1.0, "b": 0.0, "only-left": 1.0}
    right = {"a": 0.0, "b": 0.0, "only-right": 1.0}
    assert paired_deltas(left, right) == [1.0, 0.0]


def test_separation_tiers_keeps_overlapping_intervals_together():
    entries = [
        ("best", {"low": 0.76, "high": 1.0}),
        ("overlaps-best", {"low": 0.70, "high": 0.96}),
        ("clears-both", {"low": 0.30, "high": 0.60}),
    ]
    tiers = separation_tiers(entries)
    assert tiers["best"] == 1
    assert tiers["overlaps-best"] == 1
    assert tiers["clears-both"] == 2


def test_separation_tiers_places_missing_intervals_in_trailing_tier():
    entries = [
        ("has-interval", {"low": 0.8, "high": 0.9}),
        ("no-interval", {"low": None, "high": None}),
    ]
    tiers = separation_tiers(entries)
    assert tiers["has-interval"] == 1
    assert tiers["no-interval"] == 1


def test_separation_tiers_do_not_chain_overlap_down_the_table():
    """Overlap is measured against the tier leader, not the loosest member.

    Comparing against whichever member had the lowest bound let overlap chain
    all the way down, putting the best and worst endpoint in one tier.
    """
    entries = [
        ("a", {"low": 0.80, "high": 1.00}),
        ("b", {"low": 0.60, "high": 0.85}),
        ("c", {"low": 0.40, "high": 0.70}),
    ]
    # c overlaps b, but its whole interval is below a's lower bound.
    assert separation_tiers(entries) == {"a": 1, "b": 1, "c": 2}


def test_separation_tiers_matches_the_real_nine_model_panel():
    """The published panel separates the leader from Llama 4 Maverick only."""
    entries = [
        ("kendr", {"low": 0.761, "high": 1.000}),
        ("deepseek", {"low": 0.704, "high": 0.967}),
        ("opus48", {"low": 0.622, "high": 0.956}),
        ("kimi", {"low": 0.561, "high": 0.933}),
        ("sol", {"low": 0.489, "high": 0.911}),
        ("opus5", {"low": 0.518, "high": 0.889}),
        ("terra", {"low": 0.422, "high": 0.867}),
        ("glm", {"low": 0.378, "high": 0.844}),
        ("llama", {"low": 0.301, "high": 0.736}),
    ]
    tiers = separation_tiers(entries)
    assert tiers["kendr"] == 1
    assert tiers["glm"] == 1
    assert tiers["llama"] == 2
