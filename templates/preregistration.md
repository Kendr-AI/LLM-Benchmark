# Preregistration: [study name]

> Protocol ID/version: [immutable ID]<br>
> Registration URI: [public or time-stamped controlled URI]<br>
> Freeze timestamp: [UTC]<br>
> Source commit/config hash: [SHA-256]<br>
> Status: [draft / frozen; never mark frozen before signing]

## 1. Authors, roles, funding, and conflicts

List study owner, dataset steward, operators, statistical/domain/safety reviewers, release manager, affiliations, funding, provider relationships, benchmark/model authorship, and recusal plan.

## 2. Decision and confirmatory claim

- Decision:
- Claim type:
- Target users/tasks/locales/modalities/time horizon:
- System boundary being compared:
- Primary estimand(s):
- Direction and decision threshold:
- Minimum practically important difference or equivalence margin and rationale:
- Explicitly unsupported claims:
- Result expiry/drift rule:

## 3. Systems and divisions

| System ID | Type/scope | Version/snapshot | Access/region | Division | Card URI/hash |
|---|---|---|---|---|---|
| | | | | | |

Freeze prompts, provider settings, reasoning/sampling, tools, safeguards, context/output/time/cost budgets, retries, cache, streaming, and service tier. Describe controlled and provider-optimized divisions separately.

## 4. Source population and sampling

- Construct/task population:
- Sources, versions, provenance, and licenses:
- Inclusion/exclusion rules:
- Pool size by stratum:
- Cluster definition:
- Strata and target/production weights:
- Sampling algorithm and seed:
- Planned item count and repeats:
- Replacement policy for pre-inference invalid items:
- Sample/pool content hashes:

## 5. Freshness and contamination

- Actual release-date eligibility and maximum age:
- Private-holdout fraction and access controls:
- Exact/semantic deduplication:
- Lexical/semantic/answer-reproduction/benchmark-awareness tests:
- Canaries and leakage threshold:
- Blind broken-item review:
- Incident, retirement, refresh, and rerun policy:

## 6. Coverage

Specify planned counts/weights for track, language, language family, locale, modality, difficulty, source, context bucket, multi-turn, tools, production segment, safety domain, region, day, and load scenario. Identify primary and worst-slice claims.

## 7. Grading

- Grader IDs/versions and task mapping:
- Objective scoring details:
- Model/human rubric and prompt hashes:
- Blinding/randomization:
- Human sample and reviewer qualifications:
- Minimum agreement and bias thresholds:
- Adjudication, invalid judgment, and fallback rules:

## 8. Experimental schedule and operations

- Schedule-generation algorithm/seed:
- Blocking/interleaving unit:
- Measurement dates/days and regions:
- Load scenarios and concurrency/arrival process:
- Deadlines, output caps, per-request/run spend caps:
- Retry and hidden-transport-retry policy:
- Streaming/timing/queue metrics:
- Attempt/failure/error taxonomy:
- Stop criteria for spend, safety, privacy, outage, and integrity:
- Partial-run and resume policy:

## 9. Outcomes and scoring

Define every primary and secondary endpoint mathematically. State score range, item/repeat aggregation, cluster/stratum weights, failure/timeout/invalid/missing treatment, safety refusal semantics, operational-goodput constraints, conditional diagnostics, and optional composite policy.

## 10. Power and sample size

- Pilot source and independence from test sample:
- Item, repeat, and cluster variance assumptions:
- Pairwise correlation:
- Expected failure/missingness:
- Alpha, power, effect/equivalence margin:
- Multiplicity and slice inflation:
- Calculation/simulation code, seed, and result:
- Sensitivity to assumptions:

## 11. Confirmatory analysis

- Primary comparison family:
- Paired test/model, link, fixed/random effects:
- Confidence interval procedure and bootstrap seed/replicates:
- Multiplicity correction:
- Equivalence/non-inferiority procedure:
- Model diagnostics/fallback:
- Decision rule combining effect, uncertainty, safety/reliability gates:

## 12. Secondary, slice, and exploratory analyses

List prespecified secondary endpoints and slices, their correction families, and whether they are powered. Define exploratory labels. No new analysis becomes confirmatory after results are inspected.

## 13. Missingness and sensitivity

Predeclare complete-denominator analysis, observed-only/conditional diagnostic, best/worst bounds, failed-cost/token bounds, broken-item analysis, grader sensitivity, provider-outage scenario, alternative weights, and temporal/region robustness.

## 14. Deviations, exclusions, and amendments

- Automated exclusion rules:
- Blind broken-item adjudication:
- Who may authorize a deviation:
- Required impact analysis:
- Deviation-log URI:
- Amendment/version rule:
- Conditions requiring correction, new run, or withdrawal:

## 15. Safety, privacy, security, legal, and accessibility

Link the threat model. Record threat actors/attack budget, sandbox/tools/egress, operator safety, personal/sensitive data, redaction, provider retention/training settings, data/provider licenses, accessibility, cultural validity, and incident response.

## 16. Evidence and release plan

- Public/controlled/private/withheld artifact classes:
- Attempt-answer-judgment-observation lineage:
- Environment/container/lock/SBOM:
- Manifest hashing/signing and key custody:
- Offline reconstruction test:
- Independent reviewers and evidence access:
- Replication plan:
- Benchmark card and standards crosswalk:
- Appeal/correction channel:

## 17. Freeze attestation

By signing, the named roles attest that system identities, item/sample IDs, graders, settings, exclusions, weights, primary endpoints, comparison families, and decision rules are frozen before provider inference. Signatures attest process state; they do not certify scientific validity.

| Role | Name | Signature reference | Timestamp | Conflict statement |
|---|---|---|---|---|
| Study owner | | | | |
| Dataset steward | | | | |
| Statistical reviewer | | | | |
| Safety/privacy reviewer | | | | |
