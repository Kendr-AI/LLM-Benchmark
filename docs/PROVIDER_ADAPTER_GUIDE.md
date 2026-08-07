# Provider adapter guide

This guide describes how to connect a model-serving provider without weakening the benchmark's identity, retry, failure, cost, or evidence rules. Adapter code executes paid or rate-limited calls; obtain explicit authorization and budget approval before running it.

## Two integration layers

The repository has two related integration paths:

1. **Case-runner provider:** implements the small `BenchmarkProvider` protocol used by `llm-benchmark`. This is the easiest extension point for controlled text cases.
2. **LiveBench instrumentation adapter:** integrates with the LiveBench worker and must preserve its task-specific prompts, outputs, grading workspace, call attempts, and resume/finalize semantics. Built-in instrumentation currently supports Kendr and OpenAI paths.

Adding a case-runner provider does not automatically make it a LiveBench or matrix provider. Document which layer is implemented.

## Minimal provider interface

The runtime protocol in `src/kendr_bench/providers.py` requires:

```python
class BenchmarkProvider(Protocol):
    name: str
    model: str

    def generate(
        self,
        case: BenchmarkCase,
        *,
        max_output_tokens: int,
        run_id: str,
        repeat: int,
    ) -> ProviderResult: ...
```

A simplified adapter skeleton:

```python
import time

from kendr_bench.domain import ProviderResult, Usage


class ExampleProvider:
    name = "example"

    def __init__(self, *, model, client, pricing):
        self.model = model
        self.client = client
        self.pricing = pricing

    def generate(self, case, *, max_output_tokens, run_id, repeat):
        request = {
            "model": self.model,
            "input": case.input,
            "instructions": case.instructions or None,
            "max_output_tokens": max_output_tokens,
            "metadata": {
                "benchmark_run_id": run_id,
                "benchmark_case_id": case.id,
                "benchmark_repeat": str(repeat),
            },
        }
        started = time.perf_counter()
        response = self.client.generate(**request)
        latency_ms = (time.perf_counter() - started) * 1000

        usage = Usage.from_provider(response.usage)
        cost = self.pricing.estimate(
            provider=self.name,
            requested_model=self.model,
            actual_model=response.model,
            usage=usage,
        )
        return ProviderResult(
            provider=self.name,
            requested_model=self.model,
            actual_model=response.model,
            output_text=response.text,
            usage=usage,
            cost=cost,
            latency_ms=latency_ms,
            request_id=response.request_id,
            metadata={"finish_reason": response.finish_reason},
        )
```

Adapt names to the real SDK. Do not invent token, cost, model, or request identifiers when the provider does not return them; preserve unknown values.

## Required behavioral invariants

### Identity

- `name` is a stable provider key, not a display label.
- `model` is the exact requested identifier.
- `actual_model` captures the served snapshot or selected route when observable.
- Record API base, region, SDK version, request date, and provider-setting source in the system card/evidence.
- If the service routes dynamically, classify it as a router and record candidates and selected routes; do not present the router name as fixed model weights.

### Request parity

Map the declared shared controls exactly: input, instructions/system prompt, output cap, tools, reasoning/sampling settings, stop rules, timeout, and service tier. If a provider cannot express one control, document the incompatibility and place it in a separate division where required.

Avoid silent defaults. Serialize and hash the effective request parameters after provider-specific translation, excluding credentials.

### Retries and failures

- Prefer disabling hidden SDK retries.
- If hidden retries cannot be disabled, disclose that attempt visibility is incomplete.
- Record each benchmark-layer or application-layer retry as a separate attempt.
- Normalize failure type without discarding the original sanitized provider code.
- Preserve failed latency, usage, and billed cost when reported.
- Never turn a provider error into an empty successful answer.
- Resume from the earliest captured trial; do not select a later cleaner rerun.

Attempt records should conform to [`attempt-v1.schema.json`](../config/attempt-v1.schema.json). Final logical outcomes use [`answer-v1.schema.json`](../config/answer-v1.schema.json).

### Usage and cost

Capture, when available:

- input, cached input, cache-write, output, and reasoning tokens;
- provider-reported total;
- tool/search/router charges;
- charge for failed/retried work;
- currency, conversion rate/date/source, price tier, and service margin;
- whether the result is invoice-derived, provider-reported, catalog-estimated, or unavailable.

`Usage.from_provider` recognizes common field spellings, but inspect the provider's response rather than assuming it maps perfectly. Do not equate absent usage with zero. A list-price estimate and an invoice amount are different measures.

### Timing

Measure client-observed end-to-end latency around the actual SDK call. For streaming adapters also capture time to first token, time to first answer token, and completion duration. Record queue time only if exposed. Use a monotonic timer for duration and UTC timestamps for chronology.

### Content and privacy

- Never place API keys in request metadata, logs, exceptions, or artifacts.
- Sanitize credential-like error strings before persistence.
- Hash/redact content according to the evidence policy.
- Do not publish provider request IDs or raw prompts/responses without privacy and license review.
- Set provider retention/training flags explicitly where supported and document them.

## LiveBench adapter requirements

A LiveBench integration must additionally:

1. preserve the upstream question ID, category, task, prompt, and task-specific output format;
2. disable provider-side web/tool augmentation in a closed division unless the task and all systems permit it;
3. return the exact final text expected by the upstream grader;
4. write attempt evidence even when generation raises an exception;
5. preserve `$ERROR$` or equivalent failure lineage so the conservative scorer assigns zero;
6. support interrupted-run finalization without replaying paid inference;
7. separate provider generation from local grading;
8. pin and disclose the LiveBench source/release and local compatibility patches.

Register a new adapter explicitly in the CLI/worker dispatch and add it only to panel configurations whose capabilities match the frozen task division.

## Test strategy

Use fake clients; unit tests must not make network calls. Cover:

- exact request mapping and output-cap behavior;
- actual/requested model identity;
- usage aliases and reasoning/cached tokens;
- provider-reported cost, estimated cost, and unknown cost;
- timeout, provider error, client error, malformed response, and empty output;
- retry visibility and unique attempt IDs;
- credential redaction in exceptions;
- routed response metadata and candidate/route identity;
- deterministic serialization and request-parameter hash;
- no call replay during finalize/resume;
- schema validation and schedule/answer/judgment lineage.

Add a contract fixture containing no secrets and no copyrighted provider output.

## Review checklist

- [ ] System boundary and access path are classified correctly.
- [ ] Effective request controls match the declared division.
- [ ] Hidden retry behavior is disabled or disclosed.
- [ ] Failures remain failures and keep available cost/latency telemetry.
- [ ] Unknown usage/cost stays unknown.
- [ ] Requested and actual model/route identities are recorded.
- [ ] Secrets and personal data are excluded from persisted/public evidence.
- [ ] Fake-client tests cover success, failure, retry, routing, and redaction.
- [ ] Provider terms permit the planned testing and artifact release.
- [ ] A system card and adapter-version hash are frozen before the study.

Provider support is an engineering capability, not scientific comparability. The study design must still establish that prompts, tools, budgets, and score semantics are fair for the intended claim.
