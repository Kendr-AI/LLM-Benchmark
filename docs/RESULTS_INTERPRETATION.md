# Results interpretation guide

This guide explains how to read LLM Benchmark Protocol result sets, with the 2026-08-07 Kendr catalog pilot as the concrete example. The pilot is a research artifact, not a certified or globally accepted ranking.

## Start with the claim boundary

The pilot supports only this narrow statement:

> It describes 35 text-compatible endpoint identifiers as served through the captured Kendr API catalog on a frozen 15-question LiveBench slice, under the recorded output, timeout, concurrency, scoring, and failure rules.

It does not estimate all LLM capability, global user utility, multilingual quality, safety, agent performance, or future provider reliability. A display name is not the unit of analysis: the endpoint identifier and serving path are. That is why two Claude Opus 4.8 endpoint IDs remain separate rows.

## Read divisions before ranks

The release uses three operational divisions:

- **Fixed managed text endpoints:** a named served endpoint is requested.
- **Routed systems:** the service can select a downstream endpoint per request.
- **Managed research systems:** catalog-classified research/search-oriented endpoints under the release's mechanical rule.

Division labels describe observed service boundaries, not model architecture or vendor intent. Cross-division ranks are printed for traceability, but fixed endpoints, routers, and research services do not expose identical semantics.

## Primary and supporting metrics

| Metric | Question answered | Common mistake |
|---|---|---|
| Operational goodput | How much task score survived failures and declared operational constraints? | Reading it as conditional capability |
| End-to-end quality | What objective score was earned over all planned questions? | Dropping provider failures from the denominator |
| Conditional quality | How good were returned answers, conditional on success? | Using it alone for production selection |
| Availability | What fraction of planned requests returned successful final answers? | Treating a transient run as permanent model reliability |
| Latency percentiles | What client-observed delay occurred under the declared load? | Comparing sequential blocks as a controlled load study |
| Cost | What recorded or estimated spend was associated with the run? | Treating lower bounds or different price bases as exact inference cost |
| Track score | What happened on one declared capability/task slice? | Generalizing three questions to the full construct |

The frozen overall order uses score-weighted operational goodput descending, followed by objective quality, complete cost, and p50 latency tie-breakers. A row can therefore have higher raw quality but lower operational goodput when responses fail or miss declared constraints.

## Confidence intervals and pairwise tests answer different questions

The table intervals are marginal uncertainty summaries for one endpoint. Overlapping intervals do not formally prove equality, and non-overlapping marginal intervals are not a substitute for the preregistered paired test.

The pilot evaluated every endpoint pair on shared selected questions:

- comparisons: `35 choose 2 = 595`;
- test: two-sided paired sign-randomization;
- correction: Holm family-wise error control at alpha 0.05;
- significant after correction: **0/595**;
- practical-equivalence margin: `+/-0.02`.

The result is unresolved ordering, not 35 statistically tied systems. Failure to reject a difference is not proof of equivalence. Conversely, a tiny p-value would not by itself establish a useful effect, deployment fitness, fairness, or safety.

## Why the table still has ranks

Ranks provide a deterministic view of point estimates and make artifacts comparable. With only 15 questions, however, rank positions are unstable and much finer than the evidence resolves. Use them to select hypotheses or candidates for a larger study, not as a purchasing decision by themselves.

A defensible shortlist should consider at least:

1. the relevant system-type division;
2. per-track scores and the target workload mix;
3. availability and failure modes;
4. latency and cost under a representative load scenario;
5. interval width and paired effects;
6. safety, privacy, licensing, and operational requirements not tested here.

## Failures, zeros, and N/A

The public aggregate contains complete result rows for all 35 text endpoints. `complete` at the campaign level does not mean every provider call succeeded.

Seven endpoints returned zero successful final answers in the captured run. Their operational score of zero is an observation about the endpoint-as-served campaign. It is not proof that the underlying model has zero capability. Provider failures are kept in the denominator because excluding them would answer a conditional-capability question and overstate delivered service quality.

The two non-text catalog entries are **N/A**, not zero:

- `kc-pegasus-1.2` advertised video and structured output;
- `kc-image` advertised image generation.

They were outside the frozen text-task construct and never entered the rank order.

## Cost and latency qualifications

`cost_is_lower_bound: true` means one or more failed attempts lacked complete billing or usage telemetry. A missing cost is unknown, not free. The pilot converted Kendr-reported credits using the configured USD-per-credit value; it should be read as the buyer-facing observed basis, not underlying compute cost.

Latency is client-observed end-to-end time on a non-streaming path. Endpoints were executed in sequential blocks at generation concurrency two. Time of day, transient provider state, and block order are confounded, so latency ordering is descriptive. A production claim requires interleaving across days, regions, and load scenarios with p90/p95/p99 and goodput SLOs.

## Freshness and coverage

The LiveBench release identifier is `2026-06-25`, but actual selected question dates are older: six from 2024-06-24 and nine from 2024-11-25. A release label is not a freshness measure.

The sample covers only five task strata with three questions each. It lacks the protocol's global-study requirements for multiple languages and locales, private-holdout coverage, current items, repeated generations, safety tracks, controlled operational replication, independent review, and external replication.

## Acceptable citation language

Recommended:

> In the frozen 2026-08-07 Kendr catalog pilot, gpt-5.5 had the highest operational-goodput point estimate among fixed managed text endpoints. The 15-question study found zero significant endpoint-pair differences among 595 tests after Holm correction.

Avoid:

- "gpt-5.5 is the world's best LLM";
- "all models were proven equivalent";
- "the protocol certifies these systems";
- "zero-score endpoints cannot answer the tasks";
- "the rankings are globally accepted."

## Public files

- [Complete human-readable rankings](RANKINGS_2026-08-08.md)
- [Aggregate JSON](data/kendr-catalog-pilot-2026-08-08.json)
- [Aggregate CSV](data/kendr-catalog-pilot-2026-08-08.csv)
- [Checksums](data/SHA256SUMS)

The aggregate release intentionally excludes raw prompts, responses, provider request IDs, and local paths. See [Evidence bundle](EVIDENCE_BUNDLE.md) for controlled-evidence handling.
