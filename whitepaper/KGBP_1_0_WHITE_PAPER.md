# LLM Benchmark Protocol 1.0

## Technical foundations, normative controls, and empirical reference report

Version 1.0 - KGBP 1.0 reference profile - Technical White Paper - 8 August 2026

Researcher: Dr. Prashant Kumar Dey - LLM Benchmark Protocol contributors - Reference implementation initiated by Kendr

Status: Public research proposal and reference implementation. The automated profile audit checks declared controls; it is not an independent validation of their truth or adequacy. This document is not an ISO, NIST, OECD, EU, or MLCommons certification, endorsement, accreditation, or conformity assessment.

## Abstract

Foundation-model evaluation is often compressed into a leaderboard whose rows mix models, managed endpoints, routed systems, and applications, and whose columns hide differences in tasks, prompting, reasoning budgets, failures, and cost. Such tables are useful for exploration but are weak measurement instruments. A high benchmark score may reflect memorization, favorable elicitation, a mutable endpoint, an unrepresentative sample, or a grader artifact rather than the construct named by the headline.

The LLM Benchmark Protocol (LBP) 1.0 is a claim-first, system-aware, failure-aware framework for comparative AI evaluation. KGBP 1.0 is the initial, standards-oriented reference profile implemented by this repository. The protocol classifies the system under test before measurement; separates capability, operations, safety, and production outcomes; distinguishes controlled comparison from strong elicitation; requires item and generation uncertainty to be modeled; and makes freshness, contamination, artifact lineage, cost, and external replication first-class properties. Ten profile dimensions use non-compensatory declaration gates. Every dimension must score above 9.0 in the reference configuration, and a critical missing declaration caps its dimension below the gate. That number measures machine-checkable declaration completeness, not scientific validity, execution quality, certification, or international acceptance.

The KGBP reference profile draws from the NIST AI Risk Management Framework and Generative AI Profile, the Initial Public Draft of NIST AI 800-2, NIST AI 800-3, ISO/IEC 25059:2023, ISO/IEC 23894:2023, ISO/IEC 42001:2023, ISO/IEC 17025:2017, OECD AI Principles, Regulation (EU) 2024/1689, MLPerf, LiveBench, HELM, measurement theory, psychometrics, reliability engineering, and statistical work on language-model evaluation. These sources are mapped conceptually; their mention does not establish conformance. The reference implementation provides machine-readable configuration and observation schemas, deterministic interleaved execution planning, hierarchical cluster bootstrap estimation, paired comparisons, failure-aware scorecards, Pareto reporting, and evidence-presence gates. Some controls remain research prototypes and are identified as such.

This paper develops the measurement argument, statistical estimands, sampling and uncertainty model, execution controls, artifact contract, conformance evidence states, governance model, and adoption path. It also reports a Kendr API catalog campaign as an empirical case study. That case study is deliberately qualified: breadth across endpoints is not equivalent to a globally representative study when freshness, repetition, multilingual coverage, independent review, and external replication are absent. The paper therefore distinguishes what the protocol proposes, what the current software checks, what the pilot observed, and what future independent evidence must establish.

## Executive summary

LBP and its KGBP 1.0 reference profile are built around seven propositions.

1. A benchmark result is meaningful only relative to a declared claim, target population, system boundary, task distribution, and resource budget.
2. Models, endpoints, routers, agents, and applications are different systems under test and require different estimands.
3. A benchmark must measure at least two sources of uncertainty: the sampled items and stochastic generations. Shared passages, repositories, scenarios, or templates add clustering that must also be respected.
4. Capability is only one decision axis. Reliability, latency, cost, safety, privacy, fairness, energy, and operational goodput can change a deployment decision even when objective quality is unchanged.
5. Reproducibility requires content-addressed evidence and end-to-end lineage, not only a source-code repository.
6. Global acceptance is a governance outcome. A vendor cannot award it to itself. Independent replication, multistakeholder review, public corrections, and standards engagement are required.
7. Conformance evidence has maturity states. A declared control is not an implemented control; an implemented control is not verified evidence; and verified evidence is not accreditation.

The reference profile has ten dimensions: construct validity; statistical validity; coverage and representativeness; freshness and contamination control; fairness and comparability; reproducibility and traceability; operational realism; safety, security, and trustworthiness; system classification and specialized evaluation; and governance and external auditability. Its automated score is a geometric summary of declared checks, but the gate is non-compensatory: the minimum dimension controls declaration readiness. Evidence verification is reported separately and is never inferred from the numeric score.

The example study configuration begins with 1,200 items and five independent generations per stochastic item, stratified across capability, difficulty, language, modality, source, and production frequency. These are planning values, not universal recommendations or substitutes for endpoint- and slice-specific prospective power analysis. A declaration floor of 300 items and three repeats is enforced by the automated profile audit. Operational tails require a separate load campaign sized for the target quantile or SLO precision; 1,000 requests is only a screening floor, and the example configuration uses 5,000 across multiple concurrency levels, days, and regions.

KGBP does not use one universal intelligence rank as its primary output. It publishes track scorecards, paired effects with uncertainty, practical-equivalence decisions, worst-slice results, failure and refusal rates, cost-performance surfaces, and a Pareto frontier. A descriptive macro score may be shown, but it cannot hide a failed track or governance gate.

### How to read this document

Four kinds of statement are kept separate throughout the paper.

| Statement type | Meaning | What it does not mean |
| --- | --- | --- |
| Protocol requirement | A normative control for a declared LBP/KGBP profile | That the current pilot met the control |
| Reference implementation behavior | What the published software currently checks or computes | That every protocol control is automated |
| Empirical observation | A result from the frozen Kendr API catalog campaign | A universal property of a model family |
| Assurance statement | Evidence reviewed by an identified independent party | Certification, accreditation, or regulatory approval unless explicitly issued by an authorized body |

The words *global*, *publication candidate*, and *conformant* are therefore qualified. “Global-scope” describes a target population and design ambition. “Publication candidate” means a package is ready to enter an external review process. “Conformant” names the protocol version, profile, claim class, division, satisfied controls, waivers, and evidence state. None of these words means “globally accepted.”

### Conceptual measurement chain

The protocol treats a benchmark claim as the last node of a traceable measurement chain, not as a property emitted by a leaderboard script.

```text
decision question
      |
      v
claim class -> target population -> system boundary -> resource regime
      |                |                  |                  |
      +----------------+------------------+------------------+
                               |
                               v
eligible task universe -> frozen sample -> randomized schedule
                               |
                               v
attempts -> answers -> judgments -> scored observations
                               |
                               v
estimand -> uncertainty -> sensitivity analysis -> qualified claim
                               |
                               v
evidence bundle -> independent review -> replication -> governance decision
```

Breaking any arrow changes the interpretation. For example, an answer without its attempt history cannot establish retry-inclusive cost, and a score without a sampling frame cannot justify a generalized population claim.

## 1. Motivation: from leaderboard culture to measurement science

Language-model benchmarks are asked to support incompatible decisions: which checkpoint learned more, which API is best for production, which router adds value, whether an agent can complete a workflow, and whether a system is safe enough for a regulated use. These questions do not share a single unit of analysis. A checkpoint has no network availability; an API endpoint has mutable infrastructure; a router changes the model selected per request; an agent includes tools and a control loop; and an application includes policies, humans, and downstream consequences.

The common leaderboard pattern creates five recurring validity failures.

### 1.1 Construct ambiguity

A headline such as "intelligence" may average mathematics, factual recall, coding, and instruction following without a defensible target population or weighting rule. The average is mathematically valid but its interpretation is not. NIST AI 800-2 begins with evaluation objectives and conceptual fit because protocol design and reporting depend on the intended use of the measurement [3]. HELM similarly argues for broad coverage, multi-metric measurement, standardization, and explicit recognition of what remains unmeasured [12]. The metrology vocabulary and uncertainty tradition further motivate explicit measurands, influence quantities, traceability, and qualified uncertainty statements [36, 37], while recognizing that AI behavior is not a conventional physical quantity.

### 1.2 Unit-of-analysis errors

If one model produces five generations for an item and another produces one, treating all six outputs as independent rows overweights the first model. If ten questions share one passage, repository, or template, treating them as ten independent items understates uncertainty. The item, generation, cluster, endpoint, day, and region are separate experimental units.

### 1.3 Hidden resource differences

Reasoning effort, token budgets, tools, retries, browsing, context compaction, and wall-clock time materially affect performance. Equal prompts do not guarantee equal elicitation. Conversely, provider-optimized settings do not guarantee a controlled comparison. NIST AI 800-2 treats cost control and external validity as protocol-design concerns [3], while recent third-party evaluation guidance distinguishes controlled comparisons from strong-elicitation claims [14].

### 1.4 Survivorship and availability bias

Discarding failed calls, substituting a clean rerun, or ranking only successful answers estimates conditional quality rather than user-experienced quality. Both may be reported, but they answer different questions. A production result must preserve the frozen denominator, the first governed trial, every retry, and unknown telemetry.

### 1.5 Governance deficits

Weights, exclusions, endpoint identities, and corrected items can change after results are observed. Without preregistration, versioned rules, conflicts disclosure, an appeal process, and independent replication, readers cannot distinguish scientific correction from result optimization. ISO/IEC 42001 frames AI governance as a management system requiring policies, objectives, processes, and continual improvement [7]. OECD principles emphasize traceability, robustness, accountability, and international multi-stakeholder cooperation [9].

## 2. Scope and intended use

KGBP applies to automated and hybrid evaluations of:

- base and instruction-tuned language models;
- reasoning and specialist models;
- multimodal and generative media models;
- embedding and reranking systems;
- managed inference endpoints;
- routers and ensembles;
- agents with tools, memory, and execution loops; and
- user-facing AI applications and human-AI workflows.

KGBP does not claim that automated benchmarks alone can establish universal safety, social benefit, legal compliance, or field effectiveness. NIST AI 800-2 explicitly notes that automated benchmarks are not appropriate for every objective and should be complemented by red teaming, human-subject research, field testing, and post-deployment monitoring when needed [3].

### 2.1 Claim classes

| Claim class | Required experimental setup | Permitted interpretation |
| --- | --- | --- |
| Controlled comparison | Same task distribution, grader, tools, and explicit budgets | A outperformed B under the declared common setup |
| Capability under strong elicitation | Strongest credible system-specific harness and budget | The system achieved at least this capability under this setup |
| Production selection | Production-weighted tasks, policies, SLOs, regions, load, and costs | Best observed choice for the declared deployment population |
| Router value | Full destination panel and item-level counterfactuals | Incremental value, regret, calibration, and stability of routing |
| Safety assurance | Explicit threat model and adaptive attack budget | Evidence about tested safeguards under the declared adversary |

The claim class is frozen before inference. Mixing claim classes in one headline rank is prohibited.

### 2.2 Closed and open divisions

KGBP borrows the useful distinction between MLPerf closed and open divisions [10]. The closed division fixes the evaluation setup for comparability. The open division permits provider-recommended or system-specific scaffolding to estimate strong elicitation. Both are valuable; neither is a replacement for the other.

Closed-division reports must disclose turns, tools, context policy, maximum output, reasoning effort, temperature, retries, wall-clock deadline, cost budget, and grader. Open-division reports additionally disclose every system-specific optimization and its source. Scores from the two divisions are never combined.

### 2.3 Normative language and conformance

In the protocol and schemas, MUST and REQUIRED identify controls necessary for the declared KGBP claim class; SHOULD identifies a recommended control that may be omitted only with a published rationale and impact analysis; MAY identifies an optional control. A conformance statement names the KGBP version, claim class, division, evaluated tracks, system-card version, evidence-bundle hash, and every unmet or waived control. A report cannot claim KGBP conformance merely because it used the reference software or achieved a design score. Certification, accreditation, and regulatory conformity remain the responsibility of authorized external bodies.

## 3. System-under-test taxonomy

The system card is the primary key of a KGBP result. A marketing name or mutable alias is insufficient. System classification is compositional: “reasoning,” “multimodal,” “endpoint,” and “router” describe different facets and may all apply to one deployed system. A single mutually exclusive label would discard information and invite invalid comparisons.

| System type | Measured object | Mandatory specialized controls |
| --- | --- | --- |
| Base model | Pretrained checkpoint | Completion protocol, adaptation, contamination |
| Instruction model | Chat/instruction checkpoint | Instruction and refusal behavior, multi-turn state |
| Reasoning model | Model with test-time compute | Repeat generations, reasoning-budget curve, hidden-token treatment |
| Specialist model | Domain model | Expert-validated domain tasks and baselines |
| Multimodal model | Multi-input/output model | Native modality tasks and modality-specific graders |
| Embedding model | Vector endpoint | Recall, nDCG, clustering, hard negatives, robustness |
| Reranker | Query-document scorer | nDCG, MRR, recall, calibration, domain shift |
| Endpoint | Model plus serving stack | Availability, latency, retries, rate limits, region, version drift |
| Router | Dynamic destination policy | Full counterfactual panel, regret, calibration, stability |
| Ensemble | Combined systems | Marginal contribution, diversity, oracle gap, cost |
| Agent | Model, loop, tools, memory | Verified state outcome, side effects, trajectory, recovery |
| Application | Socio-technical product | End-to-end outcomes, policy, escalation, accessibility, burden |

### 3.1 Required system-card fields

