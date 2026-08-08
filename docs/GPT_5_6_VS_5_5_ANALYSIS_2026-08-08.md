# GPT-5.6 Sol versus GPT-5.5: frozen-pilot analysis

**Analysis date:** 2026-08-08<br>
**Frozen matrix:** `20260807T135702Z-kendr-catalog-text-full-20260807-797042f1`<br>
**Scope:** Kendr endpoints as served in one narrow engineering pilot—not a general model-family verdict

## Result in one sentence

GPT-5.5 had a **3.51 percentage-point higher observed operational-goodput point estimate** than GPT-5.6 Sol in this 15-item slice, but the paired 95% interval ran from **−16.49 to +23.51 points**, the exact paired randomization test gave **p = 1.0**, and the Holm-adjusted p-value was **1.0**. The run therefore establishes neither GPT-5.5 superiority nor practical equivalence.

## Exact frozen results

| Metric | GPT-5.5 | GPT-5.6 Sol | GPT-5.5 minus Sol |
|---|---:|---:|---:|
| Kendr panel key | `kc-openai-gpt-5-5` | `kc-gpt-5.6-sol` | — |
| Score-weighted operational goodput | **83.800%** | **80.289%** | **+3.511 pp** |
| Quality points over 15 planned items | 12.5700 | 12.0433 | +0.5267 |
| Availability | **86.667% (13/15)** | **86.667% (13/15)** | 0 pp |
| Conditional quality on successful answers | **96.692%** | **92.641%** | +4.051 pp |
| Paired item wins / losses / ties | 2 / 2 / 11 | 2 / 2 / 11 | Even split |
| Provider failures | 2/15 | 2/15 | Even count |

The primary metric is the mean score over **all 15 planned items**, retaining failed endpoint calls as zero:

```text
operational goodput = sum(item scores, with failures scored zero) / 15

GPT-5.5     = 12.5700 / 15 = 0.838000 = 83.800%
GPT-5.6 Sol = 12.0433 / 15 = 0.802889 = 80.289%
```

Conditional quality asks a different question: how good were the answers when the endpoint returned a successful final answer? Because both endpoints succeeded on 13 items:

```text
GPT-5.5     = 12.5700 / 13 = 0.966923 = 96.692%
GPT-5.6 Sol = 12.0433 / 13 = 0.926410 = 92.641%
```

Goodput is the appropriate primary operational measure here because it does not hide provider failures. Conditional quality is diagnostic and must not be substituted for it.

## Where the point difference came from

Only four paired item scores differed. Using `GPT-5.5 score − GPT-5.6 Sol score`:

| Task stratum | Non-tied item difference | Item winner |
|---|---:|---|
| Data analysis / table join | −14.00 pp | GPT-5.6 Sol |
| Instruction following / summarization | +66.67 pp | GPT-5.5 |
| Language / connections | −100.00 pp | GPT-5.6 Sol |
| Reasoning / zebra puzzle | +100.00 pp | GPT-5.5 |
| Remaining 11 paired items | 0 pp | Tie |

Those four differences sum to +52.67 points; divided across all 15 planned items, they produce the +3.51-point mean gap. At the five three-item task-stratum aggregates, GPT-5.5 led instruction following and reasoning, GPT-5.6 Sol led data analysis and language, and math tied:

| Task stratum | GPT-5.5 | GPT-5.6 Sol | Observed leader |
|---|---:|---:|---|
| Data analysis / table join | 85.67% | 90.33% | Sol |
| Instruction following / summarization | 100.00% | 77.78% | GPT-5.5 |
| Language / connections | 66.67% | 100.00% | Sol |
| Math / computation | 66.67% | 66.67% | Tie |
| Reasoning / zebra puzzle | 100.00% | 66.67% | GPT-5.5 |

With only three observations per stratum, these category values are descriptive. They are not reliable evidence of domain specialization.

## Paired uncertainty and hypothesis test

