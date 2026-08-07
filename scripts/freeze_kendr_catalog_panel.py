from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from dotenv import load_dotenv


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
    return parser


def freeze_panel(
    catalog: Sequence[Mapping[str, Any]],
    *,
    include_non_text: bool = False,
) -> list[dict[str, str]]:
    panel: list[dict[str, str]] = []
    for model in catalog:
        model_id = str(model.get("id") or "").strip()
        capabilities = {str(value) for value in model.get("capabilities") or []}
        if not model_id or model.get("available") is not True:
            continue
        if not include_non_text and "text" not in capabilities:
            continue
        display_name = str(model.get("display_name") or model_id)
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
    panel = freeze_panel(catalog, include_non_text=args.include_non_text)
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
                "created_at": datetime.now(timezone.utc).isoformat(),
                "catalog_entries": len(catalog),
                "selected_entries": len(panel),
                "selection": (
                    "all available catalog entries"
                    if args.include_non_text
                    else "all available entries advertising text capability"
                ),
                "excluded_entries": [
                    {
                        "id": model.get("id"),
                        "display_name": model.get("display_name"),
                        "capabilities": model.get("capabilities"),
                        "reason": (
                            "not available"
                            if model.get("available") is not True
                            else "does not advertise text capability"
                        ),
                    }
                    for model in catalog
                    if model.get("available") is not True
                    or (
                        not args.include_non_text
                        and "text" not in set(model.get("capabilities") or [])
                    )
                ],
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
