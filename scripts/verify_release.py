#!/usr/bin/env python3
"""Verify that a source tree is safe and internally consistent for release.

The verifier is intentionally offline. It validates the repository snapshot and
the privacy-reviewed public ranking bundle, but it never calls a model provider,
changes Git state, creates a tag, or publishes an artifact.
"""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import re
import subprocess
import sys
import tomllib
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence
from urllib.parse import unquote


PROJECT_DISTRIBUTION = "llm-benchmark-protocol"
PROJECT_TITLE = "LLM Benchmark Protocol"
BRAND_NAME = "Kendr"
RESEARCHER_NAME = "Dr. Prashant Kumar Dey"
CANONICAL_REPOSITORY = "https://github.com/Kendr-AI/LLM-Benchmark"
PUBLIC_RESULTS_STEM = "kendr-catalog-pilot-2026-08-08"
FRONTIER_RESULTS_STEM = "kendr-frontier-leaderboard-2026-08-08"
FRONTIER_MATRIX_ID = (
    "20260808T070202Z-frontier-market-kendr-20260808-cfec3672"
)
FRONTIER_DATA_RELATIVE = Path("docs/data/frontier-2026-08-08")
FRONTIER_COMPANION_RESULTS_STEM = (
    "kendr-frontier-preview-companion-2026-08-08"
)
FRONTIER_COMPANION_MATRIX_ID = (
    "20260808T083825Z-frontier-preview-kendr-20260808-d910f1e1"
)
FRONTIER_COMPANION_DATA_RELATIVE = Path(
    "docs/data/frontier-preview-2026-08-08"
)
FRONTIER_COMPANION_SOURCE_COMMIT = (
    "33ea04dc78f4f2fb50fb45c822a245bcbd686d38"
)
FRONTIER_COMPANION_PROVENANCE = {
    "catalog_sha256": "e7c61de227223aad5e4531044c792e0ecb5ac11d4796c0f2bd6491a3d96de7b0",
    "coverage_audit_sha256": "365882eaccd5e7db1c2e1bb65fcfe6b312b8e51257c5ffe3e42a57e4b61f81f6",
    "execution_panel_sha256": "ca0fa4b4b1e4b5b4002755d03b2debf154d34c7906d2a5f40fd51b085d185f8a",
    "matrix_catalog_file_sha256": "5924bcb0ecf640a9cba4d5e825f0b2eb057575e5235c0f19949485226567c8dc",
    "matrix_leaderboard_sha256": "57d39cacaab8bb199ade5daf983671e1bb532c1ab32f361741f55b04c84c22d9",
    "matrix_manifest_sha256": "df3669c6f39e5967072f32cb93794f3ad22a19c7d7b6aeecf74f659a42f5b2c5",
    "profile_sha256": "a0dcfee9ea22ab518b982577c9e790509b9d2efba62c02afaaabf59aacfd8b38",
}
FRONTIER_COMPANION_ARTIFACT_SHA256 = {
    f"{FRONTIER_COMPANION_RESULTS_STEM}.csv": (
        "2801dbbe5c15cc4fb95745b334f8898f573f5ad8b178e57da0c5f9e1c1cbae60"
    ),
    f"{FRONTIER_COMPANION_RESULTS_STEM}.json": (
        "d71fd8df6de37ff6d43be7013815fbdbe16ec024e9a2b8d7fdc0b317b25fc1dd"
    ),
    f"{FRONTIER_COMPANION_RESULTS_STEM}.md": (
        "91b20062da050f530847c7d4e18042657465d7355f3100bffac5ca87b509b434"
    ),
}
PILOT_EXECUTION_VERSION = "1.0.0"
FRONTIER_EXECUTION_VERSION = "1.0.2"
FRONTIER_COMPANION_EXECUTION_VERSION = "1.0.2"
LOGO_RELATIVE_PATH = Path("assets/brand/kendr-mark-ink-512.png")
LEGACY_DISPLAY_BRAND = "Kendr" + " " + "AI"
CANONICAL_PDF_PALETTE = {
    "ink": (21, 20, 18),
    "saffron": (226, 113, 42),
    "paper": (250, 248, 244),
    "warm_grey": (138, 131, 120),
}
LEGACY_PDF_PALETTE = {
    "navy": (17, 35, 63),
    "blue": (22, 102, 217),
    "cyan": (32, 164, 184),
}
REQUIRED_FRONTIER_RELEASE_ASSETS = {
    "docs/FRONTIER_EXECUTION_LEADERBOARD_2026-08-08.md": "release-assets/",
    "docs/FRONTIER_MODEL_COVERAGE_2026-08-08.md": "release-assets/",
    "docs/GPT_5_6_VS_5_5_ANALYSIS_2026-08-08.md": "release-assets/",
    "docs/data/frontier-2026-08-08/kendr-frontier-leaderboard-2026-08-08.json": "release-assets/",
    "docs/data/frontier-2026-08-08/kendr-frontier-leaderboard-2026-08-08.csv": "release-assets/",
    "docs/data/frontier-2026-08-08/kendr-frontier-leaderboard-2026-08-08.md": "release-assets/",
    "docs/data/frontier-2026-08-08/SHA256SUMS": (
        "release-assets/frontier-2026-08-08-SHA256SUMS"
    ),
    "docs/data/frontier-preview-2026-08-08/kendr-frontier-preview-companion-2026-08-08.json": "release-assets/",
    "docs/data/frontier-preview-2026-08-08/kendr-frontier-preview-companion-2026-08-08.csv": "release-assets/",
    "docs/data/frontier-preview-2026-08-08/kendr-frontier-preview-companion-2026-08-08.md": "release-assets/",
    "docs/data/frontier-preview-2026-08-08/SHA256SUMS": (
        "release-assets/frontier-preview-2026-08-08-SHA256SUMS"
    ),
}

REQUIRED_FILES = (
    ".env.example",
    ".gitattributes",
    ".gitleaks.toml",
    ".github/ISSUE_TEMPLATE/bug.yml",
    ".github/ISSUE_TEMPLATE/protocol-change.yml",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/dependabot.yml",
    ".github/workflows/ci.yml",
    ".github/workflows/release-check.yml",
    "AUTHORS.md",
    "CHANGELOG.md",
    "CITATION.cff",
    "CODE_OF_CONDUCT.md",
    "CONTRIBUTING.md",
    "DATA_LICENSE.md",
    "GLOBAL_BENCHMARK_PROTOCOL.md",
    "GOVERNANCE.md",
    "LICENSE",
    "README.md",
    "RELEASING.md",
    "SECURITY.md",
    "assets/brand/README.md",
    LOGO_RELATIVE_PATH.as_posix(),
    "benchmarks/cases.jsonl",
    "config/global-observation-v1.schema.json",
    "config/global-protocol-v1.example.json",
    "config/global-protocol-v1.schema.json",
    "config/kendr-current-frontier-profile-20260808.json",
    "config/kendr-frontier-execution-panel-20260808.json",
    "config/kendr-frontier-preview-execution-panel-20260808.json",
    "docs/ADOPTION_GUIDE.md",
    "docs/APPEALS_AND_CORRECTIONS.md",
    "docs/CURRENT_FRONTIER_PANEL_2026-08-08.md",
    "docs/EVIDENCE_BUNDLE.md",
    "docs/FAQ.md",
    "docs/FRONTIER_EXECUTION_LEADERBOARD_2026-08-08.md",
    "docs/FRONTIER_MODEL_COVERAGE_2026-08-08.md",
    "docs/GPT_5_6_VS_5_5_ANALYSIS_2026-08-08.md",
    "docs/PROTOCOL_CARD.md",
    "docs/PROVIDER_ADAPTER_GUIDE.md",
    "docs/QUICKSTART.md",
    "docs/RANKINGS_2026-08-08.md",
    "docs/RESULTS_INTERPRETATION.md",
    "docs/SCHEMA_REFERENCE.md",
    "docs/STATISTICAL_ANALYSIS_PLAN.md",
    "docs/THREAT_MODEL.md",
    f"docs/data/{PUBLIC_RESULTS_STEM}.csv",
    f"docs/data/{PUBLIC_RESULTS_STEM}.json",
    "docs/data/SHA256SUMS",
    (
        FRONTIER_DATA_RELATIVE
        / f"{FRONTIER_RESULTS_STEM}.csv"
    ).as_posix(),
    (
        FRONTIER_DATA_RELATIVE
        / f"{FRONTIER_RESULTS_STEM}.json"
    ).as_posix(),
    (
        FRONTIER_DATA_RELATIVE
        / f"{FRONTIER_RESULTS_STEM}.md"
    ).as_posix(),
    (FRONTIER_DATA_RELATIVE / "SHA256SUMS").as_posix(),
    (
        FRONTIER_COMPANION_DATA_RELATIVE
        / f"{FRONTIER_COMPANION_RESULTS_STEM}.csv"
    ).as_posix(),
    (
        FRONTIER_COMPANION_DATA_RELATIVE
        / f"{FRONTIER_COMPANION_RESULTS_STEM}.json"
    ).as_posix(),
    (
        FRONTIER_COMPANION_DATA_RELATIVE
        / f"{FRONTIER_COMPANION_RESULTS_STEM}.md"
    ).as_posix(),
    (FRONTIER_COMPANION_DATA_RELATIVE / "SHA256SUMS").as_posix(),
    "examples/README.md",
    "examples/expected/toy-scorecards-summary.json",
    "examples/toy-observations.jsonl",
    "examples/toy-schedule.jsonl",
    "output/pdf/LLM_Benchmark_Protocol_1_0_White_Paper.pdf",
    "output/pdf/LLM_Benchmark_Protocol_1_0_White_Paper.resolved.md",
    "pyproject.toml",
    "scripts/export_frontier_companion_results.py",
    "src/kendr_bench/__init__.py",
    "templates/benchmark-card.md",
    "templates/deviation-log.csv",
    "templates/preregistration.md",
    "templates/system-card.yaml",
    "templates/threat-model.md",
    "whitepaper/KGBP_1_0_WHITE_PAPER.md",
)

