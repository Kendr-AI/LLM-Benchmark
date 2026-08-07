from __future__ import annotations

import importlib.util
import hashlib
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "scripts" / "export_public_results.py"
SPEC = importlib.util.spec_from_file_location("export_public_results", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _row(rank: int, key: str, *, complete: bool = True) -> dict:
    return {
        "rank": rank,
        "panel_key": key,
        "requested_model": key,
        "model": key,
        "tier": 1,
        "questions_scored": 2,
        "complete": complete,
        "score_weighted_operational_goodput": 0.5,
        "quality_score": 0.5,
        "availability": 1.0,
        "successful_answers": 2,
        "failed_answers": 0,
    }


def test_public_bundle_removes_private_lineage_and_classifies_divisions():
    rows = [_row(1, "kendr-flash"), _row(2, "fixed")]
    rows[0]["run_dir"] = "C:/private/run"
    bundle = MODULE.build_public_bundle(
        {
            "matrix_id": "matrix",
            "results": rows,
            "failures": [],
            "pairwise_tests": [{"holm_reject": False}],
        },
        {"sampling": {"content_hash": "abc"}},
        [
            {"id": "kendr-flash", "mode": "intelligent", "capabilities": ["text"]},
            {"id": "fixed", "mode": "direct", "capabilities": ["text"]},
        ],
        {"selected_entries": 2, "catalog_entries": 2, "excluded_entries": []},
    )
    assert bundle["results"][0]["division"] == "Routed systems"
    assert bundle["results"][1]["division"] == "Fixed managed text endpoints"
    assert "run_dir" not in bundle["results"][0]
    assert bundle["pairwise_inference"]["holm_rejections"] == 0


def test_public_bundle_rejects_incomplete_matrix():
    with pytest.raises(ValueError, match="not publication-complete"):
        MODULE.build_public_bundle(
            {"results": [_row(1, "one")], "failures": [{"model": "two"}]},
            {},
            [],
            {"selected_entries": 2},
        )


def test_write_bundle_is_platform_stable_and_checksums_stored_bytes(tmp_path: Path):
    bundle = {"results": [_row(1, "fixed")]}

    json_path, csv_path, checksum_path = MODULE.write_bundle(bundle, tmp_path, "pilot")

    assert b"\r" not in json_path.read_bytes()
    assert b"\r" not in csv_path.read_bytes()
    checksum_entries = dict(
        reversed(line.split("  ", 1))
        for line in checksum_path.read_text(encoding="ascii").splitlines()
    )
    assert checksum_entries[json_path.name] == hashlib.sha256(
        json_path.read_bytes()
    ).hexdigest()
    assert checksum_entries[csv_path.name] == hashlib.sha256(
        csv_path.read_bytes()
    ).hexdigest()
