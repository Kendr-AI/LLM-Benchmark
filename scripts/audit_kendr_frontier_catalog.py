from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

try:  # Supports both ``python -m scripts...`` and direct script execution.
    from .freeze_kendr_catalog_panel import (
        catalog_audit,
        catalog_exclusion_reason,
        catalog_sha256,
        normalize_display_label,
    )
except ImportError:  # pragma: no cover - exercised by direct CLI use
    from freeze_kendr_catalog_panel import (  # type: ignore[no-redef]
        catalog_audit,
        catalog_exclusion_reason,
        catalog_sha256,
        normalize_display_label,
    )


DEFAULT_PROFILE = (
    Path(__file__).resolve().parents[1]
    / "config"
    / "kendr-current-frontier-profile-20260808.json"
)

COVERAGE_ONLY_STATUSES = frozenset({"staged", "missing", "hold"})


class FrontierProfileError(RuntimeError):
    """Raised when a frontier profile is invalid or not audit-ready."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Audit an offline Kendr catalog snapshot against a dated frontier "
            "profile; this command never invokes a model."
        )
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        required=True,
        help="JSON array captured from the Kendr model catalog",
    )
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--audit-output", type=Path, required=True)
    parser.add_argument(
        "--core-panel-output",
        type=Path,
        help="Write the core GA panel only when every core identity passes",
    )
    parser.add_argument(
        "--companion-panel-output",
        type=Path,
        help=(
            "Write the preview/limited-access companion only when every "
            "companion identity passes"
        ),
    )
    return parser


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise FrontierProfileError(f"Invalid JSON in {path}: {exc}") from exc


def _validate_profile(profile: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    cohorts = profile.get("cohorts")
    if not isinstance(cohorts, list) or not cohorts:
        raise FrontierProfileError("Profile must contain a non-empty cohorts array")
    cohort_ids: set[str] = set()
    entry_keys: set[str] = set()
    configured_catalog_ids: set[str] = set()
    coverage_model_ids: set[str] = set()
    for cohort in cohorts:
        if not isinstance(cohort, Mapping):
            raise FrontierProfileError("Every cohort must be an object")
        cohort_id = str(cohort.get("id") or "").strip()
        if not cohort_id or cohort_id in cohort_ids:
            raise FrontierProfileError("Cohort ids must be present and unique")
        cohort_ids.add(cohort_id)
        entries = cohort.get("entries")
        if not isinstance(entries, list) or not entries:
            raise FrontierProfileError(
                f"Cohort {cohort_id!r} must contain a non-empty entries array"
            )
        for entry in entries:
            if not isinstance(entry, Mapping):
                raise FrontierProfileError("Every profile entry must be an object")
            key = str(entry.get("key") or "").strip()
            label = str(entry.get("label") or "").strip()
            if not key or not label or key in entry_keys:
                raise FrontierProfileError(
                    "Profile entry keys must be unique and labels must be present"
                )
            entry_keys.add(key)
            coverage_only = entry.get("coverage_only") is True
            catalog_id = entry.get("catalog_id")
            if coverage_only:
                if catalog_id not in (None, ""):
                    raise FrontierProfileError(
                        "Coverage-only entries cannot declare a Kendr catalog id"
                    )
                if str(entry.get("role") or "candidate").strip() != "candidate":
                    raise FrontierProfileError(
                        "Coverage-only entries must use the candidate role"
                    )
                vendor_model_id = str(
                    entry.get("vendor_model_id") or ""
                ).strip()
                coverage_status = str(
                    entry.get("coverage_status") or ""
                ).strip()
                n_a_reason = str(entry.get("n_a_reason") or "").strip()
                if (
                    not vendor_model_id
                    or vendor_model_id.casefold() in coverage_model_ids
                ):
                    raise FrontierProfileError(
                        "Coverage-only vendor model ids must be present and unique"
                    )
                if coverage_status not in COVERAGE_ONLY_STATUSES:
                    raise FrontierProfileError(
                        "Coverage-only entries must declare a supported coverage_status"
                    )
                if not n_a_reason:
                    raise FrontierProfileError(
                        "Coverage-only entries must declare an N/A reason"
                    )
                coverage_model_ids.add(vendor_model_id.casefold())
            elif catalog_id is not None:
                catalog_id = str(catalog_id).strip()
                if not catalog_id or catalog_id.casefold() in configured_catalog_ids:
                    raise FrontierProfileError(
                        "Configured catalog ids must be non-empty and unique"
                    )
                configured_catalog_ids.add(catalog_id.casefold())
    ga_cohort_id = str(profile.get("ga_cohort_id") or "").strip()
    companion_cohort_id = str(
        profile.get("companion_cohort_id") or ""
    ).strip()
    if (
        not ga_cohort_id
        or not companion_cohort_id
        or ga_cohort_id == companion_cohort_id
        or ga_cohort_id not in cohort_ids
        or companion_cohort_id not in cohort_ids
    ):
        raise FrontierProfileError(
            "Profile must identify distinct, existing GA and companion cohorts"
        )
    cohorts_by_id = {str(cohort["id"]): cohort for cohort in cohorts}
    if cohorts_by_id[ga_cohort_id].get("claim_class") != "general-availability":
        raise FrontierProfileError(
            "The GA cohort must use claim_class 'general-availability'"
        )
    if (
        cohorts_by_id[companion_cohort_id].get("claim_class")
        != "preview-or-limited-access"
    ):
        raise FrontierProfileError(
            "The companion cohort must use claim_class "
            "'preview-or-limited-access'"
        )
    return cohorts


def _panel_row(
    entry: Mapping[str, Any],
    model: Mapping[str, Any],
    cohort: Mapping[str, Any],
) -> dict[str, str]:
    model_id = str(model["id"])
    return {
        "key": str(entry["key"]),
        "provider": "kendr",
        "model": model_id,
        "label": str(entry["label"]),
        "access": str(
            entry.get("access")
            or f"Kendr API catalog snapshot; {cohort.get('claim_scope')}"
        ),
        "license": str(
            entry.get("license")
            or "Provider/model terms - verify before external publication"
        ),
        "license_source": str(
            entry.get("license_source") or "https://api.kendr.org"
        ),
    }


def audit_frontier_profile(
    catalog: Sequence[Mapping[str, Any]],
    profile: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, list[dict[str, str]]]]:
    """Resolve only exact configured ids and report every unresolved slot."""
    cohorts = _validate_profile(profile)
    by_id: dict[str, list[Mapping[str, Any]]] = {}
    eligible_by_label: dict[str, list[Mapping[str, Any]]] = {}
    for model in catalog:
        model_id = str(model.get("id") or "").strip()
        if model_id:
            by_id.setdefault(model_id.casefold(), []).append(model)
        if catalog_exclusion_reason(model) is None:
            label_key = normalize_display_label(
                model.get("display_name") or model_id
            )
            if label_key:
                eligible_by_label.setdefault(label_key, []).append(model)

    base_audit = catalog_audit(catalog)
    panels: dict[str, list[dict[str, str]]] = {}
    cohort_audits: list[dict[str, Any]] = []
    selected_identity_rows: list[dict[str, Any]] = []

    for cohort in cohorts:
        cohort_id = str(cohort["id"])
        entry_audits: list[dict[str, Any]] = []
        panel: list[dict[str, str]] = []
        for entry in cohort["entries"]:
            key = str(entry["key"])
            expected_label = str(entry["label"])
            coverage_only = entry.get("coverage_only") is True
            expected_catalog_label = str(
                entry.get("expected_display_name") or expected_label
            )
            configured_id = entry.get("catalog_id")
            item: dict[str, Any] = {
                "key": key,
                "label": expected_label,
                "expected_display_name": expected_catalog_label,
                "role": entry.get("role", "candidate"),
                "catalog_id": configured_id,
                "required": (
                    False
                    if coverage_only
                    else entry.get("required", True) is not False
                ),
                "coverage_only": coverage_only,
                "vendor_model_id": entry.get("vendor_model_id"),
            }
            if coverage_only:
                item.update(
                    {
                        "status": "coverage_only",
                        "vendor_model_id": entry.get("vendor_model_id"),
                        "coverage_status": entry.get("coverage_status"),
                        "execution_eligible": False,
                        "reason": entry.get("n_a_reason"),
                    }
                )
                entry_audits.append(item)
                continue
            if configured_id is None:
                label_matches = eligible_by_label.get(
                    normalize_display_label(expected_catalog_label), []
                )
                item.update(
                    {
                        "status": "identity_unresolved",
                        "candidate_catalog_ids_by_exact_label": [
                            model.get("id") for model in label_matches
                        ],
                        "reason": (
                            "No canonical catalog id is configured; exact-label "
                            "matches are advisory and are never selected "
                            "automatically."
                        ),
                    }
                )
                entry_audits.append(item)
                continue

            matches = by_id.get(str(configured_id).casefold(), [])
            if not matches:
                item.update(
                    {
                        "status": "missing",
                        "reason": (
                            entry.get("n_a_reason")
                            or "Configured catalog id is absent from the snapshot."
                        ),
                    }
                )
                entry_audits.append(item)
                continue
            if len(matches) > 1:
                item.update(
                    {
                        "status": "ambiguous_catalog_id",
                        "reason": "Configured catalog id occurs more than once.",
                    }
                )
                entry_audits.append(item)
                continue

            model = matches[0]
            exclusion_reason = catalog_exclusion_reason(model)
            if exclusion_reason is not None:
                item.update(
                    {
                        "status": "ineligible",
                        "reason": exclusion_reason,
                        "observed_display_name": model.get("display_name"),
                    }
                )
                entry_audits.append(item)
                continue
            observed_label = str(model.get("display_name") or model.get("id"))
            if normalize_display_label(observed_label) != normalize_display_label(
                expected_catalog_label
            ):
                item.update(
                    {
                        "status": "label_mismatch",
                        "observed_display_name": observed_label,
                        "reason": (
                            "The configured id exists under a different display "
                            "label; review alias drift before selection."
                        ),
                    }
                )
                entry_audits.append(item)
                continue

            item.update(
                {
                    "status": "present",
                    "observed_display_name": observed_label,
                    "owned_by": model.get("owned_by"),
                    "mode": model.get("mode"),
                }
            )
            entry_audits.append(item)
            panel.append(_panel_row(entry, model, cohort))
            selected_identity_rows.append(
                {
                    "cohort_id": cohort_id,
                    "key": key,
                    "catalog_id": model.get("id"),
                    "normalized_label": normalize_display_label(observed_label),
                }
            )

        required_items = [item for item in entry_audits if item["required"]]
        cohort_ready = all(item["status"] == "present" for item in required_items)
        panels[cohort_id] = panel
        cohort_audits.append(
            {
                "id": cohort_id,
                "claim_class": cohort.get("claim_class"),
                "claim_scope": cohort.get("claim_scope"),
                "ready": cohort_ready,
                "required_entries": len(required_items),
                "present_entries": sum(
                    item["status"] == "present" for item in required_items
                ),
                "entries": entry_audits,
            }
        )

    selected_by_label: dict[str, list[dict[str, Any]]] = {}
    for row in selected_identity_rows:
        selected_by_label.setdefault(row["normalized_label"], []).append(row)
    selected_duplicate_labels = [
        {
            "normalized_label": label,
            "entries": rows,
            "resolution": (
                "identity unresolved; no cohort panel may be emitted until the "
                "duplicate label has route-level evidence or explicit annotation"
            ),
        }
        for label, rows in sorted(selected_by_label.items())
        if len(rows) > 1
    ]
    if selected_duplicate_labels:
        affected_cohorts = {
            row["cohort_id"]
            for group in selected_duplicate_labels
            for row in group["entries"]
        }
        for cohort in cohort_audits:
            if cohort["id"] in affected_cohorts:
                cohort["ready"] = False

    ga_cohort_id = str(profile.get("ga_cohort_id") or "")
    companion_cohort_id = str(profile.get("companion_cohort_id") or "")
    readiness = {cohort["id"]: cohort["ready"] for cohort in cohort_audits}
    audit = {
        "schema_version": "1.0",
        "profile_id": profile.get("profile_id"),
        "snapshot_date": profile.get("snapshot_date"),
        "catalog_entries": len(catalog),
        "catalog_sha256": catalog_sha256(catalog),
        "ga_claim_ready": bool(ga_cohort_id and readiness.get(ga_cohort_id)),
        "companion_claim_ready": bool(
            companion_cohort_id and readiness.get(companion_cohort_id)
        ),
        "claim_separation": (
            "Preview and limited-access companion results must be reported "
            "separately and must not be pooled into core GA claims."
        ),
        "catalog_selection_policy": base_audit["selection_policy"],
        "catalog_excluded_entries": base_audit["excluded_entries"],
        "catalog_duplicate_model_id_groups": base_audit[
            "duplicate_model_id_groups"
        ],
        "catalog_duplicate_display_label_groups": base_audit[
            "duplicate_display_label_groups"
        ],
        "selected_duplicate_display_label_groups": selected_duplicate_labels,
        "cohorts": cohort_audits,
    }
    return audit, panels


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_name = handle.name
            json.dump(value, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        Path(temporary_name).replace(path)
    finally:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)


def _validate_distinct_paths(named_paths: Mapping[str, Path]) -> None:
    seen: dict[str, str] = {}
    for label, path in named_paths.items():
        normalized = str(path.resolve(strict=False)).casefold()
        prior = seen.get(normalized)
        if prior is not None:
            raise FrontierProfileError(
                f"{label} must not reuse the path configured for {prior}"
            )
        seen[normalized] = label


def _invalidate_generated_outputs(paths: Sequence[Path]) -> None:
    for path in paths:
        if path.is_dir() and not path.is_symlink():
            raise FrontierProfileError(
                f"Generated output path is a directory: {path}"
            )
        if path.exists() or path.is_symlink():
            path.unlink()


def _ready_panel(
    *,
    cohort_id: str,
    audit: Mapping[str, Any],
    panels: Mapping[str, list[dict[str, str]]],
) -> list[dict[str, str]]:
    cohort = next(
        (item for item in audit["cohorts"] if item["id"] == cohort_id),
        None,
    )
    if cohort is None:
        raise FrontierProfileError(f"Profile has no cohort {cohort_id!r}")
    if not cohort["ready"]:
        unresolved = ", ".join(
            f"{item['key']}={item['status']}"
            for item in cohort["entries"]
            if item["required"] and item["status"] != "present"
        )
        raise FrontierProfileError(
            f"Cohort {cohort_id!r} is not ready: {unresolved}"
        )
    return panels[cohort_id]


def _write_ready_panel(
    *,
    cohort_id: str,
    output: Path,
    audit: Mapping[str, Any],
    panels: Mapping[str, list[dict[str, str]]],
) -> None:
    _write_json(
        output,
        _ready_panel(cohort_id=cohort_id, audit=audit, panels=panels),
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    named_paths = {
        "catalog input": args.catalog,
        "profile input": args.profile,
        "audit output": args.audit_output,
    }
    generated_outputs = [args.audit_output]
    if args.core_panel_output:
        named_paths["core panel output"] = args.core_panel_output
        generated_outputs.append(args.core_panel_output)
    if args.companion_panel_output:
        named_paths["companion panel output"] = args.companion_panel_output
        generated_outputs.append(args.companion_panel_output)
    _validate_distinct_paths(named_paths)
    _invalidate_generated_outputs(generated_outputs)

    raw_catalog = _load_json(args.catalog)
    raw_profile = _load_json(args.profile)
    if not isinstance(raw_catalog, list):
        raise FrontierProfileError("Catalog snapshot must be a JSON array")
    if not isinstance(raw_profile, Mapping):
        raise FrontierProfileError("Frontier profile must be a JSON object")
    catalog = [item for item in raw_catalog if isinstance(item, Mapping)]
    if len(catalog) != len(raw_catalog):
        raise FrontierProfileError("Every catalog entry must be a JSON object")

    audit, panels = audit_frontier_profile(catalog, raw_profile)
    audit = {
        **audit,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "profile_sha256": _sha256_file(args.profile),
    }
    _write_json(args.audit_output, audit)

    ga_cohort_id = str(raw_profile.get("ga_cohort_id") or "")
    companion_cohort_id = str(raw_profile.get("companion_cohort_id") or "")
    ready_outputs: list[tuple[Path, list[dict[str, str]]]] = []
    if args.core_panel_output:
        ready_outputs.append(
            (
                args.core_panel_output,
                _ready_panel(
                    cohort_id=ga_cohort_id, audit=audit, panels=panels
                ),
            )
        )
    if args.companion_panel_output:
        ready_outputs.append(
            (
                args.companion_panel_output,
                _ready_panel(
                    cohort_id=companion_cohort_id,
                    audit=audit,
                    panels=panels,
                ),
            )
        )
    for output, panel in ready_outputs:
        _write_json(output, panel)

    print(f"Catalog entries: {len(catalog)}")
    print(f"Core GA ready: {audit['ga_claim_ready']}")
    print(f"Companion ready: {audit['companion_claim_ready']}")
    print(f"Audit: {args.audit_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
