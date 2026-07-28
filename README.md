# Kendr LLM Benchmarking

Reproducible quality, cost, token-usage, latency, and reliability benchmarking
for Kendr, direct OpenAI models, and popular open-weight or proprietary models
served through Kendr.

The methodology is based on the
[LiveBench paper](https://arxiv.org/abs/2406.19314) and the
[LiveBench implementation](https://github.com/LiveBench/LiveBench). LiveBench
uses recent questions and objective, task-specific graders to reduce test-set
contamination and avoid an LLM-as-judge. The public leaderboard at
[livebench.ai](https://livebench.ai/) is the reference presentation, but the
results below are from this project's own fixed, instrumented slice.

> [!IMPORTANT]
> This is an observed endpoint-as-served comparison, not a table of vendor
> claims and not a reproduction of the full public LiveBench leaderboard.
> Every model received the same 15-question slice and requested output cap.

## Latest verified report

**Run:** `20260727T214108Z-all-models-timeout-fixed-594145d3`

Kendr Intelligent ranked first on this slice at **89.1% quality** and cost
**$0.027234**. It was **4.71x as cost-efficient as direct OpenAI GPT-5.6 Sol**
by quality points per measured USD. It used more tokens and had higher latency
than Sol, so the result should be read across quality, cost, usage, latency,
and reliability rather than as a quality-only ranking.

The complete pass produced:

- 9 models or routed systems;
- 5 capabilities and 15 questions per model;
- 135 final answers from 136 raw provider attempts;
- 97,189 input tokens and 75,959 output tokens;
- 173,148 total captured tokens;
- $0.775727 total measured API cost;
- no final-answer failures and no HTTP 504 timeout failures.

### Overall leaderboard

| Rank | Model/system | Quality (95% question-bootstrap CI) | Input / output tokens | Cost | p50 / p95 latency | Final / raw reliability | Cap compliance |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | Kendr Intelligent | 89.1% (76.0%-100.0%) | 12,232 / 15,203 | $0.027234 | 9.70s / 60.20s | 100.0% / 93.8% | 80.0% |
| 2 | DeepSeek V3.2 | 84.8% (70.0%-96.7%) | 10,119 / 11,491 | $0.029459 | 12.88s / 53.24s | 100.0% / 100.0% | 86.7% |
| 3 | Claude Opus 4.8 | 80.0% (62.2%-95.6%) | 13,987 / 3,534 | $0.169365 | 4.29s / 10.61s | 100.0% / 100.0% | 100.0% |
| 4 | Kimi K2.5 | 76.1% (56.1%-93.9%) | 10,460 / 8,662 | $0.034520 | 5.56s / 20.28s | 100.0% / 100.0% | 93.3% |
| 5 | OpenAI GPT-5.6 Sol | 71.1% (48.9%-91.1%) | 7,574 / 2,146 | $0.102250 | 3.67s / 10.04s | 100.0% / 100.0% | 100.0% |
| 6 | Claude Opus 5 | 70.9% (51.8%-88.9%) | 14,017 / 7,952 | $0.287707 | 7.87s / 14.56s | 100.0% / 100.0% | 100.0% |
| 7 | OpenAI GPT-5.6 Terra | 64.4% (42.2%-86.7%) | 7,574 / 1,918 | $0.047705 | 2.01s / 4.74s | 100.0% / 100.0% | 100.0% |
| 8 | GLM-5 | 62.2% (37.8%-86.7%) | 10,722 / 15,638 | $0.065017 | 20.03s / 80.48s | 100.0% / 100.0% | 80.0% |
| 9 | Llama 4 Maverick | 51.6% (30.0%-73.0%) | 10,504 / 9,415 | $0.012469 | 3.32s / 7.61s | 100.0% / 100.0% | 100.0% |

The confidence intervals resample these 15 questions only. They do not include
generation-to-generation variation or uncertainty from choosing this task
slice.

### Quality by capability

| Model/system | Data analysis | Instruction following | Language | Math | Reasoning |
| --- | ---: | ---: | ---: | ---: | ---: |
| Kendr Intelligent | 45.7% | 100.0% | 100.0% | 100.0% | 100.0% |
| DeepSeek V3.2 | 46.3% | 77.8% | 100.0% | 100.0% | 100.0% |
| Claude Opus 4.8 | 44.3% | 55.6% | 100.0% | 100.0% | 100.0% |
| Kimi K2.5 | 25.0% | 55.6% | 100.0% | 100.0% | 100.0% |
| OpenAI GPT-5.6 Sol | 33.3% | 55.6% | 66.7% | 100.0% | 100.0% |
| Claude Opus 5 | 21.3% | 33.3% | 100.0% | 100.0% | 100.0% |
| OpenAI GPT-5.6 Terra | 33.3% | 55.6% | 66.7% | 66.7% | 100.0% |
| GLM-5 | 0.0% | 77.8% | 33.3% | 100.0% | 100.0% |
| Llama 4 Maverick | 29.0% | 50.0% | 66.7% | 33.3% | 79.2% |

LiveBench task correctness and instruction compliance are the relevance proxy.
No generic semantic-relevance judge was added.

### Quality-adjusted efficiency

Direct OpenAI GPT-5.6 Sol is the `1.00x` baseline. Higher is better for both
indices.

| Model/system | USD / quality point | Tokens / quality point | Cost efficiency vs Sol | Token efficiency vs Sol |
| --- | ---: | ---: | ---: | ---: |
| Kendr Intelligent | $0.002037 | 2,052 | 4.71x | 0.44x |
| DeepSeek V3.2 | $0.002315 | 1,698 | 4.14x | 0.54x |
| Claude Opus 4.8 | $0.014118 | 1,460 | 0.68x | 0.62x |
| Kimi K2.5 | $0.003024 | 1,675 | 3.17x | 0.54x |
| OpenAI GPT-5.6 Sol | $0.009586 | 911 | 1.00x | 1.00x |
| Claude Opus 5 | $0.027040 | 2,065 | 0.35x | 0.44x |
| OpenAI GPT-5.6 Terra | $0.004935 | 982 | 1.94x | 0.93x |
| GLM-5 | $0.006966 | 2,824 | 1.38x | 0.32x |
| Llama 4 Maverick | $0.001610 | 2,572 | 5.95x | 0.35x |

A quality point is one point on the `0` to `1` task scale, summed across the 15
questions. Provider-reported token counts use different tokenizers, so
cross-family token efficiency is directional, not tokenizer-normalized.

### Reliability and the one raw failure

Kendr Intelligent returned all 15 final answers, but one upstream attempt
failed with HTTP 502 after its selected DeepSeek route generated exactly 4,096
output tokens and the routed result was rejected as truncated. The safe retry
succeeded and no credits were charged for the failed attempt. Therefore:

- final-answer availability was 15/15, or 100%;
- raw-attempt reliability was 15/16, or 93.8%;
- the fixed timeout did not recur; there were no HTTP 504 failures.

The run also exposed a separate output-limit compatibility issue. The
OpenAI-compatible benchmark sent `max_tokens=2048`, while the inspected Kendr
request contract accepts `max_output_tokens`; the omitted recognized field
fell back to 4,096. This explains the 80% cap compliance for Kendr Intelligent.
Until those request fields are normalized, the matrix is an endpoint-as-served
comparison rather than a perfectly controlled foundation-model ablation.

### Why Opus 5 ranked below Opus 4.8 in this run

The observed 9.0-point gap was concentrated in table joining and
summarization. The models tied on 12 of 15 questions; Opus 4.8 won three and
Opus 5 won none. The paired question-bootstrap interval for the difference was
`-20.5` to `0.0` percentage points.

This small, single-generation slice is not evidence that Opus 4.8 is generally
better. Provider-effective reasoning settings were also not normalized through
the Kendr request contract. Vendor aggregate claims and this narrow observed
endpoint result therefore answer different questions.

## Methodology

### LiveBench principles used here

The benchmark follows the core design described in
[LiveBench: A Challenging, Contamination-Limited LLM Benchmark](https://arxiv.org/abs/2406.19314):

- recent, frequently refreshed questions to reduce contamination;
- objective, verifiable task graders instead of human or LLM preference
  judging;
- capability-separated reporting rather than one opaque score;
- pinned source, release, task selection, and run parameters for
  reproducibility.

The local adapter adds telemetry that the public benchmark does not own:
provider request IDs, retries, routing, tokens, credits, normalized USD cost,
end-to-end latency, and requested-output-cap compliance. Official LiveBench
judgments are preserved unchanged.

### Reproduction identity

| Parameter | Value |
| --- | --- |
| LiveBench source | `https://github.com/LiveBench/LiveBench` |
| Pinned commit | `4355e9b04222745ccc02a2661d1deebe767a85a2` |
| Release | `2026-06-25` |
| Tasks | `tablejoin`, `summarize`, `connections`, `math_comp`, `zebra_puzzle` |
| Questions per task | 3 |
| Questions per model | 15 |
| Requested maximum output | 2,048 tokens |
| Concurrent requests / grading | 2 / 4 |
| Generations per question | 1 |
| Streaming | Off |
| Tools and web search | Off |
| Kendr conversion used | $0.002 per reported credit |

### Metrics

| Dimension | Definition |
| --- | --- |
| Quality | Mean official, task-specific LiveBench score over all requested questions; provider failures count as zero |
| Relevance | Task correctness and instruction compliance; there is no separate generic relevance score |
| Reliability | Final successful answers and raw successful attempts are reported separately |
| Latency | Client-observed, non-streaming end-to-end request duration; TTFT is unavailable |
| Token usage | Provider-reported input, cached-input, reasoning, and output usage when supplied |
| OpenAI cost | Captured token usage multiplied by the versioned rate card in `config/pricing.json` |
| Kendr cost | Provider-reported credits multiplied by the configured USD-per-credit conversion |
| Efficiency | Captured USD or tokens divided by accumulated quality points |

### Limitations

- This is a five-task, 15-question slice, not the complete LiveBench suite.
- One generation per question does not measure output variance.
- Latency includes different transports and routing overhead; it is not a pure
  model-compute comparison.
- Kendr Intelligent is a routed system and may select different models over
  time.
- Sampling, reasoning, and output-limit parameters are not fully normalized
  across every provider path.
- The test does not cover vision, tools, long context, multi-turn behavior,
  safety, or company-specific production relevance.
- Prices, aliases, routes, and model implementations can change. A new report
  should always identify its date, manifest, release, and source commit.

## Run the benchmark

All commands below use PowerShell from the repository root. Benchmark API calls
are chargeable.

### 1. Install

Requirements:

- Python 3.11 or newer;
- Git;
- provider credentials for the endpoints being tested.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev,kendr]"
kendr-livebench setup
```

The `kendr` extra installs the SDK directly from
[Kendr-AI/Kendr](https://github.com/Kendr-AI/Kendr) at the pinned source
revision declared in `pyproject.toml`; it does not depend on a PyPI release.
`kendr-livebench setup` installs the pinned LiveBench checkout under the
ignored `.vendor/` directory.

### 2. Configure credentials

Create a local `.env` file in the repository root and set only the credentials
needed by the selected providers. This README intentionally contains no
credential values.

| Variable | Purpose |
| --- | --- |
| `OPENAI_API_KEY` | Required for direct OpenAI models |
| `KENDR_API_KEY` | Preferred credential for Kendr API calls |
| `KENDR_SESSION_TOKEN` | Optional Kendr authentication alternative for the custom paired benchmark |
| `KENDR_SESSION_COOKIE` | Optional Kendr authentication alternative for the custom paired benchmark |
| `KENDR_USD_PER_CREDIT` | Optional override for the USD conversion; defaults to `0.002` |

The LiveBench and matrix commands require `KENDR_API_KEY` for Kendr runs.
Credential values are never written to generated reports. `.env` and related
local secret files are excluded by `.gitignore`.

Use `--env-file` to select another local file, or `--no-env-file` to use
process environment variables only.

### 3. Run a charged smoke test

Start with one question before launching a full matrix:

```powershell
.\.venv\Scripts\kendr-livebench.exe run `
  --provider kendr `
  --model kc-intelligent `
  --model-display-name kendr-intelligent-smoke `
  --bench-name live_bench/reasoning/zebra_puzzle `
  --livebench-release-option 2026-06-25 `
  --question-end 1 `
  --max-tokens 512 `
  --ignore-missing-answers `
  --label smoke
```

Inspect the generated summary for provider errors, missing token/cost data, and
output-cap violations before continuing.

### 4. Run the nine-model matrix

```powershell
.\.venv\Scripts\kendr-benchmark-matrix.exe `
  --confirm-paid-run `
  --label all-models
```

`--confirm-paid-run` is mandatory because the command makes chargeable API
calls. By default, the command runs the same five tasks and nine-model panel
used in the latest report.

To run a smaller panel, repeat `--include`:

```powershell
.\.venv\Scripts\kendr-benchmark-matrix.exe `
  --include kendr-intelligent `
  --include openai-sol `
  --include deepseek-v3-2 `
  --confirm-paid-run `
  --label focused-comparison
```

Available panel keys are:

- `kendr-intelligent`
- `claude-opus-5`
- `claude-opus-4-8`
- `openai-sol`
- `openai-terra`
- `glm-5`
- `deepseek-v3-2`
- `kimi-k2-5`
- `llama-4-maverick`

Run `kendr-benchmark-matrix --help` before changing release, tasks, question
counts, concurrency, pricing, or reasoning settings.

### 5. Run paired custom cases

For controlled cost and token experiments using
`benchmarks/cases.jsonl`:

```powershell
.\.venv\Scripts\kendr-bench.exe `
  --providers openai,kendr `
  --repeat 3 `
  --label paired-baseline
```

Each JSON Lines case contains `id`, `category`, `instructions`, and `input`.
Use this path for production-shaped prompts; use the LiveBench path for
standard objective quality scoring.

### 6. Rebuild reports without API calls

Recompute a completed matrix after reporting-code changes:

```powershell
.\.venv\Scripts\kendr-benchmark-matrix.exe `
  --rebuild "results\matrix\<matrix-id>"

.\.venv\Scripts\python.exe `
  scripts\generate_matrix_documentation.py `
  "results\matrix\<matrix-id>"
```

Rebuild a single LiveBench run:

```powershell
.\.venv\Scripts\kendr-livebench.exe summarize `
  "results\livebench\<run-id>"
```

These commands do not make provider calls.

### 7. Run the test suite

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## Generated data and security

Paid runs write plaintext prompts, model responses, request metadata, grades,
and aggregate reports below `results/`. That directory is intentionally
ignored: only the latest reviewed aggregate report is published in this
README.

Never put secrets or personal data in benchmark prompts. Before publishing an
updated report, review the aggregate values, confirm the source release and
commit, and scan the staged files for credentials. Do not publish raw request
or response artifacts without a separate privacy review.

## References

- Colin White et al.,
  [LiveBench: A Challenging, Contamination-Limited LLM Benchmark](https://arxiv.org/abs/2406.19314),
  ICLR 2025 Spotlight.
- [LiveBench source repository](https://github.com/LiveBench/LiveBench)
- [LiveBench public leaderboard](https://livebench.ai/)
- [Kendr source SDK](https://github.com/Kendr-AI/Kendr)