Each result records a unique system identifier; provider and owner; exact model or application version; model snapshot if available; endpoint and region; access mode; deployment scope; input and output modalities; context and output limits; reasoning modes; tools and safeguards; tokenizer; pricing source and effective date; license; API and SDK versions; and any routing candidate set.

Two providers serving nominally identical weights are separate endpoints for operational analysis. They may be grouped as one model family only for a preregistered capability analysis that can justify equivalence of weights, prompt templates, quantization, and inference settings.

### 3.2 Applicability, not forced ranking

An image generator is not assigned zero on a text-only reasoning test merely to put it in a catalog-wide table. It is marked not applicable to that track and evaluated in a modality-specific division. A router is not called a model. An application is not compared with a base checkpoint unless the result is explicitly labeled system-to-system and the extra components are part of the intended construct.

### 3.3 Compositional classification model

The system card records independent facets rather than attempting to place every system on one axis.

| Facet | Representative values | Why the facet matters |
| --- | --- | --- |
| Behavioral adaptation | base, instruction-tuned, preference-tuned, domain-adapted | Determines prompt format, refusal expectations, and relevant baselines |
| Test-time computation | direct, fixed reasoning, adaptive reasoning, search | Determines compute curves and resource comparability |
| Modalities | text, image, audio, video, structured data, embeddings | Determines applicable tasks and graders |
| Specialization | general, code, legal, medical, scientific, retrieval | Determines domain validity and expert-review requirements |
| Serving boundary | checkpoint, local runtime, first-party API, third-party API | Determines what operational properties belong to the measured object |
| Orchestration | single endpoint, router, ensemble, agent, application | Determines counterfactual, trajectory, and component-attribution needs |
| Augmentation | retrieval, tools, web, memory, sandbox, human escalation | Determines allowed resources and leakage/security surface |
| Governance state | fixed snapshot, mutable alias, preview, deprecated | Determines identity certainty and comparison lifetime |

The classification can be visualized as a stack:

```text
application policy and human workflow
                |
agent loop / router / ensemble policy
                |
tools, retrieval, memory, and safeguards
                |
managed endpoint and serving infrastructure
                |
model checkpoint, adaptation, and reasoning mode
                |
hardware, runtime, region, and dependency state
```

A result names the highest layer inside the declared system boundary and identifies all material lower layers. If the boundary ends at a checkpoint, network failures are out of scope. If it ends at a managed API, network and serving behavior are part of the endpoint result. If it ends at an application, prompts, retrieval, policy, tools, humans, and user burden are part of the result.

### 3.4 Identity confidence and mutable systems

System identity has its own assurance state. A provider-supplied immutable snapshot with a documented model card has stronger identity evidence than a marketing alias whose backing model can change. The report records the identifier requested, identifier returned, provider request ID, API and SDK versions, region, effective settings, routing decision, pricing date, and observation time. Where a provider cannot expose a snapshot, the result is explicitly “endpoint as served during the measurement window.”

Identity confidence is not averaged into quality. It is a publication qualifier:

| Identity level | Minimum evidence | Permitted longitudinal claim |
| --- | --- | --- |
| I0 unknown | Display name only | None; exploratory result only |
| I1 alias | Stable requested alias and timestamps | Endpoint-as-served during the observed window |
| I2 declared snapshot | Provider snapshot/version plus effective settings | Comparison of declared versions, subject to provider attestation |
| I3 verified artifact | Content digest or independently inspectable weights/runtime | Repeatability claim within the verified artifact boundary |

### 3.5 Comparison admissibility matrix

Before ranking, the evaluator freezes which comparisons are admissible.

| Left / right system | Capability comparison | Operational comparison | Required qualification |
| --- | --- | --- | --- |
| Same checkpoint, different providers | Usually admissible if elicitation is aligned | Admissible and often primary | Quantization, prompt template, and runtime differences disclosed |
| Fixed endpoint versus router | System-to-system only | Admissible for a deployment decision | Router candidates, overhead, and counterfactual coverage reported |
| Model versus application | Normally inadmissible | Only if the application is the intended product | Extra components treated as part of the construct |
| Text model versus image generator | Not applicable on text-only track | Separate modality divisions | No forced zero for inapplicable tasks |
| Open versus closed elicitation | Never pooled | Separately reportable | Division and resource regime in every table |

This admissibility decision is part of preregistration. A post-run decision to merge or split system classes is a protocol deviation because it changes the comparison population.

## 4. KGBP design architecture

KGBP has ten non-compensatory dimensions.

| Dimension | Central question | Critical examples |
| --- | --- | --- |
| Construct validity | Does the study measure the declared decision construct? | Claim, population, estimands, decision thresholds |
| Statistical validity | Can effects and uncertainty be interpreted? | Power, repeats, hierarchy, clustering, multiplicity |
| Coverage | Does the sample represent capabilities and users? | Tracks, languages, modalities, difficulty, production tasks |
| Freshness | Is memorization or leakage controlled? | Item age, private holdout, audit, canaries, frozen plan |
| Fairness | Are comparisons controlled and elicitation qualified? | Budgets, dual regimes, snapshots, refusal policy |
| Reproducibility | Can evidence and outputs be reconstructed? | Hashes, schemas, raw artifacts, lineage, signed log |
| Operations | Does the test resemble service use? | Interleaving, load, tails, retries, cost, energy, drift |
| Trustworthiness | Are material risks measured? | Safety, privacy, bias, security, factuality, escalation |
| Specialized evaluation | Is each system type evaluated correctly? | Router, agent, retrieval, modality and judge controls |
| Governance | Can outsiders inspect, challenge, and replicate? | Preregistration, reviewers, conflicts, appeals, replication |

### 4.1 Readiness algorithm

Let `d_j` be the score from 0 to 10 for design dimension `j`, calculated as the fraction of weighted declarations present. If a critical declaration is missing, `d_j` is capped at 8.9. The descriptive declaration-completeness score is the geometric mean:

```text
D = exp((1/J) * sum_j(log(d_j)))
```

Profile declaration readiness is not `D >= 9`. It is:

```text
design_ready = AND_j(d_j > 9.0)
```

This non-compensatory gate is intentional, but its interpretation is narrow. A value of 10 means that the machine-readable configuration contains every declaration recognized by the profile. It does not show that a dataset is uncontaminated, an analysis is correctly implemented, a reviewer is independent, or an evidence URI is authentic. Perfect documentation cannot compensate for a contaminated dataset; broad coverage cannot compensate for no uncertainty analysis; and low cost cannot compensate for unsafe behavior.

### 4.2 Execution and publication gates

Declaration readiness describes a plan. Execution readiness additionally requires a frozen, content-addressed run plan and validated infrastructure. An external-review candidate additionally requires completed primary tracks, prespecified precision targets, a timestamped preregistration, privacy-reviewed raw artifacts or controlled auditor access, a signed manifest, resolved deviations, an independent review report, a benchmark card, a standards crosswalk, and at least two independent replication reports.

Passing the automated declaration audit is necessary but not sufficient. The current reference software can test the presence and syntax of selected evidence references; their authenticity, provenance, substantive adequacy, independence, and relevance require separate verification.

### 4.3 Conformance evidence states

Every control receives an evidence state. These states prevent a boolean such as `independent_red_team: true` from being mistaken for an independently reviewed red-team report.

| State | Meaning | Minimum machine-readable evidence |
| --- | --- | --- |
| E0 absent | Required control is not declared | Missing or invalid field |
| E1 declared | Intended method or control is stated | Versioned declaration and accountable owner |
| E2 implemented | Execution artifacts show the control operated | Artifact IDs, hashes, timestamps, and validation output |
| E3 internally verified | A separate internal reviewer checked implementation and evidence | Signed review record and resolved findings |
| E4 independently verified | A conflict-disclosed external party reviewed the evidence | Reviewer identity, competence, scope, methods, findings, and signature |
| E5 replicated | An independent organization repeated the relevant protocol | Replication bundle, compatibility analysis, and discrepancy report |

The state of dimension `j` is the minimum evidence state among its applicable critical controls. A study may report both declaration completeness and evidence maturity, but must not average them:

```text
declaration_ready = AND_j(d_j > 9.0)
evidence_state_j = min_k(state_jk for applicable critical control k)
external_review_ready = declaration_ready AND min_j(evidence_state_j) >= E2
independently_verified = min_j(evidence_state_j) >= E4
```

E5 is not a claim of exact numerical reproduction. Replications compare a frozen estimand under compatible conditions, report effect differences and heterogeneity, and investigate endpoint drift or environment differences.

### 4.4 Control applicability, waivers, and deviations

A control can be not applicable only when the system boundary or claim makes it logically irrelevant, and the rationale is published before results. “Not measured” is not “not applicable.” Waivers identify the approving authority, duration, risk, compensating evidence, and effect on permitted claims. Deviations identify when the plan changed, why, who knew system identities, which results were affected, and whether the deviation invalidates confirmatory inference.

```text
protocol controls
      |
      +--> applicable --> evidence state E0..E5 --> claim permissions
      |
      +--> not applicable --> public rationale --> independent review
      |
      +--> waived/deviated --> impact analysis --> correction or invalidation
```

### 4.5 Assurance roles and non-endorsement

The benchmark author may declare controls and publish evidence. An internal quality function may verify execution. An independent evaluator may assess evidence within a stated scope. An accreditation or certification body may issue a formal decision only under its own authority. LBP does not collapse these roles. Passing the reference software, obtaining a high declaration score, or citing a standard never creates certification or endorsement.

## 5. Measurement model and estimands

### 5.1 Validity argument

A benchmark is a measurement procedure, not the construct itself. “Reasoning,” “helpfulness,” “safety,” and “production suitability” are latent or decision-defined concepts that cannot be identified by naming a dataset column. For every primary claim, the evaluator writes a validity argument linking the intended interpretation to evidence and foreseeable consequences, following the argument-based and multi-source view of validity used in measurement practice [21, 22].

| Validity evidence | Question | Required evidence |
| --- | --- | --- |
| Content representation | Does the task universe cover the declared construct? | Domain blueprint, target population, expert review, omitted-content analysis |
| Response process | Does the system interact with tasks as intended? | Prompt protocol, extraction audit, tool policy, refusal analysis, transcript review |
| Internal structure | Do items and subscales behave consistently with the construct? | Dimensionality, reliability, item difficulty/discrimination, local-dependence analysis |
| Relations to external variables | Do scores relate to qualified humans, incumbent systems, or field outcomes as expected? | Convergent, discriminant, criterion, and predictive evidence |
| Generalization | Can the result extend beyond this fixed item set, time, locale, or endpoint window? | Sampling frame, repeated generations, cluster/day/region effects, replication |
| Consequences | What decisions and harms can follow from using the score? | Decision analysis, subgroup impacts, gaming risk, false-selection costs, monitoring plan |

Validity is claim-specific. A dataset may validly measure exact code-test success while being invalid evidence for maintainability, security, or developer productivity. A refusal may be a capability failure on a harmless task and a correct safety outcome on a prohibited task. The protocol therefore separates task outcome, service status, policy outcome, and decision utility.

### 5.2 Observation model

For system `s`, item `i`, repeat `r`, and track `t`, let `Y_sirt` be a normalized task outcome in `[0,1]`. Binary exact-match tasks use 0 or 1. Partial-credit tasks require a validated, task-specific scale with a declared meaning. Let `S_sirt` indicate that a valid answer was delivered, while separate indicators record deadline, budget, cap, policy, and telemetry conformance. A provider failure or timeout receives zero in the conservative end-to-end endpoint, but benchmark defects and inapplicable items are handled by frozen adjudication rules rather than attributed automatically to the system.

For a complete planned cell, the item mean first averages generation repeats, including governed failures as zero:

```text
Ybar_sit = (1 / R_sit) * sum_(r=1..R_sit)(Y_sirt)
```

`R_sit` is the planned repeat count, not the number of successful or present rows. The scoring pipeline joins observations to the frozen schedule before aggregation; absent cells become explicit `missing` observations. The track estimand is a preregistered weighted mean over item strata. Equal item weight is the default for a designed benchmark. Production selection may use frozen traffic or inclusion-probability weights, but both unweighted and target-population-weighted estimates are reported.

### 5.3 Finite-benchmark and generalized-population estimands

NIST AI 800-3 distinguishes performance on a fixed benchmark from performance generalized to a broader universe [4]. LBP makes that distinction explicit.

For the finite set of `N_t` benchmark items in track `t`:

```text
mu_B(s,t) = (1 / N_t) * sum_(i=1..N_t) E_r[Y_sirt]
```

For a target item population `P_t` from which items are treated as sampled:

```text
mu_G(s,t) = E_(I ~ P_t)[E_r(Y_sIrt)]
```

`mu_B` supports a claim about this frozen benchmark. Its uncertainty comes from generation and other repeated execution factors, not from pretending the fixed items were randomly sampled. `mu_G` supports a superpopulation claim only when the sampling frame, inclusion mechanism, cluster structure, and exchangeability assumptions are defensible. Resampling items estimates generalized uncertainty; it must not be labeled merely “the benchmark confidence interval” without naming the estimand.

For stratified sampling with target stratum weights `W_h` that sum to one:

```text
mu_hat_G(s,t) = sum_h W_h * [(1 / n_h) * sum_(i in h) Ybar_sit]
```

If inclusion probabilities differ within strata, a Horvitz-Thompson or Hájek estimator is used and the probability of selection is retained in the item manifest. Traffic weights are versioned, time-bounded, privacy-reviewed, and accompanied by an equal-stratum sensitivity view so dominant markets cannot hide underserved populations.

