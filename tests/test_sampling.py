from __future__ import annotations

import json
from datetime import date, datetime

import pytest

from kendr_bench.sampling import SamplingError, select_question_ids


def _records() -> list[dict[str, object]]:
    return [
        {
            "question_id": "math-old",
            "category": "reasoning",
            "task": "math",
            "livebench_release_date": "2025-01-01",
            "prompt": "old math",
        },
        {
            "question_id": "math-mid",
            "category": "reasoning",
            "task": "math",
            "livebench_release_date": "2025-03-01",
            "prompt": "mid math",
        },
        {
            "question_id": "math-new",
            "category": "reasoning",
            "task": "math",
            "livebench_release_date": "2025-04-01",
            "prompt": "new math",
        },
        {
            "question_id": "code-old",
            "category": "coding",
            "task": "code",
            "livebench_release_date": "2025-01-15",
            "prompt": "old code",
        },
        {
            "question_id": "code-mid",
            "category": "coding",
            "task": "code",
            "livebench_release_date": "2025-03-15",
            "prompt": "mid code",
        },
        {
            "question_id": "code-new",
            "category": "coding",
            "task": "code",
            "livebench_release_date": "2025-04-15",
            "prompt": "new code",
        },
    ]


def test_newest_first_selects_exact_ids_per_task() -> None:
    provenance = select_question_ids(
        _records(),
        questions_per_stratum=2,
        stratify_by="task",
        seed=2026,
        mode="newest-first",
    )

    assert provenance.selected_ids_by_stratum == {
        'task="code"': ("code-new", "code-mid"),
        'task="math"': ("math-new", "math-mid"),
    }
    assert provenance.selected_ids == (
        "code-new",
        "code-mid",
        "math-new",
        "math-mid",
    )
    assert provenance.pool_counts == {
        'task="code"': 3,
        'task="math"': 3,
    }
    assert provenance.source_pool_counts == provenance.pool_counts
    assert provenance.selected_date_distribution == {
        "2025-03-01": 1,
        "2025-03-15": 1,
        "2025-04-01": 1,
        "2025-04-15": 1,
    }


def test_seeded_random_is_reproducible_and_input_order_independent() -> None:
    records = _records()
    first = select_question_ids(
        records,
        questions_per_stratum=2,
        seed=17,
        mode="seeded-random",
    )
    second = select_question_ids(
        reversed(records),
        questions_per_stratum=2,
        seed=17,
        mode="seeded-random",
    )

    assert first.selected_ids == second.selected_ids
    assert first.content_hash == second.content_hash
    assert len(first.content_hash) == 64


def test_different_seeds_change_the_hash_ranked_sample() -> None:
    records = [
        {
            "question_id": f"q{index}",
            "task": "many",
            "livebench_release_date": "2025-01-01",
        }
        for index in range(30)
    ]
    first = select_question_ids(
        records, questions_per_stratum=5, seed=1
    )
    second = select_question_ids(
        records, questions_per_stratum=5, seed=2
    )

    assert first.selected_ids != second.selected_ids
    # The content hash describes the pool, not the selection configuration.
    assert first.content_hash == second.content_hash


def test_stratifies_by_category_or_multiple_fields() -> None:
    by_category = select_question_ids(
        _records(),
        questions_per_stratum=1,
        stratify_by="category",
        seed=0,
    )
    by_category_and_task = select_question_ids(
        _records(),
        questions_per_stratum=1,
        stratify_by=("category", "task"),
        seed=0,
    )

    assert set(by_category.pool_counts) == {
        'category="coding"',
        'category="reasoning"',
    }
    assert set(by_category_and_task.pool_counts) == {
        'category="coding"/task="code"',
        'category="reasoning"/task="math"',
    }


def test_minimum_release_date_is_inclusive_and_recorded() -> None:
    provenance = select_question_ids(
        _records(),
        questions_per_stratum=2,
        seed=3,
        minimum_release_date=date(2025, 3, 1),
    )

    assert provenance.minimum_release_date == "2025-03-01"
    assert provenance.source_record_count == 6
    assert provenance.eligible_record_count == 4
    assert provenance.excluded_record_count == 2
    assert provenance.source_pool_counts == {
        'task="code"': 3,
        'task="math"': 3,
    }
    assert provenance.pool_counts == {
        'task="code"': 2,
        'task="math"': 2,
    }
    assert provenance.date_distribution == {
        "2025-03-01": 1,
        "2025-03-15": 1,
        "2025-04-01": 1,
        "2025-04-15": 1,
    }


