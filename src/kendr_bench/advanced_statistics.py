from __future__ import annotations

import math
import random
from collections import defaultdict
from dataclasses import dataclass
from statistics import NormalDist
from typing import Any, Iterable, Mapping, Sequence


@dataclass(frozen=True)
class IntervalEstimate:
    estimate: float | None
    low: float | None
    high: float | None
    confidence: float
    method: str
    items: int
    clusters: int
    observations: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "estimate": self.estimate,
            "low": self.low,
            "high": self.high,
            "confidence": self.confidence,
            "method": self.method,
            "items": self.items,
            "clusters": self.clusters,
            "observations": self.observations,
        }


def _percentile(values: Sequence[float], fraction: float) -> float:
    if not values:
        raise ValueError("cannot compute a percentile of an empty sequence")
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def wilson_interval(
    successes: int,
    trials: int,
    *,
    confidence: float = 0.95,
) -> IntervalEstimate:
    """Wilson score interval for a binary rate.

    This is preferable to a normal/Wald interval for reliability and safety
    rates near zero or one.
    """
    if trials < 0 or successes < 0 or successes > trials:
        raise ValueError("require 0 <= successes <= trials")
    if not 0 < confidence < 1:
        raise ValueError("confidence must be between zero and one")
    if trials == 0:
        return IntervalEstimate(None, None, None, confidence, "wilson", 0, 0, 0)
    z = NormalDist().inv_cdf(0.5 + confidence / 2)
    rate = successes / trials
    denominator = 1 + z * z / trials
    center = (rate + z * z / (2 * trials)) / denominator
    half = z * math.sqrt(rate * (1 - rate) / trials + z * z / (4 * trials * trials)) / denominator
    return IntervalEstimate(
        estimate=rate,
        low=max(0.0, center - half),
        high=min(1.0, center + half),
        confidence=confidence,
        method="wilson",
        items=trials,
        clusters=trials,
        observations=trials,
    )


def hierarchical_cluster_bootstrap(
    rows: Iterable[Mapping[str, Any]],
    *,
    score_field: str = "score",
    item_field: str = "item_id",
    cluster_field: str = "cluster_id",
    samples: int = 10_000,
    confidence: float = 0.95,
    seed: int = 0,
) -> IntervalEstimate:
    """Estimate a score and interval while preserving evaluation hierarchy.

    Clusters are sampled first, then items within each sampled cluster, then
    generation observations within each sampled item. The point estimate gives
    each item equal weight after averaging its repeats. This prevents extra
    generations or several questions from one shared source from pretending to
    be independent evidence.
    """
    if samples <= 0:
        raise ValueError("samples must be positive")
    if not 0 < confidence < 1:
        raise ValueError("confidence must be between zero and one")
    grouped: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    observations = 0
    for index, row in enumerate(rows):
        try:
            score = float(row[score_field])
        except (KeyError, TypeError, ValueError):
            continue
        if not math.isfinite(score):
            continue
        item = str(row.get(item_field) or f"__row_{index}")
        cluster = str(row.get(cluster_field) or item)
        grouped[cluster][item].append(score)
        observations += 1
    if not grouped:
        return IntervalEstimate(
            None,
            None,
            None,
            confidence,
            "hierarchical-cluster-bootstrap",
            0,
            0,
            0,
        )

    item_means = [
        sum(values) / len(values)
        for items in grouped.values()
        for values in items.values()
    ]
    estimate = sum(item_means) / len(item_means)
    cluster_ids = sorted(grouped)
    rng = random.Random(seed)
    draws: list[float] = []
    for _ in range(samples):
        sampled_scores: list[float] = []
        for _cluster_draw in cluster_ids:
            cluster_id = rng.choice(cluster_ids)
            items = grouped[cluster_id]
            item_ids = sorted(items)
            for _item_draw in item_ids:
                item_id = rng.choice(item_ids)
                values = items[item_id]
                sampled_values = [rng.choice(values) for _value in values]
                sampled_scores.append(sum(sampled_values) / len(sampled_values))
        draws.append(sum(sampled_scores) / len(sampled_scores))
    tail = (1 - confidence) / 2
    return IntervalEstimate(
        estimate=estimate,
        low=_percentile(draws, tail),
        high=_percentile(draws, 1 - tail),
        confidence=confidence,
        method="hierarchical-cluster-bootstrap",
        items=len(item_means),
        clusters=len(cluster_ids),
        observations=observations,
    )


def paired_hierarchical_bootstrap(
    rows: Iterable[Mapping[str, Any]],
    *,
    left_system: str,
    right_system: str,
    system_field: str = "system_id",
    score_field: str = "score",
    item_field: str = "item_id",
    cluster_field: str = "cluster_id",
    samples: int = 10_000,
    confidence: float = 0.95,
    seed: int = 0,
) -> IntervalEstimate:
    """Paired hierarchical interval for the left-minus-right effect."""
    by_system_item: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    item_clusters: dict[str, str] = {}
    for index, row in enumerate(rows):
        system = str(row.get(system_field) or "")
        if system not in {left_system, right_system}:
            continue
        try:
            score = float(row[score_field])
        except (KeyError, TypeError, ValueError):
            continue
        if not math.isfinite(score):
            continue
        item = str(row.get(item_field) or f"__row_{index}")
        by_system_item[system][item].append(score)
        item_clusters[item] = str(row.get(cluster_field) or item)
    shared = sorted(
        set(by_system_item[left_system]) & set(by_system_item[right_system])
    )
    paired_rows: list[dict[str, Any]] = []
    observations = 0
    for item in shared:
        left = by_system_item[left_system][item]
        right = by_system_item[right_system][item]
        observations += len(left) + len(right)
        # Repeat counts need not match; averaging per system/item preserves the
        # paired item while avoiding silent truncation of valid generations.
        paired_rows.append(
            {
                "item_id": item,
                "cluster_id": item_clusters[item],
                "score": sum(left) / len(left) - sum(right) / len(right),
            }
        )
    result = hierarchical_cluster_bootstrap(
        paired_rows,
        samples=samples,
        confidence=confidence,
        seed=seed,
    )
    return IntervalEstimate(
        estimate=result.estimate,
        low=result.low,
        high=result.high,
        confidence=result.confidence,
        method="paired-hierarchical-cluster-bootstrap",
        items=result.items,
        clusters=result.clusters,
        observations=observations,
    )


def approximate_required_items(
    *,
    minimum_detectable_effect: float,
    standard_deviation: float = 0.5,
    power: float = 0.8,
    alpha: float = 0.05,
    paired_correlation: float = 0.0,
) -> int:
    """Approximate paired-comparison item count for protocol planning.

    The result is deliberately only a planning estimate. Final sizing should
    use pilot-derived cluster and item variance and account for multiplicity.
    """
    if minimum_detectable_effect <= 0:
        raise ValueError("minimum_detectable_effect must be positive")
    if standard_deviation <= 0:
        raise ValueError("standard_deviation must be positive")
    if not 0 < power < 1 or not 0 < alpha < 1:
        raise ValueError("power and alpha must be between zero and one")
    if not -1 < paired_correlation < 1:
        raise ValueError("paired_correlation must be between -1 and 1")
    z_alpha = NormalDist().inv_cdf(1 - alpha / 2)
    z_power = NormalDist().inv_cdf(power)
    difference_sd = standard_deviation * math.sqrt(2 * (1 - paired_correlation))
    return math.ceil(((z_alpha + z_power) * difference_sd / minimum_detectable_effect) ** 2)