### 5.4 Conditional quality and the two-part availability-quality model

Conditional quality answers: how good were valid returned answers? End-to-end quality answers: what quality did a planned request receive? They are calculated separately.

```text
conditional_quality = sum(score for valid answers) / valid_answer_count
end_to_end_quality = sum(score, with all failures = 0) / planned_count
```

Equivalently, when a valid answer has score `Y` and delivery indicator `S`:

```text
availability = P(S = 1)
conditional_quality = E[Y | S = 1]
end_to_end_quality = E[S * Y]
```

The factorization `E[S*Y] = P(S=1)E[Y|S=1]` is an identity when `Y` is defined for delivered valid answers and failures contribute zero. It does not assume independence. Reporting all three quantities prevents a high conditional score from hiding poor availability and prevents a service failure from being misread as evidence that the underlying model lacks capability.

The denominator and first-trial policy are frozen. A later successful rerun may be reported as a separate trial but cannot replace an observed failed trial. Model-capability analyses may additionally report a provider-failure sensitivity analysis, but that secondary result cannot overwrite the endpoint-as-served estimand.

### 5.5 Operational goodput and decision utility

For each logical question, define conformance indicators for success, deadline, budget, and output cap. Conservative score-weighted goodput is:

```text
G_si = Y_si * I(success) * I(deadline_ok) * I(cost_ok) * I(all_attempt_caps_ok)
```

Unknown required telemetry sets the corresponding conservative indicator to zero. A second optimistic sensitivity estimate may treat unknowns as conforming, but it cannot replace the conservative primary result.

Goodput is deliberately conjunctive. A useful answer that arrives after a hard deadline or exceeds a regulated cost budget may have zero decision utility. For soft constraints, a preregistered utility function can be more informative:

```text
U_si = value(Y_si) - lambda_cost*C_si - lambda_latency*L_si - lambda_risk*R_si
```

The lambdas are stakeholder-specific exchange rates, not universal constants. The report shows conclusions over a plausible range of weights and retains the underlying metric vector. A utility score never replaces the safety or evidence gates.

### 5.6 Pairwise effects, noninferiority, and equivalence

Because all systems receive the same frozen items, the primary comparison is paired:

```text
Delta_ab,t = mean_i(Ybar_a,i,t - Ybar_b,i,t)
```

KGBP reports the paired effect, an interval, wins/losses/ties, and a multiplicity-adjusted p-value for the preregistered family. Failure to detect a difference is not evidence of equivalence. Practical equivalence is concluded only if the entire compatible confidence interval lies within the frozen margin `[-delta, +delta]`, or through a preregistered two-one-sided-test procedure [27]. Noninferiority uses a one-sided margin selected from decision consequences before results. The margin is expressed on the reported scale and justified by a stakeholder decision, historical variability, or external criterion; choosing it after seeing the gap is prohibited.

### 5.7 Rank uncertainty and no universal intelligence scalar

The primary output is a vector of track and operational outcomes. A descriptive macro averages track estimates equally so a large dataset cannot silently dominate the construct. A total order can always be printed from point estimates, but it may contain more precision than the experiment supports. LBP therefore reports bootstrap or posterior rank distributions, simultaneous rank intervals where available, probability of being best under the declared estimand, and the set of systems not practically separated from each decision frontier.

Deployment choices use a Pareto frontier over declared metrics. System A point-dominates B only if A is no worse on every selected metric and strictly better on at least one. A robust dominance claim additionally requires uncertainty bounds to support the direction under the preregistered rule. Stakeholder-specific utility functions may be applied after publication, but their weights are not presented as universal truth.

| Output | Interpretation | Prohibited interpretation |
| --- | --- | --- |
| Point rank | Ordering of observed point estimates | Proven universal ordering |
| Rank interval | Positions compatible with resampled/model uncertainty | Probability statement unless the method supports it |
| Corrected paired effect | Evidence for a declared pair/family | Evidence for every unplanned comparison |
| Equivalence decision | Effect lies within a justified margin under the test | Exact equality |
| Pareto set | Systems not point-dominated on selected metrics | One objectively best system |

### 5.8 Measurement invariance and differential item functioning

A global comparison requires more than translated prompts. An item exhibits differential item functioning when systems or groups with comparable underlying capability have different probabilities of success for construct-irrelevant reasons such as translation artifacts, locale-specific assumptions, formatting, or grader behavior [33]. The study tests invariance of rubric meaning, item difficulty, and score interpretation across languages, modalities, system families, and elicitation regimes.

Evidence can include multi-group item-response models, logistic DIF analysis, matched expert review, response-process inspection, and sensitivity estimates with flagged items removed. DIF is diagnostic rather than automatically disqualifying: some items intentionally measure locale-specific competence. The benchmark blueprint declares which differences are construct-relevant.

## 6. Sampling, freshness, and contamination

### 6.1 Target population

Before choosing a dataset, the protocol states the population of future tasks, users, languages, modalities, difficulty, deployment contexts, and time horizon to which results should generalize. Benchmark items are then sampled or constructed to represent that population. Dataset convenience is not a target population.

The sampling frame makes the abstract population operational. It records candidate sources, coverage gaps, inclusion and exclusion rules, authoring process, unit of sampling, cluster structure, and inclusion probability. A production claim also records the traffic window from which weights were derived and how privacy filtering changed the frame.

| Population element | Example declaration | Consequence for design |
| --- | --- | --- |
| Task | Repository bug fixes encountered by an enterprise team | Sample repositories, languages, defect types, and difficulty from that workflow |
| User | Adult knowledge workers in specified locales | Include locale, accessibility, and expertise strata |
| System | Text API endpoint with tools disabled | Do not generalize to browser-enabled agents |
| Environment | Three provider regions under declared load | Model day, region, and load effects |
| Time | Next release quarter | Measure endpoint drift and refresh items during that horizon |
| Decision | Select systems meeting quality, cost, safety, and SLO thresholds | Power every decision-critical endpoint, not only the mean score |

### 6.2 Sample size and power

The automated declaration floor is 300 items and three independent generations per stochastic system-item cell. The example design uses 1,200 items and five repeats. Neither number is automatically adequate. Prospective power analysis must use a minimum effect that changes a decision and pilot estimates of item, cluster, system-item, generation, day, and region variance. Multiplicity, expected failures, intended slice estimates, unequal weights, and measurement error increase the required sample.

For an approximate paired continuous outcome, a planning calculation is:

```text
n = ceil(((z_(1-alpha/2) + z_power) * sigma_delta / MDE)^2)
sigma_delta = sigma * sqrt(2 * (1 - rho_paired))
```

The reference implementation exposes this calculation for planning. Final analysis uses the preregistered model and realized design.

The approximation assumes independent paired item differences, an approximately continuous outcome, stable variance, and one primary comparison. It is not the final sizing method for clustered binary tasks or a large leaderboard. The preferred design process is:

1. Run a blinded variance pilot across representative systems without selecting winner-favoring tasks.
2. Fit the planned hierarchical model and estimate variance components with uncertainty.
3. Simulate complete studies under null, minimum-important, and heterogeneous effects.
4. Apply the full missingness, multiplicity, slice, and stopping rules to each simulation.
5. Select sample sizes that achieve both error-rate and interval-width targets over plausible variance values.
6. Freeze the simulation code, random seeds, assumptions, and decision before the confirmatory run.

Precision can be a clearer planning target than power. A track may require a 95 percent interval half-width below 0.02, an availability lower bound above 0.995, or a safety-violation upper bound below a declared threshold. Every primary endpoint and required worst slice receives its own target. The largest requirement controls the study.

For a binary rare event with target rate `p_star`, observing zero events in `n` independent trials yields the exact one-sided upper relation:

```text
P(zero events | p_star) = (1 - p_star)^n
n >= log(alpha) / log(1 - p_star)
```

Dependence, adaptive attacks, multiple languages, or clustered scenarios reduce effective information and require a hierarchical or simulation-based calculation.

### 6.3 Stratification and clustering

Minimum design strata include track, difficulty, language, modality, source, and production frequency. Domain, locale, safety risk, answer form, and context length may be added. A cluster identifier links items that share a passage, repository, scenario, template, source document, or author. Clustered items are never treated as independent in uncertainty estimation.

If the mean cluster size is approximately `m` and the intracluster correlation is `rho`, a screening approximation to the design effect is:

```text
DEFF = 1 + (m - 1) * rho
n_effective = n_observed / DEFF
```

This formula is diagnostic, not a substitute for the preregistered crossed model. Highly unequal cluster sizes, shared graders, repeated templates, and system-item interactions require explicit modeling. The item manifest retains every dependency that an analyst would need to reproduce the clustering decision.

### 6.4 Allocation across tracks and slices

An overall floor does not guarantee useful subgroup evidence. Allocating 1,200 items across fourteen tracks and fifteen languages could leave many cells with only a handful of observations. The protocol therefore publishes an allocation matrix with planned and realized counts and marks each intended inference as confirmatory, supportive, or descriptive.

| Allocation objective | Recommended mechanism | Required sensitivity |
| --- | --- | --- |
| Equal construct coverage | Minimum items per primary track | Reweight to production distribution |
| Production selection | Traffic-proportional sampling | Equal-track and equal-language views |
| Worst-slice assurance | Oversample low-volume or high-risk slices | Restore population weights for aggregate estimates |
| Frontier discovery | Adaptive difficulty allocation in a pilot | Confirm on a fresh frozen sample |
| Safety assurance | Risk-weighted scenarios and adaptive attacks | Report natural-frequency and stress-test results separately |

### 6.5 Freshness controls

For an external-review candidate, the KGBP reference profile declares a maximum item age of 180 days and at least a 20 percent private or access-controlled holdout in reused public domains. These are screening controls, not universal scientific constants. A timeless proof problem does not become invalid solely because it is old, while a current-events task may be stale within days. Each track therefore declares an exposure-risk model based on public availability, answer stability, training incentives, provider access, and reuse.

The actual age and exposure-risk distributions are published. The item pool has exact and semantic deduplication, lexical and semantic contamination checks, answer-reproduction probes, benchmark-awareness canaries, and a leakage incident policy. Private status alone is not proof against leakage: item authors, evaluation operators, provider logs, and repeated submissions are potential exposure channels.

LiveBench demonstrates the value of periodically updated questions and objective ground-truth graders [11]. However, a release option can be cumulative. KGBP therefore records actual item dates rather than treating a release label as proof of freshness.

### 6.6 Contamination evidence model

Contamination is rarely observed directly. The report combines evidence rather than treating one similarity threshold as dispositive.

| Evidence source | Signal | Important limitation |
| --- | --- | --- |
| Exact/near duplicate search | Prompt or answer overlap with known corpora | Training corpora are incomplete or unavailable |
| Semantic retrieval | Paraphrase or shared-solution structure | Embeddings can over- or under-match |
| Answer reproduction probe | Memorized phrase, identifier, or distractor pattern | Capability can resemble memorization |
| Canary behavior | Access to controlled strings or task conventions | Canary may itself leak or be guessed |
| Temporal analysis | Performance discontinuity after public release | Model and harness changes confound time |
| Provider attestation | Training cutoff and exclusion procedure | Requires trust and scope clarity |

The incident policy declares quarantine scope, affected systems and releases, replacement sampling, whether prior results are invalidated, and how corrected estimates link to the original publication. Contamination sensitivity reports results with high-risk items removed and never silently replaces the frozen primary analysis.

### 6.7 Broken-item policy

Items are reviewed for solvability, ambiguity, grader correctness, dependency availability, and shortcut leakage before model identities are revealed. Exclusions and replacements are frozen. Post-run challenges are adjudicated blind to model identity where possible, recorded in a public correction log, and applied consistently to all systems.

The protocol distinguishes an invalid benchmark item from a difficult item. Poor performance is not evidence that an item is broken. Adjudicators receive item content, grader evidence, and blinded response samples but not aggregate model ranks. A post-run exclusion triggers a versioned sensitivity analysis and preserves the superseded result.

## 7. Statistical analysis and uncertainty

NIST AI 800-2 recommends a statistically valid analysis aligned with objectives, explicit assumptions, suitable aggregate statistics, uncertainty for relevant variation, shared evaluation details, and qualified claims [3]. NIST AI 800-3 develops a generalized linear mixed-model view that separates system capability from item difficulty [4]. KGBP supports both model-based and design-based analysis.

### 7.1 Hierarchical cluster bootstrap

The reference design-based method resamples clusters, then items within sampled clusters, then generations within sampled items. Repeats are averaged inside the item before item aggregation. This preserves the experimental hierarchy and avoids pseudoreplication [25].

For paired effects, only shared planned items are included, and differences are formed inside each item before cluster resampling. The bootstrap seed, sample count, percentile method, confidence level, and any studentization are recorded.

The resampling unit follows the estimand. For finite-benchmark accuracy, items are fixed and only repeat-generation or execution uncertainty is resampled. For generalized accuracy, clusters and items are resampled from the declared sampling frame. A percentile interval is a baseline, not an automatic guarantee: the analysis checks discreteness, skew, boundary effects, influential clusters, and the number of distinct bootstrap values. Studentized or bias-corrected intervals may be used when validated and preregistered.

Bootstrap pseudocode for a generalized paired effect is:

```text
for b in 1..B:
    draw source clusters with replacement
    within each selected cluster, draw items with replacement
    within each selected item and system, draw planned repeats
    form system difference inside each item
    aggregate with frozen stratum weights
return point estimate, interval, rank draws, and diagnostics
```

The same random resample is used across systems to preserve pairing. Missing planned cells are explicit observations before resampling; they are not dropped by intersecting only successful results.

### 7.2 Generalized linear mixed model

A preregistered binary-outcome model may take a crossed form [4, 24]:

```text
logit(P(Y_sirtdg = 1)) =
    alpha + theta_s + beta_t + (theta*beta)_st
    + u_i + q_si + v_cluster[c(i)] + w_day[d] + z_region[g]
    + x_sirtdg * gamma
```

`theta_s` estimates system effects; `beta_t` track effects; `u_i` item difficulty; `q_si` system-item interaction; `v_cluster` shared-cluster variation; and `w_day` and `z_region` temporal and regional variation. The interaction `q_si` is important because systems need not rank items in the same difficulty order. Covariates `x` can encode language, difficulty, context length, elicitation regime, or load, but confirmatory covariates and interactions are frozen before unblinding.

Partial scores require an appropriate likelihood or robust estimating approach: beta or ordered models for bounded/ordinal scores, hurdle models for zero inflation, survival models for censored latency, and Bradley-Terry/Thurstone-type models for pairwise preference. Reports include the formula, coding, link, estimand transformation, random-effects covariance, priors if Bayesian, convergence diagnostics, posterior predictive or residual checks, influence analysis, and sensitivity models.

### 7.3 Generalizability theory and variance decomposition

Generalizability theory treats the observed score as a combination of facets such as item, generation, day, region, and grader. A G-study estimates variance components; a D-study asks how reliability and precision would change under a proposed allocation of items and repeats [23].

```text
Var(Y) = sigma_item^2 + sigma_system_item^2 + sigma_generation^2
       + sigma_day^2 + sigma_region^2 + sigma_grader^2 + sigma_residual^2
```

Not every component is identifiable in every design. For example, one generation per item cannot separate generation variance from residual variation, and sequential endpoint blocks cannot separate system from time. The report contains an identifiability table stating which effects the realized design can estimate.

| Facet | Repeated/crossed design needed | Decision risk if omitted |
| --- | --- | --- |
| Item | Shared frozen items across systems | Task-selection uncertainty understated |
| Generation | Multiple independent generations per system-item | Stochastic instability hidden |
| System-item | Shared items and multiple systems | Rank reversals across task types hidden |
| Day/region | Interleaved calls across windows and regions | Service state confounded with system identity |
| Grader/rater | Multiple blinded graders or validation sample | Judge variability and bias hidden |

### 7.4 Multiplicity and selective reporting

All planned pairwise primary comparisons form one declared family unless a hierarchical testing strategy is preregistered. Holm family-wise correction is the default because it is valid under arbitrary dependence and is easy to audit; resampling-based family procedures may be used when their assumptions and implementation are validated [26]. Exploratory comparisons are clearly labeled and may use false-discovery-rate control, but they cannot be promoted to confirmatory claims after inspection.

The family must be scientifically meaningful. Testing every pair among many systems can consume nearly all power while answering no specific decision. Preferred designs identify primary challengers, incumbent comparisons, noninferiority questions, or a hierarchical track-first procedure. Every omitted, added, or selectively emphasized comparison is recorded. Winner-versus-runner-up inference selected after observing ranks requires selective-inference or fresh confirmation; it is not equivalent to a preregistered pair.

### 7.5 Reliability, tail latency, and censored observations

Availability, refusal, violation, and pass rates use Wilson, exact, or model-based intervals rather than a naive Wald interval, especially near zero or one [29]. Tail latency is not reported from tiny samples: at 15 observations, p95 is essentially an order statistic near the maximum. The KGBP declaration floor of 1,000 requests per system is only a screening threshold; the actual count is sized for the target quantile or SLO confidence interval. At `n=1,000`, the empirical p99 is informed by roughly ten observations in the upper one percent before clustering or censoring.

Timeouts are right-censored durations, not ordinary fast failures. Reports show the timeout threshold, Kaplan-Meier or other suitable survival estimates [30], competing failure causes, and sensitivity to treating the deadline as the observed value. Quantile method, interpolation rule, warm-up removal, clock source, and streaming event definition are frozen. Cluster bootstrap or block bootstrap respects bursts and shared provider incidents.

### 7.6 Missingness, failure attribution, and bounds

The primary endpoint maps system-attributable no-answer outcomes to zero because that is the user-experienced result. It does not assume all missingness has the same cause. The observation model separates:

- provider/network failure;
- model refusal or invalid output;
- policy block;
- harness or grader failure;
- invalid benchmark item;
- unavailable required telemetry; and
- absent or corrupted evidence.

For `m` unresolved planned scores among `N` items with observed score sum `T`, scale-bounded worst-case sensitivity is:

```text
lower_bound = T / N
upper_bound = (T + m) / N
```

Narrower assumptions require justification and are secondary. Missing-at-random models are not assumed merely because software can fit them. If attribution is contested, the report publishes both endpoint-as-served scoring and a clearly labeled capability sensitivity, plus the adjudication evidence. A harness-caused failure triggers correction or invalidation rather than automatic model penalty.

### 7.7 Calibration and selective prediction

Where a system emits confidence `p_i` with a documented probabilistic meaning for binary outcome `y_i`, KGBP reports proper scores and reliability diagnostics [31, 32]:

```text
Brier = (1/N) * sum_i (p_i - y_i)^2
log_loss = -(1/N) * sum_i [y_i*log(p_i) + (1-y_i)*log(1-p_i)]
ECE = sum_b (n_b/N) * abs(mean_p_b - mean_y_b)
```

ECE depends materially on bin count and boundaries, so bins are frozen and accompanied by reliability diagrams, uncertainty, Brier decomposition, and alternative calibration-error sensitivity. For soft task scores, the target semantics are stated; treating a router's proprietary confidence as probability of exact correctness is prohibited unless documented and validated.

Selective prediction reports risk as a function of retained coverage when the system abstains below a confidence threshold. Thresholds are selected on calibration data and confirmed on held-out data. Calibration claims require substantially more than a few dozen observations and are sliced by track, language, route, and drift period.

### 7.8 Rank distributions and robust Pareto analysis

Each hierarchical resample or posterior draw produces a complete metric vector. From these draws the report can estimate a rank distribution, probability of occupying each rank, and probability of point dominance. These are conditional on the declared sampling and model assumptions; they do not make ranking universal.

For metrics with directions encoded by `a_k` (`+1` higher is better, `-1` lower is better), point dominance of A over B requires:

```text
a_k * metric_Ak >= a_k * metric_Bk for every selected metric k
and strict inequality for at least one k
```

Robust dominance additionally requires the preregistered joint uncertainty rule to support that relation. If cost is a lower bound or energy is missing, the system is not silently placed on a complete-data frontier. Reports show a complete-case frontier, a conservative-bound frontier, and the missing-information pattern.

## 8. Evaluation tracks and graders

The twelve core tracks are reasoning, knowledge, factuality, instruction following, coding, long context, multilingual performance, robustness, safety, efficiency, reliability, and production tasks. Agentic tool use, human preference, retrieval, vision, audio, video, and generative-media tracks become mandatory when the system claims those capabilities.

### 8.1 Objective graders first

Exact answers, executable tests, database-state checks, symbolic equivalence, schema validation, and environment outcomes are preferred. Objective grading reduces judge drift and family bias, but the benchmark must still audit extraction errors, broken references, and unintended shortcuts.

### 8.2 Model judges

When objective grading is impossible, the judge protocol records the exact prompt, model snapshot, temperature, order randomization, blinding, rubric, and aggregation. A panel spanning multiple model families is preferred to a single judge. Position bias, verbosity bias, self-family bias, and score drift are tested.

Automated judges are validated blindly against qualified humans by task, language, system family, answer length, and score band. The KGBP profile requires a predeclared agreement target of at least 0.80, but the metric must be named: raw agreement, weighted kappa, Krippendorff alpha, intraclass correlation, or rank correlation are not interchangeable. Prevalence, category imbalance, uncertainty, and criterion-level false positives and false negatives are reported. Agreement alone is not validity; a judge and humans can agree on a rubric that does not measure the intended construct.

### 8.3 Human evaluation

Human evaluation records qualifications, recruitment, geography, language, compensation, conflicts, instructions, blinding, order, adjudication, and agreement. High-stakes domain evaluation uses qualified practitioners. Preference results are reported as pairwise probabilities or a preregistered Bradley-Terry model with uncertainty and judge effects [28].

The comparison graph must be connected for relative preference parameters to be identified. Pair allocation, left/right order, response ties, skipped judgments, rater exclusions, and stopping rules are frozen. The model can include position, verbosity, rater, prompt, and language effects:

```text
logit(P(A preferred to B)) = ability_A - ability_B
                               + beta_position + beta_length
                               + u_prompt + v_rater
```

### 8.4 Grader validity and error propagation

Grader error is measurement error. A validation sample is drawn across score bands, systems, languages, lengths, and failure categories rather than only from typical responses. The report provides confusion matrices or criterion-level error rates, confidence intervals, adjudication outcomes, and whether the grader changes system ordering.

| Grader risk | Diagnostic | Mitigation |
| --- | --- | --- |
| Extraction failure | Compare parsed answer with transcript | Preserve raw answer and versioned parser; manual audit sample |
| Position bias | Swap blinded answer order | Randomize order and estimate position effect |
| Verbosity/style bias | Matched-content length perturbation | Criterion-level rubric and length covariate |
| Self/family preference | Cross-family judge panel and human reference | Report judge-specific estimates; avoid single-family authority |
| Drift | Regrade stable anchor set over time | Pin snapshot and publish anchor change |
| Language inequivalence | Native-rater validation by language | Language-specific rubric adaptation and DIF analysis |

If grader uncertainty is material, it is propagated by jointly resampling judgments or modeling the latent true label. Treating a noisy judge score as error-free can produce overly narrow system intervals.

### 8.5 Human-subject and labor protections

Human evaluation may create privacy, emotional, or occupational risk. The protocol records informed-consent or applicable review basis, exposure to harmful material, opt-out and support mechanisms, compensation, data retention, accessibility, and whether judgments affect employment or access. Safety raters receive risk-appropriate training and exposure limits. These controls are part of evidence quality rather than an administrative appendix.

## 9. Operational measurement

MLPerf separates offline, interactive, and server scenarios and uses governed load generation, logging, latency tracking, accuracy validation, and submission checking [10]. KGBP adopts this scenario discipline for managed AI endpoints.

### 9.1 Randomized interleaving

Sequential model blocks confound system identity with time. KGBP generates every item-system-repeat cell before execution, distributes cells across day and region blocks, and randomizes system order within cells. The schedule is deterministic given the frozen seed and is validated for duplicate, missing, and unexpected cells.

Randomization does not erase interference. Provider rate limits, shared caches, autoscaling, and incident recovery can make one request affect later requests. The run plan therefore records warm-up, cool-down, cache policy, arrival process, concurrency, client host, network path, and whether systems share upstream capacity. Block and cluster definitions follow the operational dependency rather than only the question ID.

### 9.2 Service metrics

The operational scorecard includes:

- time to first token;
- time to first answer token after hidden or visible reasoning;
- time per output token;
- end-to-end logical-request duration;
- queue time where exposed;
- output throughput and request throughput;
- p50, p90, p95, and p99 with adequate samples;
- raw-attempt and logical-request availability;
- retry amplification in calls, time, tokens, and cost;
- deadline, output-cap, and budget conformance;
- rate-limit, provider, policy, model, network, and harness failures; and
- drift across time, version, alias, and region.

Opaque SDK retries are disabled or separately observed. Every attempt is linked to its logical request. Unknown failure usage or cost is not silently zero.

### 9.3 Load model and queueing interpretation

Offline, interactive, and server scenarios answer different questions. Offline tests measure throughput with a pre-existing work queue. Interactive tests approximate a user session and emphasize response latency. Server tests use a declared arrival process and measure whether the system sustains offered load while meeting quality and latency constraints.

| Scenario | Controlled input | Primary outputs | Common invalid comparison |
| --- | --- | --- | --- |
| Offline | Fixed batch/work queue | Completed work per time, cost, accuracy | Comparing with an interactive request path |
| Interactive | Session pacing and concurrency | TTFT, answer latency, deadline success | Ignoring think time or streaming semantics |
| Server | Arrival distribution and offered rate | Goodput, queue delay, saturation, SLO success | Reporting throughput after silently dropping load |

The report shows offered load, admitted load, completed load, and goodput separately. Saturation is identified from the concurrency/arrival curve rather than a single test point. Client-side bottlenecks are ruled out with utilization and connection-pool telemetry. Queueing results are descriptive unless the arrival and service assumptions of a formal model are checked.

### 9.4 Latency events, censoring, and service-level inference

Streaming timestamps are defined operationally:

- request start: final byte handed to the client transport;
- time to first token: first provider output event;
- time to first answer token: first answer event after any classified reasoning stream;
- end-to-end time: terminal answer or governed failure;
- timeout: right-censored at the declared deadline unless a later terminal event is observed for diagnosis.

Clock source, resolution, synchronization, instrumentation overhead, connection reuse, DNS/TLS policy, and retry boundaries are recorded. Empirical quantiles include confidence intervals and minimum effective sample sizes. A deadline success rate is often more decision-relevant than p99 when the tail is heavily censored.