REQUIRED_SCHEMA_FILES = frozenset(
    {
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
)

REQUIRED_PUBLIC_FIELDS = frozenset(
    {
        "rank",
        "division",
        "division_rank",
        "endpoint_id",
        "endpoint_label",
        "questions_scored",
        "operational_goodput",
        "quality_score",
        "availability",
        "successful_answers",
        "failed_answers",
        "latency_p50_ms",
        "cost_usd",
        "cost_is_lower_bound",
    }
)

EXCLUDED_WALK_PARTS = frozenset(
    {
        ".git",
        ".pytest_cache",
        ".venv",
        ".vendor",
        "__pycache__",
        "artifacts",
        "build",
        "dist",
        "outputs",
        "results",
        "tmp",
    }
)

SECRET_PATTERNS = (
    ("OpenAI-style API key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    (
        "private key",
        re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"),
    ),
    (
        "credential assignment",
        re.compile(
            r"(?im)^\s*[A-Z0-9_]*(?:API_KEY|TOKEN|SECRET|PASSWORD)\s*[:=]\s*"
            r"[\"']?[A-Za-z0-9_./+=-]{20,}[\"']?\s*$"
        ),
    ),
)

MARKDOWN_INLINE_LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
MARKDOWN_REFERENCE_LINK = re.compile(r"(?m)^\[[^\]]+\]:\s*(\S+)")
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")


@dataclass(frozen=True)
class CheckResult:
    """One release check and all problems found by it."""

    name: str
    problems: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.problems


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[Any]:
    rows: list[Any] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_number}: {exc}") from exc
    return rows


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _project_metadata(root: Path) -> dict[str, Any]:
    return tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))


def _module_version(path: Path) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if any(isinstance(target, ast.Name) and target.id == "__version__" for target in targets):
            value = ast.literal_eval(node.value)
            if isinstance(value, str):
                return value
    raise ValueError(f"{path} does not define a literal __version__")


def check_required_files(root: Path, version: str) -> list[str]:
    required = list(REQUIRED_FILES)
    required.append(f"docs/RELEASE_NOTES_v{version}.md")
    required.extend(f"config/{name}" for name in sorted(REQUIRED_SCHEMA_FILES))
    problems: list[str] = []
    for relative in sorted(set(required)):
        path = root / relative
        if not path.is_file():
            problems.append(f"missing required file: {relative}")
        elif path.stat().st_size == 0:
            problems.append(f"required file is empty: {relative}")
    problems.extend(_check_branding(root, version))
    return problems


def check_release_workflow_assets(root: Path) -> list[str]:
    """Require the frozen frontier publications in tagged release assets."""

    workflow_path = root / ".github/workflows/release-check.yml"
    if not workflow_path.is_file():
        return ["release workflow is missing"]
    workflow = workflow_path.read_text(encoding="utf-8")
    problems: list[str] = []
    for source, destination in REQUIRED_FRONTIER_RELEASE_ASSETS.items():
        command = f"cp {source} {destination}"
        if command not in workflow:
            problems.append(f"release workflow omits frontier asset command: {command}")
    if (
        "release-assets/frontier-2026-08-08-SHA256SUMS" not in workflow
        or "release-assets/frontier-preview-2026-08-08-SHA256SUMS" not in workflow
    ):
        problems.append("release workflow must give nested SHA manifests unique names")
    if "(cd release-assets && sha256sum * > SHA256SUMS)" not in workflow:
        problems.append("release workflow omits the release-wide SHA256SUMS manifest")
    return problems


def _check_branding(root: Path, version: str) -> list[str]:
    problems: list[str] = []
    logo_path = root / LOGO_RELATIVE_PATH
    if logo_path.is_file():
        data = logo_path.read_bytes()
        if not data.startswith(b"\x89PNG\r\n\x1a\n") or len(data) < 24:
            problems.append("Kendr logo is not a valid PNG")
        else:
            width = int.from_bytes(data[16:20], "big")
            height = int.from_bytes(data[20:24], "big")
            if (width, height) != (512, 512):
                problems.append(f"Kendr logo dimensions {(width, height)} != (512, 512)")

    required_attribution = (
        "README.md",
        "AUTHORS.md",
        "GLOBAL_BENCHMARK_PROTOCOL.md",
        "GOVERNANCE.md",
        "docs/PROTOCOL_CARD.md",
        f"docs/RELEASE_NOTES_v{version}.md",
        "whitepaper/KGBP_1_0_WHITE_PAPER.md",
        "output/pdf/LLM_Benchmark_Protocol_1_0_White_Paper.resolved.md",
    )
    for relative in required_attribution:
        path = root / relative
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        if RESEARCHER_NAME not in text:
            problems.append(f"{relative} does not credit {RESEARCHER_NAME}")
        if BRAND_NAME not in text:
            problems.append(f"{relative} does not identify {BRAND_NAME}")

    readme_path = root / "README.md"
    if readme_path.is_file() and LOGO_RELATIVE_PATH.as_posix() not in readme_path.read_text(
        encoding="utf-8"
    ):
        problems.append("README.md does not display the canonical Kendr logo")

    citation_path = root / "CITATION.cff"
    if citation_path.is_file():
        citation = citation_path.read_text(encoding="utf-8")
        for token in ('given-names: "Prashant Kumar"', 'family-names: "Dey"', 'affiliation: "Kendr"'):
            if token not in citation:
                problems.append(f"CITATION.cff is missing researcher token {token!r}")

    builder_path = root / "scripts/build_kgbp_whitepaper.py"
    if builder_path.is_file():
        builder = builder_path.read_text(encoding="utf-8")
        for name, rgb in CANONICAL_PDF_PALETTE.items():
            hex_value = "#" + "".join(f"{channel:02X}" for channel in rgb)
            if hex_value not in builder:
                problems.append(
                    f"white-paper builder is missing canonical {name} color {hex_value}"
                )
        for name, rgb in LEGACY_PDF_PALETTE.items():
            hex_value = "#" + "".join(f"{channel:02X}" for channel in rgb)
            if hex_value in builder:
                problems.append(
                    f"white-paper builder retains legacy {name} color {hex_value}"
                )

    for path in sorted(root.rglob("*")):
        if not path.is_file() or not _looks_textual(path):
            continue
        relative = path.relative_to(root)
        if any(part in EXCLUDED_WALK_PARTS for part in relative.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if LEGACY_DISPLAY_BRAND in text:
            problems.append(
                f"legacy display brand remains in {relative.as_posix()}"
            )
    return problems


def _cff_scalar(text: str, key: str) -> str | None:
    match = re.search(rf"(?m)^{re.escape(key)}:\s*(.+?)\s*$", text)
    if not match:
        return None
    value = match.group(1).strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"\"", "'"}:
        value = value[1:-1]
    return value


