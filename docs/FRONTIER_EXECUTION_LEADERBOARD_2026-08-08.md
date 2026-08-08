# Current-frontier callable-subset leaderboard — 2026-08-08

**Matrix ID:** `20260808T070202Z-frontier-market-kendr-20260808-cfec3672`

**Profile:** `kendr-current-frontier-20260808`

**Primary metric:** score-weighted operational goodput

**Scientific status:** descriptive endpoint-as-served engineering snapshot

This handout reports the current-frontier configurations that were callable
through Kendr under the frozen campaign rules. It also keeps every unmeasured
coverage target visible as N/A. It is not a universal model ranking,
certification, standards-body decision, or proof of intrinsic model capability.

## Result at a glance

Five generally available candidates were scored and ranked. GPT-5.5 was scored
only as a declared historical baseline and is not assigned a candidate rank.
Six additional GA coverage targets and two preview/limited-access targets were
not measured. N/A is not zero: those configurations never entered the scored
denominator because their identity, access, maturity, or cohort gate was not
satisfied.

| Frozen field | Value |
|---|---|
| Profile entries | 14 |
| Core GA candidates | 11: five scored, six N/A |
| Baseline | One scored, unranked GPT-5.5 endpoint |
| Preview companion | Two entries, both unranked and N/A |
| Sample | 15 items: three each from five LiveBench task strata |
| Item dates | Six from 2024-06-24; nine from 2024-11-25 |
| Generations | One per scored endpoint-item cell |
| Requested output cap | 2,048 tokens |
| Deadline | 120 seconds per answer |
| Requested reasoning-effort field | `none`; provider defaults were not normalized |
| Execution software | `llm-benchmark-protocol 1.0.2` |
| Source identity | commit `12ae34e5ffbd1a461b7c85819d3c16fce34bb97f`; clean worktree |

## Ranked GA candidates

The printed order follows operational-goodput point estimates. The intervals
are question-resampling intervals for the same failure-normalized estimand;
they are not simultaneous rank intervals. Corrected pairwise inference is
reported separately below.

| Rank | Candidate and exact Kendr endpoint | Goodput | 95% interval | Conditional quality | Availability | Final records |
|---:|---|---:|---:|---:|---:|---:|
| 1 | GPT-5.6 Sol — `kc-gpt-5.6-sol` | **79.36%** | 60.00%–95.60% | 91.56% | 86.67% | 13 successful, 2 failed |
| 2 | Grok 4.5 — `kc-grok-4.5` | **72.00%** | 46.67%–92.00% | 98.18% | 73.33% | 11 successful, 4 failed |
| 3 | Claude Opus 5 — `kc-claude-opus-5` | **68.91%** | 46.71%–88.89% | 86.14% | 80.00% | 12 successful, 3 failed |
| 4 | Gemini 3.6 Flash — `kc-google-gemini-3-6-flash` | **33.11%** | 12.00%–57.33% | 33.11% | 100.00% | 15 successful, 0 failed |
| 5 | DeepSeek V4 Flash 0731 — `kc-ollama-deepseek-v4-flash-0731` | **13.33%** | 0.00%–33.33% | 100.00% | 13.33% | 2 successful, 13 failed |

Operational goodput retains failed endpoint outcomes as zero. Conditional
quality describes only successful answers and can therefore look high when
availability is poor; DeepSeek's 100% conditional value came from only two
successful answers and must not be read as 100% overall performance.

## Unranked GPT-5.5 baseline

| Role | Exact Kendr endpoint | Goodput | 95% interval | Conditional quality | Availability | Final records |
|---|---|---:|---:|---:|---:|---:|
| Declared baseline | `kc-openai-gpt-5-5` | **68.89%** | 46.67%–88.89% | 93.94% | 73.33% | 11 successful, 4 failed |

The baseline's raw matrix order was fourth, but it is deliberately excluded
from the five-candidate rank sequence. Calling it rank 4 would incorrectly
classify a historical comparator as a current-frontier candidate.

## Corrected paired inference

Six scored endpoints yield 15 endpoint-pair comparisons. Exact paired
sign-randomization tests were adjusted together with Holm's family-wise
procedure at 5%.

- **Two of 15 pairs separated after correction:** GPT-5.6 Sol versus DeepSeek
  V4 Flash 0731, and Claude Opus 5 versus DeepSeek V4 Flash 0731. The observed
  effects favored GPT-5.6 Sol and Claude Opus 5, respectively.
- **The other 13 pairs did not separate after correction.** This includes
  adjacent point-estimate ranks and the GPT-5.6 Sol/GPT-5.5 comparison.
- A non-significant comparison is unresolved, not automatically tied or
  equivalent. Equivalence requires its interval to fit inside the declared
  practical-equivalence margin.

For GPT-5.6 Sol minus the GPT-5.5 baseline:

| Statistic | Result |
|---|---:|
| Point-estimate difference | **+10.4667 percentage points** |
| Paired 95% interval | **[−2.6667, +28.7333] percentage points** |
| Exact randomization p-value | **0.5** |
| Holm-adjusted p-value | **1.0** |
| Significant after correction | **No** |
| Practically equivalent at the declared ±2-point margin | **No** |