### 9.5 Cost and economic uncertainty

Cost includes input, cached input, cache writes, reasoning, output, tools, router overhead, retries, and failed work. Reported provider invoices and modeled list-price estimates are labeled differently. Primary economic metrics are total cost, cost per planned task, cost per successful outcome, and budget-qualified goodput.

Costs include currency, exchange-rate source and timestamp, tax treatment, discounts, credits, committed-spend assumptions, and pricing effective date. An invoice measures buyer expenditure; a modeled rate card estimates expenditure under stated prices; neither is inference cost. Where failed calls lack usage, totals are lower bounds and cost-efficiency ratios retain bound direction. Fixed engineering, evaluation, human-review, and infrastructure costs may be reported separately for total-cost-of-ownership decisions.

### 9.6 Energy, carbon, and environmental boundary

Energy results state the measurement or supplier-attestation source, boundary, allocation method, hardware, region, time, power-usage effectiveness, carbon-intensity source, and uncertainty. Missing supplier data remains unknown. Financial price is not a proxy for energy.

For measured energy `E_kWh` allocated to the workload and time/region-specific carbon intensity `CI_kg_per_kWh`:

```text
operational_CO2e_kg = sum_(region,time)(E_kWh * CI_kg_per_kWh)
```

Embodied hardware emissions, datacenter overhead, networking, client energy, and tool services are either included with a stated allocation method or explicitly outside the boundary. Carbon estimates report ranges because utilization, marginal grid intensity, hardware lifetime, and provider allocation are uncertain.

### 9.7 Drift and longitudinal monitoring

Managed endpoints are changing services. Repeated anchor sets estimate drift, but public anchors can contaminate future models. The monitoring design therefore combines a small disclosed anchor set for continuity, rotating private strata for freshness, and operational canaries for serving changes. Change-point or control-chart alerts trigger diagnosis; they do not automatically attribute cause to model weights.

Every longitudinal chart marks model aliases, provider release notes, API versions, price changes, harness changes, dataset rotations, incidents, and region changes. A breaking change starts a new comparison series unless a bridge study establishes compatibility.

## 10. Routers, ensembles, agents, and applications

### 10.1 Router evaluation

Every destination a router can select must be run independently on the same item-repeat cells. For item `i`, selected-route regret is:

```text
regret_i = max_m(Y_mi) - Y_selected(i),i
```

The panel oracle is an upper bound within the tested candidates, not a deployable policy. Required baselines include best single endpoint, uniform random, a simple cost/track policy where relevant, and the panel oracle. Report route coverage, stability across repeats, confidence calibration, regret, oracle gap, failover, candidate availability, and marginal quality/cost/latency over the best single endpoint.

Quality-only regret can reward an economically or operationally impossible route. For a declared stakeholder utility:

```text
U_m(x) = Q_m(x) - lambda_c*C_m(x) - lambda_l*L_m(x) - lambda_r*Risk_m(x)
regret_U(x) = max_(m in available candidates) U_m(x) - U_selected(x)
```

The candidate set and availability state are part of each counterfactual. An endpoint that was unavailable when the router acted is not silently treated as a feasible oracle choice. The report provides both an unconstrained panel oracle for diagnostic headroom and an availability/budget-constrained oracle for the declared decision.

When only historical router logs exist, selected outcomes are observational and can be confounded with route policy. Off-policy evaluation requires logged action probabilities or a defensible behavior policy, positivity, stable outcomes, and sensitivity to unmeasured confounding. Inverse-propensity, doubly robust, or model-based estimates are labeled separately from a fully crossed experimental panel.

### 10.2 Agent evaluation

Agent success is determined from verified environment state, not only final prose. The observation includes initial state, tools, permissions, trajectory, state transitions, side effects, policy violations, turn/token/time/cost budgets, recovery, escalation, final state, and cleanup. Environments are reset and inspected for hidden answers, repository history shortcuts, flaky dependencies, or inaccessible services.

Agent outcomes are trajectory-level and often multi-valued. A task can achieve the final state while causing an unacceptable side effect, require human rescue, or leave resources uncleaned. The scorecard therefore includes verified task success, side-effect severity, policy compliance, intervention count, recovery success, and resource use rather than compressing all behavior into final-text quality.

```text
agent utility = outcome value
              - side-effect loss
              - human-intervention burden
              - time, tool, and monetary cost
```

Environment reliability is measured with control agents or deterministic checks. If an inaccessible dependency would fail every competent agent, the event is an environment failure and is handled by the frozen attribution policy rather than being misclassified as model incapability.

### 10.3 Application evaluation

Applications include prompts, retrieval, tools, guardrails, UI, human operators, policies, and downstream actions. Production evaluation therefore measures task outcome, user burden, escalation, accessibility, inappropriate automation, recoverability, and incident response. Model-only scores may inform component choice but cannot establish application fitness.

### 10.4 Component attribution and ablation

System-level performance does not identify which component caused an effect. When component attribution is a claim, the design uses controlled ablations or factorial experiments: model, prompt, retrieval, tool, safeguard, and orchestration policy are varied under a frozen plan. Interactions are expected; the improvement from retrieval with one model need not transfer to another. Post hoc anecdotes about a single trace are diagnostic, not causal estimates.

### 10.5 Stateful reliability and recovery

Long-horizon systems accumulate risk. The protocol samples failure injection at meaningful states: tool timeout, stale memory, malformed tool output, permission denial, provider outage, partial write, conflicting human instruction, and context compaction. Outcomes include safe pause, retry, failover, rollback, escalation, and irreversible side effect. The state machine and recovery budget are published.

```text
normal -> degraded dependency -> detect -> contain -> recover
   |              |                |        |        |
   +-> unsafe action               |        |        +-> verified final state
                  +-> silent error +-> escalate
```

### 10.6 Router and agent publication minimums

| Claim | Minimum evidence |
| --- | --- |
| Router improves quality | Full item-matched candidate panel or qualified off-policy design |
| Router reduces cost | Retry-inclusive billed/modeled cost for router and candidates |
| Router is calibrated | Defined confidence semantics, held-out calibration, adequate sample |
| Agent completes tasks | Independent final-state verifier and environment-health evidence |
| Agent is safe | Side-effect, permission, injection, recovery, and escalation tracks |
| Application improves outcomes | Production-relevant comparator, human burden, and downstream outcome |

## 11. Safety, security, and trustworthiness

OECD principles call for AI systems to remain robust, secure, and safe throughout their lifecycle, including foreseeable use, misuse, and adverse conditions, supported by traceability and risk management [9]. The EU AI Act requires appropriate accuracy, robustness, and cybersecurity for high-risk systems and encourages benchmark and measurement-method development [8]. KGBP treats these as separate evidence tracks rather than a quality bonus.

Minimum domains are harmful content, jailbreak robustness, privacy, bias and fairness, factuality, cybersecurity, overrefusal, and deception. Each has a threat model defining actors, access, expertise, assets, harm thresholds, tools, attempts, and budget.

Static prompt sets are insufficient for strong adversaries. Adaptive, multi-turn, and tool-aware attacks are required where the claim concerns expert misuse. Safety is evaluated across claimed languages and modalities. Reports distinguish safe refusal, excessive refusal, task failure, policy inconsistency, and successful harmful assistance.

Human escalation is evaluated as a system: precision, recall, response time, reviewer burden, resolution quality, and disparate outcomes. Incident exercises cover degraded dependencies, malicious tool output, prompt injection, credential boundaries, failover, rollback, and safe shutdown.

NIST AI 600-1 provides a cross-sectoral GenAI risk profile to help organizations incorporate trustworthiness considerations across design, development, use, and evaluation [2]. KGBP maps evidence into that risk-management lifecycle but does not claim that benchmark scores alone close organizational risks.

### 11.1 Threat-model contract

Each safety claim identifies actor, objective, access, knowledge, tools, iteration budget, target assets, environment, harm threshold, and stopping rule. A “jailbreak rate” without this contract is not comparable across studies.

| Threat-model field | Example question |
| --- | --- |
| Actor and expertise | Ordinary user, domain expert, insider, automated attacker? |
| Access | Text only, tools, weights, gradients, system prompt, repeated queries? |
| Asset and harm | Which person, system, data, or process can be harmed? |
| Budget | How many turns, attempts, accounts, tools, and dollars? |
| Success criterion | What observable event constitutes a violation and at what severity? |
| Defense adaptation | Can safeguards, moderators, or humans react during the test? |
| Stopping | When does the attacker stop, and are unsuccessful attempts retained? |

### 11.2 Safety outcome model

Safety reporting separates policy correctness, harmful capability, attack success, severity, and normal-task utility. A model that refuses every prompt may have low attack success but unacceptable overrefusal. A model that answers benign tasks well may still create rare catastrophic risk. These axes are never averaged into a single “safety score.”

```text
risk = sum_h P(harm event h under declared exposure) * severity(h)
```

When natural exposure probabilities are unknown, the report uses conditional attack-success rates and stress-test severity rather than inventing population risk. Severity scales require domain justification and uncertainty. Near-zero observed violation rates use exact or model-based upper bounds; zero observed events never proves zero risk.

### 11.3 Adaptive testing and multiplicity

Adaptive attackers learn from responses, so prompts within an attack campaign are dependent. The unit of analysis may be scenario or campaign rather than prompt. The protocol records the attacker model or human team, initialization, feedback, tool access, mutation/search algorithm, and total query budget. Static suites and adaptive red teaming are separate tracks.

Searching many attacks and reporting only the best success inflates apparent evidence. Conversely, testing many defenses and highlighting the safest inflates assurance. The analysis freezes primary attack families, controls multiplicity where confirmatory claims are made, and labels discovery attacks as exploratory until reproduced on a holdout.

### 11.4 Refusal and policy attribution

Transport status, policy action, and safety judgment are separate fields. `policy_block` is not universally assigned zero. On a benign capability task, an unjustified refusal is a task failure; on a prohibited harmful request, a safe refusal may be correct; on an ambiguous request, the rubric may reward clarification or escalation. The policy version and jurisdictional context are part of the system card.

### 11.5 Security and privacy evaluation

Security tracks include prompt injection, data exfiltration, tool authorization, confused-deputy behavior, insecure code/action generation, model extraction where applicable, dependency compromise, and audit-log integrity. Privacy tracks distinguish memorization, inference, logging, retention, cross-tenant exposure, and human-review access. Tests use synthetic or consented data wherever possible and never introduce real credentials into prompts.

### 11.6 Residual risk and decision gates

Every safety report ends with tested controls, untested threats, observed failures, uncertainty, residual risks, responsible owner, treatment plan, and monitoring triggers. A benchmark can support a risk decision but cannot declare universal safety. High-severity unresolved findings remain visible even when aggregate rates are low.

## 12. Global coverage and inclusion

An English-only benchmark cannot substantiate a global claim. The design gate requires at least eight languages across four language families and native-speaker review across at least eight locales. A serious deployment study samples the actual user distribution, includes low-resource languages, and publishes both weighted and equal-language views.

Translation is not equivalent to local validity. Tasks should be natively authored or culturally adapted; reviewers examine pragmatics, domain practice, safety norms, names, units, legal context, and dialect. Every language and locale reports item count, source, original/translated status, difficulty, reviewer qualifications, agreement, quality, safety, refusal, and worst-slice intervals.

Accessibility includes assistive-technology compatibility, plain-language alternatives, input/output modality access, disability-related bias, and human escalation. Governance includes affected communities, not only providers and benchmark authors.

### 12.1 Population-weighted and equal-group views

Production weighting answers how the system performs for the declared current user distribution. Equal-language or equal-locale weighting answers whether low-volume groups are hidden by aggregate traffic. Both are necessary and neither is inherently “the global score.” Weight provenance, effective date, sampling error, privacy transformation, and excluded populations are published.

### 12.2 Native construction, adaptation, and translation

Tasks are labeled as natively authored, culturally adapted, professionally translated, machine translated with review, or untranslated. Back translation can detect some errors but does not establish functional equivalence. Review covers intent, difficulty, answer form, politeness, dialect, legal/social context, names, units, and grader behavior. Changes made during adaptation are versioned as item content, not hidden preprocessing.

### 12.3 Measurement invariance and slice uncertainty

Aggregate gaps can reflect true capability, task composition, grader bias, or translation effects. The analysis therefore examines item difficulty and discrimination across groups, system-by-language interactions, differential item functioning, and response-process samples. Small intersectional slices use partial pooling or wide intervals rather than unstable league tables. The report publishes counts and uncertainty for every displayed slice.

### 12.4 Fairness is construct-specific

No universal fairness metric applies to all benchmark tasks. Depending on the use, relevant outcomes can include quality parity, error severity, refusal, calibration, exposure, accessibility, escalation, or downstream burden. Protected or sensitive attributes are collected only with a lawful, ethical, privacy-preserving basis. The protocol states the affected population, potential harm, comparator, metric, threshold, and remediation owner.

| Evaluation question | Possible metric | Required qualification |
| --- | --- | --- |
| Does answer quality differ by language? | Weighted paired effect and worst-slice interval | Comparable construct and adequate per-language sample |
| Are refusals disparate? | Refusal-rate difference/ratio | Separate appropriate from inappropriate refusal |
| Is confidence reliable across groups? | Group calibration and selective risk | Same probability semantics and adequate outcomes |
| Does escalation burden differ? | Escalation rate, delay, and resolution quality | Include human process and access constraints |