For each shared item, the artifact formed the operational-score difference `GPT-5.5 − GPT-5.6 Sol`. Its reported statistics were:

- Mean paired difference: **+0.035111**, or **+3.51 percentage points**.
- Paired 95% interval: **[−0.164889, +0.235111]**, or **[−16.49, +23.51] percentage points**.
- Non-zero pairs: **4**; GPT-5.5 wins: **2**; Sol wins: **2**; ties: **11**.
- Exact two-sided paired sign-randomization p-value: **1.0** over 16 sign permutations.
- Holm-adjusted p-value: **1.0** in the matrix-wide family of 595 endpoint-pair tests.
- Separation after Holm family-wise correction at 5%: **no**.

The interval includes zero and sizeable effects in both directions. A p-value of 1.0 is not proof that the models are equal; it says this sparse, tied outcome is fully compatible with the randomization null used by the protocol. The declared practical-equivalence margin was ±2 points, but the interval is much wider than that band, so this run also does **not** establish equivalence.

## Configuration and scope constraints

This was not a comparison of each model at its strongest advertised setting.

- The sample contained **15 English-oriented items**, three each from table join, summarization, word connections, math computation, and zebra puzzles.
- It used **one captured generation per endpoint/item**, selected by the `earliest-captured-provider-trial` policy. There was no estimate of within-model generation variance.
- Both run manifests requested **`reasoning_effort: "none"`**, temperature 0, a 2,048-token output cap, a 120-second deadline, and request concurrency 2.
- Calls went through Kendr catalog aliases `kc-openai-gpt-5-5` and `kc-gpt-5.6-sol`. The recorded `actual_model` echoed those aliases rather than an immutable OpenAI snapshot, so the provider-resolved revision and effective downstream configuration were not independently established.
- Consequently, this was **not** GPT-5.6 Sol at `xhigh` or `max`, and it should not be compared directly with leaderboard entries carrying those effort labels.
- Both endpoints produced 13 successful answers and two `InternalServerError` outcomes. Goodput therefore measures the endpoint-as-served combination of answer quality and operational success, not latent model capability alone.

