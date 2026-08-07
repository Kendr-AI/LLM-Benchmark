"""Resolve repository resources and their wheel-packaged equivalents."""

from __future__ import annotations

import importlib.resources
from pathlib import Path


def bundled_resource(name: str) -> Path:
    """Return a filesystem path for a small bundled configuration resource."""
    repository_relative = {
        "cases.jsonl": Path("benchmarks") / "cases.jsonl",
    }.get(name, Path("config") / name)
    repository_path = Path(__file__).resolve().parents[2] / repository_relative
    if repository_path.is_file():
        return repository_path
    candidate = importlib.resources.files("kendr_bench").joinpath("resources", name)
    path = Path(str(candidate))
    if not path.is_file():
        raise FileNotFoundError(f"Bundled benchmark resource not found: {name}")
    return path