def check_versions(root: Path, expected_version: str | None, tag: str | None) -> list[str]:
    problems: list[str] = []
    metadata = _project_metadata(root)
    project = metadata.get("project", {})
    version = str(project.get("version") or "")
    if not SEMVER.fullmatch(version):
        problems.append(f"project.version is not valid Semantic Versioning: {version!r}")
    if expected_version is not None and version != expected_version:
        problems.append(f"project.version {version!r} != expected {expected_version!r}")
    module_version = _module_version(root / "src/kendr_bench/__init__.py")
    if module_version != version:
        problems.append(f"kendr_bench.__version__ {module_version!r} != project.version {version!r}")

    citation_text = (root / "CITATION.cff").read_text(encoding="utf-8")
    citation_version = _cff_scalar(citation_text, "version")
    if citation_version != version:
        problems.append(f"CITATION.cff version {citation_version!r} != project.version {version!r}")
    if _cff_scalar(citation_text, "title") != PROJECT_TITLE:
        problems.append(f"CITATION.cff title must be {PROJECT_TITLE!r}")

    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    if not re.search(rf"(?m)^## \[{re.escape(version)}\](?:\s|$)", changelog):
        problems.append(f"CHANGELOG.md has no [{version}] release section")
    notes = root / f"docs/RELEASE_NOTES_v{version}.md"
    if notes.is_file() and version not in notes.read_text(encoding="utf-8"):
        problems.append(f"{notes.relative_to(root)} does not mention version {version}")

    if tag is not None:
        expected_tag = f"v{version}"
        if tag != expected_tag:
            problems.append(f"release tag {tag!r} != expected {expected_tag!r}")
    return problems


def _iter_release_markdown(root: Path) -> Iterable[Path]:
    for path in root.rglob("*.md"):
        relative = path.relative_to(root)
        if any(part in EXCLUDED_WALK_PARTS for part in relative.parts):
            continue
        if path.is_file():
            yield path


def _clean_markdown_target(raw: str) -> str:
    target = raw.strip()
    if target.startswith("<") and ">" in target:
        return target[1 : target.index(">")]
    # Discard an optional Markdown title. Repository paths with spaces should
    # use angle brackets or percent encoding.
    return target.split(maxsplit=1)[0]


def _is_external_link(target: str) -> bool:
    lowered = target.lower()
    return lowered.startswith(("http://", "https://", "mailto:", "tel:", "data:", "#"))


def check_markdown_links(root: Path) -> list[str]:
    problems: list[str] = []
    for source in sorted(_iter_release_markdown(root)):
        text = source.read_text(encoding="utf-8")
        raw_targets = [*MARKDOWN_INLINE_LINK.findall(text), *MARKDOWN_REFERENCE_LINK.findall(text)]
        for raw_target in raw_targets:
            target = _clean_markdown_target(raw_target)
            if not target or _is_external_link(target):
                continue
            path_part = unquote(target.split("#", 1)[0]).replace("\\", "/")
            if not path_part:
                continue
            if path_part.startswith("/") or re.match(r"^[A-Za-z]:", path_part):
                problems.append(
                    f"{source.relative_to(root)} uses non-portable absolute link {target!r}"
                )
                continue
            resolved = (source.parent / path_part).resolve()
            try:
                resolved.relative_to(root.resolve())
            except ValueError:
                problems.append(f"{source.relative_to(root)} link escapes repository: {target!r}")
                continue
            if not resolved.exists():
                problems.append(f"{source.relative_to(root)} has missing local link: {target!r}")
    return problems


def check_json_and_schemas(root: Path) -> list[str]:
    problems: list[str] = []
    json_roots = (root / "config", root / "docs/data", root / "examples")
    for base in json_roots:
        if not base.exists():
            continue
        for path in sorted(base.rglob("*.json")):
            try:
                _read_json(path)
            except (OSError, json.JSONDecodeError) as exc:
                problems.append(f"invalid JSON in {path.relative_to(root)}: {exc}")
        for path in sorted(base.rglob("*.jsonl")):
            try:
                _read_jsonl(path)
            except (OSError, ValueError) as exc:
                problems.append(str(exc))

    try:
        from jsonschema import Draft202012Validator, FormatChecker
        from jsonschema.exceptions import SchemaError, ValidationError
    except ImportError:
        problems.append("jsonschema is unavailable; install project dependencies")
        return problems

    schema_paths = sorted((root / "config").glob("*-v1.schema.json"))
    names = {path.name for path in schema_paths}
    missing = sorted(REQUIRED_SCHEMA_FILES - names)
    unexpected = sorted(names - REQUIRED_SCHEMA_FILES)
    if missing:
        problems.append(f"missing schemas: {', '.join(missing)}")
    if unexpected:
        problems.append(f"unregistered schemas: {', '.join(unexpected)}")

    identifiers: dict[str, Path] = {}
    schemas: dict[str, dict[str, Any]] = {}
    for path in schema_paths:
        try:
            schema = _read_json(path)
            Draft202012Validator.check_schema(schema)
        except (OSError, json.JSONDecodeError, SchemaError) as exc:
            problems.append(f"invalid JSON Schema {path.relative_to(root)}: {exc}")
            continue
        if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            problems.append(f"{path.relative_to(root)} does not declare JSON Schema 2020-12")
        identifier = schema.get("$id")
        if not isinstance(identifier, str) or not identifier.startswith("https://"):
            problems.append(f"{path.relative_to(root)} has an invalid or missing $id")
        elif identifier in identifiers:
            problems.append(
                f"duplicate schema $id {identifier!r}: "
                f"{identifiers[identifier].relative_to(root)} and {path.relative_to(root)}"
            )
        else:
            identifiers[identifier] = path
        schemas[path.name] = schema

    protocol_schema = schemas.get("global-protocol-v1.schema.json")
    example_path = root / "config/global-protocol-v1.example.json"
    if protocol_schema is not None and example_path.is_file():
        try:
            Draft202012Validator(
                protocol_schema, format_checker=FormatChecker()
            ).validate(_read_json(example_path))
        except ValidationError as exc:
            location = ".".join(str(part) for part in exc.absolute_path) or "<root>"
            problems.append(f"global protocol example fails schema at {location}: {exc.message}")

    schedule_schema = schemas.get("schedule-cell-v1.schema.json")
    schedule_path = root / "examples/toy-schedule.jsonl"
    if schedule_schema is not None and schedule_path.is_file():
        validator = Draft202012Validator(schedule_schema, format_checker=FormatChecker())
        for index, row in enumerate(_read_jsonl(schedule_path), 1):
            for error in validator.iter_errors(row):
                problems.append(f"toy schedule row {index} fails schema: {error.message}")
    return problems


def _checksum_entries(path: Path) -> tuple[dict[str, str], list[str]]:
    entries: dict[str, str] = {}
    problems: list[str] = []
    for line_number, line in enumerate(path.read_text(encoding="ascii").splitlines(), 1):
        if not line.strip():
            continue
        match = re.fullmatch(r"([0-9a-f]{64})  ([^/\\]+)", line)
        if not match:
            problems.append(f"{path.name}:{line_number}: invalid SHA256SUMS entry")
            continue
        digest, name = match.groups()
        if name in entries:
            problems.append(f"{path.name}:{line_number}: duplicate entry {name!r}")
        entries[name] = digest
    return entries, problems


def _walk_keys(value: Any) -> Iterable[str]:
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield str(key)
            yield from _walk_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_keys(child)


def _walk_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for child in value.values():
            yield from _walk_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_strings(child)


