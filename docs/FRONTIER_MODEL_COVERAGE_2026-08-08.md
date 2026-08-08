# Frontier model coverage register — 2026-08-08

**Status:** Research snapshot and campaign-planning input<br>
**Evidence cut-off:** 2026-08-08<br>
**Not a benchmark result:** This document does not replace or revise the [frozen Kendr pilot rankings](RANKINGS_2026-08-08.md).

This register defines which current frontier systems should be considered for the next globally scoped LLM Benchmark campaign. It records exact vendor API identifiers, access maturity, system type, and the independent evidence used to justify coverage. Inclusion means that a system is relevant to one or more measured constructs; it does **not** mean that it is universally best, globally certified, or more popular than another model.

## 1. Eligibility and classification

A model configuration is eligible only when all of the following can be recorded before the run:

1. An exact callable model ID or immutable self-hosted revision.
2. Provider, endpoint, region, access date, and applicable terms or weight license.
3. Requested and resolved model identity, including any router, fallback, or provider-side substitution.
4. Reasoning effort or budget, tool policy, context/output limits, sampling parameters, and harness version.
5. At least one relevant external qualification signal or a documented diversity rationale.
6. A legally and operationally reproducible access path for the intended campaign sites.

Coverage tiers:

| Tier | Definition | Reporting rule |
|---|---|---|
| **Core production** | Callable production API or reproducible released weights, with current frontier evidence or a necessary provider/open-weight diversity role | May enter the principal comparison, but only within compatible task and system divisions |
| **Preview / limited** | Preview, token-plan-only, invite-only, region-limited, or otherwise unstable access | Report in a separate maturity stratum; never silently merge with production systems |
| **Coverage baseline** | Important cost, deployment, geographic, or open-weight comparator outside the leading capability cluster | Report as a comparator, not as proof of frontier leadership |
| **Hold** | No verified ID, no reproducible access, identity ambiguity, or an unresolved legal/telemetry requirement | Do not run or rank until the blocking field is resolved |

Every scored row is a **system configuration**, not merely a brand name:

```text
configuration_id = provider + requested_model_id + resolved_revision
                 + endpoint/region + reasoning_effort_or_budget
                 + tools_and_fallback_policy + harness_version + run_time
```

Reasoning settings such as `max` or `xhigh` are configuration values, not model IDs. A rolling alias is unsuitable for archival comparison unless the provider-returned revision is captured. “Open-weight” does not imply “open source”; the exact license must be reported.

## 2. Constructs used to qualify coverage

The external sources below measure different things and must not be blended into a single claim of “best model.”

