# Statistical analysis plan

This document is the reference analysis policy for LLM Benchmark Protocol 1.0 studies. A study must copy, specialize, version, and freeze it before provider inference. It is not itself a preregistration, and the included 35-endpoint pilot does not satisfy the sample-size and replication requirements below.

## 1. Study identifiers and analysis status

Record protocol ID, analysis-plan version, source commit, registry URI, freeze timestamp, authors, statistical reviewer, and amendment history. Label analyses as:

- **confirmatory:** fully specified before inference;
- **secondary:** prespecified but not part of the primary decision family;
- **exploratory:** introduced after freeze and clearly marked;
- **sensitivity:** tests robustness to declared assumptions.

Post-result changes never replace the frozen plan. They create an amendment and deviation entry.

## 2. Claim, population, and systems

Define the target population as a distribution over tasks, users, languages/locales, modalities, difficulty, context length, tools, regions, load scenarios, and time. Define each system at the measured boundary: checkpoint, endpoint, routed service, agent, or application.

The same weights through different providers are distinct systems for operational estimands. A router is a policy over candidate endpoints and requires counterfactual coverage. An agent includes its model, tools, memory, control loop, environment, budgets, and safeguards.

## 3. Experimental units and dependence

The planned observation cell is:

`system x item x generation repeat x day x region x load scenario`

The inferential item unit is the item-level mean over generation repeats unless the preregistered hierarchical model explicitly represents both levels. Record `cluster_id` for shared passages, repositories, scenarios, templates, authors, or sources. Never treat repeated generations or clustered questions as independent items.

Use the same frozen items across systems so primary comparisons are paired. Randomize or block-interleave execution order within item/day/region to reduce provider-time confounding.

## 4. Outcomes and estimands

### Primary task estimand

For system `s`, item `i`, and repeat `r`, let `Y_sir` be the objective or validated score on `[0,1]`. Provider failure, timeout, invalid output, missing planned observation, and other declared conservative failures receive zero. An appropriate refusal may receive positive credit only on a safety track whose success criterion defines that refusal as correct.

Average repeats within item:

`Y_si = mean_r(Y_sir)`

The primary track estimand is the target-population-weighted mean of `Y_si`. Report one estimate per track. If a production-weight vector is used, freeze its source and normalization. Equal item weighting is the default within a track.

### Primary comparison estimand

For systems A and B on shared items:

`Delta_AB = mean_i(Y_Ai - Y_Bi)`

State direction, minimum practically important difference, and decision threshold before data collection.

### Operational estimands

Report separately:

- logical-request availability and attempt availability;
- score-weighted goodput satisfying deadline/output/budget constraints;
- p50/p90/p95/p99 latency and deadline success by scenario;
- throughput and queueing where observable;
- total cost, failed-work cost, and cost per successful outcome;
- retry amplification and failure taxonomy;
- energy/carbon with system boundary and uncertainty when measured.

Conditional quality is secondary because it excludes failed service delivery. A descriptive macro across tracks may be shown only after track scorecards and must not be the sole decision endpoint.

## 5. Sampling and power

Stratify the source pool by the variables needed to support the claim, typically track, difficulty, language/locale, modality, source, production segment, and context length. Freeze inclusion/exclusion rules before sampling.

Sample size must come from a prospective calculation or simulation using pilot-derived:

- item variance;
- generation-repeat variance;
- pairwise correlation;
- cluster-size distribution and intracluster correlation;
- expected failure and missingness rates;
- target effect/equivalence margin;
- desired power and family-wise alpha;
- planned slice and interaction analyses.

The automated `300 items x 3 repeats` checks are floors, not general recommendations. The reference global profile starts larger because multilingual, multi-track, worst-slice, and temporal claims require more information. Inflate for expected invalid/broken items without allowing post hoc replacement based on system outcomes.

Use `llm-benchmark-protocol power` only as a first approximation. Confirm the final design with simulation matching the intended hierarchical analysis.

## 6. Randomization and masking

- Generate the system order from a recorded seed after system and item freeze.
- Interleave systems within blocks of item/day/region/load.
- Randomize answer order and remove system identity for model/human graders.
- Keep grader prompts/rubrics versioned and fixed.
- Blind broken-item adjudicators to system identity and aggregate rank.
- Record deviations caused by outages or provider constraints.

## 7. Scoring and denominator policy

The frozen schedule defines the denominator. Join observations to `schedule_id`; synthesize absent planned cells as `missing` with score zero. Reject duplicate schedule cells unless the repeat/retry semantics identify them unambiguously.

Recommended status treatment:

| Status | Capability track | Safety track |
|---|---:|---:|
| Successful valid answer | Validated score | Validated safe-outcome score |
| Provider failure / timeout / missing | 0 | 0 |
| Invalid output | 0 | 0 |
| Inappropriate refusal | 0 | 0 |
| Appropriate refusal | 0 unless task defines refusal as success | Score declared by safety rubric |
| Unsafe compliance | 0 | 0 and record severity |

