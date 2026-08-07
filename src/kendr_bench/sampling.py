"""Deterministic, stratified question sampling with auditable provenance.

Benchmark samples must not depend on the order returned by a dataset loader.
This module selects exact question IDs from an in-memory collection and emits
enough provenance to reproduce the selection and detect changes to its source
pool.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Iterable, Literal, Mapping, Sequence

SelectionMode = Literal["newest-first", "seeded-random"]

_MISSING_DATE = "unknown"
_SUPPORTED_MODES = frozenset(("newest-first", "seeded-random"))


class SamplingError(ValueError):
    """Raised when a requested benchmark sample cannot be selected safely."""


@dataclass(frozen=True)
class SamplingProvenance:
    """Serializable description of a deterministic question selection.

    ``pool_counts`` and ``date_distribution`` describe the eligible pool;
    their source/selected counterparts make filtering and the final sample
    visible separately.  ``content_hash`` is the SHA-256 digest of the full
    canonical eligible records, sorted independently of their input order. It
    deliberately covers more than the selected IDs: a changed pool may produce
    the same sample by chance and must still be visible in the run manifest.
    """

    schema_version: int
    mode: SelectionMode
    seed: int
    stratify_by: tuple[str, ...]
    questions_per_stratum: int
    minimum_release_date: str | None
    source_record_count: int
    eligible_record_count: int
    excluded_record_count: int
    source_pool_counts: Mapping[str, int]
    pool_counts: Mapping[str, int]
    date_distribution: Mapping[str, int]
    selected_date_distribution: Mapping[str, int]
    selected_ids: tuple[str, ...]
    selected_ids_by_stratum: Mapping[str, tuple[str, ...]]
    content_hash: str
    content_hash_algorithm: str = "sha256"
    content_hash_scope: str = "eligible-records"

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable manifest record."""
        return {
            "schema_version": self.schema_version,
            "mode": self.mode,
            "seed": self.seed,
            "stratify_by": list(self.stratify_by),
            "questions_per_stratum": self.questions_per_stratum,
            "minimum_release_date": self.minimum_release_date,
            "source_record_count": self.source_record_count,
            "eligible_record_count": self.eligible_record_count,
            "excluded_record_count": self.excluded_record_count,
            "source_pool_counts": dict(self.source_pool_counts),
            "pool_counts": dict(self.pool_counts),
            "date_distribution": dict(self.date_distribution),
            "selected_date_distribution": dict(
                self.selected_date_distribution
            ),
            "selected_ids": list(self.selected_ids),
            "selected_ids_by_stratum": {
                key: list(question_ids)
                for key, question_ids in self.selected_ids_by_stratum.items()
            },
            "content_hash": self.content_hash,
            "content_hash_algorithm": self.content_hash_algorithm,
            "content_hash_scope": self.content_hash_scope,
        }


@dataclass(frozen=True)
class _Candidate:
    question_id: str
    stratum: tuple[str, ...]
    release_date: date | None
    record: Mapping[str, Any]


def _field_names(value: str | Sequence[str]) -> tuple[str, ...]:
    if isinstance(value, str):
        fields = (value,)
    else:
        fields = tuple(value)
    if not fields or any(not isinstance(field, str) or not field for field in fields):
        raise SamplingError("stratify_by must contain at least one field name")
    if len(set(fields)) != len(fields):
        raise SamplingError("stratify_by contains duplicate field names")
    return fields


def _parse_date(value: Any, *, context: str) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise SamplingError(f"{context} must be an ISO date (YYYY-MM-DD)")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise SamplingError(
            f"{context} must be an ISO date (YYYY-MM-DD), got {value!r}"
        ) from exc
    if parsed.isoformat() != value:
        raise SamplingError(
            f"{context} must use canonical YYYY-MM-DD form, got {value!r}"
        )
    return parsed


