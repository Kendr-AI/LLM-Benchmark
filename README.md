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
> Every model received the same 15-question slice and the same *requested*
> output cap; not every endpoint honored it. The published artifacts under
> `results/` are gitignored, so a third party cannot verify these figures
> without re-running a paid matrix with their own credentials.

## Latest verified report

**Run:** `20260727T214108Z-all-models-timeout-fixed-594145d3`

Kendr Intelligent placed first on this slice at **89.1% quality** and cost
**$0.027234**. It was **4.71x as cost-efficient as direct OpenAI GPT-5.6 Sol**
by quality points per measured USD.

> [!WARNING]
> **No adjacent rank gap in this table is separated at 95% confidence.** On a
> paired per-question test, 0 of 8 neighbouring pairs clear zero, including
> first versus second. Read the ordering as one plausible arrangement of a
> nine-way near-tie, not as a ranking. Only Llama 4 Maverick separates from the
> leader at all.

Kendr also used more tokens and had higher latency than Sol, and did not honor
the requested output cap on 4 of 16 attempts, so its token axis is not directly
comparable to a fully compliant endpoint's.

The complete pass produced:

- 9 models or routed systems;
- 5 capabilities and 15 questions per model;
- 135 final answers from 136 raw provider attempts;
- 97,372 input tokens and 80,055 output tokens;
- 177,427 total captured tokens;
- $0.775727 total measured API cost;
- no final-answer failures and no HTTP 504 timeout failures.

### Overall leaderboard

Models sharing a tier are not separated at 95% confidence. `*` marks an
interval whose bound is censored by the score scale rather than estimated —
a `100.0%` bound means the resampled mean hit the ceiling.

| Rank | Tier | Model/system | Quality (95% question-bootstrap CI) | Input / output tokens | Cost | p50 / p95 latency | Final / raw reliability | Cap compliance |
| ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 1 | Kendr Intelligent | 89.1% (76.1%-100.0%*) | 12,415 / 19,299 | $0.027234 | 9.70s / 60.20s | 100.0% / 93.8% | 75.0% |
| 2 | 1 | DeepSeek V3.2 | 84.8% (70.4%-96.7%) | 10,119 / 11,491 | $0.029459 | 12.88s / 53.24s | 100.0% / 100.0% | 86.7% |
| 3 | 1 | Claude Opus 4.8 | 80.0% (62.2%-95.6%) | 13,987 / 3,534 | $0.169365 | 4.29s / 10.61s | 100.0% / 100.0% | 100.0% |
| 4 | 1 | Kimi K2.5 | 76.1% (56.1%-93.3%) | 10,460 / 8,662 | $0.034520 | 5.56s / 20.28s | 100.0% / 100.0% | 93.3% |
| 5 | 1 | OpenAI GPT-5.6 Sol | 71.1% (48.9%-91.1%*) | 7,574 / 2,146 | $0.102250 | 3.67s / 10.04s | 100.0% / 100.0% | 100.0% |
| 6 | 1 | Claude Opus 5 | 70.9% (51.8%-88.9%) | 14,017 / 7,952 | $0.287707 | 7.87s / 14.56s | 100.0% / 100.0% | 100.0% |
| 7 | 1 | OpenAI GPT-5.6 Terra | 64.4% (42.2%-86.7%*) | 7,574 / 1,918 | $0.047705 | 2.01s / 4.74s | 100.0% / 100.0% | 100.0% |
| 8 | 1 | GLM-5 | 62.2% (37.8%-84.4%*) | 10,722 / 15,638 | $0.065017 | 20.03s / 80.48s | 100.0% / 100.0% | 80.0% |
| 9 | 2 | Llama 4 Maverick | 51.6% (30.1%-73.6%) | 10,504 / 9,415 | $0.012469 | 3.32s / 7.61s | 100.0% / 100.0% | 100.0% |

The confidence intervals resample these 15 questions only. They do not include
generation-to-generation variation or uncertainty from choosing this task
slice. At 15 discrete-valued questions the resampled mean takes roughly 150
distinct values, so bounds are coarse.

### Does any rank gap survive a paired test?

Each row resamples the per-question differences between two adjacent ranks,
which is the only test that uses the fact that both answered the same
questions.

| Higher rank | Lower rank | Mean difference | 95% CI | W/L/T | Separated? |
| --- | --- | ---: | ---: | ---: | --- |
| Kendr Intelligent | DeepSeek V3.2 | +4.3 pp | -0.4 to +13.3 | 1/1/13 | no |
| DeepSeek V3.2 | Claude Opus 4.8 | +4.8 pp | -8.1 to +19.0 | 2/2/11 | no |
| Claude Opus 4.8 | Kimi K2.5 | +3.9 pp | +0.0 to +9.4 | 2/0/13 | no |
| Kimi K2.5 | OpenAI GPT-5.6 Sol | +5.0 pp | -5.0 to +20.0 | 1/1/13 | no |
| OpenAI GPT-5.6 Sol | Claude Opus 5 | +0.2 pp | -18.0 to +16.6 | 2/2/11 | no |
| Claude Opus 5 | OpenAI GPT-5.6 Terra | +6.5 pp | -13.7 to +28.9 | 3/2/10 | no |
| OpenAI GPT-5.6 Terra | GLM-5 | +2.2 pp | -22.2 to +26.7 | 2/2/11 | no |
| GLM-5 | Llama 4 Maverick | +10.6 pp | -17.2 to +38.7 | 4/3/8 | no |

