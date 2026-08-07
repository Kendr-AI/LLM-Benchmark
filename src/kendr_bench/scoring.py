"""Shared quality normalization and resampling.

Every published quality number has to come from one definition. The failure
normalization rule and the bootstrap used to be reimplemented at each call
site, which let a reported confidence interval describe a different dataset
than the point estimate it annotated, and let two artifacts in the same
directory disagree about the same capability score.
"""

from __future__ import annotations

import hashlib
import itertools
import random
from typing import Any, Iterable, Mapping, Sequence

ERROR_SENTINEL = "$ERROR$"
UNSCORED_SENTINELS = (None, -1)


def answer_failed(answer: Mapping[str, Any]) -> bool:
    """True when LiveBench recorded a provider failure for this answer."""
    if bool(answer.get("error")):
        return True
    for choice in answer.get("choices") or []:
        if not isinstance(choice, Mapping):
            continue
        for turn in choice.get("turns") or []:
            if turn == ERROR_SENTINEL:
                return True
    return False


def failed_question_ids(answers: Iterable[Mapping[str, Any]]) -> set[str]:
    return {
        str(answer.get("question_id"))
        for answer in answers
        if answer_failed(answer)
    }


def is_scored(judgment: Mapping[str, Any]) -> bool:
    """LiveBench writes -1 (occasionally null) when a question was not graded."""
    return judgment.get("score") not in UNSCORED_SENTINELS


def normalized_score(
    judgment: Mapping[str, Any], failed_ids: set[str]
) -> float:
    """Official score with provider failures forced to zero.

    Some instruction-following graders award format credit to the literal
    ``$ERROR$`` sentinel. A provider failure is an availability failure, not a
    low-quality answer.
    """
    if str(judgment.get("question_id")) in failed_ids:
        return 0.0
    return float(judgment["score"])


def normalized_scores(
    judgments: Iterable[Mapping[str, Any]], failed_ids: set[str]
) -> list[float]:
    return [
        normalized_score(judgment, failed_ids)
        for judgment in judgments
        if is_scored(judgment)
    ]


def category_scores(
    judgments: Iterable[Mapping[str, Any]], failed_ids: set[str]
) -> dict[str, float]:
    grouped: dict[str, list[float]] = {}
    for judgment in judgments:
        category = judgment.get("category")
        if not category or not is_scored(judgment):
            continue
        grouped.setdefault(str(category), []).append(
            normalized_score(judgment, failed_ids)
        )
    return {
        category: sum(scores) / len(scores)
        for category, scores in sorted(grouped.items())
        if scores
    }


def stable_seed(key: str) -> int:
    """Deterministic seed derived from identity rather than position.

    Seeding from a row index made every published interval depend on panel
    order, so running a subset reported different bounds for the same model on
    the same data.
    """
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def percentile(values: Sequence[float], fraction: float) -> float | None:
    """Linear-interpolated percentile. ``fraction`` is in [0, 1]."""
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    index = (len(ordered) - 1) * fraction
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    weight = index - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def bootstrap_ci(
    values: Sequence[float],
    *,
    seed: int,
    iterations: int = 20_000,
) -> dict[str, Any]:
    """Percentile bootstrap over question scores, with degeneracy reported.

    At fifteen questions the resampled mean takes very few distinct values and
    can pile up against the ends of the score scale. A bound equal to the
    smallest or largest observed score is censored by the scale rather than
    estimated from it, so callers must be able to say so instead of printing
    ``100.0%`` as though it were a real upper limit.
    """
    if not values:
        return {
            "low": None,
            "high": None,
            "n": 0,
            "iterations": 0,
            "distinct_resample_means": 0,
            "low_at_bound": False,
            "high_at_bound": False,
            "degenerate": True,
        }
    rng = random.Random(seed)
    n = len(values)
    means = [
        sum(values[rng.randrange(n)] for _ in range(n)) / n
        for _ in range(iterations)
    ]
    low = percentile(means, 0.025)
    high = percentile(means, 0.975)
    distinct = len(set(means))
    tolerance = 1e-12
    low_at_bound = abs(low - min(values)) <= tolerance
    high_at_bound = abs(high - max(values)) <= tolerance
    return {
        "low": low,
        "high": high,
        "n": n,
        "iterations": iterations,
        "distinct_resample_means": distinct,
        "low_at_bound": low_at_bound,
        "high_at_bound": high_at_bound,
        "degenerate": low_at_bound or high_at_bound or distinct < 100,
    }


