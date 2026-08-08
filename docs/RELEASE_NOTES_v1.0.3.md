# LLM Benchmark Protocol v1.0.3

Release date: 2026-08-08

Researcher: **Dr. Prashant Kumar Dey**<br>
Project steward: **Kendr**

## Purpose of this release

Version 1.0.3 publishes the dated Kendr current-frontier evaluation and its
separate preview companion. It adds release-grade human-readable handouts,
machine-readable aggregates, provenance and privacy checks, and GitHub release
assets without changing the KGBP 1.0 protocol profile.

This is a research publication. It is not a universal model ranking,
certification, declaration of global acceptance, or standards-body decision.

## Current-frontier GA publication

The frozen callable-subset matrix used 15 objective questions: three from each
of five LiveBench task strata, one generation per endpoint-question cell, and
score-weighted operational goodput as its primary metric. Five generally
available candidates were ranked; GPT-5.5 was an explicitly declared,
unranked baseline.

| Rank | GA candidate | Kendr endpoint | Goodput | 95% interval | Availability |
|---:|---|---|---:|---:|---:|
| 1 | GPT-5.6 Sol | `kc-gpt-5.6-sol` | 79.36% | 60.00%–95.60% | 86.67% |
| 2 | Grok 4.5 | `kc-grok-4.5` | 72.00% | 46.67%–92.00% | 73.33% |
| 3 | Claude Opus 5 | `kc-claude-opus-5` | 68.91% | 46.71%–88.89% | 80.00% |
| 4 | Gemini 3.6 Flash | `kc-google-gemini-3-6-flash` | 33.11% | 12.00%–57.33% | 100.00% |
| 5 | DeepSeek V4 Flash 0731 | `kc-ollama-deepseek-v4-flash-0731` | 13.33% | 0.00%–33.33% | 13.33% |

The unranked GPT-5.5 baseline recorded 68.89% goodput and 73.33%
availability. Six other GA targets remain explicit N/A entries because their
frozen identity, access, maturity, or preflight gate was not satisfied. N/A is
not a zero-capability score.

Six scored endpoints produced 15 paired comparisons. Two separated after Holm
family-wise correction: GPT-5.6 Sol versus DeepSeek V4 Flash 0731, and Claude
Opus 5 versus DeepSeek V4 Flash 0731. GPT-5.6 Sol's point estimate exceeded the
GPT-5.5 baseline by 10.4667 percentage points, but the paired interval was
−2.6667 to +28.7333 points (`p = 0.5`; Holm-adjusted `p = 1.0`). This run
therefore established neither a GPT-5.6/GPT-5.5 difference nor practical
equivalence.

Authoritative materials:

- [execution handout](FRONTIER_EXECUTION_LEADERBOARD_2026-08-08.md);
- [market and Kendr coverage register](FRONTIER_MODEL_COVERAGE_2026-08-08.md);
- [GPT-5.6 versus GPT-5.5 analysis](GPT_5_6_VS_5_5_ANALYSIS_2026-08-08.md);
- [GA aggregate JSON](data/frontier-2026-08-08/kendr-frontier-leaderboard-2026-08-08.json),
  [CSV](data/frontier-2026-08-08/kendr-frontier-leaderboard-2026-08-08.csv),
  [generated Markdown](data/frontier-2026-08-08/kendr-frontier-leaderboard-2026-08-08.md),
  and [bundle checksum manifest](data/frontier-2026-08-08/SHA256SUMS).

GA matrix ID:
`20260808T070202Z-frontier-market-kendr-20260808-cfec3672`.

## Preview companion publication

Preview and limited-access configurations were not pooled into the GA rank
sequence. A separately frozen companion matrix used the same 15 question IDs
and sample hash.

Gemini 3.1 Pro Preview (`kc-gemini-3.1-pro-preview`) completed 15/15 cells with
**39.78% operational goodput**, a **16.67% to 65.11%** 95% interval,
**39.78% conditional quality**, and **100.00% availability**.

