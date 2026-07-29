from __future__ import annotations

import json
from types import SimpleNamespace

import openai

from kendr_bench.livebench_adapter import (
    LIVEBENCH_PRICING_PATH,
    OPENAI_LIVEBENCH_REASONING_EFFORT,
    kendr_chat_completion,
    openai_chat_completion,
)


class Dumpable:
    def __init__(self, value):
        self.value = value

    def model_dump(self, *, mode):
        assert mode == "json"
        return self.value


def test_kendr_adapter_adds_idempotency_and_captures_metadata(
    monkeypatch, tmp_path
):
    captured = {}
    response = SimpleNamespace(
        id="req-123",
        model="kendr-intelligent",
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content="The answer is 4.")
            )
        ],
        usage=Dumpable(
            {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            }
        ),
        kendr_usage=Dumpable(
            {
                "credits_charged": "0.125",
                "input_tokens": 10,
                "output_tokens": 5,
            }
        ),
        kendr_routing=Dumpable({"selected_model_alias": "kc-test"}),
        kendr_optimization=Dumpable({"enabled": False}),
    )

    class FakeCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return response

    class FakeOpenAI:
        def __init__(self, **kwargs):
            captured["client"] = kwargs
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr(openai, "OpenAI", FakeOpenAI)
    log = tmp_path / "calls.jsonl"
    monkeypatch.setenv("KENDR_LIVEBENCH_CALL_LOG", str(log))
    monkeypatch.setenv("KENDR_LIVEBENCH_RUN_ID", "test-run")
    monkeypatch.setenv("KENDR_LIVEBENCH_USD_PER_CREDIT", "0.002")

    output, output_tokens, metadata = kendr_chat_completion(
        model="kendr-intelligent",
        messages=[{"role": "user", "content": "What is 2 + 2?"}],
        temperature=0,
        max_tokens=64,
        api_dict={
            "api_key": "not-written-to-artifacts",
            "api_base": "https://kendr.org/v1",
        },
    )

    assert output == "The answer is 4."
    assert output_tokens == 5
    assert captured["extra_headers"]["Idempotency-Key"]
    assert captured["client"]["max_retries"] == 0
    assert captured["max_tokens"] == 64
    assert metadata["input_tokens"] == 10
    assert metadata["kendr_credits_charged"] == "0.125"
    assert metadata["kendr_calls"][0]["request_id"] == "req-123"

    logged = json.loads(log.read_text(encoding="utf-8"))
    assert logged["input_messages"][0]["content"] == "What is 2 + 2?"
    assert logged["request_parameters"]["max_tokens"] == 64
    assert logged["output_text"] == "The answer is 4."
    assert logged["kendr_usage"]["credits_charged"] == "0.125"
    assert logged["kendr_cost_usd"] == "0.000250"
    assert "not-written-to-artifacts" not in log.read_text(encoding="utf-8")


def test_kendr_adapter_accumulates_multiturn_credits(
    monkeypatch, tmp_path
):
    responses = iter(
        [
            SimpleNamespace(
                id="first",
                model="kendr-intelligent",
                choices=[
                    SimpleNamespace(message=SimpleNamespace(content="First"))
                ],
                usage=Dumpable(
                    {"prompt_tokens": 2, "completion_tokens": 1}
                ),
                kendr_usage=Dumpable({"credits_charged": "0.01"}),
                kendr_routing=None,
                kendr_optimization=None,
            ),
            SimpleNamespace(
                id="second",
                model="kendr-intelligent",
                choices=[
                    SimpleNamespace(message=SimpleNamespace(content="Second"))
                ],
                usage=Dumpable(
                    {"prompt_tokens": 4, "completion_tokens": 1}
                ),
                kendr_usage=Dumpable(
                    {"credits_charged_micros": 20_000}
                ),
                kendr_routing=None,
                kendr_optimization=None,
            ),
        ]
    )

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(
                    create=lambda **request: next(responses)
                )
            )

    monkeypatch.setattr(openai, "OpenAI", FakeOpenAI)
    monkeypatch.delenv("KENDR_LIVEBENCH_CALL_LOG", raising=False)
    api = {"api_key": "key", "api_base": "https://kendr.org/v1"}
    kendr_chat_completion(
        "kendr-intelligent",
        [{"role": "user", "content": "First question"}],
        0,
        32,
        api_dict=api,
    )
    _, _, metadata = kendr_chat_completion(
        "kendr-intelligent",
        [
            {"role": "user", "content": "First question"},
            {"role": "assistant", "content": "First"},
            {"role": "user", "content": "Follow-up"},
        ],
        0,
        32,
        api_dict=api,
    )

    assert metadata["kendr_credits_charged"] == "0.03"
    assert [call["request_id"] for call in metadata["kendr_calls"]] == [
        "first",
        "second",
    ]