Do not delete failures or divide the primary quality total only by successful answers. Conditional quality can be reported as a secondary diagnostic.

## 8. Uncertainty

Use 95% intervals unless preregistered otherwise.

- Binary availability: Wilson interval or a cluster-aware alternative.
- Track means: hierarchical/cluster bootstrap resampling clusters, then items, while preserving paired system observations.
- Repeated generations: average within item or model generation variance explicitly.
- Pairwise effects: paired hierarchical cluster bootstrap and the preregistered paired test.
- Tail latency: scenario-specific bootstrap intervals with enough requests; do not infer p99 from a tiny sample.

Report the resampling seed, number of replicates, degeneracy/censoring diagnostics, failed fit/convergence checks, and effective sample sizes.

## 9. Hypothesis tests and multiplicity

Define each confirmatory family before inference. Examples:

- all primary endpoint pairs within one track;
- each candidate versus a declared incumbent;
- safety non-inferiority across preregistered domains;
- router versus best-single and policy baselines.

Use paired tests on shared items. The reference small-sample procedure is a two-sided paired sign-randomization test. Control family-wise error with Holm for the declared family unless another method is preregistered and justified. Do not create a new family after seeing ranks.

Report raw and adjusted p-values, paired effect, interval, wins/losses/ties, and number of nonzero pairs. "Not significant" means unresolved, not tied.

## 10. Equivalence, non-inferiority, and practical importance

Freeze the equivalence or non-inferiority margin from domain consequences, not observed variance. Demonstrate equivalence with a valid two-one-sided-test procedure or an interval fully inside the declared margin. Test superiority and equivalence as distinct claims.

An effect can be statistically detectable but operationally trivial. Conversely, an operationally meaningful effect can remain unresolved when the sample is small. Report both.

## 11. Hierarchical models

A publication-grade study may use a generalized linear or ordinal mixed model. Preregister:

- outcome distribution and link;
- fixed effects and interactions;
- random intercepts/slopes for item, cluster, generation, day, region, or source;
- weights and offsets;
- estimation method or priors;
- convergence, posterior, and predictive checks;
- fallback model;
- transformation from model coefficients to reported marginal effects.

Do not use a complex model to conceal sparse cells, separation, or poor overlap.

## 12. Missingness and sensitivity

Primary analysis: all absent planned cells and operational failures receive zero. Also report:

- best/worst bounds for genuinely unknown scores;
- conditional-on-success quality;
- observed-only analysis, explicitly biased toward reliable responders;
- failure-type-specific scenarios;
- cost and token lower/upper bounds when failed usage is unavailable;
- results excluding independently adjudicated broken items, alongside the frozen-denominator result.

If conclusions change across plausible assumptions, state that they are not robust.

## 13. Slice and fairness analysis

Report preregistered slices with counts and uncertainty: language, locale, difficulty, modality, source, context bucket, production segment, demographic/safety domain where lawful and appropriate, day, region, and load scenario. Publish worst-slice performance and gaps.

Mark underpowered slices descriptive. Control multiplicity for confirmatory slice claims; do not select only favorable slices after inspection.

## 14. Grader validation

Objective graders are preferred when valid. Model, human, or hybrid graders require blinded validation against qualified humans, stratified by language, model family, answer length/style, task, and score band.

Predeclare minimum agreement, adjudication rules, position-bias checks, grader-family sensitivity, invalid-judgment policy, and drift monitoring. Keep the grader prompt/rubric hash in every judgment record.

## 15. Exclusions, stopping, and amendments

Freeze automated invalid-output rules and independent broken-item criteria. The operator may stop only for preregistered spend, safety, privacy, legal, or integrity thresholds. Provider outage does not authorize silently replacing the captured trial.

Every exclusion or change records who decided, when, blinded status, affected systems/items, impact analysis, and disposition in the deviation log. Rerun both frozen and corrected analyses when feasible.

## 16. Reporting

Publish:

- planned/attempted/completed/valid/scored counts;
- system cards and exact boundary;
- item dates, pool/sample hashes, strata, and weights;
- track estimates, intervals, pairwise effects, multiplicity results, and equivalence decisions;
- failures, refusals, invalids, missing telemetry, and sensitivity bounds;
- operational and safety scorecards separately;
- exploratory labels, deviations, conflicts, funding, and evidence-access policy;
- machine-readable outputs, checksums, code/environment version, and correction channel.

## 17. Instantiation for the included pilot

The public 2026-08-07 pilot used 35 endpoint rows, 15 shared questions, five strata with three questions each, one repeat, and a `+/-0.02` practical margin. All 595 pairwise comparisons used the paired sign-randomization/Holm family; zero survived correction.

That result demonstrates complete-family reporting and conservative failure treatment. It does not have enough items/repeats or coverage for definitive ranking, equivalence, multilingual, safety, or global claims. The [ranking handout](RANKINGS_2026-08-08.md) is the authoritative public summary.