def check_public_ranking(root: Path, version: str) -> list[str]:
    problems: list[str] = []
    data_dir = root / "docs/data"
    json_path = data_dir / f"{PUBLIC_RESULTS_STEM}.json"
    csv_path = data_dir / f"{PUBLIC_RESULTS_STEM}.csv"
    checksum_path = data_dir / "SHA256SUMS"
    ranking_path = root / "docs/RANKINGS_2026-08-08.md"
    if not all(path.is_file() for path in (json_path, csv_path, checksum_path, ranking_path)):
        return ["public ranking bundle is incomplete"]

    bundle = _read_json(json_path)
    if bundle.get("project") != PROJECT_TITLE:
        problems.append(f"public ranking project must be {PROJECT_TITLE!r}")
    if bundle.get("software_version") != PILOT_EXECUTION_VERSION:
        problems.append(
            "public ranking execution software_version "
            f"{bundle.get('software_version')!r} != {PILOT_EXECUTION_VERSION!r}; "
            f"publication release is {version!r}"
        )
    results = bundle.get("results")
    not_applicable = bundle.get("not_applicable")
    scope = bundle.get("scope") or {}
    sample = bundle.get("sample") or {}
    inference = bundle.get("pairwise_inference") or {}
    privacy = bundle.get("privacy_review") or {}
    if not isinstance(results, list):
        return [*problems, "public ranking results must be an array"]
    if not isinstance(not_applicable, list):
        problems.append("public ranking not_applicable must be an array")
        not_applicable = []

    ranked = int(scope.get("text_endpoints_ranked", -1))
    excluded = int(scope.get("not_applicable_entries", -1))
    catalog_entries = int(scope.get("catalog_entries", -1))
    if (catalog_entries, ranked, excluded) != (37, 35, 2):
        problems.append(
            "frozen public scope must remain 37 catalog entries, "
            "35 ranked text endpoints, and 2 not-applicable entries"
        )
    if len(results) != ranked:
        problems.append(f"public ranking has {len(results)} rows; scope declares {ranked}")
    if len(not_applicable) != excluded:
        problems.append(
            f"public ranking has {len(not_applicable)} not-applicable rows; scope declares {excluded}"
        )
    if ranked + excluded != catalog_entries:
        problems.append(
            f"ranked ({ranked}) + not applicable ({excluded}) != catalog entries ({catalog_entries})"
        )

    ranks = [row.get("rank") for row in results if isinstance(row, dict)]
    if ranks != list(range(1, len(results) + 1)):
        problems.append("public ranking ranks are not the ordered sequence 1..N")
    endpoint_ids = [str(row.get("endpoint_id") or "") for row in results if isinstance(row, dict)]
    if any(not value for value in endpoint_ids) or len(set(endpoint_ids)) != len(endpoint_ids):
        problems.append("public ranking endpoint_id values must be non-empty and unique")
    question_count = int(sample.get("questions", -1))
    division_ranks: defaultdict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(results, 1):
        if not isinstance(row, dict):
            problems.append(f"public ranking row {index} is not an object")
            continue
        missing_fields = sorted(REQUIRED_PUBLIC_FIELDS - set(row))
        if missing_fields:
            problems.append(f"public ranking row {index} is missing: {', '.join(missing_fields)}")
        if row.get("questions_scored") != question_count:
            problems.append(
                f"public ranking row {index} questions_scored "
                f"{row.get('questions_scored')!r} != sample questions {question_count}"
            )
        division_ranks[str(row.get("division"))].append(int(row.get("division_rank", -1)))
    for division, values in division_ranks.items():
        if values != list(range(1, len(values) + 1)):
            problems.append(f"division ranks are not consecutive for {division!r}")

    expected_comparisons = len(results) * (len(results) - 1) // 2
    if inference.get("comparisons") != expected_comparisons:
        problems.append(
            f"pairwise comparison count {inference.get('comparisons')!r} != {expected_comparisons}"
        )
    if inference.get("holm_rejections") != 0:
        problems.append(
            "frozen public inference must report zero Holm-adjusted rejections"
        )
    if any(privacy.get(key) is not False for key in (
        "raw_prompts_included",
        "raw_responses_included",
        "provider_request_ids_included",
        "local_paths_included",
    )):
        problems.append("public ranking privacy_review must explicitly exclude all raw/private fields")
    forbidden_keys = {
        "answer",
        "api_key",
        "authorization",
        "headers",
        "prompt",
        "provider_request_id",
        "raw_request",
        "raw_response",
        "response",
    }
    exposed = sorted({key.lower() for key in _walk_keys(bundle)} & forbidden_keys)
    if exposed:
        problems.append(f"public ranking exposes forbidden fields: {', '.join(exposed)}")

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        csv_rows = list(csv.DictReader(handle))
    if len(csv_rows) != len(results):
        problems.append(f"public CSV has {len(csv_rows)} rows; JSON has {len(results)}")
    csv_ids = [row.get("endpoint_id", "") for row in csv_rows]
    if csv_ids != endpoint_ids:
        problems.append("public CSV endpoint order does not match JSON")
    if [int(row.get("rank", -1)) for row in csv_rows] != list(range(1, len(results) + 1)):
        problems.append("public CSV ranks are not the ordered sequence 1..N")

    checksum_entries, checksum_problems = _checksum_entries(checksum_path)
    problems.extend(checksum_problems)
    expected_names = {json_path.name, csv_path.name}
    if set(checksum_entries) != expected_names:
        problems.append(
            f"SHA256SUMS entries {sorted(checksum_entries)} != expected {sorted(expected_names)}"
        )
    for name, expected_digest in checksum_entries.items():
        artifact = data_dir / name
        if artifact.is_file() and _sha256(artifact) != expected_digest:
            problems.append(f"checksum mismatch: docs/data/{name}")

    ranking_text = ranking_path.read_text(encoding="utf-8")
    if "0/595" not in ranking_text:
        problems.append("ranking handout omits the required 0/595 Holm disclosure")
    for endpoint_id in endpoint_ids:
        if f"`{endpoint_id}`" not in ranking_text:
            problems.append(f"ranking handout omits endpoint ID {endpoint_id!r}")
    for item in not_applicable:
        endpoint_id = str(item.get("id") or "") if isinstance(item, dict) else ""
        if endpoint_id and f"`{endpoint_id}`" not in ranking_text:
            problems.append(f"ranking handout omits not-applicable ID {endpoint_id!r}")
    return problems


