from __future__ import annotations

import json
from pathlib import Path

from kendr_bench.protocol_cli import main


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "config" / "global-protocol-v1.example.json"


def test_audit_cli_writes_reports(tmp_path: Path) -> None:
    output = tmp_path / "audit"

    status = main(["audit", str(EXAMPLE), "--output", str(output), "--strict"])

    assert status == 0
    report = json.loads((output / "protocol-audit.json").read_text(encoding="utf-8"))
    assert report["design_ready"] is True
    assert report["global_publication_candidate"] is False
    assert (output / "protocol-audit.md").is_file()


def test_audit_cli_can_require_execution_evidence(tmp_path: Path) -> None:
    status = main(
        [
            "audit",
            str(EXAMPLE),
            "--output",
            str(tmp_path / "audit"),
            "--require-publication-evidence",
        ]
    )
    assert status == 3


def test_power_cli_prints_item_count(capsys) -> None:
    status = main(
        [
            "power",
            "--minimum-detectable-effect",
            "0.05",
            "--standard-deviation",
            "0.25",
            "--paired-correlation",
            "0.5",
        ]
    )

    assert status == 0
    assert int(capsys.readouterr().out.strip()) > 0


def test_schedule_cli_builds_complete_plan(tmp_path: Path) -> None:
    items = tmp_path / "items.jsonl"
    items.write_text(
        '{"item_id":"a","cluster_id":"c1","track":"reasoning"}\n'
        '{"item_id":"b","cluster_id":"c2","track":"coding"}\n',
        encoding="utf-8",
    )
    output = tmp_path / "schedule.jsonl"

    status = main(
        [
            "schedule",
            str(EXAMPLE),
            str(items),
            "--output",
            str(output),
            "--region",
            "us",
            "--region",
            "eu",
        ]
    )

    assert status == 0
    assert len(output.read_text(encoding="utf-8").splitlines()) == 2 * 2 * 5
    validation = json.loads(
        output.with_suffix(".jsonl.validation.json").read_text(encoding="utf-8")
    )
    assert validation["valid"] is True


def test_score_cli_writes_track_report(tmp_path: Path) -> None:
    observations = tmp_path / "observations.jsonl"
    observations.write_text(
        '{"system_id":"a","item_id":"x","repeat":1,"track":"reasoning","status":"success","score":1,"language":"en","modality":"text","difficulty":"hard"}\n'
        '{"system_id":"b","item_id":"x","repeat":1,"track":"reasoning","status":"timeout","language":"en","modality":"text","difficulty":"hard"}\n',
        encoding="utf-8",
    )
    output = tmp_path / "score"

    status = main(
        [
            "score",
            str(observations),
            "--output",
            str(output),
            "--bootstrap-samples",
            "100",
        ]
    )

    assert status == 0
    result = json.loads((output / "global-scorecards.json").read_text(encoding="utf-8"))
    assert result["observation_count"] == 2
    assert (output / "global-scorecards.md").is_file()