The interval includes zero, so this matrix does not establish that GPT-5.6 Sol
outperformed GPT-5.5. It also extends well outside ±2 points, so the matrix does
not establish equivalence. See the [paired comparison analysis](GPT_5_6_VS_5_5_ANALYSIS_2026-08-08.md)
for the historical result and the dated rerun supplement.

## GA targets reported as N/A

The sanitized matrix catalog records the first four canonical IDs below as
missing at the execution freeze. The broader integration register describes
their adapters/routes as staged fail-closed. Both statements can be true: code
or a route definition can exist without an eligible callable catalog entry.

| Coverage target | Frozen execution identity | Why it was not scored |
|---|---|---|
| Claude Fable 5 | `kc-claude-fable-5`; missing from frozen catalog | Bedrock required an explicit `provider_data_share` retention opt-in. That privacy setting was not changed, so Fable remained N/A. |
| Kimi K3 | `kc-kimi-k3`; missing from frozen catalog | Moonshot route was staged, but no Moonshot credential was configured and discovery exposed no callable model. |
| Muse Spark 1.2 standard | `kc-muse-spark-1.2`; missing from frozen catalog | The standard, non-contributor route was staged without a Meta credential or approved exact rate card. |
| GLM 5.2 | `kc-glm-5.2`; missing from frozen catalog | Z.AI route was staged without a configured credential or callable public alias. |
| DeepSeek V4 Pro | Vendor target `deepseek-v4-pro`; no executable Kendr ID | The direct DeepSeek connector was unhealthy and exposed no live alias. |
| Qwen 3.7 Max 2026-05-20 | Immutable vendor target; no executable Kendr ID | The Alibaba route was staged without a configured credential or live alias. |

These are access and identity outcomes, not measurements of model capability.
Assigning zero would falsely claim that an inference was attempted under the
frozen schedule.

## Preview and limited-access companion

| Preview target | Frozen state | Treatment |
|---|---|---|
| Qwen 3.8 Max Preview — `kc-qwen3.8-max-preview` | Missing from the frozen callable catalog; staged integration requires the dedicated paid Token Plan endpoint and credential | N/A; not pooled into GA ranks |
| Gemini 3.1 Pro Preview — `kc-gemini-3.1-pro-preview` | Present and preflighted, but classified as preview | N/A; intentionally not scheduled in the GA matrix |

Separating preview from GA prevents a changing or limited-access configuration
from silently influencing a production-model claim. The frozen audit therefore
reports both the GA and companion cohorts as not fully claim-ready.

## What this snapshot supports

Supported wording:

> In the 2026-08-08 Kendr current-frontier callable-subset matrix, GPT-5.6 Sol
> had the highest operational-goodput point estimate among five scored GA
> candidates. Two of 15 endpoint pairs separated after Holm correction. The
> sample was small, and GPT-5.6 Sol did not separate from the unranked GPT-5.5
> baseline.

Unsupported wording includes “best model globally,” “all frontier models were
tested,” “N/A models scored zero,” “GPT-5.6 proved superior to GPT-5.5,” or
“the non-significant pairs are equal.”

## Scope and limitations

- The sample has 15 English-oriented items dated in 2024 and only one
  generation per endpoint-item cell.
- It covers table join, summarization, word connections, math computation, and
  zebra puzzles—not multilingual, multimodal, long-context, tool-use, safety,
  fairness, regional-load, human-outcome, or external-replication constructs.
- `reasoning_effort: none` is the harness request value. The Kendr request
  contract did not normalize every provider's effective reasoning/default
  behavior, so these rows are labeled “Kendr served default,” not max/xhigh.
- Exact Kendr endpoint IDs are public, but the aggregate does not claim an
  immutable downstream provider revision where one was not independently
  captured.
- Several observed costs are lower bounds because failed calls did not provide
  complete billable telemetry. Cost should not be used as a definitive
  tie-breaker without its completeness flag.
- Managed endpoints, aliases, prices, and availability can change. This result
  belongs to the recorded matrix, catalog hash, profile hash, and execution
  date.

## Public artifacts and privacy boundary

- [Sanitized aggregate JSON](data/frontier-2026-08-08/kendr-frontier-leaderboard-2026-08-08.json)
- [Sanitized aggregate CSV](data/frontier-2026-08-08/kendr-frontier-leaderboard-2026-08-08.csv)
- [Generated bundle handout](data/frontier-2026-08-08/kendr-frontier-leaderboard-2026-08-08.md)
- [Bundle-local SHA-256 manifest](data/frontier-2026-08-08/SHA256SUMS)
- [Dated market and Kendr coverage register](FRONTIER_MODEL_COVERAGE_2026-08-08.md)

The public artifacts include aggregate metrics, exact public endpoint IDs,
catalog/profile/manifest hashes, execution software `1.0.2`, and source commit
`12ae34e5ffbd1a461b7c85819d3c16fce34bb97f`. They exclude raw prompts, raw
responses, provider request IDs, provider error messages, credentials, and
machine-local paths. SHA-256 detects drift; it does not authenticate the
publisher or substitute for independent review.