It receives no ordinal rank because it is the companion's only scored
endpoint. No pairwise test exists for a one-endpoint comparison family, and
the result must not be read as a rank against the GA candidates. Qwen 3.8 Max
Preview (`kc-qwen3.8-max-preview`) remains N/A because the dedicated paid Model
Studio Token Plan endpoint and credential were not configured.

Authoritative companion materials:

- [companion handout](data/frontier-preview-2026-08-08/kendr-frontier-preview-companion-2026-08-08.md);
- [aggregate JSON](data/frontier-preview-2026-08-08/kendr-frontier-preview-companion-2026-08-08.json);
- [aggregate CSV](data/frontier-preview-2026-08-08/kendr-frontier-preview-companion-2026-08-08.csv);
- [bundle checksum manifest](data/frontier-preview-2026-08-08/SHA256SUMS).

Companion matrix ID:
`20260808T083825Z-frontier-preview-kendr-20260808-d910f1e1`.

## Version and provenance boundaries

Publication version and execution-software version are intentionally separate:

- `v1.0.3` is the software and publication release described here;
- the GA current-frontier matrix records execution software `1.0.2`;
- the preview companion records execution software `1.0.2`;
- the earlier 35-endpoint catalog pilot records execution software `1.0.0`.

The version bump does not retroactively relabel any execution. The GA and
preview-companion JSON, CSV, generated Markdown, and nested `SHA256SUMS` files
remain byte-identical to their frozen publication inputs.

## Privacy and integrity boundary

The public frontier bundles contain aggregate metrics, public configuration
identity, explicit N/A states, source hashes, and bounded scientific claims.
They exclude raw prompts, raw responses, provider request identifiers,
provider error messages, credentials, and machine-local paths.

The offline release verifier pins the execution versions, matrix IDs, scope,
row identity and order, scoring content, no-rank companion treatment,
provenance hashes, privacy declarations, CSV/Markdown consistency, and bundle
checksums. Checksums detect byte drift; they are not a substitute for release
attestation or independent replication.

The LiveBench adapter also has a bounded grading-recovery path: when every
planned answer is current but a successful answer lacks a judgment, it retries
only that missing local judgment once with serial grading. It never replays a
provider inference and still fails closed if grading remains incomplete.

## Tagged release assets

The GitHub tag workflow retains the existing package, white paper, catalog
pilot, protocol-audit, SBOM, brand, and release-wide checksum assets. Version
1.0.3 additionally includes:

- the frontier execution, coverage, and GPT-5.6/GPT-5.5 handouts;
- the GA JSON, CSV, and generated Markdown;
- the preview-companion JSON, CSV, and generated Markdown;
- both nested bundle manifests under unique GA and preview-companion filenames.

The workflow then generates an outer release-wide `SHA256SUMS` and provenance
attestations for the assembled assets.

## Limitations and permitted claim

Both frontier runs are small, English-oriented, one-generation,
endpoint-as-served snapshots. Preview behavior can change, provider defaults
were not fully normalized, rank intervals were not estimated, and the study
does not cover the multilingual, multimodal, safety, repeated-generation,
multi-region, load, independent-review, or external-replication requirements
needed for a broad global claim.

Permitted summary:

> In the dated 2026-08-08 Kendr callable-subset matrix, GPT-5.6 Sol had the
> highest operational-goodput point estimate among five scored GA candidates;
> most pairwise comparisons remained unresolved after correction. A separate
> one-endpoint preview companion measured Gemini 3.1 Pro Preview at 39.78%
> goodput with 100% availability and assigned no rank. Qwen 3.8 Max Preview
> remained N/A.

## Citation

Use [CITATION.cff](../CITATION.cff), cite release `v1.0.3`, identify
**Dr. Prashant Kumar Dey** as the researcher and **Kendr** as project steward,
and include the exact matrix ID for every reused result set.