def check_frontier_ranking(root: Path, version: str) -> list[str]:
    """Validate the dated current-frontier public aggregate bundle."""

    problems: list[str] = []
    data_dir = root / FRONTIER_DATA_RELATIVE
    json_path = data_dir / f"{FRONTIER_RESULTS_STEM}.json"
    csv_path = data_dir / f"{FRONTIER_RESULTS_STEM}.csv"
    markdown_path = data_dir / f"{FRONTIER_RESULTS_STEM}.md"
    checksum_path = data_dir / "SHA256SUMS"
    handout_path = root / "docs/FRONTIER_EXECUTION_LEADERBOARD_2026-08-08.md"
    required = (json_path, csv_path, markdown_path, checksum_path, handout_path)
    if not all(path.is_file() for path in required):
        return ["frontier ranking bundle is incomplete"]

    bundle = _read_json(json_path)
    if bundle.get("project") != PROJECT_TITLE:
        problems.append(f"frontier ranking project must be {PROJECT_TITLE!r}")
    if bundle.get("matrix_id") != FRONTIER_MATRIX_ID:
        problems.append("frontier ranking matrix id is not the frozen release id")
    software = bundle.get("execution_software") or {}
    if software.get("package") != PROJECT_DISTRIBUTION:
        problems.append("frontier ranking execution package is incorrect")
    if software.get("version") != FRONTIER_EXECUTION_VERSION:
        problems.append(
            "frontier ranking execution version "
            f"{software.get('version')!r} != frozen execution version "
            f"{FRONTIER_EXECUTION_VERSION!r}; publication release is {version!r}"
        )
    if software.get("source_repository") != CANONICAL_REPOSITORY:
        problems.append("frontier ranking source repository is not canonical")
    if not re.fullmatch(r"[0-9a-f]{40}", str(software.get("source_commit") or "")):
        problems.append("frontier ranking source commit is not a full Git SHA")
    if software.get("source_worktree_dirty") is not False:
        problems.append("frontier ranking execution worktree must be recorded clean")

    rows = bundle.get("rows")
    if not isinstance(rows, list):
        return [*problems, "frontier ranking rows must be an array"]
    scope = bundle.get("scope") or {}
    expected_scope = {
        "profile_entries": 14,
        "core_ga_candidates": 11,
        "scored_core_ga_candidates": 5,
        "not_measured_core_ga_candidates": 6,
        "scored_baselines": 1,
        "preview_companion_entries": 2,
        "scored_preview_companion_entries": 0,
    }
    for key, value in expected_scope.items():
        if scope.get(key) != value:
            problems.append(
                f"frontier ranking scope {key}={scope.get(key)!r}, expected {value}"
            )
    if len(rows) != expected_scope["profile_entries"]:
        problems.append(
            f"frontier ranking has {len(rows)} rows; expected "
            f"{expected_scope['profile_entries']}"
        )

    scored = [
        row
        for row in rows
        if isinstance(row, Mapping) and row.get("benchmark_status") == "scored"
    ]
    candidates = [row for row in scored if row.get("role") == "candidate"]
    baselines = [row for row in scored if row.get("role") == "baseline"]
    not_measured = [
        row
        for row in rows
        if isinstance(row, Mapping)
        and row.get("benchmark_status") == "not_measured"
    ]
    if len(candidates) != 5 or [row.get("rank") for row in candidates] != list(
        range(1, 6)
    ):
        problems.append("frontier candidate ranks must be the ordered sequence 1..5")
    if len(baselines) != 1 or baselines[0].get("rank") is not None:
        problems.append("frontier GPT-5.5 baseline must be scored and unranked")
    if len(not_measured) != 8:
        problems.append("frontier bundle must retain eight explicit N/A rows")
    for row in not_measured:
        if row.get("operational_goodput") is not None:
            problems.append("frontier N/A rows cannot carry a goodput score")
        if not str(row.get("n_a_reason") or "").strip():
            problems.append("frontier N/A rows must carry a reason")

    scored_ids = [str(row.get("endpoint_id") or "") for row in scored]
    if any(not value for value in scored_ids) or len(set(scored_ids)) != len(
        scored_ids
    ):
        problems.append("frontier scored endpoint ids must be non-empty and unique")
    sample = bundle.get("sample") or {}
    if sample.get("questions") != 15 or sample.get("questions_per_task") != 3:
        problems.append("frontier sample must remain 15 questions, three per task")
    inference = bundle.get("pairwise_inference") or {}
    if inference.get("comparisons") != 15 or inference.get("holm_rejections") != 2:
        problems.append(
            "frontier inference must report 15 comparisons and two Holm rejections"
        )

    privacy = bundle.get("privacy_review") or {}
    privacy_fields = (
        "raw_prompts_included",
        "raw_responses_included",
        "provider_request_ids_included",
        "local_paths_included",
        "provider_error_messages_included",
    )
    if any(privacy.get(key) is not False for key in privacy_fields):
        problems.append(
            "frontier privacy_review must explicitly exclude all raw/private fields"
        )
    forbidden_keys = {
        "answer",
        "api_key",
        "authorization",
        "headers",
        "prompt",
        "provider_request_id",
        "raw_request",
        "raw_response",
        "response",
    }
    exposed = sorted({key.lower() for key in _walk_keys(bundle)} & forbidden_keys)
    if exposed:
        problems.append(f"frontier ranking exposes forbidden fields: {', '.join(exposed)}")

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        csv_rows = list(csv.DictReader(handle))
    if len(csv_rows) != len(rows):
        problems.append(
            f"frontier CSV has {len(csv_rows)} rows; JSON has {len(rows)}"
        )

    checksum_entries, checksum_problems = _checksum_entries(checksum_path)
    problems.extend(checksum_problems)
    expected_names = {json_path.name, csv_path.name, markdown_path.name}
    if set(checksum_entries) != expected_names:
        problems.append(
            "frontier SHA256SUMS entries "
            f"{sorted(checksum_entries)} != expected {sorted(expected_names)}"
        )
    for name, expected_digest in checksum_entries.items():
        artifact = data_dir / name
        if artifact.is_file() and _sha256(artifact) != expected_digest:
            problems.append(f"checksum mismatch: {FRONTIER_DATA_RELATIVE / name}")

    handout = handout_path.read_text(encoding="utf-8")
    if FRONTIER_MATRIX_ID not in handout:
        problems.append("frontier handout omits the matrix id")
    for endpoint_id in scored_ids:
        if f"`{endpoint_id}`" not in handout:
            problems.append(f"frontier handout omits endpoint ID {endpoint_id!r}")
    return problems