def test_datetime_release_values_are_supported_and_canonicalized() -> None:
    records = [
        {
            "question_id": "q1",
            "category": "a",
            "release_date": datetime(2025, 5, 1, 10, 30),
        }
    ]
    provenance = select_question_ids(
        records,
        questions_per_stratum=1,
        stratify_by="category",
        seed=1,
        minimum_release_date="2025-05-01",
        release_date_field="release_date",
    )

    assert provenance.selected_ids == ("q1",)
    assert provenance.date_distribution == {"2025-05-01": 1}


def test_missing_dates_are_allowed_for_random_selection_without_a_cutoff() -> None:
    provenance = select_question_ids(
        [{"question_id": "q1", "task": "t"}],
        questions_per_stratum=1,
        seed=1,
    )

    assert provenance.date_distribution == {"unknown": 1}


def test_newest_first_rejects_eligible_rows_without_dates() -> None:
    with pytest.raises(SamplingError, match="requires a release date"):
        select_question_ids(
            [{"question_id": "q1", "task": "t"}],
            questions_per_stratum=1,
            seed=1,
            mode="newest-first",
        )


def test_cutoff_cannot_silently_drop_a_whole_stratum() -> None:
    records = _records()
    with pytest.raises(SamplingError, match='task="math": 1 eligible'):
        select_question_ids(
            records,
            questions_per_stratum=2,
            seed=4,
            minimum_release_date="2025-04-01",
        )


def test_insufficient_pool_fails_instead_of_returning_a_short_sample() -> None:
    with pytest.raises(SamplingError, match="4 required per stratum"):
        select_question_ids(
            _records(), questions_per_stratum=3 + 1, seed=5
        )


def test_provenance_is_json_serializable() -> None:
    provenance = select_question_ids(
        _records(), questions_per_stratum=1, seed=99
    )
    encoded = json.dumps(provenance.to_dict(), sort_keys=True)
    decoded = json.loads(encoded)

    assert decoded["selected_ids"] == list(provenance.selected_ids)
    assert decoded["content_hash_algorithm"] == "sha256"
    assert decoded["content_hash_scope"] == "eligible-records"
    assert decoded["schema_version"] == 1


def test_content_hash_detects_record_content_changes() -> None:
    records = _records()
    original = select_question_ids(
        records, questions_per_stratum=1, seed=8
    )
    changed_records = [dict(record) for record in records]
    changed_records[0]["prompt"] = "changed"
    changed = select_question_ids(
        changed_records, questions_per_stratum=1, seed=8
    )

    assert original.content_hash != changed.content_hash


@pytest.mark.parametrize(
    ("records", "message"),
    [
        ([], "empty record collection"),
        (
            [
                {"question_id": "same", "task": "a"},
                {"question_id": "same", "task": "a"},
            ],
            "duplicate question ID",
        ),
        ([{"question_id": "q1"}], "stratum field 'task'"),
        ([{"question_id": "", "task": "a"}], "non-empty string"),
    ],
)
def test_invalid_records_fail_loudly(
    records: list[dict[str, object]], message: str
) -> None:
    with pytest.raises(SamplingError, match=message):
        select_question_ids(
            records, questions_per_stratum=1, seed=1
        )


def test_malformed_dates_and_invalid_configuration_fail_loudly() -> None:
    with pytest.raises(SamplingError, match="canonical YYYY-MM-DD"):
        select_question_ids(
            [
                {
                    "question_id": "q1",
                    "task": "a",
                    "livebench_release_date": "20250101",
                }
            ],
            questions_per_stratum=1,
            seed=1,
        )
    with pytest.raises(SamplingError, match="questions_per_stratum"):
        select_question_ids(_records(), questions_per_stratum=0, seed=1)
    with pytest.raises(SamplingError, match="explicit integer"):
        select_question_ids(  # type: ignore[arg-type]
            _records(), questions_per_stratum=1, seed=True
        )
    with pytest.raises(SamplingError, match="mode must be one of"):
        select_question_ids(  # type: ignore[arg-type]
            _records(), questions_per_stratum=1, seed=1, mode="first"
        )