OpenAI’s current documentation identifies `gpt-5.6-sol` as the frontier member of the GPT-5.6 family and says the `gpt-5.6` alias routes to it. The documentation also treats reasoning effort as an explicit evaluation variable: GPT-5.6 supports `none`, `low`, `medium`, `high`, `xhigh`, and `max`, while GPT-5.5 supports `none` through `xhigh` and defaults to medium. OpenAI recommends workload-specific evaluations at matched effort before migration conclusions. See the official [GPT-5.6 Sol model page](https://developers.openai.com/api/docs/models/gpt-5.6-sol), [GPT-5.5 model page](https://developers.openai.com/api/docs/models/gpt-5.5), and [GPT-5.6 model guidance](https://developers.openai.com/api/docs/guides/latest-model#update-api-and-model-parameters).

“Frontier” is a product-level capability designation, not a mathematical promise of monotonic dominance on every task, prompt, serving route, effort level, or finite sample. A newer frontier model can trail an earlier model on a small slice because of sampling variation, task mix, effort configuration, endpoint failures, prompt interaction, or genuine local strengths and weaknesses.

## Claim-safe interpretation

Supported:

> In the frozen 2026-08-07 Kendr pilot, GPT-5.5’s operational-goodput point estimate was 83.80% versus 80.29% for GPT-5.6 Sol, a +3.51-point observed gap. The endpoints tied 11 of 15 items and split the four non-ties 2–2. The paired interval and corrected test did not establish a difference.

Not supported:

- “GPT-5.5 is better than GPT-5.6 Sol.”
- “GPT-5.6 failed to improve over GPT-5.5.”
- “The two models are equivalent.”
- “This is a GPT-5.6 Sol max/xhigh result.”
- “A frontier model must win every benchmark subset.”

A confirmatory comparison should pre-register a larger representative sample, use multiple generations, verify immutable/resolved model identity, match reasoning effort and tools, and report both quality and operational metrics. It should test at least matched `none` and matched medium configurations, plus `xhigh` or `max` only as separately named quality-first configurations.

## Supplement: 2026-08-08 current-frontier callable-subset matrix

**Supplement date:** 2026-08-08

**Matrix:** `20260808T070202Z-frontier-market-kendr-20260808-cfec3672`

**Execution status:** clean worktree at source commit `12ae34e5ffbd1a461b7c85819d3c16fce34bb97f`

The current-frontier matrix reran the same frozen 15-item sample as a new
endpoint campaign. Its result reversed the earlier point-estimate direction:
GPT-5.6 Sol led the GPT-5.5 baseline by **10.4667 percentage points**. The
reversal does not invalidate either artifact; it demonstrates why a single
small, one-generation endpoint trial cannot support a stable model-family
ordering.

| New-matrix metric | GPT-5.6 Sol | GPT-5.5 baseline | Sol minus GPT-5.5 |
|---|---:|---:|---:|
| Score-weighted operational goodput | **79.3556%** | **68.8889%** | **+10.4667 pp** |
| Availability | **86.6667% (13/15)** | **73.3333% (11/15)** | **+13.3333 pp** |
| Conditional quality on successful answers | **91.5641%** | **93.9394%** | **−2.3753 pp** |
| Failed final records | 2/15 | 4/15 | −2 failures for Sol |

Operational goodput combines answer score with endpoint success over all 15
planned items. In this run, Sol returned two more successful final records,
while GPT-5.5 had the slightly higher conditional quality among successful
answers. The goodput difference therefore cannot be interpreted as a pure
latent-quality effect.

The paired primary-metric inference was:

- Sol minus GPT-5.5 mean difference: **+10.4667 percentage points**.
- Paired 95% interval: **[−2.6667, +28.7333] percentage points**.
- Exact two-sided randomization p-value: **0.5**.
- Holm-adjusted p-value across the six-endpoint, 15-comparison family:
  **1.0**.
- Separation after Holm correction at 5%: **no**.
- Practical equivalence at the declared ±2-point margin: **no**.

The interval contains zero, so the rerun does not establish GPT-5.6 Sol
superiority. It also extends well outside the equivalence margin, so it does
not establish equality. “Not significant” and “equivalent” remain different
claims.

Only **two of all 15 endpoint pairs** separated after Holm correction:
GPT-5.6 Sol versus DeepSeek V4 Flash 0731, and Claude Opus 5 versus DeepSeek V4
Flash 0731. The GPT-5.6 Sol/GPT-5.5 pair was not one of them. Thirteen pairs
remained unresolved after correction.

The configuration caveat also remains. `reasoning_effort: none` was the harness
request value, while provider-side effective reasoning/default behavior was
not normalized through the Kendr request contract. The rows are therefore
“Kendr served default” configurations, not matched max/xhigh evaluations.

Claim-safe summary:

> The 2026-08-08 callable-subset matrix observed 79.36% operational goodput for
> GPT-5.6 Sol and 68.89% for the unranked GPT-5.5 baseline. The +10.47-point
> paired estimate was statistically unresolved after multiplicity correction
> and did not establish practical equivalence.

## Local evidence

- [Frozen ranking handout](RANKINGS_2026-08-08.md)
- [Release-safe aggregate JSON](data/kendr-catalog-pilot-2026-08-08.json)
- [Current-frontier execution handout](FRONTIER_EXECUTION_LEADERBOARD_2026-08-08.md)
- [Current-frontier aggregate JSON](data/frontier-2026-08-08/kendr-frontier-leaderboard-2026-08-08.json)

The public handout’s governing disclosure remains unchanged: zero of 595 pairwise comparisons separated after Holm family-wise correction at 5%.