def check_frontier_companion(root: Path, version: str) -> list[str]:
    """Validate the separate, descriptive current-frontier preview bundle."""

    problems: list[str] = []
    data_dir = root / FRONTIER_COMPANION_DATA_RELATIVE
    json_path = data_dir / f"{FRONTIER_COMPANION_RESULTS_STEM}.json"
    csv_path = data_dir / f"{FRONTIER_COMPANION_RESULTS_STEM}.csv"
    markdown_path = data_dir / f"{FRONTIER_COMPANION_RESULTS_STEM}.md"
    checksum_path = data_dir / "SHA256SUMS"
    profile_path = root / "config/kendr-current-frontier-profile-20260808.json"
    panel_path = root / "config/kendr-frontier-preview-execution-panel-20260808.json"
    public_surfaces = (
        root / "README.md",
        root / "docs/FRONTIER_EXECUTION_LEADERBOARD_2026-08-08.md",
        root / "docs/CURRENT_FRONTIER_PANEL_2026-08-08.md",
        root / "docs/FRONTIER_MODEL_COVERAGE_2026-08-08.md",
    )
    required = (
        json_path,
        csv_path,
        markdown_path,
        checksum_path,
        profile_path,
        panel_path,
        *public_surfaces,
    )
    missing = [
        path.relative_to(root).as_posix() for path in required if not path.is_file()
    ]
    if missing:
        return ["frontier companion bundle is incomplete: " + ", ".join(missing)]

    bundle = _read_json(json_path)
    expected_identity = {
        "schema_version": "1.0",
        "project": PROJECT_TITLE,
        "protocol_profile": "KGBP-1.0",
        "campaign_type": "current-frontier-preview-companion",
        "matrix_id": FRONTIER_COMPANION_MATRIX_ID,
        "profile_id": "kendr-current-frontier-20260808",
        "snapshot_date": "2026-08-08",
        "livebench_release": "2026-06-25",
    }
    for key, expected in expected_identity.items():
        if bundle.get(key) != expected:
            problems.append(
                f"frontier companion {key}={bundle.get(key)!r}, expected {expected!r}"
            )
    expected_cohort = {
        "id": "preview-companion",
        "claim_class": "preview-or-limited-access",
    }
    if bundle.get("cohort") != expected_cohort:
        problems.append("frontier companion cohort identity is incorrect")

    software = bundle.get("execution_software") or {}
    expected_software = {
        "package": PROJECT_DISTRIBUTION,
        "version": FRONTIER_COMPANION_EXECUTION_VERSION,
        "source_repository": CANONICAL_REPOSITORY,
        "source_commit": FRONTIER_COMPANION_SOURCE_COMMIT,
        "source_worktree_dirty": False,
    }
    if software != expected_software:
        problems.append(
            "frontier companion execution software/provenance identity is incorrect; "
            f"execution remains {FRONTIER_COMPANION_EXECUTION_VERSION!r} while "
            f"publication is {version!r}"
        )

    sample = bundle.get("sample") or {}
    expected_tasks = [
        "live_bench/data_analysis/tablejoin",
        "live_bench/instruction_following/summarize",
        "live_bench/language/connections",
        "live_bench/math/math_comp",
        "live_bench/reasoning/zebra_puzzle",
    ]
    expected_sample_fields = {
        "mode": "seeded-random",
        "seed": 20260807,
        "content_hash_algorithm": "sha256",
        "questions": 15,
        "questions_per_task": 3,
        "generations_per_endpoint_question": 1,
    }
    for key, expected in expected_sample_fields.items():
        if sample.get(key) != expected:
            problems.append(
                f"frontier companion sample {key}={sample.get(key)!r}, "
                f"expected {expected!r}"
            )
    if sample.get("tasks") != expected_tasks:
        problems.append("frontier companion task strata changed")
    if sample.get("selected_date_distribution") != {
        "2024-06-24": 6,
        "2024-11-25": 9,
    }:
        problems.append("frontier companion item-date distribution changed")
    if not re.fullmatch(r"[0-9a-f]{64}", str(sample.get("content_hash") or "")):
        problems.append("frontier companion sample content hash is not SHA-256")

    execution_configuration = bundle.get("execution_configuration") or {}
    expected_execution_configuration = {
        "requested_max_output_tokens": 2048,
        "deadline_ms": 120000,
        "max_cost_usd_per_answer": None,
        "parallel_requests": 2,
        "parallel_grading": 4,
        "requested_reasoning_effort": "none",
    }
    if execution_configuration != expected_execution_configuration:
        problems.append("frontier companion execution configuration changed")

    expected_scope = {
        "companion_profile_entries": 2,
        "scored_companion_entries": 1,
        "not_measured_companion_entries": 1,
        "ga_or_baseline_entries": 0,
    }
    if bundle.get("scope") != expected_scope:
        problems.append(
            "frontier companion scope must remain 2 entries: 1 scored, 1 N/A"
        )
    ranking = bundle.get("ranking") or {}
    if ranking.get("status") != "single-scored-endpoint-descriptive-no-rank":
        problems.append("frontier companion must retain descriptive no-rank status")
    inference = bundle.get("pairwise_inference") or {}
    if inference.get("comparisons") != 0 or inference.get("tests") != []:
        problems.append("frontier companion must not contain pairwise tests")
    readiness = bundle.get("claim_readiness") or {}
    if readiness.get("companion_claim_ready") is not False:
        problems.append("frontier companion must remain explicitly not claim-ready")

    rows = bundle.get("rows")
    if not isinstance(rows, list):
        return [*problems, "frontier companion rows must be an array"]
    if len(rows) != 2:
        problems.append(f"frontier companion has {len(rows)} rows; expected 2")
    row_objects = [row for row in rows if isinstance(row, Mapping)]
    if len(row_objects) != len(rows):
        problems.append("frontier companion rows must all be objects")
    endpoint_ids = [str(row.get("endpoint_id") or "") for row in row_objects]
    expected_endpoint_ids = [
        "kc-gemini-3.1-pro-preview",
        "kc-qwen3.8-max-preview",
    ]
    if endpoint_ids != expected_endpoint_ids:
        problems.append("frontier companion endpoint identity/order changed")
    if [row.get("display_order") for row in row_objects] != [1, 2]:
        problems.append("frontier companion display order must remain 1, 2")

    forbidden_rank_fields = {"rank", "companion_rank", "execution_rank", "tier"}
    for index, row in enumerate(row_objects, 1):
        exposed_rank_fields = sorted(set(row) & forbidden_rank_fields)
        if exposed_rank_fields:
            problems.append(
                f"frontier companion row {index} exposes rank/tier fields: "
                + ", ".join(exposed_rank_fields)
            )
        if row.get("cohort") != "preview-companion":
            problems.append(f"frontier companion row {index} has the wrong cohort")
        if row.get("claim_class") != "preview-or-limited-access":
            problems.append(f"frontier companion row {index} has the wrong claim class")

    rows_by_id = {str(row.get("endpoint_id")): row for row in row_objects}
    gemini = rows_by_id.get("kc-gemini-3.1-pro-preview") or {}
    expected_gemini = {
        "vendor_model_id": "gemini-3.1-pro-preview",
        "benchmark_status": "scored",
        "catalog_status": "present",
        "questions_scored": 15,
        "operational_goodput": 0.3977777777777778,
        "operational_goodput_ci95_low": 0.16666666666666666,
        "operational_goodput_ci95_high": 0.6511111111111111,
        "conditional_quality_score": 0.3977777777777778,
        "availability": 1.0,
        "successful_answers": 15,
        "failed_answers": 0,
        "missing_answers": 0,
        "n_a_reason_code": None,
        "n_a_reason": None,
    }
    for key, expected in expected_gemini.items():
        if gemini.get(key) != expected:
            problems.append(
                f"Gemini companion {key}={gemini.get(key)!r}, expected {expected!r}"
            )

    qwen = rows_by_id.get("kc-qwen3.8-max-preview") or {}
    if qwen.get("vendor_model_id") != "qwen3.8-max-preview":
        problems.append("Qwen companion vendor identity changed")
    if qwen.get("benchmark_status") != "not_measured":
        problems.append("Qwen companion must remain not measured")
    if qwen.get("catalog_status") != "missing":
        problems.append("Qwen companion catalog status must remain missing")
    if qwen.get("n_a_reason_code") != "missing":
        problems.append("Qwen companion must retain the missing reason code")
    expected_qwen_reason = (
        "The exact preview route is staged fail-closed, but it requires a "
        "dedicated paid Model Studio Token Plan endpoint and credential that "
        "are not configured."
    )
    if qwen.get("n_a_reason") != expected_qwen_reason:
        problems.append("Qwen companion N/A reason changed")
    null_qwen_fields = (
        "questions_scored",
        "operational_goodput",
        "operational_goodput_ci95_low",
        "operational_goodput_ci95_high",
        "quality_score",
        "quality_ci95_low",
        "quality_ci95_high",
        "conditional_quality_score",
        "availability",
        "successful_answers",
        "failed_answers",
        "missing_answers",
        "latency_p50_ms",
        "latency_p95_ms",
        "cost_usd",
    )
    non_null_qwen_fields = [
        key for key in null_qwen_fields if qwen.get(key) is not None
    ]
    if non_null_qwen_fields:
        problems.append(
            "Qwen companion N/A row contains metrics: "
            + ", ".join(non_null_qwen_fields)
        )

    provenance = bundle.get("provenance") or {}
    for key, expected in FRONTIER_COMPANION_PROVENANCE.items():
        if provenance.get(key) != expected:
            problems.append(
                f"frontier companion provenance {key}={provenance.get(key)!r}, "
                f"expected {expected!r}"
            )
    if set(provenance) != set(FRONTIER_COMPANION_PROVENANCE):
        problems.append("frontier companion provenance field set changed")
    if provenance.get("profile_sha256") != _sha256(profile_path):
        problems.append(
            "frontier companion profile hash does not match the profile file"
        )
    if provenance.get("execution_panel_sha256") != _sha256(panel_path):
        problems.append("frontier companion panel hash does not match the panel file")

    privacy = bundle.get("privacy_review") or {}
    privacy_fields = (
        "raw_prompts_included",
        "raw_responses_included",
        "provider_request_ids_included",
        "provider_error_messages_included",
        "local_paths_included",
    )
    if set(privacy) != set(privacy_fields) or any(
        privacy.get(key) is not False for key in privacy_fields
    ):
        problems.append(
            "frontier companion privacy_review must explicitly exclude all "
            "raw/private fields"
        )
    forbidden_keys = {
        "answer",
        "api_key",
        "authorization",
        "headers",
        "prompt",
        "provider_error_message",
        "provider_request_id",
        "raw_request",
        "raw_response",
        "response",
    }
    exposed = sorted({key.lower() for key in _walk_keys(bundle)} & forbidden_keys)
    if exposed:
        problems.append(
            "frontier companion exposes forbidden fields: " + ", ".join(exposed)
        )
    local_path_patterns = (
        re.compile(r"(?i)\bfile://"),
        re.compile(r"(?<![A-Za-z0-9])(?:[A-Za-z]:[\\/]|\\\\[^\\/])"),
        re.compile(r"(?<![A-Za-z0-9])/(?:Users|home|tmp|var/tmp)/"),
    )
    if any(
        pattern.search(value)
        for value in _walk_strings(bundle)
        for pattern in local_path_patterns
    ):
        problems.append("frontier companion JSON exposes a machine-local path")

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        csv_rows = list(reader)
        csv_fields = set(reader.fieldnames or [])
    if len(csv_rows) != 2:
        problems.append(f"frontier companion CSV has {len(csv_rows)} rows; expected 2")
    if [row.get("endpoint_id") for row in csv_rows] != expected_endpoint_ids:
        problems.append("frontier companion CSV endpoint order does not match JSON")
    exposed_csv_rank_fields = sorted(csv_fields & forbidden_rank_fields)
    if exposed_csv_rank_fields:
        problems.append(
            "frontier companion CSV exposes rank/tier fields: "
            + ", ".join(exposed_csv_rank_fields)
        )
    required_csv_fields = {
        "display_order",
        "benchmark_status",
        "catalog_status",
        "endpoint_id",
        "vendor_model_id",
        "operational_goodput",
        "operational_goodput_ci95_low",
        "operational_goodput_ci95_high",
        "availability",
        "successful_answers",
        "failed_answers",
        "n_a_reason_code",
        "n_a_reason",
    }
    if not required_csv_fields <= csv_fields:
        problems.append(
            "frontier companion CSV is missing fields: "
            + ", ".join(sorted(required_csv_fields - csv_fields))
        )
    if csv_rows:
        expected_gemini_csv = {
            "benchmark_status": "scored",
            "operational_goodput": "0.3977777777777778",
            "operational_goodput_ci95_low": "0.16666666666666666",
            "operational_goodput_ci95_high": "0.6511111111111111",
            "availability": "1.0",
            "successful_answers": "15",
            "failed_answers": "0",
        }
        for key, expected in expected_gemini_csv.items():
            if csv_rows[0].get(key) != expected:
                problems.append(
                    f"frontier companion CSV Gemini {key}="
                    f"{csv_rows[0].get(key)!r}, expected {expected!r}"
                )
    if len(csv_rows) > 1:
        qwen_csv_metrics = (
            "operational_goodput",
            "operational_goodput_ci95_low",
            "operational_goodput_ci95_high",
            "availability",
            "successful_answers",
            "failed_answers",
        )
        if any(csv_rows[1].get(key) != "N/A" for key in qwen_csv_metrics):
            problems.append("frontier companion CSV Qwen metrics must render as N/A")
        if csv_rows[1].get("n_a_reason_code") != "missing":
            problems.append("frontier companion CSV Qwen reason code must be missing")

    checksum_entries, checksum_problems = _checksum_entries(checksum_path)
    problems.extend(checksum_problems)
    if checksum_entries != FRONTIER_COMPANION_ARTIFACT_SHA256:
        problems.append(
            "frontier companion SHA256SUMS does not match the pinned release digests"
        )
    for name, expected_digest in checksum_entries.items():
        artifact = data_dir / name
        if not artifact.is_file():
            problems.append(f"frontier companion checksum target is missing: {name}")
        elif _sha256(artifact) != expected_digest:
            problems.append(
                f"checksum mismatch: {FRONTIER_COMPANION_DATA_RELATIVE / name}"
            )

    markdown = markdown_path.read_text(encoding="utf-8")
    required_markdown_fragments = (
        FRONTIER_COMPANION_MATRIX_ID,
        "`kc-gemini-3.1-pro-preview`",
        "`kc-qwen3.8-max-preview`",
        "Not assigned (single row)",
        "39.78%",
        "16.67% to 65.11%",
        "100.00%",
        "15 / 15",
        "No pairwise test exists",
        FRONTIER_COMPANION_SOURCE_COMMIT,
    )
    for fragment in required_markdown_fragments:
        if fragment not in markdown:
            problems.append(
                f"frontier companion Markdown omits required content {fragment!r}"
            )
    for path in (json_path, csv_path, markdown_path):
        text = path.read_text(encoding="utf-8")
        if any(pattern.search(text) for pattern in local_path_patterns):
            problems.append(
                f"frontier companion artifact exposes a machine-local path: {path.name}"
            )

    companion_handout_name = f"{FRONTIER_COMPANION_RESULTS_STEM}.md"
    for path in public_surfaces:
        text = path.read_text(encoding="utf-8")
        if FRONTIER_COMPANION_MATRIX_ID not in text:
            problems.append(
                f"{path.relative_to(root).as_posix()} omits the companion matrix id"
            )
        if companion_handout_name not in text:
            problems.append(
                f"{path.relative_to(root).as_posix()} omits the companion handout link"
            )
        if "39.78%" not in text:
            problems.append(
                f"{path.relative_to(root).as_posix()} omits Gemini companion goodput"
            )
    return problems


