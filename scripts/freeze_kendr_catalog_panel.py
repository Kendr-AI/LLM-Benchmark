from __future__ import annotations

import argparse
import json
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from dotenv import load_dotenv
from kendr_bench.catalog_identity import catalog_sha256


DUPLICATE_LABEL_POLICIES = ("error", "annotate")


class CatalogIdentityError(RuntimeError):
    """Raised when catalog identities cannot be frozen without ambiguity."""


def normalize_display_label(value: Any) -> str:
    """Return a conservative comparison key for provider display labels."""
    normalized = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return "".join(character for character in normalized if character.isalnum())


def is_user_owned_alias(model: Mapping[str, Any]) -> bool:
    """Identify catalog entries explicitly marked as user-managed aliases.

    This deliberately relies only on ownership or custom-profile metadata. It
    does not infer ownership from an unfamiliar model id or display label.
    """
    owner = str(model.get("owned_by") or "").strip().casefold()
    explicit_user_owners = {
        "user",
        "kendr-user",
        "kendr_user",
        "customer",
        "tenant",
    }
    return bool(
        owner in explicit_user_owners
        or owner.endswith("-user")
        or owner.endswith("_user")
        or model.get("custom_routing_profile") is True
    )


def catalog_exclusion_reason(
    model: Mapping[str, Any],
    *,
    include_non_text: bool = False,
    include_user_owned: bool = False,
) -> str | None:
    model_id = str(model.get("id") or "").strip()
    capabilities = {str(value) for value in model.get("capabilities") or []}
    if not model_id:
        return "missing catalog id"
    if model.get("available") is not True:
        return "not available"
    if not include_user_owned and is_user_owned_alias(model):
        return "user-owned alias excluded by default"
    if not include_non_text and "text" not in capabilities:
        return "does not advertise text capability"
    return None


def catalog_audit(
    catalog: Sequence[Mapping[str, Any]],
    *,
    include_non_text: bool = False,
    include_user_owned: bool = False,
) -> dict[str, Any]:
    """Audit eligibility and identity ambiguity without modifying the catalog."""
    eligible_entries: list[dict[str, Any]] = []
    excluded_entries: list[dict[str, Any]] = []
    model_id_groups: dict[str, list[dict[str, Any]]] = {}
    label_groups: dict[str, list[dict[str, Any]]] = {}

    for model in catalog:
        model_id = str(model.get("id") or "").strip()
        display_name = str(model.get("display_name") or model_id).strip()
        summary = {
            "id": model_id or None,
            "display_name": display_name or None,
            "owned_by": model.get("owned_by"),
            "mode": model.get("mode"),
            "capabilities": list(model.get("capabilities") or []),
        }
        reason = catalog_exclusion_reason(
            model,
            include_non_text=include_non_text,
            include_user_owned=include_user_owned,
        )
        if reason is not None:
            excluded_entries.append({**summary, "reason": reason})
            continue
        eligible_entries.append(summary)
        model_id_groups.setdefault(model_id.casefold(), []).append(summary)
        label_key = normalize_display_label(display_name)
        if label_key:
            label_groups.setdefault(label_key, []).append(summary)

    duplicate_model_ids = [
        {
            "normalized_id": key,
            "entries": entries,
            "resolution": "fatal: catalog ids must be unique",
        }
        for key, entries in sorted(model_id_groups.items())
        if len(entries) > 1
    ]
    duplicate_display_labels = [
        {
            "normalized_label": key,
            "display_name": entries[0]["display_name"],
            "catalog_ids": [entry["id"] for entry in entries],
            "resolution": (
                "identity unresolved; do not merge or describe as distinct "
                "physical models without route evidence"
            ),
        }
        for key, entries in sorted(label_groups.items())
        if len(entries) > 1
    ]
    return {
        "schema_version": "1.0",
        "catalog_entries": len(catalog),
        "eligible_entries": len(eligible_entries),
        "excluded_entries_count": len(excluded_entries),
        "selection_policy": {
            "available_only": True,
            "text_only": not include_non_text,
            "include_user_owned_aliases": include_user_owned,
        },
        "identity_status": (
            "fail"
            if duplicate_model_ids or duplicate_display_labels
            else "pass"
        ),
        "duplicate_model_id_groups": duplicate_model_ids,
        "duplicate_display_label_groups": duplicate_display_labels,
        "selected_candidates": eligible_entries,
        "excluded_entries": excluded_entries,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Freeze the currently available Kendr text-response catalog as a matrix panel"
    )
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--include-non-text",
        action="store_true",
        help="Include specialized entries that do not advertise text output",
    )
    parser.add_argument(
        "--include-user-owned",
        action="store_true",
        help=(
            "Include user-owned/custom routing aliases. They are excluded by "
            "default because they are not shared catalog identities."
        ),
    )
    parser.add_argument(
        "--duplicate-label-policy",
        choices=DUPLICATE_LABEL_POLICIES,
        default="error",
        help=(
            "Fail on duplicate normalized display labels (default), or retain "
            "them with endpoint-id identity warnings in their labels."
        ),
    )
    parser.add_argument(
        "--audit-output",
        type=Path,
        help="Catalog audit path; defaults to <output>.audit.json",
    )
    return parser