### 12.5 Accessibility protocol

Accessibility evaluation uses representative assistive technologies and users where appropriate. It covers keyboard/screen-reader compatibility, alternative text, captioning, speech interaction, cognitive load, plain-language modes, time limits, and recovery from misunderstood input. Automated accessibility checks are useful but do not replace task-based evaluation with affected users.

## 13. Reproducibility and evidence architecture

### 13.1 Artifact graph

Every published value must trace through this graph:

```text
protocol -> eligible pool -> frozen sample -> schedule -> request attempts
         -> final answer -> judgment -> observation -> scorecard -> claim
```

Each node has a stable identifier, schema version, content hash, and provenance. Referential-integrity checks reject missing planned items, mismatched answer IDs, orphaned judgments, or unlinked calls.

The evidence graph also records transformations. A published table cell points to a scorecard field; the scorecard points to scored observations; each observation points to a judgment and answer; the answer points to every attempt; and attempts point to the frozen schedule, effective system card, prompt, and environment. A later correction creates new nodes linked by `supersedes`; it never mutates history silently. FAIR data principles and explicit provenance vocabularies provide useful foundations for portable evidence [34, 35].

### 13.2 Required artifacts

- protocol and preregistration;
- benchmark and system cards;
- eligible-pool and frozen-plan manifests;
- code, harness, SDK, lockfile/container, SBOM, hardware, and region manifests;
- raw attempts, answers, judgments, usage, cost, timing, and errors;
- grader prompts, versions, validation, and adjudication;
- statistical code, seeds, assumptions, diagnostics, and sensitivity results;
- machine-readable scorecards and human-readable report;
- signed append-only manifest and correction log; and
- independent review and replication reports.

NIST AI 800-2 recommends full logs with exact system versions, code or commit hashes, purpose metadata, grouped comparable runs, item-level results, cost alongside performance, transcripts where appropriate, and published evaluation code [3]. KGBP makes these expectations enforceable publication gates.

### 13.3 Evidence-bundle layout

A portable bundle separates public, controlled-access, and secret material.

```text
bundle/
  protocol/          versioned specification, preregistration, deviations
  systems/           system cards and effective settings
  data/              pool/sample manifests, licenses, cluster and weight metadata
  execution/         schedule, environment, attempts, answers, errors
  grading/           graders, judgments, validation, adjudication
  analysis/          code, lockfile, seeds, diagnostics, scorecards
  reports/           human and machine-readable results
  assurance/         hashes, signatures, reviews, replications, corrections
  access-policy/     redaction, retention, auditor-access procedure
```

The root manifest contains schema versions, media types, byte lengths, content hashes, sensitivity classifications, license or access basis, and provenance links. Signatures cover the manifest rather than only the PDF. Verification reconstructs hashes, validates schemas and references, rebuilds reports offline, and fails closed on unexpected or missing files.

### 13.4 Repeatability, reproducibility, and replicability

These assurance goals are distinct:

| Goal | Who/where | Required demonstration |
| --- | --- | --- |
| Computational repeatability | Same artifacts and analysis | Offline rebuild produces equivalent scorecards and tables |
| Execution repeatability | Same operator and setup | New governed generations fall within declared variability |
| Reproducibility | Independent operator with supplied artifacts | Independent rebuild and interpretation of the same evidence |
| Replicability | Independent organization and new execution | Compatible claim under a declared replication design |

Exact output text is not expected from stochastic or mutable endpoints. Replication criteria use effect tolerances, uncertainty, heterogeneity, and protocol compatibility rather than byte equality.

### 13.5 Privacy and security

Public transparency is constrained by privacy, intellectual property, safety, and contamination. A privacy-reviewed public bundle is preferred. Where raw disclosure is unsafe, controlled auditor access supplies the evidence, while the public release provides construction methods, aggregate data, hashes, schema, redaction procedure, and independent attestation. Secrets and personal data are excluded from prompts and logs. Deterministic redaction occurs before the bundle is signed.

The access model defines data controller/processor roles where applicable, lawful basis or consent, purpose limitation, retention, geographic transfer, reviewer access, deletion, breach response, and whether provider terms permit submitted data to be retained or used for training. Hashes of sensitive low-entropy values can disclose them through guessing; the protocol uses keyed commitments or access-controlled manifests where necessary.

### 13.6 Supply-chain assurance

The software bill of materials identifies direct and transitive dependencies, licenses, provenance, and known vulnerabilities. Container or environment digests, model/download hashes, grader dependencies, and external services are recorded. Signed release provenance can show which source revision produced a bundle, but signature verification does not establish that the methodology is correct; it establishes origin and integrity within the signature trust model.

## 14. Governance model

### 14.1 Roles and separation of duties

The benchmark owner maintains the protocol and infrastructure. Dataset stewards control item provenance and access. Evaluation operators execute frozen schedules. Statistical reviewers approve estimands and analysis. Safety and domain reviewers validate relevant tracks. An independent review board adjudicates appeals and publication readiness. Replicating organizations execute the protocol without result-contingent incentives.

No person should both make an outcome-changing post-run decision and know the affected system identities unless the decision is mechanical and preregistered.

### 14.2 Change control

Semantic versioning distinguishes breaking changes from corrections. A breaking change to tasks, graders, system boundary, resource budget, or primary estimand creates a new comparison series and requires re-evaluation. Corrections preserve the previous result, explain the cause, show impact, and link the replacement.

### 14.3 Appeals

Providers and researchers can challenge identity, availability, broken items, scoring, policy treatment, or artifacts within a published window. Challenges, evidence, conflicts, adjudication, and effect on results are recorded. Appeals cannot privately negotiate a favorable rerun.

### 14.4 Independence and replication

External-review candidacy requires at least three independent reviewers and two independent replicating organizations. Funding, API credits, vendor assistance, and conflicts are public, and compensation is never contingent on outcomes. Independent results need not be identical; differences are investigated as evidence about endpoint drift, environment, or protocol portability. The International Network for Advanced AI Measurement, Evaluation, and Science - whose members include public bodies from ten countries and the European Union - has separately published international consensus areas and open questions for automated evaluation practice [19]. KGBP treats that type of multilateral process as the path toward international legitimacy, not as an endorsement of this protocol.

The minimum three reviewers cover statistical validity, system/domain validity, and evidence/reproducibility; safety or human-subject expertise is additionally required when relevant. “Independent” means the reviewer did not design or operate the evaluated systems or study, has no result-contingent compensation, discloses material funding and relationships, and can publish unresolved findings. Counting three reviewers from one controlled organization does not automatically provide three independent perspectives.

### 14.5 Decision rights and separation of duties

| Decision | Proposer | Approver | Evidence made public |
| --- | --- | --- | --- |
| Protocol or metric change | Technical working group | Multistakeholder governance body | RFC, alternatives, vote/consensus record, version impact |
| Item exclusion after run | Dataset steward | Blind adjudication panel | Challenge, blinded evidence, decision, score impact |
| Result invalidation | Evaluation owner or reviewer | Independent review board | Cause, affected versions, replacement, retained history |
| Conflict waiver | Affected participant | Unconflicted governance members | Conflict, mitigation, duration, residual risk |
| Release approval | Evaluation operator | Authorized release committee | Gate checklist, dissent, signatures, unresolved limitations |

No organization evaluates its own independence. When the protocol owner also operates a benchmark or provides evaluated systems, the conflict is explicit and external reviewers receive sufficient evidence to challenge favorable assumptions.

### 14.6 Replication compatibility and synthesis

A replication plan freezes which elements must match and which are intentionally varied. Exact checkpoint studies may require the same artifacts; endpoint-as-served studies may intentionally test a later window or region. Replications report protocol compatibility, deviations, effect differences, interval overlap, and heterogeneity rather than a binary “replicated/not replicated” badge.

Where studies are sufficiently compatible, effects may be synthesized with a preregistered fixed- or random-effects meta-analysis. Endpoint drift, language composition, and implementation differences are potential moderators. A disagreement can reveal a boundary condition and is not suppressed to protect a leaderboard.

### 14.7 Toward international adoption

International adoption requires transparent, consensus-oriented governance with participation from multiple regions, affected communities, researchers, deployers, providers, accessibility experts, civil society, and measurement specialists. The project can contribute a public proposal and reference implementation; it cannot award itself global acceptance. Formal standardization or accreditation follows the rules and authority of the relevant organizations.

## 15. Standards and guidance crosswalk

| Source | Relevant theme | KGBP mechanism |
| --- | --- | --- |
| NIST AI RMF 1.0 | Govern, Map, Measure, Manage; trustworthy lifecycle | Claim, risk, measurement, governance, monitoring scorecards |
| NIST AI 600-1 | Generative-AI risk profile | Trustworthiness tracks, incident tests, risk register linkage |
| NIST AI 800-2 IPD | Objectives, protocol, execution, statistics, disclosure, qualified claims | Claim classes, frozen protocol, logs, uncertainty, evidence bundle |
| NIST AI 800-3 | Statistical modeling for benchmark evaluation | Hierarchical estimation and optional GLMM |
| ISO/IEC 25059 | AI-system quality model | Multi-dimensional quality and context-specific measures |
| ISO/IEC 23894 | AI risk-management guidance | Threat models, risk ownership, treatment and residual risk |
| ISO/IEC 42001 | AI management system | Roles, controls, evidence, audit, corrective action, continual improvement |
| ISO/IEC 17025 | Competence and impartiality of testing/calibration laboratories | Evaluator competence, method validation, traceability, uncertainty, records, impartiality |
| OECD AI Principles | Fairness, transparency, robustness, accountability, cooperation | Global slices, disclosure, traceability, multistakeholder governance |
| EU AI Act | Accuracy, robustness, cybersecurity, lifecycle consistency | Declared metrics, robustness/security tracks, drift and incidents |
| MLPerf | Categories, system types, scenarios, divisions, governed submission | SUT taxonomy, open/closed divisions, load scenarios, checker |
| LiveBench | Refreshed items and objective grading | Rolling pool, actual item dates, task-specific graders |
| HELM | Broad coverage, multi-metric measurement, transparency | Track taxonomy, scorecards, explicit incompleteness, artifacts |

This crosswalk is conceptual, not a clause-level conformity statement. ISO standards are copyrighted and should be consulted through authorized copies for formal implementation. Regulatory applicability depends on jurisdiction, system role, and intended use; legal counsel should review high-risk deployments.

### 15.1 Standards status as of 8 August 2026

Standards and guidance are versioned dependencies. NIST AI 800-2 is cited as an Initial Public Draft, not final guidance. NIST AI 800-3 is a published NIST report. ISO/IEC 25059:2023 remains the cited published edition, while ISO lists it as being revised and a second edition has progressed through draft stages; the release therefore freezes the 2023 edition and monitors the replacement. ISO/IEC 17025:2017 was confirmed in 2023 and remains current at the stated status date [20].

The standards register records title, identifier, edition, publication or draft status, access date, scope used, and whether the source is normative or informative for this profile. A later standards revision does not silently change an existing benchmark series; maintainers publish an impact assessment and new profile version.

### 15.2 Measurement-laboratory perspective

ISO/IEC 17025 is not an AI benchmark standard, but its principles are relevant to trusted testing: competence, impartiality, consistent operation, method validation, measurement traceability, handling of test items, technical records, uncertainty, reporting, complaints, and nonconforming work [20]. A future independent assurance program should map evaluator procedures to these principles and engage competent accreditation experts before making any accreditation claim.

### 15.3 Clause-level crosswalk roadmap

The current table is thematic. A release suitable for formal assurance needs an authorized clause-level crosswalk containing:

- exact edition and clause identifier;
- applicability to protocol owner, evaluator, provider, or deployer;
- implementing control and artifact;
- evidence owner and verifier;
- deviations or exclusions; and
- review date and change impact.

Because standards have different scopes, the crosswalk must not imply that satisfying one protocol control establishes legal or management-system conformance.

## 16. Reference implementation

The Python reference implementation contains four protocol components.

1. `global_protocol.py` implements ten design dimensions, weighted checks, critical caps, geometric summary, non-compensatory readiness, and publication-evidence blockers.
2. `global_planning.py` constructs deterministic item-system-repeat schedules balanced across days and regions and validates completeness.
3. `advanced_statistics.py` implements Wilson intervals, hierarchical cluster bootstrap, paired hierarchical effects, and approximate power planning.
4. `global_scoring.py` validates observations, maps all non-success outcomes to zero in the conservative endpoint, emits track and slice scorecards, computes paired effects, and identifies Pareto-optimal systems.

Versioned JSON Schemas define the protocol configuration and scored observations. The command-line interface provides `audit`, `power`, `schedule`, and `score` operations. The existing LiveBench adapter supplies endpoint calls, task-specific official grading, call lineage, cost, usage, latency, retry, route, completeness, and artifact hashes.

These components do not yet automate every control described in this paper. In particular, a syntactically present evidence URI is not substantively verified; the general score command must be joined to a frozen schedule to guarantee that entirely absent cells remain in the denominator; and the planner does not by itself operate real multi-day, multi-region infrastructure. Release documentation distinguishes implemented, partially implemented, and procedural controls.