def check_whitepaper_artifacts(root: Path) -> list[str]:
    problems: list[str] = []
    pdf_path = root / "output/pdf/LLM_Benchmark_Protocol_1_0_White_Paper.pdf"
    resolved_path = root / "output/pdf/LLM_Benchmark_Protocol_1_0_White_Paper.resolved.md"
    source_path = root / "whitepaper/KGBP_1_0_WHITE_PAPER.md"
    if pdf_path.is_file():
        if pdf_path.stat().st_size < 10_000:
            problems.append("white-paper PDF is unexpectedly small")
        elif not pdf_path.read_bytes().startswith(b"%PDF-"):
            problems.append("white-paper PDF does not have a PDF file signature")
        else:
            try:
                from pypdf import PdfReader
                from pypdf.generic import ContentStream

                reader = PdfReader(pdf_path)
                metadata = reader.metadata
                if not metadata or RESEARCHER_NAME not in str(metadata.author or ""):
                    problems.append(
                        f"white-paper PDF author must credit {RESEARCHER_NAME!r}"
                    )
                cover_text = reader.pages[0].extract_text() or ""
                if RESEARCHER_NAME not in cover_text or BRAND_NAME not in cover_text:
                    problems.append("white-paper PDF cover has incomplete Kendr attribution")
                resources = reader.pages[0].get("/Resources") or {}
                xobjects = resources.get("/XObject") or {}
                image_count = sum(
                    1
                    for item in xobjects.values()
                    if item.get_object().get("/Subtype") == "/Image"
                )
                if image_count < 1:
                    problems.append("white-paper PDF cover does not embed the Kendr logo")
                palette_counts: defaultdict[tuple[int, int, int], int] = defaultdict(int)
                for page in reader.pages:
                    content = page.get_contents()
                    if content is None:
                        continue
                    stream = ContentStream(content, reader)
                    for operands, operator in stream.operations:
                        if operator not in (b"rg", b"RG") or len(operands) != 3:
                            continue
                        rgb = tuple(round(float(value) * 255) for value in operands)
                        palette_counts[rgb] += 1
                for name, rgb in CANONICAL_PDF_PALETTE.items():
                    if palette_counts[rgb] == 0:
                        problems.append(
                            f"white-paper PDF does not use canonical {name} color {rgb}"
                        )
                for name, rgb in LEGACY_PDF_PALETTE.items():
                    if palette_counts[rgb] != 0:
                        problems.append(
                            f"white-paper PDF retains legacy {name} color {rgb}"
                        )
            except ImportError:
                problems.append("pypdf is unavailable; install documentation dependencies")
            except Exception as exc:
                problems.append(f"unable to inspect white-paper PDF branding: {exc}")
    if resolved_path.is_file():
        resolved = resolved_path.read_text(encoding="utf-8")
        if "{{CAMPAIGN_RESULTS}}" in resolved:
            problems.append("resolved white-paper Markdown still contains campaign placeholder")
        if PROJECT_TITLE not in resolved:
            problems.append(f"resolved white-paper Markdown does not name {PROJECT_TITLE}")
    if source_path.is_file() and "{{CAMPAIGN_RESULTS}}" not in source_path.read_text(
        encoding="utf-8"
    ):
        problems.append("white-paper source is missing its generated campaign placeholder")
    return problems


