# Kendr current-frontier callable-subset leaderboard — 2026-08-08

**Matrix ID:** `20260808T070202Z-frontier-market-kendr-20260808-cfec3672`  
**Profile:** `kendr-current-frontier-20260808`  
**Execution software:** `llm-benchmark-protocol 1.0.2`  
**Source commit:** `12ae34e5ffbd1a461b7c85819d3c16fce34bb97f`  
**Dirty worktree:** `no`  
**Status:** Descriptive endpoint-as-served engineering evidence

Descriptive endpoint-as-served engineering snapshot; not a global model ranking, certification, or proof of intrinsic model capability.

## Frozen scope

| Field | Value |
| --- | --- |
| Profile entries | 14 |
| Core GA candidates | 11 |
| Scored GA candidates | 5 |
| Not measured GA candidates | 6 |
| Scored baselines | 1 |
| Preview companion entries | 2 |
| Questions per scored endpoint | 15 |
| Tasks | 5 |
| Generations per endpoint-question | 1 |
| Requested output cap | 2048 |
| Requested reasoning effort | none |
| Benchmark package version | 1.0.2 |
| Execution source commit | `12ae34e5ffbd1a461b7c85819d3c16fce34bb97f` |
| Execution worktree dirty | no |

## Scored GA candidates

| Rank | Model | Kendr endpoint | Operational goodput | 95% interval | Quality | Conditional quality | Availability | p50 latency (ms) | Observed cost |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | GPT-5.6 Sol | `kc-gpt-5.6-sol` | 79.4% | 60.0%–95.6% | 79.4% | 91.6% | 86.7% | 15,595 | ≥$0.268985 |
| 2 | Grok 4.5 | `kc-grok-4.5` | 72.0% | 46.7%–92.0% | 72.0% | 98.2% | 73.3% | 24,098 | ≥$0.024882 |
| 3 | Claude Opus 5 | `kc-claude-opus-5` | 68.9% | 46.7%–88.9% | 68.9% | 86.1% | 80.0% | 11,605 | ≥$0.259452 |
| 4 | Gemini 3.6 Flash | `kc-google-gemini-3-6-flash` | 33.1% | 12.0%–57.3% | 33.1% | 33.1% | 100.0% | 10,781 | $0.235908 |
| 5 | DeepSeek V4 Flash 0731 | `kc-ollama-deepseek-v4-flash-0731` | 13.3% | 0.0%–33.3% | 13.3% | 100.0% | 13.3% | 8,291 | ≥$0.000832 |

`rank` excludes the declared GPT-5.5 baseline. `execution_rank` in the machine-readable bundle preserves the original scored matrix order.

## Declared baseline

| Role | Model | Kendr endpoint | Matrix order | Operational goodput | Quality | Availability |
| --- | --- | --- | --- | --- | --- | --- |
| Baseline | GPT-5.5 baseline | `kc-openai-gpt-5-5` | 4 | 68.9% | 68.9% | 73.3% |

## Core GA candidates reported as N/A

| Model | Configured Kendr endpoint | Coverage identity | Catalog status | Reason |
| --- | --- | --- | --- | --- |
| Claude Fable 5 | `kc-claude-fable-5` | `claude-fable-5` | missing | Canonical Fable routing is staged, but Bedrock requires explicit provider_data_share consent that can share prompts and completions with Anthropic and retain them for up to 30 days. Kendr did not change that privacy setting, so this configuration is N/A rather than scored zero. |
| Kimi K3 | `kc-kimi-k3` | `kimi-k3` | missing | Canonical Moonshot routing is staged fail-closed, but no Moonshot credential is configured and discovery exposes no callable Kimi K3 endpoint. |
| Muse Spark 1.2 standard | `kc-muse-spark-1.2` | `muse-spark-1.2` | missing | The standard non-contributor Meta route is staged fail-closed, but no Meta credential or approved exact standard-route rate card is configured. |
| GLM 5.2 | `kc-glm-5.2` | `glm-5.2` | missing | Canonical Z.AI routing and verified pricing are staged fail-closed, but no Z.AI credential is configured and no callable GLM 5.2 alias is exposed. |
| DeepSeek V4 Pro | N/A | `deepseek-v4-pro` | staged | Coverage target is staged without an exact executable Kendr catalog ID; report N/A until a canonical identity passes preflight. |
| Qwen 3.7 Max 2026-05-20 | N/A | `qwen3.7-max-2026-05-20` | staged | Text-only immutable coverage target is staged without an exact executable Kendr catalog ID; report N/A until a canonical identity passes preflight. |

N/A means not measured under this frozen execution. It is not a zero score. A scheduled endpoint with complete zero-goodput evidence would remain a scored zero.

## Preview and limited-access companion

| Model | Configured Kendr endpoint | Status | Reason |
| --- | --- | --- | --- |
| Qwen 3.8 Max Preview | `kc-qwen3.8-max-preview` | N/A | The exact preview route is staged fail-closed, but it requires a dedicated paid Model Studio Token Plan endpoint and credential that are not configured. |
| Gemini 3.1 Pro Preview | `kc-gemini-3.1-pro-preview` | N/A | Preview or limited-access companion was not scheduled in the GA callable-subset matrix. |

Preview and limited-access systems are not pooled into GA ranks or superiority claims.

## GPT-5.6 Sol versus GPT-5.5 baseline

The paired operational-goodput effect for GPT-5.6 Sol minus the GPT-5.5 baseline was +10.47 percentage points (95% interval -2.67 to +28.73). The exact randomization p-value was 0.5; the Holm-adjusted p-value was 1.

This narrow endpoint-as-served comparison does not establish that either model family is intrinsically or universally superior.

## Inference and interpretation

The matrix contains 15 paired comparisons; 2 separated after the declared Holm family-wise correction. Consult corrected paired effects before interpreting point-estimate order.

The requested reasoning-effort field was `none`. This is the harness request value. Kendr endpoint labels state served default because provider-side effort/default behavior was not normalized across vendors.

The execution worktree was clean at the recorded source commit.

This campaign used a small, one-generation, 5-task objective slice. It did not measure multilingual breadth, multimodal behavior, long context, tool use, safety, fairness, regional load, human outcomes, or independent replication. Point-estimate order is therefore descriptive and may be unstable.

## Privacy and reproducibility

The public bundle contains aggregate measurements, exact public endpoint identifiers, source hashes, and N/A reasons. It excludes raw prompts, raw responses, provider request identifiers, error messages, credentials, and machine-local paths. The bundle-local `SHA256SUMS` detects byte drift but is not a digital signature.
