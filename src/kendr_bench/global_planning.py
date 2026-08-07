from __future__ import annotations

import hashlib
import random
from collections import Counter
from typing import Any, Mapping, Sequence


def _stable_seed(seed: int, *parts: str) -> int:
    value = "\0".join([str(seed), *parts]).encode("utf-8")
    return int.from_bytes(hashlib.sha256(value).digest()[:8], "big")


def build_interleaved_schedule(
    items: Sequence[Mapping[str, Any]],
    system_ids: Sequence[str],
    *,
    repeats: int,
    days: int,
    regions: Sequence[str],
    seed: int,
    protocol_id: str,
    deadline_ms: float,
    budget_usd: float | None,
    output_cap_tokens: int,
) -> list[dict[str, Any]]:
    """Build a deterministic balanced schedule for provider calls.

    Each system receives every item at every repeat. Item/repeat cells rotate
    across day and region blocks, while system order inside a cell is shuffled
    deterministically. This prevents endpoint-wide sequential blocks and makes
    time/region effects estimable.
    """
    if not items:
        raise ValueError("items must not be empty")
    if not system_ids or len(set(system_ids)) != len(system_ids):
        raise ValueError("system_ids must be non-empty and unique")
    if repeats <= 0 or days <= 0:
        raise ValueError("repeats and days must be positive")
    if not regions or len(set(regions)) != len(regions):
        raise ValueError("regions must be non-empty and unique")
    if not protocol_id.strip():
        raise ValueError("protocol_id must not be empty")
    if deadline_ms <= 0 or output_cap_tokens <= 0:
        raise ValueError("deadline_ms and output_cap_tokens must be positive")
    if budget_usd is not None and budget_usd < 0:
        raise ValueError("budget_usd must not be negative")
    normalized_items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        item_id = str(item.get("item_id") or "").strip()
        if not item_id or item_id in seen:
            raise ValueError("every item requires a unique non-empty item_id")
        seen.add(item_id)
        normalized_items.append(dict(item))

    blocks = [(day + 1, region) for day in range(days) for region in regions]
    cells: list[tuple[int, str, dict[str, Any]]] = []
    for repeat in range(1, repeats + 1):
        for item in normalized_items:
            cells.append((repeat, str(item["item_id"]), item))
    cell_rng = random.Random(_stable_seed(seed, "cells"))
    cell_rng.shuffle(cells)

    schedule: list[dict[str, Any]] = []
    block_positions = Counter()
    for cell_index, (repeat, item_id, item) in enumerate(cells):
        day, region = blocks[cell_index % len(blocks)]
        ordered_systems = list(system_ids)
        random.Random(_stable_seed(seed, item_id, str(repeat))).shuffle(ordered_systems)
        for within_cell, system_id in enumerate(ordered_systems):
            block_key = (day, region)
            position = block_positions[block_key]
            block_positions[block_key] += 1
            schedule.append(
                {
                    "schema_version": "1.0",
                    "schedule_id": hashlib.sha256(
                        f"{seed}\0{item_id}\0{repeat}\0{system_id}".encode("utf-8")
                    ).hexdigest()[:24],
                    "protocol_id": protocol_id,
                    "day": day,
                    "region": region,
                    "block_position": position,
                    "within_item_position": within_cell,
                    "item_id": item_id,
                    "cluster_id": str(item.get("cluster_id") or item_id),
                    "track": str(item.get("track") or "unspecified"),
                    "language": str(item.get("language") or "unspecified"),
                    "locale": str(item.get("locale") or "unspecified"),
                    "modality": str(item.get("modality") or "unspecified"),
                    "difficulty": str(item.get("difficulty") or "unspecified"),
                    "deadline_ms": deadline_ms,
                    "budget_usd": budget_usd,
                    "output_cap_tokens": output_cap_tokens,
                    "repeat": repeat,
                    "system_id": system_id,
                    "seed": seed,
                }
            )
    return sorted(
        schedule,
        key=lambda row: (row["day"], row["region"], row["block_position"]),
    )


def validate_schedule(
    schedule: Sequence[Mapping[str, Any]],
    *,
    item_ids: Sequence[str],
    system_ids: Sequence[str],
    repeats: int,
) -> dict[str, Any]:
    expected = {
        (item_id, system_id, repeat)
        for item_id in item_ids
        for system_id in system_ids
        for repeat in range(1, repeats + 1)
    }
    observed: list[tuple[str, str, int]] = []
    for row in schedule:
        observed.append(
            (
                str(row.get("item_id")),
                str(row.get("system_id")),
                int(row.get("repeat", 0)),
            )
        )
    counts = Counter(observed)
    observed_set = set(observed)
    duplicates = sorted(key for key, count in counts.items() if count > 1)
    missing = sorted(expected - observed_set)
    unexpected = sorted(observed_set - expected)
    return {
        "valid": not duplicates and not missing and not unexpected,
        "expected_rows": len(expected),
        "observed_rows": len(observed),
        "duplicates": duplicates,
        "missing": missing,
        "unexpected": unexpected,
    }