def _git_paths(root: Path, *, include_untracked: bool) -> list[Path]:
    command = ["git", "ls-files", "-z", "--cached"]
    if include_untracked:
        command.extend(["--others", "--exclude-standard"])
    completed = subprocess.run(
        command,
        cwd=root,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return [root / value.decode("utf-8") for value in completed.stdout.split(b"\0") if value]


def _is_forbidden_release_path(relative: Path) -> bool:
    lowered = tuple(part.lower() for part in relative.parts)
    name = relative.name.lower()
    if name.startswith(".env") and name != ".env.example":
        return True
    if lowered and lowered[0] in {"artifacts", "outputs", "results"}:
        return True
    if name.endswith((".key", ".p12", ".pem", ".pfx")):
        return True
    if re.match(r"^(credentials|secrets).*\.json$", name):
        return True
    if name in {"answers.jsonl", "attempts.jsonl", "calls.jsonl", "judgments.jsonl"}:
        return True
    return False


def _looks_textual(path: Path) -> bool:
    return path.suffix.lower() in {
        ".cff",
        ".csv",
        ".json",
        ".jsonl",
        ".md",
        ".py",
        ".toml",
        ".txt",
        ".yaml",
        ".yml",
    } or path.name in {"LICENSE", "SHA256SUMS", ".env.example"}


def check_repository_safety(root: Path) -> list[str]:
    problems: list[str] = []
    try:
        tracked = _git_paths(root, include_untracked=False)
        candidates = _git_paths(root, include_untracked=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        return [f"unable to enumerate Git release files: {exc}"]

    for path in tracked:
        relative = path.relative_to(root)
        if _is_forbidden_release_path(relative):
            problems.append(f"forbidden tracked path: {relative.as_posix()}")
    for path in candidates:
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if _is_forbidden_release_path(relative):
            problems.append(f"forbidden release-candidate path: {relative.as_posix()}")
            continue
        if path.stat().st_size > 50 * 1024 * 1024:
            problems.append(f"release-candidate file exceeds 50 MiB: {relative.as_posix()}")
            continue
        if not _looks_textual(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            problems.append(f"text release candidate is not UTF-8: {relative.as_posix()}")
            continue
        for description, pattern in SECRET_PATTERNS:
            if pattern.search(text):
                problems.append(f"possible {description} in {relative.as_posix()}")
    return sorted(set(problems))


def _dependency_names(values: Iterable[str]) -> set[str]:
    names: set[str] = set()
    for value in values:
        match = re.match(r"\s*([A-Za-z0-9_.-]+)", value)
        if match:
            names.add(match.group(1).lower().replace("_", "-"))
    return names


def check_package_metadata(root: Path, version: str) -> list[str]:
    problems: list[str] = []
    metadata = _project_metadata(root)
    project = metadata.get("project") or {}
    if project.get("name") != PROJECT_DISTRIBUTION:
        problems.append(f"project.name must be {PROJECT_DISTRIBUTION!r}")
    if project.get("version") != version:
        problems.append("project.version changed during verification")
    if project.get("readme") != "README.md":
        problems.append("project.readme must be README.md")
    authors = project.get("authors") or []
    if not any(item.get("name") == RESEARCHER_NAME for item in authors if isinstance(item, dict)):
        problems.append(f"project.authors must credit {RESEARCHER_NAME}")
    maintainers = project.get("maintainers") or []
    if not any(item.get("name") == BRAND_NAME for item in maintainers if isinstance(item, dict)):
        problems.append(f"project.maintainers must identify {BRAND_NAME}")
    license_value = project.get("license")
    if not isinstance(license_value, dict) or license_value.get("file") != "LICENSE":
        problems.append("project.license must reference LICENSE")
    if not str(project.get("requires-python") or "").startswith(">=3.11"):
        problems.append("project.requires-python must declare Python >=3.11")
    dependencies = _dependency_names(project.get("dependencies") or [])
    missing_dependencies = {"jsonschema", "openai", "python-dotenv"} - dependencies
    if missing_dependencies:
        problems.append(f"missing runtime dependencies: {', '.join(sorted(missing_dependencies))}")

    urls = project.get("urls") or {}
    for label in ("Homepage", "Documentation", "Issues", "Source"):
        value = str(urls.get(label) or "")
        if not value.startswith(CANONICAL_REPOSITORY):
            problems.append(f"project.urls.{label} is not under {CANONICAL_REPOSITORY}")

    scripts = project.get("scripts") or {}
    expected_scripts = {
        "llm-benchmark": "kendr_bench.cli:main",
        "llm-benchmark-livebench": "kendr_bench.livebench_cli:main",
        "llm-benchmark-matrix": "kendr_bench.matrix_cli:main",
        "llm-benchmark-protocol": "kendr_bench.protocol_cli:main",
        "kendr-bench": "kendr_bench.cli:main",
        "kendr-livebench": "kendr_bench.livebench_cli:main",
        "kendr-benchmark-matrix": "kendr_bench.matrix_cli:main",
        "kendr-protocol": "kendr_bench.protocol_cli:main",
    }
    for name, target in expected_scripts.items():
        if scripts.get(name) != target:
            problems.append(f"project.scripts.{name} must be {target!r}")

    force_include = (
        metadata.get("tool", {})
        .get("hatch", {})
        .get("build", {})
        .get("targets", {})
        .get("wheel", {})
        .get("force-include", {})
    )
    if not isinstance(force_include, dict):
        problems.append("wheel.force-include must be a table")
        return problems
    destinations: set[str] = set()
    for source, destination in force_include.items():
        if not (root / source).is_file():
            problems.append(f"wheel force-include source is missing: {source}")
        if not str(destination).startswith("kendr_bench/"):
            problems.append(f"wheel force-include destination escapes package: {destination}")
        if destination in destinations:
            problems.append(f"duplicate wheel force-include destination: {destination}")
        destinations.add(destination)
    included_schema_names = {
        Path(source).name for source in force_include if str(source).endswith(".schema.json")
    }
    if included_schema_names != REQUIRED_SCHEMA_FILES:
        problems.append("wheel force-include schema set does not match the public schema set")

    sdist = (
        metadata.get("tool", {})
        .get("hatch", {})
        .get("build", {})
        .get("targets", {})
        .get("sdist", {})
    )
    sdist_excludes = {str(value).rstrip("/") for value in sdist.get("exclude", [])}
    required_excludes = {
        "/.claude",
        "/.vendor",
        "/.venv",
        "/build",
        "/dist",
        "/results",
        "/tmp",
    }
    missing_excludes = sorted(required_excludes - sdist_excludes)
    if missing_excludes:
        problems.append(
            "sdist does not exclude local/private paths: "
            + ", ".join(missing_excludes)
        )
    sdist_includes = {str(value).rstrip("/") for value in sdist.get("include", [])}
    if "/assets" not in sdist_includes:
        problems.append("sdist does not include the Kendr brand asset directory")
    return problems


def _run_check(name: str, function: Callable[[], list[str]]) -> CheckResult:
    try:
        return CheckResult(name=name, problems=tuple(function()))
    except Exception as exc:  # pragma: no cover - final defensive reporting path
        return CheckResult(name=name, problems=(f"unexpected verifier error: {exc}",))


def verify_release(
    root: Path,
    *,
    expected_version: str | None = None,
    tag: str | None = None,
) -> list[CheckResult]:
    """Run all offline release checks and return structured results."""
    root = root.resolve()
    metadata = _project_metadata(root)
    version = str((metadata.get("project") or {}).get("version") or "")
    checks: list[tuple[str, Callable[[], list[str]]]] = [
        ("required files", lambda: check_required_files(root, version)),
        ("release workflow assets", lambda: check_release_workflow_assets(root)),
        ("version consistency", lambda: check_versions(root, expected_version, tag)),
        ("internal Markdown links", lambda: check_markdown_links(root)),
        ("JSON and schemas", lambda: check_json_and_schemas(root)),
        ("public ranking bundle", lambda: check_public_ranking(root, version)),
        ("frontier ranking bundle", lambda: check_frontier_ranking(root, version)),
        ("frontier companion bundle", lambda: check_frontier_companion(root, version)),
        ("white-paper artifacts", lambda: check_whitepaper_artifacts(root)),
        ("repository safety", lambda: check_repository_safety(root)),
        ("package metadata", lambda: check_package_metadata(root, version)),
    ]
    return [_run_check(name, function) for name, function in checks]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root (defaults to the parent of scripts/).",
    )
    parser.add_argument(
        "--expected-version",
        help="Require this software version in package, module, citation, and release files.",
    )
    parser.add_argument(
        "--tag",
        help="Require an exact vMAJOR.MINOR.PATCH tag matching project.version.",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable results.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    results = verify_release(
        args.root,
        expected_version=args.expected_version,
        tag=args.tag,
    )
    failed = [result for result in results if not result.passed]
    if args.json:
        print(
            json.dumps(
                {
                    "ok": not failed,
                    "checks": [
                        {
                            "name": result.name,
                            "ok": result.passed,
                            "problems": list(result.problems),
                        }
                        for result in results
                    ],
                },
                indent=2,
            )
        )
    else:
        for result in results:
            print(f"{'PASS' if result.passed else 'FAIL'}  {result.name}")
            for problem in result.problems:
                print(f"      - {problem}")
        print()
        if failed:
            count = sum(len(result.problems) for result in failed)
            print(f"Release verification FAILED: {count} problem(s) across {len(failed)} check(s).")
        else:
            print(f"Release verification PASSED: {len(results)} checks.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
