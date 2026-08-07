# Adoption guide

This guide is for teams adopting LLM Benchmark Protocol as an evaluation process, not merely running a leaderboard script. Version 1.0 is a beta research release. It provides technical controls and evidence contracts; it does not issue certifications or confer global acceptance.

## Choose an adoption level

| Level | Purpose | Minimum evidence | Permitted claim |
|---|---|---|---|
| Sandbox | Learn the data model and scoring rules | Toy schedule and observations | Software behavior only |
| Internal pilot | Compare a shortlist for one bounded use case | Frozen items/settings, system cards, failures, intervals, deviation log | Observed result for the declared internal workload |
| Production decision | Select or monitor a deployed system | Production-weighted tasks, repeated days/regions/load, SLOs, costs, safety/privacy review | Best observed choice for that deployment population |
| Public research | Publish a bounded benchmark claim | Preregistration, adequate power, evidence bundle, reviewer reports, correction channel | Result within the stated construct and population |
| Multi-organization protocol study | Seek broad legitimacy | Public change control, diverse stakeholders, at least 3 independent reviewers and 2 external replications | Replicated evidence; still not self-awarded standards certification |

Do not start at the public-research level by scaling an informal pilot. The claim, item population, system boundary, estimand, and evidence policy must be designed together.

## Establish ownership

Assign named people before freezing the study:

| Role | Accountable for | Must be independent from |
|---|---|---|
| Study owner | Decision and claim boundary | None, but conflicts must be disclosed |
| Dataset steward | Provenance, licensing, sampling, contamination, retirement | Provider marketing influence |
| Evaluation operator | Schedule execution and incident capture | Post-result scoring changes |
| Statistical reviewer | Power, estimands, intervals, multiplicity, sensitivity | System selection incentives where practical |
| Domain reviewer | Construct validity and grading | Unqualified general review |
| Safety/privacy reviewer | Threat model, redaction, access controls, incident response | Operations approval where practical |
| Independent reviewer | Evidence and deviation assessment | Study execution and system ownership |
| Release manager | Versioning, checksums, signatures, correction record | Unilateral scientific adjudication |

One person may fill several roles in an internal pilot. Record the overlap. Publication-grade work should separate execution, statistical review, system ownership, and adjudication.

## Adoption workflow

### 1. Write the decision before the benchmark

State:

- the decision the result will inform;
- the target users, tasks, locales, time horizon, and risk tier;
- the unit being selected: weights, endpoint, router, agent, or application;
- the primary estimand and minimum practically important difference;
- unacceptable outcomes and non-negotiable safety/reliability constraints;
- the expiry date after which drift makes the result stale.

Use [`templates/preregistration.md`](../templates/preregistration.md). If the claim cannot be stated without words such as "overall" or "best" lacking a population qualifier, it is not ready.

### 2. Classify and freeze systems

Complete one [`system-card.yaml`](../templates/system-card.yaml) per measured boundary. Treat the same weights behind different providers as separate endpoints for operational claims. Treat routers as routers, not as single models; record their candidate set. For agents, include tools, memory, loop limits, environment version, and side-effect controls.

Freeze:

- requested and actual snapshot identifiers;
- provider, endpoint, region, access path, and version date;
- input/output modalities and tool policy;
- prompts, reasoning/sampling parameters, budgets, timeout, and retry policy;
- safeguards and refusal handling;
- pricing source and license/terms source.

### 3. Build the item population

Define the source population before sampling. Record item/cluster IDs, track, language, locale, modality, difficulty, source, release date, content hash, grader, and holdout status using [`frozen-item-v1.schema.json`](../config/frozen-item-v1.schema.json).

Required reviews scale with the claim:

- exact and semantic deduplication;
- contamination and answer-reproduction checks;
- blind broken-item review;
- native-speaker and cultural-validity review for locale claims;
- data-license, privacy, accessibility, and sensitive-content review;
- canary and leakage-response policy for private holdouts.

### 4. Predeclare analysis and power

Use the [statistical analysis plan](STATISTICAL_ANALYSIS_PLAN.md) and record:

- primary and secondary endpoints;
- item and generation variance assumptions;
- sample size and repeat count;
- cluster, stratum, and weighting rules;
- failure, refusal, missingness, and invalid-output treatment;
- comparison family and multiplicity correction;
- equivalence margin and decision thresholds;
- planned subgroup and sensitivity analyses;
- stopping, exclusion, and rerun rules.

The protocol's automated floors are not universal sample-size recommendations. Simulate or power the analysis for the actual claim.

### 5. Audit, freeze, and schedule

Copy the reference configuration, replace illustrative values, then run:

```bash
llm-benchmark-protocol audit path/to/protocol.json \
  --output build/study/audit \
  --strict
```