def test_openai_adapter_captures_usage_and_estimates_cost(
    monkeypatch, tmp_path
):
    captured = {}
    response = SimpleNamespace(
        id="chatcmpl-123",
        model="gpt-5.6-terra",
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content="The answer is 4.")
            )
        ],
        usage=Dumpable(
            {
                "prompt_tokens": 100,
                "completion_tokens": 20,
                "total_tokens": 120,
                "prompt_tokens_details": {"cached_tokens": 10},
            }
        ),
    )

    class FakeOpenAI:
        def __init__(self, **kwargs):
            captured["client"] = kwargs
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(
                    create=lambda **request: (
                        captured.update(request) or response
                    )
                )
            )

    pricing = tmp_path / "pricing.json"
    pricing.write_text(
        json.dumps(
            {
                "models": {
                    "openai:gpt-5.6-terra": {
                        "currency": "USD",
                        "input_per_million": "2.5",
                        "cached_input_per_million": "0.25",
                        "output_per_million": "15",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    log = tmp_path / "openai-calls.jsonl"
    monkeypatch.setattr(openai, "OpenAI", FakeOpenAI)
    monkeypatch.setenv("KENDR_LIVEBENCH_CALL_LOG", str(log))
    monkeypatch.setenv(LIVEBENCH_PRICING_PATH, str(pricing))
    monkeypatch.setenv(OPENAI_LIVEBENCH_REASONING_EFFORT, "none")

    output, output_tokens, metadata = openai_chat_completion(
        model="gpt-5.6-terra",
        messages=[{"role": "user", "content": "What is 2 + 2?"}],
        temperature=0,
        max_tokens=64,
        api_dict={
            "api_key": "not-written-to-artifacts",
            "api_base": "https://api.openai.com/v1",
        },
    )

    assert output == "The answer is 4."
    assert output_tokens == 20
    assert captured["max_completion_tokens"] == 64
    assert captured["reasoning_effort"] == "none"
    assert captured["temperature"] == 0
    assert metadata["input_tokens"] == 100
    assert metadata["cached_tokens"] == 10
    assert metadata["benchmark_calls"][0]["provider"] == "openai"

    logged = json.loads(log.read_text(encoding="utf-8"))
    assert logged["cost_usd"] == "0.0005275"
    assert logged["cost_source"] == "estimated_openai_standard_rate_card"
    assert "not-written-to-artifacts" not in log.read_text(encoding="utf-8")


def test_kendr_adapter_records_provider_failure_without_aborting(
    monkeypatch, tmp_path
):
    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(
                    create=lambda **request: (_ for _ in ()).throw(
                        RuntimeError("model unavailable")
                    )
                )
            )

    monkeypatch.setattr(openai, "OpenAI", FakeOpenAI)
    log = tmp_path / "failed-calls.jsonl"
    monkeypatch.setenv("KENDR_LIVEBENCH_CALL_LOG", str(log))

    output, output_tokens, metadata = kendr_chat_completion(
        model="kendr-intelligent",
        messages=[{"role": "user", "content": "Question"}],
        temperature=0,
        max_tokens=64,
        api_dict={"api_key": "key", "api_base": "https://kendr.org/v1"},
    )

    assert output == "$ERROR$"
    assert output_tokens == 0
    assert metadata["benchmark_error"]["type"] == "RuntimeError"
    logged = json.loads(log.read_text(encoding="utf-8"))
    assert logged["output_text"] == "$ERROR$"
    assert logged["error"]["message"] == "model unavailable"


def test_kendr_adapter_retries_no_credit_failure_with_new_idempotency(
    monkeypatch, tmp_path
):
    requests = []

    class NoCreditError(RuntimeError):
        request_id = "req-failed"
        status_code = 502
        body = {
            "error": {
                "message": (
                    "Kendr Intelligent Auto did not produce a complete "
                    "response. No credits were charged."
                ),
                "details": {
                    "kendr_routing": {
                        "selected_model_alias": "kc-qwen3-next",
                    }
                },
            },
            "request_id": "req-failed",
        }

    response = SimpleNamespace(
        id="req-recovered",
        model="kendr-intelligent",
        choices=[SimpleNamespace(message=SimpleNamespace(content="Recovered"))],
        usage=Dumpable({"prompt_tokens": 4, "completion_tokens": 2}),
        kendr_usage=Dumpable({"credits_charged": "0.02"}),
        kendr_routing=Dumpable({"selected_model_alias": "kc-deepseek-v3.2"}),
        kendr_optimization=None,
    )

    class FakeCompletions:
        def create(self, **request):
            requests.append(request)
            if len(requests) == 1:
                raise NoCreditError("no accepted answer")
            return response

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr(openai, "OpenAI", FakeOpenAI)
    log = tmp_path / "retried-calls.jsonl"
    monkeypatch.setenv("KENDR_LIVEBENCH_CALL_LOG", str(log))

    output, output_tokens, metadata = kendr_chat_completion(
        model="kendr-intelligent",
        messages=[{"role": "user", "content": "Question"}],
        temperature=0,
        max_tokens=64,
        api_dict={"api_key": "key", "api_base": "https://kendr.org/v1"},
    )

    assert output == "Recovered"
    assert output_tokens == 2
    assert len(requests) == 2
    first_key = requests[0]["extra_headers"]["Idempotency-Key"]
    second_key = requests[1]["extra_headers"]["Idempotency-Key"]
    assert first_key != second_key
    assert [call["output_text"] for call in metadata["kendr_calls"]] == [
        "$ERROR$",
        "Recovered",
    ]
    assert metadata["kendr_calls"][0]["will_retry"] is True
    assert metadata["kendr_calls"][0]["retry_reason"] == "no_credits_charged"
    assert metadata["kendr_calls"][1]["retry_attempt_count"] == 1

    logged = [
        json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()
    ]
    assert [item["request_id"] for item in logged] == [
        "req-failed",
        "req-recovered",
    ]
    assert logged[0]["kendr_routing"]["selected_model_alias"] == (
        "kc-qwen3-next"
    )


def test_kendr_adapter_preserves_failed_routing_metadata(
    monkeypatch, tmp_path
):
    class ProviderError(RuntimeError):
        request_id = "req-failed"
        body = {
            "error": {
                "message": "provider disabled",
                "details": {
                    "kendr_routing": {
                        "requested_model": "kendr-intelligent",
                        "selected_model_alias": "kc-deepseek-v3.2",
                        "attempted_candidates": [
                            {
                                "selected_model_alias": "kc-deepseek-v3.2",
                                "status": "failed",
                                "error_classification": "disabled_by_admin",
                            }
                        ],
                        "final_error_classification": "disabled_by_admin",
                    }
                },
            }
        }

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(
                    create=lambda **request: (_ for _ in ()).throw(
                        ProviderError("provider disabled")
                    )
                )
            )

    monkeypatch.setattr(openai, "OpenAI", FakeOpenAI)
    log = tmp_path / "failed-routing-calls.jsonl"
    monkeypatch.setenv("KENDR_LIVEBENCH_CALL_LOG", str(log))

    output, _, metadata = kendr_chat_completion(
        model="kendr-intelligent",
        messages=[{"role": "user", "content": "Question"}],
        temperature=0,
        max_tokens=64,
        api_dict={"api_key": "key", "api_base": "https://kendr.org/v1"},
    )

    assert output == "$ERROR$"
    assert metadata["benchmark_error"]["type"] == "ProviderError"
    logged = json.loads(log.read_text(encoding="utf-8"))
    assert logged["request_id"] == "req-failed"
    assert logged["kendr_routing"]["final_error_classification"] == (
        "disabled_by_admin"
    )
    assert logged["kendr_routing"]["attempted_candidates"][0]["status"] == (
        "failed"
    )