Most pairs tied on 10 or more of 15 questions. The first-versus-second gap
rests on a single question won in each direction. A slice this small can
order endpoints but cannot separate them.

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
| Kendr Intelligent | $0.002037 | 2,372 | 4.71x | 0.38x |
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

Two asymmetries matter when reading the cost column:

- The Kendr figure is an invoice — credits actually billed, including any
  service margin. The OpenAI figure is undiscounted list price computed from
  token usage. The ratio is what a buyer pays, not a ratio of inference costs.
- Kendr Intelligent's router consumes roughly 1,600 tokens per request of its
  own. Those are inside the billed credits, and therefore inside its cost, but
  they are not in its token counts. Its tokens-per-quality-point is understated
  relative to a direct endpoint's.

### Reliability and the one raw failure

Kendr Intelligent returned all 15 final answers, but one upstream attempt
failed with HTTP 502 after its selected DeepSeek route generated exactly 4,096
output tokens and the routed result was rejected as truncated. The safe retry
succeeded and no credits were charged for the failed attempt. Therefore:

- final-answer availability was 15/15, or 100%;
- raw-attempt reliability was 15/16, or 93.8%;
- the fixed timeout did not recur; there were no HTTP 504 failures.

That rejected attempt still generated 4,096 output tokens and 812 input
tokens. They are counted in the totals above even though no credits were
charged, because the tokens were really produced; excluding them understated
Kendr's output volume by 27% and its tokens-per-quality-point by 13%.

Raw-attempt reliability is not comparable across providers. Kendr retries are
explicit and logged as separate attempts, while the OpenAI client retries
inside its transport, so an OpenAI raw-attempt rate can only ever read 100%.

The run also exposed a separate output-limit compatibility issue. The
OpenAI-compatible benchmark sent `max_tokens=2048`, while the inspected Kendr
request contract accepts `max_output_tokens`; the omitted recognized field
fell back to 4,096. That is why Kendr Intelligent complied with the requested
cap on only 12 of 16 attempts. **The harness now sends both keys**, so the cap
binds on either contract — but this run predates that change, so its token and
cost axes are not controlled and it needs re-measuring before those columns are
compared. `temperature` and `reasoning_effort` are still absent from the Kendr
contract, so those remain unnormalized.

### Opus 5 versus Opus 4.8 in this run

Opus 4.8 scored 80.0% and Opus 5 scored 70.9%. The models tied on 12 of 15
questions; Opus 4.8 won three and Opus 5 won none. The paired
question-bootstrap interval for the difference was `-20.5` to `0.0` percentage
points, which **includes zero**, so the two are not separated at 95%
confidence.

No cause is attributed here. The comparison rests on three informative
questions out of fifteen, and provider-effective reasoning was not normalized
through the Kendr request contract — Anthropic documents Opus 5 thinking as on
by default while Opus 4.8 adaptive thinking is off unless requested. This slice
is not evidence about which model is generally stronger, and it does not
contradict vendor aggregate claims; the two answer different questions.

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
| Quality | Mean official, task-specific LiveBench score over all requested questions; provider failures count as zero. The confidence interval resamples exactly these normalized scores |
| Tier | Models whose 95% intervals overlap the tier leader's share a tier; a new tier opens only when an interval falls entirely below the leader's lower bound |
| Cap compliance | Share of attempts reporting output at or under the requested cap, measured over every attempt that generated output, including rejected ones |
| Relevance | Task correctness and instruction compliance; there is no separate generic relevance score |
| Reliability | Final successful answers and raw successful attempts are reported separately |
| Latency | Client-observed, non-streaming end-to-end request duration; TTFT is unavailable |
| Token usage | Provider-reported input, cached-input, reasoning, and output usage when supplied |
| OpenAI cost | Captured token usage multiplied by the versioned rate card in `config/pricing.json` |
| Kendr cost | Provider-reported credits multiplied by the configured USD-per-credit conversion |
| Efficiency | Captured USD or tokens divided by accumulated quality points |

### Limitations

- This is a five-task, 15-question slice, not the complete LiveBench suite.
- No adjacent rank gap is separated at 95% confidence. The ordering is not a
  measured ranking.
- One generation per question does not measure output variance.
- Requests ran at concurrency 2, so every latency figure is measured under
  load and is higher than a single-request measurement. The load is identical
  for every model, so ordering is comparable while absolute values are not.
- p95 and p99 over 15 observations are functions of the top two samples only;
  they are not tail statistics.
- Latency includes different transports and routing overhead; it is not a pure
  model-compute comparison.
- Kendr cost is a billed invoice while OpenAI cost is modelled list price, and
  Kendr's router tokens are billed but not counted in its token totals.
- Where cap compliance is below 100%, that endpoint was allowed to generate
  more than the requested budget, which biases token and cost comparisons in
  its favor.
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
  --model kendr-intelligent `
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