Resolve every critical design failure. A `>9.0` result in all ten dimensions means the encoded plan clears the software gates, not that humans validated the construct or that evidence exists.

Content-address the final configuration, system cards, item pool, sample, graders, and templates. Create the interleaved schedule only after freeze. Any later change goes into [`templates/deviation-log.csv`](../templates/deviation-log.csv).

### 6. Execute with operational controls

- Obtain explicit budget and paid-run approval.
- Use least-privilege credentials and never write secrets to evidence.
- Randomize/interleave systems; do not run each provider in one long block.
- Spread operational studies over the preregistered days, regions, and load scenarios.
- Disable hidden retries or capture them; record every visible attempt.
- Preserve requested and actual model identity, timings, errors, usage, cost basis, route, and final-answer selection.
- Stop only under preregistered safety, spend, or integrity rules.
- Quarantine incidents; never silently replace the earliest captured trial with a cleaner rerun.

### 7. Score without shrinking the denominator

Join schedule cells to attempts, final answers, judgments, and observations. Missing planned cells become `status=missing`, `score=0`, `score_treatment=conservative-zero`. Provider failures, exhausted timeouts, invalid outputs, and inappropriate policy blocks remain in the denominator.

Report capability scorecards separately from:

- availability and operational goodput;
- latency distributions and deadline success;
- cost, failed-work spend, and cost per successful outcome;
- energy/carbon when evidence exists;
- safety, robustness, and worst-slice outcomes.

### 8. Review and package evidence

Run scientific, domain, safety/privacy, and reproducibility review. Resolve or disclose every deviation. Build the bundle described in [Evidence bundle](EVIDENCE_BUNDLE.md), including public, controlled, private, and withheld classifications. Reconstruct the report offline from the frozen bundle before release.

### 9. Publish narrowly and keep a correction channel open

Every public result should identify the protocol version, run ID, system boundary, time window, population, primary metric, sample size, uncertainty, comparison correction, failures, deviations, and artifact hashes. Publish the [appeals and corrections process](APPEALS_AND_CORRECTIONS.md) with the result.

## CI and quality gates

Recommended pull-request checks:

1. JSON Schema validation for protocol and evidence records.
2. `llm-benchmark-protocol audit ... --strict` for the frozen design.
3. Schedule validation: every system/item/repeat cell appears exactly once per planned allocation.
4. Complete-denominator reconciliation between schedule and observations.
5. No secret patterns, personal data, raw provider request IDs, or absolute local paths in public exports.
6. Recompute SHA-256 checksums and fail on drift.
7. Rebuild scorecards from evidence in an isolated environment.
8. Verify that public claims include scope and multiplicity disclosures.

Do not configure CI to treat `--require-publication-evidence` as an accreditation decision. It checks declared evidence structure only.

## A practical 30/60/90-day rollout

### Days 1-30: prove the mechanics

- Run the zero-cost example and one internal, non-decisional pilot.
- Agree on system and benchmark cards.
- Add schema validation and secret scanning.
- Exercise one missing-call, retry, grader-invalid, and correction scenario.
- Record what telemetry each provider cannot supply.

### Days 31-60: validate the measurement

- Conduct construct interviews with domain users.
- Build a representative item pool and run a variance pilot.
- Validate graders against blinded qualified humans.
- Simulate power, multiplicity, and missingness sensitivity.
- Run interleaved operational cells across at least two times/regions for diagnostics.

### Days 61-90: run a decision study

- Freeze and preregister the study.
- Obtain independent statistical and safety/privacy review.
- Execute with spend and incident controls.
- Reconstruct the analysis from a signed evidence bundle.
- Publish only claims the frozen design supports; schedule drift monitoring and expiry.

## Common adoption failures

- Choosing a popular benchmark before defining the target decision.
- Comparing a router, endpoint, and base model in one unlabeled table.
- Reporting only successful responses.
- Optimizing prompts after inspecting test outcomes.
- Treating a design audit score as study quality or certification.
- Using one generation to rank stochastic systems definitively.
- Ignoring old item dates because the benchmark release label is recent.
- Treating unknown cost, energy, or failed usage as zero.
- Publishing aggregate scores without failures, slices, uncertainty, and raw-evidence access policy.
- Correcting a result by overwriting the original artifact.

## Current pilot as an adoption example

The included [Kendr catalog pilot](RANKINGS_2026-08-08.md) is useful for learning endpoint identity, failure-aware goodput, division labels, integrity hashes, and cautious claim language. It is not the target maturity state: it has 15 items, one generation, older English-oriented questions, sequential endpoint blocks, no safety track, and zero Holm-significant differences among 595 pairs.