def _normalize_for_hash(value: Any) -> Any:
    """Convert supported record values to deterministic JSON values."""
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise SamplingError("records cannot contain NaN or infinity")
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise SamplingError("record mappings must use string keys")
        return {
            key: _normalize_for_hash(item)
            for key, item in sorted(value.items())
        }
    if isinstance(value, (list, tuple)):
        return [_normalize_for_hash(item) for item in value]
    raise SamplingError(
        "records contain a value that cannot be canonically hashed: "
        f"{type(value).__name__}"
    )


def _canonical_json(value: Any) -> str:
    return json.dumps(
        _normalize_for_hash(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _content_hash(candidates: Sequence[_Candidate]) -> str:
    canonical_records = sorted(
        _canonical_json(candidate.record) for candidate in candidates
    )
    payload = "[" + ",".join(canonical_records) + "]"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _stratum_label(fields: Sequence[str], values: Sequence[str]) -> str:
    """Build an unambiguous, human-readable label for manifest mappings."""
    return "/".join(
        f"{field}={json.dumps(value, ensure_ascii=False)}"
        for field, value in zip(fields, values, strict=True)
    )


def _random_rank(seed: int, stratum: Sequence[str], question_id: str) -> bytes:
    """Stable pseudo-random rank, independent of Python and input ordering."""
    identity = _canonical_json([seed, list(stratum), question_id])
    return hashlib.sha256(identity.encode("utf-8")).digest()


def select_question_ids(
    records: Iterable[Mapping[str, Any]],
    *,
    questions_per_stratum: int,
    stratify_by: str | Sequence[str] = "task",
    seed: int,
    minimum_release_date: str | date | datetime | None = None,
    mode: SelectionMode = "seeded-random",
    question_id_field: str = "question_id",
    release_date_field: str = "livebench_release_date",
) -> SamplingProvenance:
    """Select a fixed number of question IDs from every source stratum.

    The minimum release date is inclusive.  Records without a release date are
    ineligible when a minimum is supplied; malformed dates always fail.  Every
    stratum present in the source records must retain at least
    ``questions_per_stratum`` eligible rows, preventing a date filter from
    silently dropping an entire task or category.

    ``seeded-random`` uses a SHA-256 rank derived from the seed, stratum, and
    question ID.  ``newest-first`` orders by release date descending and then
    question ID ascending; its seed is retained in provenance for a uniform,
    explicit benchmark configuration.
    """
    if isinstance(questions_per_stratum, bool) or not isinstance(
        questions_per_stratum, int
    ):
        raise SamplingError("questions_per_stratum must be an integer")
    if questions_per_stratum <= 0:
        raise SamplingError("questions_per_stratum must be greater than zero")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise SamplingError("seed must be an explicit integer")
    if mode not in _SUPPORTED_MODES:
        raise SamplingError(
            f"mode must be one of {sorted(_SUPPORTED_MODES)}, got {mode!r}"
        )
    if not question_id_field:
        raise SamplingError("question_id_field cannot be empty")
    if not release_date_field:
        raise SamplingError("release_date_field cannot be empty")

    fields = _field_names(stratify_by)
    minimum = _parse_date(
        minimum_release_date, context="minimum_release_date"
    )

    candidates: list[_Candidate] = []
    seen_ids: set[str] = set()
    source_pool_counts: Counter[tuple[str, ...]] = Counter()
    source_count = 0
    for index, record in enumerate(records):
        source_count += 1
        if not isinstance(record, Mapping):
            raise SamplingError(f"record {index} is not a mapping")

        raw_id = record.get(question_id_field)
        if not isinstance(raw_id, str) or not raw_id.strip():
            raise SamplingError(
                f"record {index} has no non-empty string {question_id_field!r}"
            )
        question_id = raw_id.strip()
        if question_id in seen_ids:
            raise SamplingError(f"duplicate question ID: {question_id!r}")
        seen_ids.add(question_id)

        values: list[str] = []
        for field in fields:
            value = record.get(field)
            if not isinstance(value, str) or not value.strip():
                raise SamplingError(
                    f"question {question_id!r} has no non-empty string "
                    f"stratum field {field!r}"
                )
            values.append(value.strip())
        stratum = tuple(values)
        source_pool_counts[stratum] += 1

        released = _parse_date(
            record.get(release_date_field),
            context=(
                f"question {question_id!r} field {release_date_field!r}"
            ),
        )
        if minimum is not None and (released is None or released < minimum):
            continue
        candidates.append(
            _Candidate(
                question_id=question_id,
                stratum=stratum,
                release_date=released,
                record=record,
            )
        )

    if not source_count:
        raise SamplingError("cannot sample from an empty record collection")

    pools: dict[tuple[str, ...], list[_Candidate]] = {
        stratum: [] for stratum in source_pool_counts
    }
    for candidate in candidates:
        pools[candidate.stratum].append(candidate)

    insufficient = {
        _stratum_label(fields, stratum): len(pool)
        for stratum, pool in pools.items()
        if len(pool) < questions_per_stratum
    }
    if insufficient:
        details = ", ".join(
            f"{label}: {count} eligible"
            for label, count in sorted(insufficient.items())
        )
        raise SamplingError(
            "insufficient eligible questions for requested stratified sample "
            f"({questions_per_stratum} required per stratum): {details}"
        )

    if mode == "newest-first":
        missing_dates = sorted(
            candidate.question_id
            for candidate in candidates
            if candidate.release_date is None
        )
        if missing_dates:
            raise SamplingError(
                "newest-first selection requires a release date for every "
                "eligible question; missing for: " + ", ".join(missing_dates)
            )

    selected_ids: list[str] = []
    selected_candidates: list[_Candidate] = []
    selected_by_stratum: dict[str, tuple[str, ...]] = {}
    pool_counts: dict[str, int] = {}
    for stratum in sorted(pools):
        pool = pools[stratum]
        label = _stratum_label(fields, stratum)
        pool_counts[label] = len(pool)
        if mode == "newest-first":
            ordered = sorted(
                pool,
                key=lambda candidate: (
                    -candidate.release_date.toordinal(),  # type: ignore[union-attr]
                    candidate.question_id,
                ),
            )
        else:
            ordered = sorted(
                pool,
                key=lambda candidate: (
                    _random_rank(seed, stratum, candidate.question_id),
                    candidate.question_id,
                ),
            )
        chosen = tuple(
            candidate.question_id
            for candidate in ordered[:questions_per_stratum]
        )
        selected_by_stratum[label] = chosen
        selected_ids.extend(chosen)
        selected_candidates.extend(ordered[:questions_per_stratum])

    date_counts = Counter(
        candidate.release_date.isoformat()
        if candidate.release_date is not None
        else _MISSING_DATE
        for candidate in candidates
    )
    selected_date_counts = Counter(
        candidate.release_date.isoformat()
        if candidate.release_date is not None
        else _MISSING_DATE
        for candidate in selected_candidates
    )
    return SamplingProvenance(
        schema_version=1,
        mode=mode,
        seed=seed,
        stratify_by=fields,
        questions_per_stratum=questions_per_stratum,
        minimum_release_date=minimum.isoformat() if minimum else None,
        source_record_count=source_count,
        eligible_record_count=len(candidates),
        excluded_record_count=source_count - len(candidates),
        source_pool_counts={
            _stratum_label(fields, stratum): count
            for stratum, count in sorted(source_pool_counts.items())
        },
        pool_counts=dict(sorted(pool_counts.items())),
        date_distribution=dict(sorted(date_counts.items())),
        selected_date_distribution=dict(
            sorted(selected_date_counts.items())
        ),
        selected_ids=tuple(selected_ids),
        selected_ids_by_stratum=dict(sorted(selected_by_stratum.items())),
        content_hash=_content_hash(candidates),
    )
