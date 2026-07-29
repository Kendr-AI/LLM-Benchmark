from decimal import Decimal
from types import SimpleNamespace

from kendr_bench.domain import BenchmarkCase
from kendr_bench.pricing import PricingCatalog, RateCard
from kendr_bench.providers import KendrProvider, OpenAIProvider


class FakeResponses:
    def __init__(self) -> None:
        self.request = None

    def create(self, **request):
        self.request = request
        return SimpleNamespace(
            id="resp_test",
            model="gpt-5.6-sol",
            output_text="answer",
            status="completed",
            service_tier="default",
            incomplete_details=None,
            usage={
                "input_tokens": 100,
                "output_tokens": 20,
                "total_tokens": 120,
            },
        )


def test_openai_provider_sends_reproducibility_controls() -> None:
    responses = FakeResponses()
    client = SimpleNamespace(responses=responses)
    pricing = PricingCatalog(
        {
            "openai:gpt-5.6-sol": RateCard(
                currency="USD",
                input_per_million=Decimal("5"),
                cached_input_per_million=Decimal("0.5"),
                output_per_million=Decimal("30"),
            )
        }
    )
    provider = OpenAIProvider(
        model="gpt-5.6-sol",
        pricing=pricing,
        reasoning_effort="none",
        client=client,
    )

    result = provider.generate(
        BenchmarkCase(id="case", input="prompt", instructions="instruction"),
        max_output_tokens=64,
        run_id="run",
        repeat=1,
    )

    assert responses.request["reasoning"] == {"effort": "none"}
    assert responses.request["service_tier"] == "default"
    assert responses.request["store"] is False
    assert responses.request["max_output_tokens"] == 64
    assert result.cost.amount_usd == Decimal("0.0011")


class FakeKendrClient:
    def __init__(self) -> None:
        self.request = None

    def list_models(self):
        return [
            {
                "alias": "kc-glm-5",
                "credits_per_million_input": 2,
                "credits_per_million_cached_input": 1,
                "credits_per_million_output": 8,
            }
        ]

    def create_response(self, **request):
        self.request = request
        return SimpleNamespace(
            request_id="k_request",
            model="kendr-intelligent",
            output_text="kendr answer",
            usage={
                "input_tokens": 90,
                "output_tokens": 25,
                "total_tokens": 115,
            },
            kendr_usage={"credit_micros_charged": 250_000},
            kendr_routing={"selected_model_alias": "kc-glm-5"},
            kendr_optimization={},
            raw={},
        )


def test_kendr_provider_prefers_reported_billing_and_captures_route() -> None:
    client = FakeKendrClient()
    provider = KendrProvider(
        model="kendr-intelligent",
        usd_per_credit=Decimal("0.01"),
        client=client,
    )

    result = provider.generate(
        BenchmarkCase(id="case", input="prompt"),
        max_output_tokens=64,
        run_id="run",
        repeat=1,
    )

    assert client.request["web_search"] is False
    assert client.request["max_output_tokens"] == 64
    assert result.actual_model == "kc-glm-5"
    assert result.cost.amount == Decimal("0.25")
    assert result.cost.amount_usd == Decimal("0.0025")
    assert result.cost.source == "provider_reported_credit_micros"
    assert result.cost.rate_card["currency"] == "credits"