| Capability | Current reference status | Required assurance before strong use |
| --- | --- | --- |
| Profile declaration audit | Implemented for configured checks | Independent validation of check content and evidence |
| Deterministic schedule construction | Implemented planning primitive | Execution bridge, real region identity, clock/day enforcement |
| Hierarchical bootstrap | Implemented baseline | Estimand-specific resampling validation and diagnostics |
| General scorecards | Implemented for supplied observations | Required schedule join and complete-cell enforcement |
| LiveBench endpoint matrix | Implemented pilot path | Larger fresh multilingual repeated study |
| External evidence verification | Presence gates only | Signature, provenance, reviewer, and replication verification |
| Safety, human, agent, energy programs | Protocol requirements | Specialized harnesses and independent review |

### 16.1 Required verification pipeline

Before release, continuous integration performs unit tests, schema validation, static compilation, deterministic schedule replay, duplicate/missing cell checks, result lineage checks, hash verification, offline report reconstruction, and golden-report comparisons. A paid smoke test validates credentials and one item per track before a full campaign.

The release evidence states which checks actually ran, on which commit and environment, and preserves their output. A future-tense checklist is not execution evidence. Provider-paid tests are isolated from deterministic offline validation so that third parties can verify analysis without credentials.

### 16.2 Reference data-flow diagram

```text
protocol JSON + system cards + item manifest
                    |
                    v
             declaration audit
                    |
                    v
     frozen schedule and execution identity
                    |
                    v
 provider attempts -> answers -> task-specific graders
                    |                 |
                    +------ lineage --+
                              |
                              v
       schedule-complete scored observations
                              |
                              v
     scorecards + uncertainty + sensitivity
                              |
                              v
        signed evidence bundle and reports
```

### 16.3 Security boundary

Provider keys remain in local environment configuration and are never copied to reports. Raw prompts and outputs are treated as potentially sensitive. Agent evaluation uses isolated sandboxes. Publication operates on a separately generated, privacy-reviewed bundle.

### 16.4 Validation studies required for protocol maturity

Before presenting the reference profile as a stable measurement standard, maintainers should publish method-validation studies: simulated coverage of intervals and tests; robustness to cluster imbalance and missingness; inter-auditor agreement on profile controls; cross-language item invariance; grader error propagation; repeatability across operators; and independent replication of at least one complete campaign. Negative results and boundary conditions are part of the protocol evidence.

{{CAMPAIGN_RESULTS}}

## 18. Adoption roadmap

Adoption should be progressive. A team can obtain value from a controlled pilot without claiming full profile conformance, while an assurance program requires independent evidence and governance.

| Adoption level | Intended user | Minimum deliverable | Permitted claim |
| --- | --- | --- | --- |
| L0 offline orientation | New evaluator | Toy fixture, schema validation, rebuilt golden report | The software was installed and understood |
| L1 endpoint smoke test | Developer | Frozen small plan, one endpoint, artifact integrity | The endpoint path functioned for the tested calls |
| L2 controlled pilot | Evaluation team | Multiple systems, declared estimand, failures, intervals, limitations | Descriptive comparison under the pilot setup |
| L3 decision study | Deployer | Powered production population, SLO/cost/safety gates, stakeholder review | Evidence for the declared deployment decision |
| L4 external-review candidate | Benchmark organization | Complete bundle, preregistration, three independent reviewers | Ready for external review under KGBP profile |
| L5 independently replicated | Neutral governance program | Two independent replications and resolved discrepancies | Independently replicated within the stated scope |

### Adoption deliverables

The release should provide a ten-minute no-cost quickstart, one-paid-call smoke guide, protocol checklist, system-card template, benchmark-card template, preregistration template, threat-model template, schema/data dictionary, provider-adapter guide, evidence-bundle guide, results-interpretation guide, governance and appeals policy, and a sanitized versioned ranking report. The technical white paper explains *why*; these handouts explain *how*.

### Phase 0: protocol stabilization

Publish LBP 1.0 with the KGBP 1.0 reference profile, schemas, reference code, tests, threat model, benchmark card template, governance charter, and public issue tracker. Solicit comments from providers, independent evaluators, statisticians, domain experts, civil society, accessibility experts, and representatives from multiple world regions. Label the first release a research proposal until validation studies and independent governance mature.

### Phase 1: pilot and variance study

Run 100 to 300 items across representative systems with five repeats to estimate item, generation, cluster, day, and region variance. Validate graders against humans. Use these estimates for power analysis; do not use pilot-selected weights to make confirmatory claims.

### Phase 2: private rolling holdout

Establish secure item authoring, review, deduplication, canaries, access control, rotation, and retirement. Separate dataset authors from evaluation operators. Publish construction and sampling methods and obtain independent contamination review.

### Phase 3: full multi-track campaign

Execute the preregistered closed and open divisions across 1,200 or more powered items, five repeats, multiple days, regions, languages, modalities, and load scenarios. Run safety and human-evaluation programs in parallel. Publish scorecards, artifacts, and qualified claims.

### Phase 4: external replication and governance transfer

Fund at least two independent replications, obtain at least three independent reviewers with complementary competence, resolve deviations, conduct public review, and place normative protocol control under a neutral multistakeholder body. Establish technical committees for statistics, datasets, safety, operations, and domain tracks.

### Phase 5: standards engagement and continuous operation

Maintain a clause-level standards crosswalk, participate in relevant ISO/IEC JTC 1/SC 42, NIST, MLCommons, OECD, and regional measurement discussions, and operate versioned benchmark rounds with transparent deprecation and corrections. Only an accredited process may make formal conformity claims.

## 19. Limitations and open research questions

No finite suite represents all uses, cultures, harms, or future tasks. Private holdouts resist contamination but reduce open inspection. Public artifacts improve reproducibility but may enter training data. Automated graders scale but can import bias. Human evaluation adds contextual judgment but is expensive and variable. Provider endpoints can change without versioned snapshots. Resource-equivalent comparisons may under-elicit some systems, while provider-optimized comparisons reduce control.

The ten-dimension audit measures whether required controls are declared, not whether every declaration is true or adequate. External evidence review is indispensable. Thresholds such as 300 items, three repeats, 180-day freshness, eight languages, and 1,000 operational requests are protocol floors chosen to prevent obviously weak studies; they are not universal scientific constants.

Open problems include adaptive benchmark contamination; evaluation awareness and strategic underperformance; reliable long-horizon agent environments; judge validation under rapid model change; multilingual cultural validity; causal attribution of serving differences; energy measurement for proprietary endpoints; inference under adaptive routing; and governance that is both technically competent and globally representative.

### 19.1 Known methodological limitations

| Limitation | Why it matters | Required research or sensitivity |
| --- | --- | --- |
| Construct underrepresentation | A finite suite omits important tasks and harms | Blueprint review, field criteria, consequential-validity study |
| Public benchmark exposure | Models can train on tasks or conventions | Rolling private strata, canaries, exposure-risk model |
| Mutable endpoints | The measured system can change during or after a run | Interleaving, returned identity, anchors, bridge studies |
| Stochastic generation | One output is not a stable system property | Multiple generations and variance decomposition |
| Crossed dependencies | Items, systems, graders, days, and regions interact | Crossed hierarchical models and diagnostic simulation |
| Judge measurement error | Automated evaluation can change system order | Human validation and error propagation |
| Sparse safety events | Zero observations can coexist with material risk | Upper bounds, adaptive attacks, severity and exposure modeling |
| Global representation | Translation and item counts do not ensure cultural validity | Native construction, invariance/DIF analysis, affected-community review |
| Proprietary telemetry | Cost, energy, reasoning, and retries may be incomplete | Bounds, attestations, controlled access, explicit unknowns |
| Strategic behavior | Systems may detect evaluation or optimize to public rules | Hidden holdouts, canaries, adversarial protocol audits |

### 19.2 Limitations of the declaration score

The ten-dimension score is intentionally a completeness aid. Its equal or configured weights, the >9 threshold, and critical caps have not been psychometrically validated as an interval-scale measure of protocol quality. A 10.0 configuration may contain vague, false, or unaudited declarations. The paper therefore prohibits using that number to compare benchmark organizations, advertise scientific superiority, or infer campaign validity.

A validation program should test whether trained auditors interpret checks consistently, whether control states predict independently assessed evidence quality, whether weights and thresholds are robust, and whether important failures escape the checklist. Until then, pass/fail control details and evidence states are more informative than the aggregate.

### 19.3 Limitations of the empirical catalog pilot

The included campaign used fifteen 2024-dated LiveBench items, one governed generation, English-language text, sequential endpoint execution blocks, and a single API access context. It did not implement the global sampling, repeated-generation, multi-region load, safety, human, multimodal, energy, or external-replication program described by the reference profile. Seven finalized endpoint records had zero observed answer availability. Zero operational goodput in that run is evidence about the endpoint path during the observed window, not proof of zero underlying model capability.

The 595-pair family produced no Holm-corrected rejection. The printed order is therefore descriptive indexing, not a resolved total order. Duplicate display names represent distinct catalog endpoints and require canonical IDs. Costs are partially lower-bounded where failed attempts lack telemetry. These qualifications remain adjacent to every public ranking.

### 19.4 Priority research agenda

1. Validate interval coverage and rank uncertainty under realistic system-item interactions, cluster imbalance, and missingness.
2. Develop simulation-based power tools for multi-track, multilingual, multi-system designs.
3. Establish measurement-invariance and DIF procedures suitable for generative responses.
4. Measure inter-auditor reliability and criterion validity of the conformance controls.
5. Build privacy-preserving contamination audits and rolling holdout governance.
6. Validate model-judge panels against qualified humans with error propagation.
7. Develop off-policy and experimental methods for adaptive routers with changing candidate sets.
8. Create reliable, resettable, long-horizon agent environments with side-effect verification.
9. Establish practical energy and carbon attestation for proprietary endpoints.
10. Test neutral international governance and replication procedures across regions and institutions.

## 20. Conclusion

LLM Benchmark Protocol replaces the question "Which model is number one?" with a more disciplined set of questions: What system was tested? For which population and decision? Under what elicitation and budget? On what frozen tasks? With what failures, uncertainty, cost, and risks? Can the evidence be reconstructed, challenged, and independently replicated?

The KGBP reference profile's central design choice is non-compensation. A result cannot become credible by averaging away a weak dimension. Statistical rigor, freshness, coverage, operational realism, trustworthiness, reproducibility, and governance must all clear the bar. The reference implementation makes selected requirements executable and exposes where procedural evidence is still required. International acceptance, if earned, will depend on open consensus, validated methods, independent evidence, competent evaluation, and governance beyond any single provider.

## Appendix A. Minimum protocol checklist

### A.1 Construct

- Declare claim class, target population, SUT boundary, primary endpoints, metrics, and decision thresholds.
- Make track scorecards and Pareto analysis primary.
- Include human and incumbent-production baselines where meaningful.

### A.2 Statistics

- Complete prospective power analysis.
- Use at least 300 items and three repeats, or justify a stronger powered design.
- Model item, generation, cluster, and temporal variation.
- Report paired effects, intervals, multiplicity control, and equivalence.
- Preserve failures and publish missing-data sensitivity bounds.

### A.3 Coverage and freshness

- Cover all claimed modalities and specialized system functions.
- Include at least twelve core tracks and production-weighted tasks.
- Include global language and locale coverage with native review.
- Enforce item age, private holdout, deduplication, contamination, canary, and broken-item controls.

### A.4 Operations

- Interleave systems across at least three days and three regions.
- Run offline, interactive, and server scenarios with multiple concurrency levels.
- Observe streaming latency, availability, retries, errors, cost, energy, and drift.
- Use at least 1,000 requests per system for operational-tail claims.

### A.5 Trustworthiness

- Define threat models and harm thresholds.
- Evaluate harmful content, jailbreaks, privacy, bias, factuality, cybersecurity, overrefusal, and deception.
- Add adaptive, multilingual, multimodal, incident, failover, and escalation testing.

### A.6 Evidence and governance

- Pin code, harness, environment, system snapshots, graders, datasets, and schedules.
- Publish or provide controlled access to raw artifacts with complete lineage.
- Sign manifests and retain corrections.
- Preregister, disclose conflicts and funding, provide appeals, and obtain at least three independent reviews and two independent replications.

## Appendix B. Observation contract

The minimum scored observation includes `system_id`, `item_id`, `cluster_id`, `repeat`, `track`, `status`, `score`, `language`, `locale`, `modality`, and `difficulty`. Operational extensions include schedule ID, day, region, attempt IDs, request ID, answer ID, judgment ID, timestamps, TTFT, first-answer-token time, TPOT, E2E latency, native usage fields, normalized output volume, billed cost, modeled cost, energy, route, tool calls, policy result, and error taxonomy.

Allowed statuses are `success`, `provider_failure`, `timeout`, `invalid`, `policy_block`, and `missing`. A success requires a normalized score. All non-success statuses score zero in the conservative primary result but remain distinguishable in diagnostics.

## Appendix C. Ranking and publication rules

1. Do not rank across incompatible system or modality divisions.
2. Rank the controlled division by a preregistered primary endpoint, normally score-weighted operational goodput.
3. Publish objective quality, availability, deadline/cost/cap conformance, cost, and latency separately.
4. Treat rank as unresolved when corrected paired inference does not separate systems.
5. Do not call unresolved systems tied unless an equivalence interval supports the claim.
6. Do not substitute later successful reruns for first governed trials.
7. Do not publish p95/p99 as stable service properties from a capability-sized sample.
8. Do not label a modeled price as billed cost or missing energy as zero.
9. Publish every exclusion, correction, and invalidation.
10. Use "external-review candidate" only after empirical evidence gates; never use "globally accepted" or "globally certified" without the corresponding independent consensus or authorized conformity-assessment process.