| Source | Construct | Appropriate use | Not supported |
|---|---|---|---|
| [Artificial Analysis Intelligence Index](https://artificialanalysis.ai/models/) ([methodology](https://artificialanalysis.ai/methodology/intelligence-benchmarking)) | Composite capability across its published evaluation suite, alongside separate speed and price observations | Identify high-capability configurations and open-weight candidates | Universal quality, adoption, or popularity |
| [LiveBench](https://livebench.ai/) ([repository](https://github.com/LiveBench/LiveBench), [paper](https://livebench.ai/livebench.pdf)) | Objective, ground-truth-scored performance across seven categories; the displayed overall is the mean of category averages | Identify objectively competitive systems and category specialists | Human preference or production reliability |
| [Arena](https://arena.ai/leaderboard) ([methodology](https://help.arena.ai/articles/7011479247-how-to-see-ai-rankings-in-arena-leaderboards-2-0-wip), [dataset](https://huggingface.co/datasets/lmarena-ai/leaderboard-dataset)) | Human preference from head-to-head battles, with leaderboard-specific uncertainty | Identify preference leaders in Text, Agent, WebDev, and Vision tracks | Market share, popularity, or a statistically resolved order where intervals overlap |
| This protocol | Task quality, operational goodput, reliability, latency, cost, safety, robustness, multilingual performance, and other declared dimensions | Measure the deployed endpoint as served under a frozen campaign | An intrinsic, permanent property of the underlying model family |

As observed on 2026-08-08, these sources did not identify one common winner. LiveBench’s 2026-06-25 release displayed Fable 5 Max at 83.0, GPT-5.6 Sol Max at 81.0, GPT-5.5 xHigh at 80.2, Claude Opus 5 Max at 80.1, Kimi K3 at 79.2, and Qwen 3.8 Max at 78.5. Arena’s Text board displayed Fable 5 at 1507±6, Claude Opus 4.6 Thinking at 1505±4, Claude Opus 4.7 Thinking at 1502±4, and Muse Spark 1.2 xHigh at 1498±13; overlapping intervals make fine ordering uncertain. Artificial Analysis displayed several effort-specific configurations in its leading cluster, including Claude Opus 5, Fable 5 with fallback, GPT-5.6 Sol, Kimi K3, Muse Spark 1.2, GLM-5.2, and DeepSeek V4 Flash. These values are dated qualification signals, not results of this repository’s benchmark.

## 3. Core production coverage

Context and output limits below are vendor-advertised maxima, not proof that every access path or account receives the same limits. Verify them during preflight.

| Provider / model | Exact vendor API ID for the campaign | System and access class | Advertised I/O and limits | Coverage rationale | Primary vendor sources |
|---|---|---|---|---|---|
| Anthropic Claude Fable 5 | `claude-fable-5` | Hosted proprietary; production API | Text/image in, text out; 1M context, 128K output | LiveBench and Arena leader; Artificial Analysis entry includes fallback and therefore needs special treatment | [model guide](https://platform.claude.com/docs/en/about-claude/models/introducing-claude-fable-5-and-claude-mythos-5), [global restoration](https://www.anthropic.com/news/redeploying-fable-5), [fallback behavior](https://platform.claude.com/docs/en/build-with-claude/refusals-and-fallback) |
| Anthropic Claude Opus 5 | `claude-opus-5` | Hosted proprietary; production API | Text/image in, text out; 1M context, 128K output; adaptive thinking | Leading capability and agent configuration across independent sources | [model overview](https://platform.claude.com/docs/en/about-claude/models/overview), [Opus 5 guide](https://platform.claude.com/docs/en/about-claude/models/whats-new-opus-5), [release notes](https://platform.claude.com/docs/en/release-notes/overview) |
| OpenAI GPT-5.6 Sol | `gpt-5.6-sol` | Hosted proprietary; production API | Text/image in, text out; 1,050,000 context, 128K output | Leading objective/composite capability and agent evidence | [model card](https://developers.openai.com/api/docs/models/gpt-5.6-sol), [launch](https://openai.com/index/gpt-5-6/) |
| Moonshot AI Kimi K3 | `kimi-k3` | Hosted plus released weights; custom Kimi K3 License | Native text/image input; 1M context; verify video support for the selected API path | Leading open-weight and agent/WebDev candidate; China/provider diversity | [API selection](https://www.kimi.com/help/kimi-api/api-model-selection), [API troubleshooting](https://www.kimi.com/help/kimi-api/api-troubleshooting), [release notes](https://www.kimi.com/code/docs/en/kimi-code/whats-new.html), [weights](https://github.com/MoonshotAI/Kimi-K3) |
| Meta Muse Spark 1.2 | `muse-spark-1.2` | Hosted proprietary; production Model API | Text/image/video/audio/PDF in, text out; 1,048,576 context | Current Text preference and composite-capability candidate; US/provider diversity | [model page](https://developer.meta.com/ai/models/muse-spark/), [API model IDs](https://dev.meta.ai/docs/models), [launch](https://research.meta.ai/blog/introducing-muse-code-and-muse-spark-1-2) |
| Z.ai GLM-5.2 | `glm-5.2` | Hosted plus MIT-licensed weights | Text in, text out; 1M context, 128K output; effort controls | Competitive open-weight candidate; China/provider diversity | [model guide](https://docs.z.ai/guides/llm/glm-5.2), [quick start](https://docs.z.ai/guides/overview/quick-start), [launch](https://z.ai/blog/glm-5.2) |
| DeepSeek V4 Flash | `deepseek-v4-flash` | Hosted plus MIT-licensed weights | Text in/out; thinking and non-thinking modes; 1M context, up to 384K output | Competitive open-weight efficiency candidate; China/provider diversity | [API specification and pricing](https://api-docs.deepseek.com/quick_start/pricing), [API changes](https://api-docs.deepseek.com/updates/), [model list API](https://api-docs.deepseek.com/api/list-models), [weights](https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash) |
| DeepSeek V4 Pro | `deepseek-v4-pro` | Hosted proprietary serving path | Text in/out; thinking and non-thinking modes; 1M context, up to 384K output | Same-family quality/cost comparison and provider coverage | [API specification and pricing](https://api-docs.deepseek.com/quick_start/pricing), [API changes](https://api-docs.deepseek.com/updates/), [model list API](https://api-docs.deepseek.com/api/list-models) |
| xAI Grok 4.5 | `grok-4.5` | Hosted proprietary; production API | Text/image in, text out; 500K context; low/medium/high effort | Independent objective evidence and US/provider diversity | [model page](https://docs.x.ai/developers/models/grok-4.5), [release notes](https://docs.x.ai/developers/release-notes) |
| Google Gemini 3.6 Flash | `gemini-3.6-flash` | Hosted proprietary; generally available API | Text/image/video/audio/PDF in, text out; 1,048,576 context, 65,536 output | Multimodal, latency/cost, and provider-diversity candidate | [model page](https://ai.google.dev/gemini-api/docs/models/gemini-3.6-flash), [API changelog](https://ai.google.dev/gemini-api/docs/changelog) |
| Alibaba Qwen 3.7 Max | Prefer immutable `qwen3.7-max-2026-05-20` for text-only or `qwen3.7-max-2026-06-08` for multimodal; avoid archival use of `qwen3.7-max` | Hosted proprietary; production Model Studio | 1M context, 65,536 output; June snapshot supports image/video input | Objective evidence and China/provider diversity | [model and snapshot IDs](https://www.alibabacloud.com/help/en/model-studio/qwen3-7-max), [model catalog](https://www.alibabacloud.com/help/en/model-studio/models) |

### Required special handling

- **Claude Fable 5:** A refusal can be retried through Anthropic’s fallback mechanism. Record the response-level `model`, every `fallback` content block, and `usage.iterations`. Publish Fable-only and fallback-assisted results separately; do not label a fallback-assisted result as Fable-only.
- **DeepSeek V4 Flash:** `0731` is an observed checkpoint/backend label in third-party leaderboards, not a documented public API ID. Do not invent `deepseek-v4-flash-0731`. Capture provider-returned identity or use an immutable self-hosted weight revision.
- **OpenAI GPT-5.6:** `gpt-5.6` is a routing alias to Sol as of this snapshot. Use `gpt-5.6-sol` and record effort explicitly. Do not equate a product-level “ultra” mode with a single-model `max` configuration.
- **Meta Muse Spark 1.2:** `muse-spark-1.2-contributor` is a separate data-governance configuration whose prompts/completions may be used under contributor terms. It must not be pooled with standard `muse-spark-1.2`.
- **Alibaba Qwen:** Record the explicit dated snapshot and region. A rolling alias can change without producing a new benchmark configuration in the client.

## 4. Preview and limited-access coverage

| Provider / model | Exact API ID | Access maturity | Advertised I/O and limits | Campaign treatment | Primary vendor sources |
|---|---|---|---|---|---|
| Alibaba Qwen 3.8 Max Preview | `qwen3.8-max-preview` | Preview; Model Studio Token Plan access path and dedicated credentials | Reasoning plus visual understanding; 1M context | High-priority preview stratum because LiveBench, Arena Text, WebDev, and Vision show competitive evidence; never shorten the ID to undocumented `qwen3.8-max` | [Token Plan announcement](https://modelstudio.alibabacloud.com/intl/blog/model-studio-token-plan-individual/), [access/tool setup](https://www.alibabacloud.com/help/en/model-studio/token-plan-harness-tool) |
| Google Gemini 3.1 Pro Preview | `gemini-3.1-pro-preview` | Preview | Text/image/video/audio/PDF in, text out; 1,048,576 context, 65,536 output | Separate preview stratum; do not pool with the custom-tools endpoint | [model page](https://ai.google.dev/gemini-api/docs/models/gemini-3.1-pro-preview), [API changelog](https://ai.google.dev/gemini-api/docs/changelog) |
| Anthropic Claude Mythos 5 | `claude-mythos-5` | Invite-only Project Glasswing access | Same model-capability family described with Fable 5; access path differs | Hold unless access, identity, and fallback telemetry can be independently reproduced | [Anthropic model guide](https://platform.claude.com/docs/en/about-claude/models/introducing-claude-fable-5-and-claude-mythos-5) |

Optional coverage baselines for a full global campaign are Anthropic Claude Sonnet 5 (`claude-sonnet-5`) for cost/performance and MiniMax M3 (`MiniMax-M3`) for provider and open-weight diversity. MiniMax describes a 1M-context multimodal model and distributes weights under the MiniMax Community License; confirm the account’s `GET /v1/models` response before freezing the panel ([launch](https://www.minimax.io/blog/minimax-m3), [API availability](https://platform.minimax.io/subscribe/token-plan?tab=api-enterprise), [weights](https://huggingface.co/MiniMaxAI/MiniMax-M3)).

## 5. Kendr coverage register

`Kendr state` is deliberately an enum: `live`, `staged`, or `missing`. The values below come from an authenticated catalog capture and live invocation preflight on 2026-08-08. The 2026-08-07 frozen catalog column is historical evidence only; it must not be interpreted as current availability.

| Target configuration | Vendor ID | Kendr state (`live` / `staged` / `missing`) | Current Kendr ID | Last verified UTC | Frozen 2026-08-07 evidence |
|---|---|---|---|---|---|
| Claude Fable 5, fallback-audited | `claude-fable-5` | `staged` | `kc-claude-fable-5` | 2026-08-08T04:48:00Z | Canonical fail-closed route is staged, but Bedrock requires an explicit `provider_data_share` retention opt-in. That privacy setting was not changed, so Fable is N/A rather than scored zero. |
| Claude Opus 5 | `claude-opus-5` | `live` | `kc-claude-opus-5` | 2026-08-08T07:00:17Z | Canonical Amazon Bedrock US inference-profile route passed public-catalog and live invocation preflight after source-region-scoped pricing reconciliation. The successful response preserved the requested Kendr model identity and returned usage telemetry. |
| GPT-5.6 Sol | `gpt-5.6-sol` | `live` | `kc-gpt-5.6-sol` | 2026-08-08T04:48:00Z | Identity-resolved preflight succeeded. |
| OpenAI GPT-5.5 baseline | `gpt-5.5` | `live` | `kc-openai-gpt-5-5` | 2026-08-08T04:48:00Z | Identity-resolved preflight succeeded; retained to investigate the prior Sol comparison. |
| Kimi K3 | `kimi-k3` | `staged` | `kc-kimi-k3` | 2026-08-08T04:48:00Z | Canonical route and Moonshot adapter are staged fail-closed; no Moonshot credential is configured and discovery exposes no callable model. |
| Muse Spark 1.2 standard | `muse-spark-1.2` | `staged` | `kc-muse-spark-1.2` | 2026-08-08T04:48:00Z | Standard, non-contributor Meta adapter and canonical route are staged fail-closed; no Meta credential or approved exact rate card is configured. |
| GLM-5.2 | `glm-5.2` | `staged` | `kc-glm-5.2` | 2026-08-08T04:48:00Z | Canonical route and Z.AI adapter are staged fail-closed; no Z.AI credential is configured and the public catalog exposes no callable alias. |
| DeepSeek V4 Flash 0731 | self-hosted dated checkpoint | `live` | `kc-ollama-deepseek-v4-flash-0731` | 2026-08-08T04:48:00Z | Identity-resolved preflight succeeded at the exact dated Kendr/Ollama route. It is not merged with the rolling `kc-deepseek-v4-flash` API alias. |
| DeepSeek V4 Pro | `deepseek-v4-pro` | `staged` | — | 2026-08-08T04:48:00Z | Source route exists, but the direct DeepSeek connector is unhealthy and no live alias was exposed. |
| Grok 4.5 | `grok-4.5` | `live` | `kc-grok-4.5` | 2026-08-08T04:48:00Z | Identity-resolved preflight succeeded. |
| Gemini 3.6 Flash | `gemini-3.6-flash` | `live` | `kc-google-gemini-3-6-flash` | 2026-08-08T04:48:00Z | Identity-resolved preflight succeeded with an adequate 256-token output cap. |
| Qwen 3.7 Max immutable snapshot | `qwen3.7-max-2026-05-20` or `qwen3.7-max-2026-06-08` | `staged` | — | 2026-08-08T04:48:00Z | Source route exists, but Alibaba Qwen has no configured credential and no live alias was exposed. |
| Qwen 3.8 Max Preview | `qwen3.8-max-preview` | `staged` | `kc-qwen3.8-max-preview` | 2026-08-08T04:48:00Z | Exact preview route is staged fail-closed. It requires the dedicated paid Token Plan endpoint and credential; ordinary pay-as-you-go access is not available for this preview. |
| Gemini 3.1 Pro Preview | `gemini-3.1-pro-preview` | `live` | `kc-gemini-3.1-pro-preview` | 2026-08-08T04:48:00Z | Identity-resolved preflight succeeded with an adequate 256-token output cap; keep in the preview stratum. |
| Claude Sonnet 5 baseline | `claude-sonnet-5` | `staged` | `kc-claude-sonnet-5` | 2026-08-08T04:48:00Z | Catalog alias exists, but no fresh successful preflight was captured for this campaign. |
| MiniMax M3 baseline | `MiniMax-M3` | `missing` | — | 2026-08-08T04:48:00Z | No Kendr connector or route was present. |

Execution supplement: the separately frozen preview matrix
`20260808T083825Z-frontier-preview-kendr-20260808-d910f1e1` ran Gemini 3.1 Pro
Preview on the same 15 exact question IDs and sample hash as the GA matrix. It
recorded 39.78% operational goodput (95% interval 16.67%–65.11%) and 100%
availability, with no ordinal rank because it was the only scored preview
endpoint. Qwen 3.8 Max Preview remained N/A. See the
[privacy-reviewed companion handout](data/frontier-preview-2026-08-08/kendr-frontier-preview-companion-2026-08-08.md).

For a `live` designation, archive the catalog response hash and demonstrate one successful, identity-resolved, telemetry-complete preflight. `staged` means the adapter/configuration exists but the endpoint has not passed that preflight. `missing` means the authenticated catalog exposes no appropriate route. A failed endpoint is not a zero-capability model; it is an operational failure that belongs in the availability/goodput analysis.

## 6. Freeze checklist for the next campaign

Before the panel is signed:

- Freeze vendor ID, Kendr ID, provider route, endpoint/region, access tier, release maturity, and terms/license.
- Pin reasoning effort/budget, tool availability, fallback policy, sampling controls, context/output caps, and system prompt.
- Capture requested and resolved model identities on every response; fail closed when a router or fallback cannot be audited.
- Run identity and capability preflights without reusing their answers in the scored set.
- Stratify production, preview, routed, research-agent, proprietary-hosted, and open-weight/self-hosted systems.
- Publish construct-specific results and Pareto trade-offs; do not collapse quality, reliability, latency, cost, safety, and preference into an unexplained universal score.
- Retain the old pilot unchanged, with its campaign ID, hashes, narrow 15-question scope, and `0/595` Holm-significance disclosure.

This register should be regenerated or re-verified whenever a model ID, serving route, access maturity, or independent leaderboard release changes.
