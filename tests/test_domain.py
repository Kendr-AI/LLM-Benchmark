from kendr_bench.domain import Usage


def test_normalizes_responses_usage() -> None:
    usage = Usage.from_provider(
        {
            "input_tokens": 120,
            "input_tokens_details": {
                "cached_tokens": 20,
                "cache_write_tokens": 10,
            },
            "output_tokens": 30,
            "output_tokens_details": {"reasoning_tokens": 5},
            "total_tokens": 150,
        }
    )

    assert usage.input_tokens == 120
    assert usage.cached_input_tokens == 20
    assert usage.cache_write_input_tokens == 10
    assert usage.output_tokens == 30
    assert usage.reasoning_tokens == 5
    assert usage.total_tokens == 150


def test_normalizes_chat_completion_usage() -> None:
    usage = Usage.from_provider(
        {
            "prompt_tokens": 42,
            "completion_tokens": 8,
            "completion_tokens_details": {"reasoning_tokens": 3},
        }
    )

    assert usage.input_tokens == 42
    assert usage.output_tokens == 8
    assert usage.reasoning_tokens == 3
    assert usage.total_tokens == 50

