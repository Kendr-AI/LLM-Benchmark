# Kendr frontier preview companion — 2026-08-08

**Matrix ID:** `20260808T083825Z-frontier-preview-kendr-20260808-d910f1e1`

This is a separate preview/limited-access companion publication. It is not pooled into, and must not be read as a rank against, the GA leaderboard.

## Scope

| Field | Value |
| --- | --- |
| Companion profile entries | 2 |
| Scored companion entries | 1 |
| N/A companion entries | 1 |
| Questions | 15 |
| Tasks | 5 |
| Generations per endpoint-question | 1 |
| Ranking status | single-scored-endpoint-descriptive-no-rank |

## Companion result

| Ranking treatment | Model | Kendr endpoint | Operational goodput | 95% interval | Conditional quality | Availability | Successful / planned |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Not assigned (single row) | Gemini 3.1 Pro Preview | `kc-gemini-3.1-pro-preview` | 39.78% | 16.67% to 65.11% | 39.78% | 100.00% | 15 / 15 |

Exactly one companion endpoint was scored, so no ordinal rank is assigned. The JSON and CSV retain the full-precision aggregate metrics.

## Companion entries reported as N/A

| Model | Configured endpoint | Audit status | Reason |
| --- | --- | --- | --- |
| Qwen 3.8 Max Preview | `kc-qwen3.8-max-preview` | missing | The exact preview route is staged fail-closed, but it requires a dedicated paid Model Studio Token Plan endpoint and credential that are not configured. |

N/A means no inference was scheduled for that profile entry; it is not a zero score.

## Companion-only paired inference

No pairwise test exists because this dated campaign permits exactly one scored companion endpoint. The comparison family contains zero GA or baseline endpoints.

## Provenance and limitations

Execution software: `llm-benchmark-protocol 1.0.2` at source commit `33ea04dc78f4f2fb50fb45c822a245bcbd686d38`.

The execution worktree was clean at the recorded source commit.

This small, one-generation endpoint-as-served snapshot does not establish a global model rank, production-model superiority, or stable preview behavior.

## Privacy boundary

The public bundle contains aggregate metrics, exact public endpoint and configuration identity, source hashes, and N/A reasons. It excludes raw prompts, raw responses, provider request identifiers, provider error messages, credentials, and machine-local paths. `SHA256SUMS` detects byte drift but is not a digital signature.
