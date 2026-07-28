import json
import os
from decimal import Decimal
from pathlib import Path

from kendr_bench.cli import load_environment
from kendr_bench.domain import (
    BenchmarkCase,
    Cost,
    ProviderResult,
    Usage,
)
from kendr_bench.runner import load_cases, run_benchmark, sanitize_error_message


class FakeProvider:
    def __init__(self, name: str, cost: str) -> None:
        self.name = name
        self.model = f"{name}-model"
        self.cost = Decimal(cost)

    def generate(
        self,
        case: BenchmarkCase,
        *,
        max_output_tokens: int,
        run_id: str,
        repeat: int,
    ) -> ProviderResult:
        rate_card = {
            "currency": "USD",
            "input_per_million": "1",
            "cached_input_per_million": "0.1",
            "cache_write_input_per_million": None,
            "output_per_million": "2",
            "source": "test",
            "long_context": {
                "threshold_input_tokens": None,
                "input_multiplier": "1",
                "output_multiplier": "1",
            },
        }
        return ProviderResult(
            provider=self.name,
            requested_model=self.model,
            actual_model=self.model,
            output_text=f"{self.name}: {case.id}",
            usage=Usage(input_tokens=10, output_tokens=5, total_tokens=15),
            cost=Cost(
                amount=self.cost,
                currency="USD",
                amount_usd=self.cost,
                source="test",
                rate_card=rate_card,
            ),
            latency_ms=12.5,
            request_id=f"{self.name}-request",
        )


def test_load_cases_rejects_duplicate_ids(tmp_path: Path) -> None:
    cases = tmp_path / "cases.jsonl"
    cases.write_text(
        '{"id":"a","input":"one"}\n{"id":"a","input":"two"}\n',
        encoding="utf-8",
    )

    try:
        load_cases(cases)
    except ValueError as exc:
        assert "duplicate case id" in str(exc)
    else:
        raise AssertionError("expected duplicate case error")


def test_run_writes_auditable_artifacts(tmp_path: Path) -> None:
    pricing = tmp_path / "pricing.json"
    pricing.write_text('{"as_of":"test","models":{}}', encoding="utf-8")
    case = BenchmarkCase(id="case-1", input="hello")

    run_dir, records, paths = run_benchmark(
        providers=[FakeProvider("openai", "0.01"), FakeProvider("kendr", "0.005")],
        cases=[case],
        output_root=tmp_path / "results",
        max_output_tokens=100,
        repeat_count=1,
        pricing_file=pricing,
        pricing_as_of="test",
        label="unit",
    )

    assert run_dir.is_dir()
    assert len(records) == 2
    assert all(path.is_file() for path in paths.values())
    summary = json.loads(paths["summary"].read_text(encoding="utf-8"))
    comparison = summary["paired_comparisons"][0]
    assert comparison["kendr_to_openai_cost_ratio"] == "0.5"
    assert comparison["kendr_cost_savings_percent"] == "50.0"
    assert comparison["openai_cost_for_kendr_token_usage"] == "0.00002"
    assert comparison["kendr_cost_for_openai_token_usage"] == "0.00002"


def test_error_message_redacts_provider_credentials() -> None:
    message = (
        "Incorrect API key: sk-proj-********abcd and "
        "kndr_live_secretvalue and Bearer header.payload.signature"
    )

    sanitized = sanitize_error_message(message)

    assert "abcd" not in sanitized
    assert "secretvalue" not in sanitized
    assert "header.payload.signature" not in sanitized
    assert sanitized.count("[REDACTED]") == 3


def test_dotenv_overrides_stale_process_value(
    tmp_path: Path, monkeypatch
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "OPENAI_API_KEY=from-dotenv\nKENDR_API_KEY=kendr-dotenv\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("OPENAI_API_KEY", "stale-process-value")
    monkeypatch.delenv("KENDR_API_KEY", raising=False)

    loaded = load_environment(env_file, disabled=False)

    assert loaded == env_file.resolve()
    assert os.environ["OPENAI_API_KEY"] == "from-dotenv"
    assert os.environ["KENDR_API_KEY"] == "kendr-dotenv"