def paired_deltas(
    left: Mapping[str, float], right: Mapping[str, float]
) -> list[float]:
    """Per-question ``left - right`` over the questions both answered."""
    return [
        left[question_id] - right[question_id]
        for question_id in sorted(left.keys() & right.keys())
    ]


def paired_randomization_test(
    deltas: Sequence[float],
    *,
    seed: int,
    exact_max_nonzero: int = 18,
    iterations: int = 200_000,
) -> dict[str, Any]:
    """Two-sided paired sign-randomization test for a zero mean difference.

    Under the null, swapping the two model labels independently for each
    question changes only the sign of that question's delta.  This preserves
    the paired design, unlike comparing two marginal confidence intervals.
    Tied questions carry no information for the randomization distribution and
    are omitted from enumeration, while the reported ``n`` still describes the
    full paired sample.
    """
    values = [float(value) for value in deltas]
    nonzero = [abs(value) for value in values if value != 0]
    if not values:
        return {
            "p_value": None,
            "n": 0,
            "nonzero_pairs": 0,
            "method": "unavailable",
            "permutations": 0,
        }
    if not nonzero:
        return {
            "p_value": 1.0,
            "n": len(values),
            "nonzero_pairs": 0,
            "method": "exact",
            "permutations": 1,
        }

    # The denominator of the mean is constant under every label swap, so
    # comparing absolute sums is equivalent and avoids unnecessary rounding.
    observed = abs(sum(values))
    tolerance = 1e-12
    if len(nonzero) <= exact_max_nonzero:
        extreme = 0
        total = 0
        for signs in itertools.product((-1.0, 1.0), repeat=len(nonzero)):
            randomized = sum(
                sign * magnitude
                for sign, magnitude in zip(signs, nonzero)
            )
            extreme += abs(randomized) + tolerance >= observed
            total += 1
        p_value = extreme / total
        method = "exact"
    else:
        rng = random.Random(seed)
        extreme = 0
        for _ in range(iterations):
            randomized = sum(
                magnitude if rng.getrandbits(1) else -magnitude
                for magnitude in nonzero
            )
            extreme += abs(randomized) + tolerance >= observed
        # The plus-one correction prevents an estimated p-value of zero.
        p_value = (extreme + 1) / (iterations + 1)
        total = iterations
        method = "monte_carlo"
    return {
        "p_value": p_value,
        "n": len(values),
        "nonzero_pairs": len(nonzero),
        "method": method,
        "permutations": total,
    }


def holm_adjust(p_values: Mapping[str, float | None]) -> dict[str, float | None]:
    """Holm step-down family-wise error correction.

    Missing tests remain missing and do not enlarge the tested family.  The
    cumulative maximum is essential: without it, adjusted p-values can become
    smaller as raw p-values become larger.
    """
    available = sorted(
        (
            (key, float(value))
            for key, value in p_values.items()
            if value is not None
        ),
        key=lambda item: (item[1], item[0]),
    )
    adjusted: dict[str, float | None] = {
        key: None for key in p_values
    }
    family_size = len(available)
    running = 0.0
    for index, (key, p_value) in enumerate(available):
        candidate = min(1.0, p_value * (family_size - index))
        running = max(running, candidate)
        adjusted[key] = running
    return adjusted


def separation_tiers(
    entries: Sequence[tuple[str, dict[str, Any]]]
) -> dict[str, int]:
    """Group models whose confidence intervals overlap into one tier.

    Integer ranks over fifteen questions imply resolution the measurement does
    not have: adjacent models routinely differ by a fraction of one question's
    partial credit. A model opens a new tier only once its whole interval falls
    below the lower bound of the tier's leader.

    The comparison is against the tier leader specifically, not against every
    member. Widening the boundary to whichever member had the lowest bound would
    let overlap chain down the whole table, and a single tier containing both
    the best and worst endpoint says nothing.

    ``entries`` must already be ordered best-first. Models without an interval
    join the current tier rather than inventing a separation.
    """
    tiers: dict[str, int] = {}
    tier = 0
    leader_low: float | None = None
    for key, interval in entries:
        low = interval.get("low") if interval else None
        high = interval.get("high") if interval else None
        if low is None or high is None:
            tiers[key] = tier or 1
            continue
        if tier == 0 or (leader_low is not None and high < leader_low):
            tier += 1
            leader_low = low
        tiers[key] = tier
    return tiers