## Appendix D. Statistical analysis plan template

### D.1 Claim and estimand

- Decision and claim class:
- Finite-benchmark or generalized-population estimand:
- Target population and sampling frame:
- Primary systems and comparisons:
- Primary tracks and outcomes:
- Minimum practically important effects or noninferiority margins:
- Operational, cost, and risk constraints:

### D.2 Design

- Unit of sampling, assignment, observation, analysis, and replication:
- Item clusters and shared dependencies:
- Planned items and repeats by track and slice:
- Day, region, load, and elicitation blocks:
- Randomization seed and restricted-randomization rules:
- Broken-item, failure-attribution, and missing-cell rules:
- Stopping and rerun policy:

### D.3 Model and diagnostics

- Outcome distribution and link:
- Fixed effects, interactions, random effects, and covariance structure:
- Weighting and inclusion probabilities:
- Bootstrap or posterior algorithm:
- Multiplicity family and correction:
- Equivalence/noninferiority procedure:
- Convergence, residual, influence, calibration, and sensitivity diagnostics:
- Rank and Pareto uncertainty procedure:

### D.4 Missingness and sensitivity

The plan specifies which outcomes count as zero, which trigger item invalidation, and which remain unresolved. At minimum it produces conservative and optimistic bounds, attribution-stratified results, complete-telemetry sensitivity, and a schedule-completeness report.

### D.5 Reporting

Every table identifies the estimand, denominator, weight, uncertainty method, comparison family, system boundary, time window, and evidence state. Exploratory analyses are labeled and cannot replace the frozen primary analysis.

## Appendix E. System card minimum schema

| Group | Required fields |
| --- | --- |
| Identity | Stable system ID, display name, owner, provider, version/snapshot, returned identity, lifecycle state |
| Composition | Model/adaptation, serving layer, routing/agent policy, tools, retrieval, memory, safeguards, humans |
| Access | API/local/hybrid, endpoint, region, SDK/API version, authentication class |
| Modalities | Input/output modalities, formats, structured output, streaming |
| Resources | Context/output limits, reasoning mode, sampling settings, turns, tools, retries, deadlines, budgets |
| Operations | Rate limits, availability terms, load class, retry behavior, caching, logging |
| Economics | Currency, pricing source/date, discounts/credits, billed versus modeled status |
| Governance | License/terms, data retention/training policy, privacy/security constraints, documentation source |
| Evidence | Provider attestations, artifact hashes, identity confidence, effective dates, unresolved unknowns |

System cards are immutable within a comparison series. If a mutable provider alias is unavoidable, each run binds the alias to observation time and returned metadata, and the report uses “endpoint as served” language.

## Appendix F. Benchmark card minimum schema

The benchmark card contains:

1. intended uses, prohibited uses, claim classes, and decision thresholds;
2. target population, sampling frame, construction, provenance, licenses, and author demographics where appropriate;
3. tracks, strata, languages, locales, modalities, difficulty, context, and production weights;
4. item dependencies, graders, validation, saturation, contamination, and freshness;
5. known gaps, cultural limitations, accessibility, privacy, safety, and dual-use risks;
6. statistical estimands, power/precision, weighting, missingness, multiplicity, and uncertainty;
7. update, retirement, challenge, correction, and leakage-response process;
8. evidence-bundle identifiers, schemas, code, environment, and replication status; and
9. accountable owners, funding, conflicts, reviewers, governance version, and contact route.

## Appendix G. Conformance and evidence matrix

| Control ID | Requirement | Applicable? | State E0-E5 | Artifact/hash | Owner | Reviewer | Finding/waiver |
| --- | --- | --- | ---: | --- | --- | --- | --- |
| Example-CV01 | Claim and target population frozen | yes | E2 | preregistration digest | study lead | pending | none |
| Example-ST01 | Complete schedule joined before scoring | yes | E2 | validation digest | statistician | pending | none |
| Example-GO01 | Three independent reviewers | yes | E1 | review plan | governance lead | pending | not yet executed |

The public release includes this matrix even when evidence is incomplete. Empty cells are not hidden, and a URI without verified content remains E1 at most.

## Appendix H. Replication report template

### H.1 Independence and competence

The replicating organization discloses funding, API credits, provider assistance, relationships, relevant expertise, and which original artifacts it accessed.

### H.2 Compatibility

| Element | Original | Replication | Compatibility impact |
| --- | --- | --- | --- |
| Protocol/profile | Version and digest | Version and digest | Exact/bridge/incompatible |
| Systems | Snapshot or served window | Snapshot or served window | Identity/drift assessment |
| Items/sample | Manifest and weights | Manifest and weights | Same/fresh/translated population |
| Execution | Regions, days, load, settings | Replicated conditions | Operational comparability |
| Analysis | Estimand, model, seeds | Independent implementation | Computational agreement |

### H.3 Synthesis

The report compares effect estimates, intervals, variance components, failures, and evidence states. It investigates discrepancies before judging compatibility. A replication can support the method while finding endpoint drift, or reproduce point estimates while exposing a shared design flaw.

## Appendix I. Interpretation checklist for ranking users

Before acting on a row order, ask:

- Is the row a checkpoint, endpoint, router, agent, or application?
- Is the claim finite-benchmark, generalized capability, or production selection?
- Were items fresh, representative, and adequately powered for my use?
- Were multiple generations, days, and regions measured?
- Are failures and missing telemetry in the denominator?
- Are endpoint IDs and versions immutable or merely aliases?
- Does the corrected paired evidence separate the systems?
- Was practical equivalence tested with a justified margin?
- Are cost values invoices, modeled prices, or lower bounds?
- Are safety, fairness, and operational scorecards separate?
- Is raw or controlled evidence independently inspectable?
- Has any organization independently replicated the result?

If the answer to several questions is no, the ranking may still be a useful pilot index, but it is not a sufficient procurement, safety, or regulatory decision.

## Appendix J. Notation

| Symbol | Meaning |
| --- | --- |
| `s` | System under test |
| `i` | Benchmark item |
| `r` | Independent generation/repeat |
| `t` | Track or construct domain |
| `c(i)` | Cluster containing item `i` |
| `d`, `g` | Day and region |
| `Y_sirt` | Normalized task outcome |
| `S_sirt` | Valid-answer delivery indicator |
| `mu_B`, `mu_G` | Finite-benchmark and generalized-population estimands |
| `Delta_ab,t` | Paired effect of system A minus B in track `t` |
| `G_si` | Score-weighted operational goodput |
| `U_si` | Stakeholder-specific utility |
| `E0..E5` | Conformance evidence states |

## References

[1] National Institute of Standards and Technology. Artificial Intelligence Risk Management Framework (AI RMF 1.0), NIST AI 100-1, 2023. https://doi.org/10.6028/NIST.AI.100-1

[2] Autio, C. et al. Artificial Intelligence Risk Management Framework: Generative Artificial Intelligence Profile, NIST AI 600-1, 2024. https://doi.org/10.6028/NIST.AI.600-1

[3] Center for AI Standards and Innovation. Practices for Automated Benchmark Evaluations of Language Models, NIST AI 800-2 Initial Public Draft, January 2026. https://doi.org/10.6028/NIST.AI.800-2.ipd

[4] NIST. Expanding the AI Evaluation Toolbox with Statistical Models, NIST AI 800-3, 2026. https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.800-3.pdf

[5] ISO/IEC 25059:2023. Software engineering - Systems and software Quality Requirements and Evaluation (SQuaRE) - Quality model for AI systems. Published edition; ISO lifecycle listed “to be revised” as accessed 8 August 2026. https://www.iso.org/standard/80655.html

[6] ISO/IEC 23894:2023. Information technology - Artificial intelligence - Guidance on risk management. https://www.iso.org/standard/77304.html

[7] ISO/IEC 42001:2023. Information technology - Artificial intelligence - Management system. https://www.iso.org/standard/81230.html

[8] European Parliament and Council. Regulation (EU) 2024/1689 laying down harmonised rules on artificial intelligence, 2024. https://eur-lex.europa.eu/eli/reg/2024/1689/oj

[9] OECD. Recommendation of the Council on Artificial Intelligence, OECD/LEGAL/0449, amended 2024. https://legalinstruments.oecd.org/en/instruments/OECD-LEGAL-0449

[10] MLCommons. MLPerf Inference Benchmark and Submission Guide. https://docs.mlcommons.org/inference/submission/

[11] White, C. et al. LiveBench: A Challenging, Contamination-Limited LLM Benchmark. arXiv:2406.19314, 2024. https://arxiv.org/abs/2406.19314

[12] Liang, P. et al. Holistic Evaluation of Language Models. Transactions on Machine Learning Research, 2023. https://crfm.stanford.edu/helm/

[13] Miller, E. et al. Adding Error Bars to Evals: A Statistical Approach to Language Model Evaluations, 2024. https://www.anthropic.com/research/statistical-approach-to-model-evals

[14] OpenAI. A Shared Playbook for Trustworthy Third-Party Evaluations, 2026. https://openai.com/index/trustworthy-third-party-evaluations-foundations/

[15] Artificial Analysis. Language Model Benchmarking Methodology. https://artificialanalysis.ai/methodology/intelligence-benchmarking

[16] Google DeepMind. FACTS Grounding: A Benchmark for Evaluating Factuality, 2024. https://deepmind.google/blog/facts-grounding-a-new-benchmark-for-evaluating-the-factuality-of-large-language-models/

[17] Chiang, W.-L. et al. Chatbot Arena: An Open Platform for Evaluating LLMs by Human Preference, 2024. https://arxiv.org/abs/2403.04132

[18] Kazemi, M. et al. BIG-Bench Extra Hard, 2025. https://arxiv.org/abs/2502.19187

[19] National Institute of Standards and Technology. International Network for Advanced AI Measurement, Evaluation, and Science Publishes Consensus Areas on Practices for Automated Evaluations, 2026. https://www.nist.gov/news-events/news/2026/02/international-network-advanced-ai-measurement-evaluation-and-science

[20] ISO/IEC 17025:2017. General requirements for the competence of testing and calibration laboratories. Confirmed 2023. https://www.iso.org/standard/66912.html

[21] Kane, M. T. Validating the Interpretations and Uses of Test Scores. Journal of Educational Measurement, 50(1), 2013. https://doi.org/10.1111/jedm.12000

[22] American Educational Research Association, American Psychological Association, and National Council on Measurement in Education. Standards for Educational and Psychological Testing, 2014. https://www.testingstandards.net/

[23] Brennan, R. L. Generalizability Theory. Springer, 2001. https://doi.org/10.1007/978-1-4757-3456-0

[24] Gelman, A., Hill, J., and Vehtari, A. Regression and Other Stories. Cambridge University Press, 2020. https://doi.org/10.1017/9781139161879

[25] Efron, B. and Tibshirani, R. J. An Introduction to the Bootstrap. Chapman and Hall/CRC, 1993. https://doi.org/10.1201/9780429246593

[26] Westfall, P. H. and Young, S. S. Resampling-Based Multiple Testing. Wiley, 1993. https://doi.org/10.1002/9781118042786

[27] Schuirmann, D. J. A Comparison of the Two One-Sided Tests Procedure and the Power Approach for Assessing the Equivalence of Average Bioavailability. Journal of Pharmacokinetics and Biopharmaceutics, 15, 1987. https://doi.org/10.1007/BF01068419

[28] Bradley, R. A. and Terry, M. E. Rank Analysis of Incomplete Block Designs: I. The Method of Paired Comparisons. Biometrika, 39(3/4), 1952. https://doi.org/10.2307/2334029

[29] Wilson, E. B. Probable Inference, the Law of Succession, and Statistical Inference. Journal of the American Statistical Association, 22(158), 1927. https://doi.org/10.1080/01621459.1927.10502953

[30] Kaplan, E. L. and Meier, P. Nonparametric Estimation from Incomplete Observations. Journal of the American Statistical Association, 53(282), 1958. https://doi.org/10.1080/01621459.1958.10501452

[31] Brier, G. W. Verification of Forecasts Expressed in Terms of Probability. Monthly Weather Review, 78(1), 1950. https://doi.org/10.1175/1520-0493(1950)078%3C0001:VOFEIT%3E2.0.CO;2

[32] Niculescu-Mizil, A. and Caruana, R. Predicting Good Probabilities with Supervised Learning. ICML, 2005. https://doi.org/10.1145/1102351.1102430

[33] Holland, P. W. and Wainer, H., editors. Differential Item Functioning. Lawrence Erlbaum Associates, 1993.

[34] Wilkinson, M. D. et al. The FAIR Guiding Principles for Scientific Data Management and Stewardship. Scientific Data 3, 160018, 2016. https://doi.org/10.1038/sdata.2016.18

[35] W3C. PROV-O: The PROV Ontology, W3C Recommendation, 2013. https://www.w3.org/TR/prov-o/

[36] Joint Committee for Guides in Metrology. Evaluation of Measurement Data - Guide to the Expression of Uncertainty in Measurement, JCGM 100:2008. https://www.bipm.org/en/committees/jc/jcgm/publications

[37] Joint Committee for Guides in Metrology. International Vocabulary of Metrology, JCGM 200:2012. https://www.bipm.org/en/committees/jc/jcgm/publications