def freeze_panel(
    catalog: Sequence[Mapping[str, Any]],
    *,
    include_non_text: bool = False,
    include_user_owned: bool = False,
    duplicate_label_policy: str = "error",
) -> list[dict[str, str]]:
    if duplicate_label_policy not in DUPLICATE_LABEL_POLICIES:
        raise ValueError(
            "duplicate_label_policy must be one of "
            f"{', '.join(DUPLICATE_LABEL_POLICIES)}"
        )
    audit = catalog_audit(
        catalog,
        include_non_text=include_non_text,
        include_user_owned=include_user_owned,
    )
    if audit["duplicate_model_id_groups"]:
        duplicate_ids = ", ".join(
            group["normalized_id"]
            for group in audit["duplicate_model_id_groups"]
        )
        raise CatalogIdentityError(
            f"Duplicate catalog ids cannot be frozen: {duplicate_ids}"
        )
    duplicate_labels = audit["duplicate_display_label_groups"]
    if duplicate_labels and duplicate_label_policy == "error":
        details = "; ".join(
            f"{group['display_name']}: {', '.join(group['catalog_ids'])}"
            for group in duplicate_labels
        )
        raise CatalogIdentityError(
            "Duplicate display labels require explicit identity review: "
            + details
        )
    ambiguous_ids = {
        str(model_id)
        for group in duplicate_labels
        for model_id in group["catalog_ids"]
    }

    panel: list[dict[str, str]] = []
    for model in catalog:
        model_id = str(model.get("id") or "").strip()
        if catalog_exclusion_reason(
            model,
            include_non_text=include_non_text,
            include_user_owned=include_user_owned,
        ) is not None:
            continue
        display_name = str(model.get("display_name") or model_id).strip()
        if model_id in ambiguous_ids:
            display_name = (
                f"{display_name} [{model_id}; shared label, identity unresolved]"
            )
        panel.append(
            {
                "key": model_id,
                "provider": "kendr",
                "model": model_id,
                "label": display_name,
                "access": "Kendr API catalog snapshot",
                "license": "Provider/model terms - verify before external publication",
                "license_source": "https://api.kendr.org",
            }
        )
    return panel


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    load_dotenv(args.env_file)
    import kendr

    catalog = [
        dict(model)
        for model in kendr.Client().list_models()
        if isinstance(model, Mapping)
    ]
    audit = catalog_audit(
        catalog,
        include_non_text=args.include_non_text,
        include_user_owned=args.include_user_owned,
    )
    created_at = datetime.now(timezone.utc).isoformat()
    audit_document = {
        **audit,
        "created_at": created_at,
        "catalog_sha256": catalog_sha256(catalog),
        "duplicate_label_policy": args.duplicate_label_policy,
    }
    audit_path = args.audit_output or args.output.with_suffix(
        args.output.suffix + ".audit.json"
    )
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(
        json.dumps(audit_document, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    panel = freeze_panel(
        catalog,
        include_non_text=args.include_non_text,
        include_user_owned=args.include_user_owned,
        duplicate_label_policy=args.duplicate_label_policy,
    )
    if not panel:
        raise RuntimeError("No eligible catalog models were returned")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(panel, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    metadata_path = args.output.with_suffix(args.output.suffix + ".metadata.json")
    metadata_path.write_text(
        json.dumps(
            {
                "created_at": created_at,
                "catalog_entries": len(catalog),
                "selected_entries": len(panel),
                "selection": (
                    "all eligible available catalog entries"
                    if args.include_non_text
                    else (
                        "all eligible available entries advertising text "
                        "capability"
                    )
                ),
                "include_user_owned_aliases": args.include_user_owned,
                "duplicate_label_policy": args.duplicate_label_policy,
                "catalog_sha256": audit_document["catalog_sha256"],
                "catalog_audit": str(audit_path),
                "duplicate_display_label_groups": audit[
                    "duplicate_display_label_groups"
                ],
                "excluded_entries": audit["excluded_entries"],
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Catalog entries: {len(catalog)}")
    print(f"Selected entries: {len(panel)}")
    print(f"Panel: {args.output}")
    print(f"Audit: {audit_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
