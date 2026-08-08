from __future__ import annotations

from pathlib import Path

from scripts.verify_release import (
    check_frontier_companion,
    check_release_workflow_assets,
    check_versions,
    verify_release,
)


ROOT = Path(__file__).resolve().parents[1]


def test_release_verifier_accepts_repository_snapshot() -> None:
    results = verify_release(ROOT, expected_version="1.0.3")
    failures = {
        result.name: list(result.problems) for result in results if not result.passed
    }
    assert not failures, failures


def test_tag_must_exactly_match_package_version() -> None:
    problems = check_versions(ROOT, expected_version="1.0.3", tag="v1.0.0")
    assert "release tag 'v1.0.0' != expected 'v1.0.3'" in problems


def test_frontier_companion_bundle_is_pinned_and_privacy_reviewed() -> None:
    problems = check_frontier_companion(ROOT, version="1.0.3")
    assert not problems, problems


def test_release_workflow_carries_frontier_publication_assets() -> None:
    problems = check_release_workflow_assets(ROOT)
    assert not problems, problems
