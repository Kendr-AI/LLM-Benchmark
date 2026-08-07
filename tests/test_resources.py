from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pytest

from kendr_bench.cli import build_parser as build_benchmark_parser
from kendr_bench.resources import bundled_resource


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_RESOURCES = {
    "cases.jsonl",
    "global-protocol-v1.example.json",
    "livebench-constraints.txt",
    "pricing.json",
}
EXPECTED_SCHEMAS = {
    "answer-v1.schema.json",
    "attempt-v1.schema.json",
    "evidence-manifest-v1.schema.json",
    "frozen-item-v1.schema.json",
    "global-observation-v1.schema.json",
    "global-protocol-v1.schema.json",
    "judgment-v1.schema.json",
    "schedule-cell-v1.schema.json",
    "scorecard-v1.schema.json",
    "system-card-v1.schema.json",
}


def pyproject() -> dict:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", sorted(EXPECTED_RESOURCES))
def test_bundled_repository_resource_exists_and_is_nonempty(name: str) -> None:
    path = bundled_resource(name)
    assert path.is_file()
    assert path.stat().st_size > 0
    if path.suffix == ".json":
        json.loads(path.read_text(encoding="utf-8"))
    elif path.suffix == ".jsonl":
        rows = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert rows


def test_unknown_bundled_resource_is_rejected() -> None:
    with pytest.raises(FileNotFoundError):
        bundled_resource("not-a-real-resource.json")


def test_benchmark_parser_uses_existing_bundled_defaults() -> None:
    args = build_benchmark_parser().parse_args([])
    assert args.cases == bundled_resource("cases.jsonl")
    assert args.pricing == bundled_resource("pricing.json")
    assert args.cases.is_file()
    assert args.pricing.is_file()


def test_wheel_force_include_is_complete_and_collision_free() -> None:
    force_include = pyproject()["tool"]["hatch"]["build"]["targets"]["wheel"][
        "force-include"
    ]
    assert len(force_include.values()) == len(set(force_include.values()))
    for source, destination in force_include.items():
        assert (ROOT / source).is_file(), source
        assert destination.startswith("kendr_bench/")

    packaged_resources = {
        Path(destination).name
        for destination in force_include.values()
        if destination.startswith("kendr_bench/resources/")
    }
    packaged_schemas = {
        Path(destination).name
        for destination in force_include.values()
        if destination.startswith("kendr_bench/schemas/")
    }
    assert packaged_resources == EXPECTED_RESOURCES
    assert packaged_schemas == EXPECTED_SCHEMAS


def test_public_package_commands_keep_compatibility_aliases() -> None:
    scripts = pyproject()["project"]["scripts"]
    assert scripts["llm-benchmark"] == scripts["kendr-bench"]
    assert scripts["llm-benchmark-livebench"] == scripts["kendr-livebench"]
    assert scripts["llm-benchmark-matrix"] == scripts["kendr-benchmark-matrix"]
    assert scripts["llm-benchmark-protocol"] == scripts["kendr-protocol"]
