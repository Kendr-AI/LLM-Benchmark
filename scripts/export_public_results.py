"""Export a privacy-reviewed public leaderboard from a frozen matrix bundle."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Sequence


PUBLIC_FIELDS = (
    "rank",
    "division",
    "division_rank",
    "endpoint_id",
    "endpoint_label",
    "tier",
    "questions_scored",
    "operational_goodput",
    "quality_score",
    "quality_ci95_low",
    "quality_ci95_high",
    "availability",
    "successful_answers",
    "failed_answers",
    "latency_p50_ms",
    "latency_p95_ms",
    "cost_usd",
    "cost_is_lower_bound",
    "data_analysis_score",
    "instruction_following_score",
    "language_score",
    "math_score",
    "reasoning_score",
)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _division(row: dict[str, Any], catalog_by_id: dict[str, dict[str, Any]]) -> str:
    model_id = str(row.get("requested_model") or row.get("panel_key") or "")
    catalog_item = catalog_by_id.get(model_id, {})
    capabilities = {str(value) for value in catalog_item.get("capabilities", [])}
    if catalog_item.get("mode") == "intelligent" or model_id in {
        "kendr-intelligent",
        "kendr-research",
        "kendr-flash",
    }:
        return "Routed systems"
    if "deep-research" in model_id or capabilities == {"text", "web_search"}:
        return "Managed research systems"
    return "Fixed managed text endpoints"


def build_public_bundle(
    leaderboard: dict[str, Any],
    manifest: dict[str, Any],
    catalog: list[dict[str, Any]],
    panel_metadata: dict[str, Any],
) -> dict[str, Any]:
    rows = list(leaderboard.get("results", []))
    failures = list(leaderboard.get("failures", []))
    expected = int(panel_metadata.get("selected_entries", 0))
    if len(rows) != expected or failures:
        raise ValueError(
            f"matrix is not publication-complete: {len(rows)}/{expected} rows, "
            f"{len(failures)} failures"
        )
    if any(not row.get("complete") for row in rows):
        raise ValueError("at least one leaderboard row is incomplete")
    if sorted(int(row["rank"]) for row in rows) != list(range(1, expected + 1)):
        raise ValueError("leaderboard ranks are not a complete sequence")

    catalog_by_id = {
        str(item["id"]): item for item in catalog if isinstance(item, dict) and item.get("id")
    }
    division_counts: dict[str, int] = {}
    public_rows: list[dict[str, Any]] = []
    for source in rows:
        division = _division(source, catalog_by_id)
        division_counts[division] = division_counts.get(division, 0) + 1
        public_rows.append(
            {
                "rank": int(source["rank"]),
                "division": division,
                "division_rank": division_counts[division],
                "endpoint_id": str(source["requested_model"]),
                "endpoint_label": str(source["model"]),
                "tier": int(source["tier"]),
                "questions_scored": int(source["questions_scored"]),
                "operational_goodput": source.get("score_weighted_operational_goodput"),
                "quality_score": source.get("quality_score"),
                "quality_ci95_low": source.get("quality_ci95_low"),
                "quality_ci95_high": source.get("quality_ci95_high"),
                "availability": source.get("availability"),
                "successful_answers": int(source.get("successful_answers", 0)),
                "failed_answers": int(source.get("failed_answers", 0)),
                "latency_p50_ms": source.get("latency_p50_ms"),
                "latency_p95_ms": source.get("latency_p95_ms"),
                "cost_usd": source.get("cost_usd"),
                "cost_is_lower_bound": bool(source.get("cost_total_is_lower_bound")),
                "data_analysis_score": source.get("data_analysis_score"),
                "instruction_following_score": source.get("instruction_following_score"),
                "language_score": source.get("language_score"),
                "math_score": source.get("math_score"),
                "reasoning_score": source.get("reasoning_score"),
                "provider_error_distribution": source.get("provider_error_distribution") or {},
            }
        )

    sampling = manifest.get("sampling") or {}
    pairwise = list(leaderboard.get("pairwise_tests", []))
    rejected = sum(bool(test.get("holm_reject")) for test in pairwise)
    return {
        "schema_version": "1.0",
        "project": "LLM Benchmark Protocol",
        "software_version": "1.0.0",
        "protocol_profile": "KGBP-1.0",
        "scientific_status": (
            "Descriptive catalog pilot; not a publication-grade global study, "
            "certification, or resolved universal model ranking."
        ),
        "matrix_id": leaderboard.get("matrix_id"),
        "generated_at": leaderboard.get("created_at"),
        "livebench_release": leaderboard.get("livebench_release"),
        "sample": {
            "mode": sampling.get("mode"),
            "seed": sampling.get("seed"),
            "content_hash": sampling.get("content_hash"),
            "content_hash_algorithm": sampling.get("content_hash_algorithm"),
            "questions": max((row["questions_scored"] for row in public_rows), default=0),
            "tasks": leaderboard.get("tasks", []),
            "questions_per_task": leaderboard.get("questions_per_task"),
            "selected_date_distribution": sampling.get("selected_date_distribution", {}),
        },
        "scope": {
            "catalog_entries": panel_metadata.get("catalog_entries"),
            "text_endpoints_ranked": len(public_rows),
            "not_applicable_entries": len(panel_metadata.get("excluded_entries", [])),
            "generation_repeats_per_item": 1,
        },
        "ranking_rule": leaderboard.get("ranking_rule"),
        "pairwise_inference": {
            "comparisons": len(pairwise),
            "holm_rejections": rejected,
            "interpretation": (
                "Row order is descriptive. No pairwise difference survives the "
                "declared family-wise correction."
                if rejected == 0
                else "Consult corrected paired effects before interpreting row order."
            ),
        },
        "results": public_rows,
        "not_applicable": panel_metadata.get("excluded_entries", []),
        "privacy_review": {
            "raw_prompts_included": False,
            "raw_responses_included": False,
            "provider_request_ids_included": False,
            "local_paths_included": False,
        },
    }


def write_bundle(bundle: dict[str, Any], output_dir: Path, stem: str) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{stem}.json"
    csv_path = output_dir / f"{stem}.csv"
    checksum_path = output_dir / "SHA256SUMS"
    json_path.write_text(
        json.dumps(bundle, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=PUBLIC_FIELDS,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(bundle["results"])
    checksum_lines = []
    for path in (csv_path, json_path):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        checksum_lines.append(f"{digest}  {path.name}")
    checksum_path.write_text(
        "\n".join(checksum_lines) + "\n", encoding="ascii", newline="\n"
    )
    return [json_path, csv_path, checksum_path]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--leaderboard", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--panel-metadata", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("docs/data"))
    parser.add_argument("--stem", default="kendr-catalog-pilot-2026-08-08")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    bundle = build_public_bundle(
        _read_json(args.leaderboard),
        _read_json(args.manifest),
        _read_json(args.catalog),
        _read_json(args.panel_metadata),
    )
    for path in write_bundle(bundle, args.output, args.stem):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
