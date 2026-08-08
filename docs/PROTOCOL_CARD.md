# Protocol card: LLM Benchmark Protocol 1.0

## Identity

| Field | Value |
|---|---|
| Public name | LLM Benchmark Protocol |
| Researcher | Dr. Prashant Kumar Dey |
| Steward | Kendr |
| Reference profile | KGBP 1.0 |
| Software release | 1.0.2 |
| Lifecycle | Beta research release |
| Primary specification | [`GLOBAL_BENCHMARK_PROTOCOL.md`](../GLOBAL_BENCHMARK_PROTOCOL.md) |
| Configuration schema | [`global-protocol-v1.schema.json`](../config/global-protocol-v1.schema.json) |
| License | MIT for software; dataset and provider terms are separate |

## Purpose

The protocol supports claim-first, reproducible evaluation of models, managed endpoints, routers, agents, and applications. It separates capability, operational service quality, safety, efficiency, and governance rather than collapsing them into one universal intelligence score.

Intended uses include:

- designing controlled comparisons and production-selection studies;
- freezing system boundaries, items, estimands, and schedules before inference;
- retaining failures and missing planned observations in conservative denominators;
- producing track scorecards, paired effects, uncertainty, and evidence manifests;
- evaluating routers and agents with specialized counterfactual or state-based evidence;
- enabling independent review, correction, and replication.

It is not intended to certify systems, guarantee safety, replace domain experts, or justify a universal ranking from a small convenience sample.

## Non-compensatory design gates

Every dimension must score strictly above 9.0 in the automated design audit:

1. Construct validity
2. Statistical validity
3. Coverage and representativeness
4. Freshness and contamination control
5. Fairness and comparability
6. Reproducibility and traceability
7. Operational realism
8. Safety, security, and trustworthiness
9. System classification and specialized evaluation
10. Governance and external auditability

An average cannot rescue a failed dimension. A high design score describes the plan, not the evidence produced by running it.

## Core measurement rules

- Declare the claim and target population before choosing tasks.
- Classify each system boundary before comparison.
- Freeze items, graders, settings, exclusions, weights, and analysis before calls.
- Use shared items and paired analysis for system comparisons.
- Average repeated generations within item before treating items as independent evidence.
- Preserve cluster structure for passages, repositories, scenarios, sources, or templates.
- Keep provider failures, invalid outputs, and missing planned observations in the denominator.
- Report task quality separately from availability, latency, cost, energy, and goodput.
- Control the declared comparison family and distinguish equivalence from non-significance.
- Publish scorecards and Pareto trade-offs before any optional composite.

## Publication evidence floor

Automated audit success is necessary but insufficient. A credible publication candidate additionally needs a completed evidence bundle, privacy and license review, documented deviations, at least three independent reviewers, and reports from at least two external replicating organizations. Any standards-body acceptance or certification must come from the relevant external institution; it cannot be self-awarded by this project.

## Current empirical release

The included 2026-08-07 catalog campaign is a descriptive pilot:

- 35 Kendr-served text endpoint identifiers;
- 15 selected LiveBench questions across five task types;
- one generation per endpoint/question;
- two catalog entries excluded as non-text and reported N/A;
- zero of 595 pairwise comparisons significant after Holm correction.

It does not meet the protocol's multilingual, freshness, repeated-generation, multi-region, load, safety, independent-review, or external-replication requirements. See [the ranking handout](RANKINGS_2026-08-08.md).

## Required study outputs

At minimum, a serious study should produce:

- preregistration and immutable protocol configuration;
- system cards and frozen item descriptors;
- deterministic schedule and validation report;
- attempt, answer, judgment, and observation records with lineage;
- failure-aware track scorecards and preregistered pairwise analyses;
- benchmark card, deviation log, threat model, and privacy/license review;
- content-addressed evidence manifest and correction history;
- independent reviews and replication reports when broad public claims are made.

## Known limitations

- Automated rules cannot establish construct validity or cultural validity alone.
- Private holdouts improve contamination resistance but reduce public inspectability.
- Provider telemetry may omit hidden retries, queueing, energy, or failed-attempt usage.
- Model and routing services drift; snapshots must be time-bounded and replicated.
- LLM graders can exhibit family, language, length, style, and position bias.
- Statistical significance does not establish practical importance, fairness, or safety.

Use the [adoption guide](ADOPTION_GUIDE.md) for an implementation path and the [appeals policy](APPEALS_AND_CORRECTIONS.md) for challenges to published evidence.
