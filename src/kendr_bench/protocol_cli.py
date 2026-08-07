from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from .advanced_statistics import approximate_required_items
from .global_planning import build_interleaved_schedule, validate_schedule
from .global_protocol import DESIGN_THRESHOLD, audit_protocol, load_protocol, render_audit_markdown
from .global_scoring import build_global_scorecards


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="llm-benchmark-protocol",
        description=(
            "Audit, plan, and score a study against LLM Benchmark Protocol "
            "1.0 (the KGBP reference profile) without making provider calls."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    audit = subparsers.add_parser(
        "audit",
        help="Score a protocol configuration and emit machine/human reports",
    )
    audit.add_argument("config", type=Path)
    audit.add_argument(
        "--output",
        type=Path,
        help="Output directory (default: next to the configuration)",
    )
    audit.add_argument(
        "--strict",
        action="store_true",
        help=(
            f"Return a non-zero status unless every design dimension is >{DESIGN_THRESHOLD:.1f}"
        ),
    )
    audit.add_argument(
        "--require-publication-evidence",
        action="store_true",
        help=(
            "Also fail unless structural execution/evidence declarations are "
            "complete; this does not award publication or conformity status"
        ),
    )

    power = subparsers.add_parser(
        "power",
        help="Compute an approximate paired-study item count for planning",
    )
    power.add_argument("--minimum-detectable-effect", type=float, required=True)
    power.add_argument("--standard-deviation", type=float, default=0.5)
    power.add_argument("--power", type=float, default=0.8)
    power.add_argument("--alpha", type=float, default=0.05)
    power.add_argument("--paired-correlation", type=float, default=0.0)

    schedule = subparsers.add_parser(
        "schedule",
        help="Create a deterministic provider-interleaved execution schedule",
    )
    schedule.add_argument("config", type=Path)
    schedule.add_argument("items", type=Path, help="JSON array or JSONL item plan")
    schedule.add_argument("--output", type=Path, required=True)
    schedule.add_argument("--seed", type=int, default=20260807)
    schedule.add_argument(
        "--region",
        action="append",
        dest="regions",
        help="Concrete provider region; repeat for each region",
    )

    score = subparsers.add_parser(
        "score",
        help="Build failure-aware hierarchical track scorecards from JSON/JSONL observations",
    )
    score.add_argument("observations", type=Path)
    score.add_argument(
        "--schedule",
        type=Path,
        help=(
            "Frozen schedule JSON/JSONL. When supplied, absent planned cells are "
            "materialized as status=missing with score zero."
        ),
    )
    score.add_argument("--output", type=Path, required=True)
    score.add_argument("--bootstrap-samples", type=int, default=10_000)
    score.add_argument("--seed", type=int, default=20260807)
    return parser


def _audit(args: argparse.Namespace) -> int:
    config = load_protocol(args.config)
    result = audit_protocol(config)
    output = args.output or args.config.parent / f"{args.config.stem}-audit"
    output.mkdir(parents=True, exist_ok=True)
    json_path = output / "protocol-audit.json"
    markdown_path = output / "protocol-audit.md"
    json_path.write_text(
        json.dumps(result.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_audit_markdown(result), encoding="utf-8")
    print(f"Design score: {result.design_score:.2f}/10")
    print(f"Minimum dimension: {result.minimum_dimension_score:.2f}/10")
    print(f"Design ready: {result.design_ready}")
    print(
        "Evidence bundle structurally complete: "
        f"{result.evidence_bundle_structurally_complete}"
    )
    print("Global publication candidate: False (requires external determination)")
    print(f"Report: {markdown_path}")
    if args.require_publication_evidence and not result.evidence_bundle_structurally_complete:
        return 3
    if args.strict and not result.design_ready:
        return 2
    return 0


def _power(args: argparse.Namespace) -> int:
    count = approximate_required_items(
        minimum_detectable_effect=args.minimum_detectable_effect,
        standard_deviation=args.standard_deviation,
        power=args.power,
        alpha=args.alpha,
        paired_correlation=args.paired_correlation,
    )
    print(count)
    return 0


def _read_rows(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        value = json.loads(text)
        if not isinstance(value, list) or not all(isinstance(row, dict) for row in value):
            raise ValueError("JSON input must be an array of objects")
        return value
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"line {line_number}: expected a JSON object")
        rows.append(row)
    return rows


def _schedule(args: argparse.Namespace) -> int:
    config = load_protocol(args.config)
    audit = audit_protocol(config)
    if not audit.design_ready:
        raise ValueError("protocol design does not pass every >9.0 dimension gate")
    items = _read_rows(args.items)
    system_ids = [str(system["system_id"]) for system in config["systems"]]
    repeats = int(config["sampling"]["repeats_per_item"])
    days = int(config["operations"]["measurement_days"])
    if args.regions:
        regions = args.regions
    else:
        region_count = int(config["operations"]["regions"])
        regions = [f"region-{index}" for index in range(1, region_count + 1)]
    schedule = build_interleaved_schedule(
        items,
        system_ids,
        repeats=repeats,
        days=days,
        regions=regions,
        seed=args.seed,
        protocol_id=str(config["study"]["protocol_id"]),
        deadline_ms=float(config["operations"]["request_deadline_ms"]),
        budget_usd=(
            float(config["operations"]["max_cost_usd_per_request"])
            if config["operations"]["max_cost_usd_per_request"] is not None
            else None
        ),
        output_cap_tokens=int(config["operations"]["output_cap_tokens"]),
    )
    validation = validate_schedule(
        schedule,
        item_ids=[str(item["item_id"]) for item in items],
        system_ids=system_ids,
        repeats=repeats,
    )
    if not validation["valid"]:
        raise RuntimeError("generated schedule failed its completeness invariant")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        for row in schedule:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    validation_path = args.output.with_suffix(args.output.suffix + ".validation.json")
    validation_path.write_text(
        json.dumps(validation, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Schedule rows: {len(schedule)}")
    print(f"Schedule: {args.output}")
    print(
        "Scope: deterministic planning artifact; execution evidence begins only "
        "after an operator records attempts against these schedule IDs."
    )
    return 0


def _render_scorecards(scorecards: dict[str, Any]) -> str:
    lines = [
        "# LLM Benchmark Protocol track scorecards",
        "",
        f"- Observations: {scorecards['observation_count']}",
        f"- Failure policy: {scorecards['failure_policy']}",
        f"- Aggregation: {scorecards['aggregation_policy']}",
        f"- Denominator mode: {scorecards['coverage']['mode']}",
        f"- Complete denominator enforced: {scorecards['coverage']['complete_denominator_enforced']}",
        "",
        "| System | Descriptive macro | Tracks | Observations |",
        "| --- | ---: | ---: | ---: |",
    ]
    for system in scorecards["systems"]:
        lines.append(
            f"| {system['system_id']} | {system['macro_track_score']:.4f} | "
            f"{system['track_count']} | {system['observation_count']} |"
        )
        lines.extend(["", f"## {system['system_id']}", "", "| Track | Score | 95% interval | Items | Clusters |", "| --- | ---: | ---: | ---: | ---: |"])
        for track in system["tracks"]:
            lines.append(
                f"| {track['track']} | {track['estimate']:.4f} | "
                f"{track['low']:.4f}-{track['high']:.4f} | {track['items']} | {track['clusters']} |"
            )
    lines.extend(
        [
            "",
            "> The macro is descriptive. Track scorecards, paired effects, uncertainty, "
            "operational constraints, and the Pareto frontier are the decision outputs; this report does not assert a universal rank.",
            "",
        ]
    )
    return "\n".join(lines)


def _score(args: argparse.Namespace) -> int:
    observations = _read_rows(args.observations)
    schedule = _read_rows(args.schedule) if args.schedule else None
    scorecards = build_global_scorecards(
        observations,
        expected_schedule=schedule,
        bootstrap_samples=args.bootstrap_samples,
        seed=args.seed,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "global-scorecards.json").write_text(
        json.dumps(scorecards, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (args.output / "global-scorecards.md").write_text(
        _render_scorecards(scorecards),
        encoding="utf-8",
    )
    print(f"Systems: {len(scorecards['systems'])}")
    print(f"Report: {args.output / 'global-scorecards.md'}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "audit":
            return _audit(args)
        if args.command == "power":
            return _power(args)
        if args.command == "schedule":
            return _schedule(args)
        if args.command == "score":
            return _score(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
