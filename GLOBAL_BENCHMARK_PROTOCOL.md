# LLM Benchmark Protocol 1.0

**Researcher:** Dr. Prashant Kumar Dey<br>
**Project steward:** Kendr

KGBP 1.0 is the reference profile implemented by LLM Benchmark Protocol. It is
a standards-informed research protocol for comparing language models, endpoints,
routers, agents, and AI applications without pretending those are the same kind
of system. It extends the existing LiveBench harness; it does not replace the
objective LiveBench graders or historical results.

The example in `config/global-protocol-v1.example.json` scores 10/10 in every
automated design dimension. That is a declaration-completeness audit of the
*planned protocol*, not empirical validation, conformity assessment, or proof
of global acceptance. A publication claim requires completed execution
evidence, competent independent review, and external replication under the
governance rules below.

## Normative principles

1. **The claim determines the experiment.** A controlled comparison, a
   capability-ceiling study, production selection, router evaluation, and
   safety assurance require different elicitation and evidence.
2. **The system under test is classified before ranking.** Base models,
   managed endpoints, routed systems, agents, and applications cannot be mixed
   silently in one model leaderboard.
3. **No average can rescue a weak dimension.** Every design dimension must be
   strictly above 9.0. Critical failures cap the affected dimension at 8.9.
4. **Scorecards are primary.** A single composite is secondary and may never
   hide a failed safety, reliability, coverage, or reproducibility gate.
5. **Failures stay in the planned denominator.** Missing answers, exhausted
   retries, invalid outputs, and missing required telemetry receive zero in the
   conservative operational endpoint.
6. **Capability and service quality are separate.** Task score, availability,
   latency, cost, energy, and operational goodput are reported independently.
7. **Uncertainty has two levels.** The analysis separates variation between
   items from variation between repeated generations and respects clusters such
   as shared passages, repositories, or scenarios.
8. **Freshness is a measured property.** A release name does not prove
   freshness. Actual item dates, private-holdout share, contamination checks,
   and pool hashes are required.
9. **Controlled fairness and maximum elicitation are separate divisions.** The
   closed division fixes budgets and harnesses. The open division permits
   provider-recommended or system-specific elicitation and labels it clearly.
10. **Acceptance is governed, not self-awarded.** Passing software checks is
    necessary but cannot substitute for external replication, multistakeholder
    review, public correction processes, or standards-body adoption.

## System taxonomy

Every evaluated system must have an immutable system card containing provider,
version/snapshot, access mode, deployment scope, input/output modalities,
declared capabilities, region, safeguards, tools, reasoning mode, context
limits, price source, and license.

| System type | Unit being measured | Required specialized evaluation |
| --- | --- | --- |
| Base model | Pretrained model/checkpoint | Completion likelihood, few/zero-shot behavior, contamination |
| Instruction model | Chat/instruction checkpoint | Instruction following, factuality, refusal, multi-turn |
| Reasoning model | Model with test-time reasoning | Repeated generations, reasoning budget curve, hidden-token accounting |
| Specialist model | Domain/code/math model | Domain-valid tasks and qualified expert baselines |
| Multimodal model | Model accepting or producing multiple modalities | Native modality tasks and modality-specific graders |
| Embedding model | Vector representation endpoint | Recall, nDCG, clustering, robustness, multilingual/domain slices |
| Reranker | Query-document scoring endpoint | nDCG, MRR, recall, hard negatives, calibration |
| Router | Dynamic selection layer | All candidate counterfactuals, regret, calibration, route stability |
| Ensemble | Multiple models combined | Marginal contribution, diversity, oracle gap, cost/reliability |
| Agent | Model plus loop/tools/memory | Outcome/state verification, side effects, trajectory budget, recovery |
| Application | User-facing socio-technical system | End-to-end outcomes, safeguards, escalation, accessibility, human burden |

Deployment scope and access are independent axes. For example, the same
underlying weights served through two providers are two endpoints for
operational comparisons but one model family for some capability analyses.

## Claim types and elicitation

| Claim | Required setup | Permitted conclusion |
| --- | --- | --- |
| Controlled comparison | Same task distribution, scoring, tools, and explicit resource budgets | System A did better under the declared shared setup |
| Capability under strong elicitation | Strongest credible harness/settings for each system | The system achieved at least this capability under that setup |
| Production selection | Production-weighted tasks, regions, load, costs, policies, and SLOs | Best observed choice for the declared deployment population |
| Router value | Full destination panel and per-item counterfactual outcomes | Incremental routing value, regret, stability, and cost versus baselines |
| Safety assurance | Explicit threat model and adaptive, independently reviewed attack budget | Evidence about the tested safeguards under that adversary—not universal safety |

The closed and open divisions must be reported separately. They answer
different questions and must never be blended into one rank.

## Required scorecards

The global protocol defines ten non-compensatory design dimensions:

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

Within a completed study, the primary result is a collection of track
scorecards and their Pareto frontier—not a universal intelligence number. At a
minimum, report reasoning, knowledge, factuality, instruction following,
coding, long context, multilingual ability, robustness, safety, efficiency,
reliability, and production tasks separately. Agentic tool use, multimodal
behavior, retrieval, preference, or domain tracks become mandatory when the
system or claim includes them.

Each track must report:

- planned, attempted, completed, valid, and scored item counts;
- mean/median as appropriate, paired effects, confidence intervals, and the
  predeclared practical-equivalence margin;
- results by difficulty, language/locale, modality, source, system type, and
  important production segment;
- worst-slice performance with sample sizes and uncertainty;
- failure, refusal, grader-invalid, and missing-telemetry rates;
- human and incumbent-production baselines when meaningful;
- saturation and broken-item diagnostics.

## Sampling and statistical design

The `300 items × 3 repeats` checks are floors, not universal recommendations.
Every primary endpoint requires prospective power analysis using pilot-derived
item, cluster, and generation variance. KGBP's example begins at 1,200 items
and five repeats because global, multilingual, multi-track claims need much
more evidence than a small endpoint smoke test.

Required analysis rules:

- freeze IDs, strata, graders, exclusions, endpoints, and weights before
  provider calls;
- sample by declared task, difficulty, language, modality, source, and
  production-frequency strata;
- average repeats within item before treating items as evidence;
- use cluster-aware/hierarchical intervals where questions share a passage,
  repository, scenario, source, author, or template;
- use paired comparisons on the same items;
- control family-wise error for the planned comparison family;
- report equivalence separately from failure to reject a difference;
- keep failures in the denominator and publish missing-data sensitivity bounds;
- replicate across days/regions and model temporal drift explicitly;
- validate any LLM grader blindly against qualified humans by task, language,
  model family, answer length, and score band.

`kendr_bench.advanced_statistics` supplies Wilson intervals, a hierarchical
cluster bootstrap, a paired hierarchical cluster bootstrap, and an approximate
power-planning calculation. A paper-grade analysis may additionally use a
preregistered generalized linear mixed model; its formula, link, random
effects, priors (if any), convergence checks, and sensitivity models must be
published.

## Freshness and contamination

Global-publication studies require:

- maximum item age of 180 days, with the actual age distribution reported;
- at least 20% private/access-controlled items for reused public benchmark
  domains;
- exact and semantic deduplication across sources and splits;
- lexical, semantic, answer-reproduction, and benchmark-awareness audits;
- canary items and a documented leakage incident threshold;
- blind broken-item review and predeclared exclusions;
- a rolling refresh, retirement, correction, and rerun policy;
- hashes for the eligible pool, frozen sample, prompts, graders, and outputs.

Private items improve contamination resistance but reduce public inspection.
The resolution is controlled auditor access plus publication of construction,
sampling, aggregate statistics, hashes, and an independently attested audit.

## Global and cultural coverage

English-only evaluation cannot support a global claim. The example protocol
requires at least eight languages across four language families and eight
locales, with native-speaker review; a serious release should cover the actual
user distribution and include low-resource languages. Translation alone is not
enough: tasks must be culturally and functionally valid in each locale.

For every language and locale, report task mix, difficulty, source,
translation/original status, reviewer qualifications, inter-rater agreement,
sample size, intervals, refusal/safety behavior, and worst-slice gaps.

## Operational benchmark design

Operational claims require randomized, interleaved calls over at least three
days and three regions. The global example uses seven days. It also separates
MLPerf-style scenarios:

- **Offline:** throughput under a fixed batch/work queue;
- **Interactive:** latency and responsiveness for one user/session;
- **Server:** throughput, queueing, goodput, and SLO compliance under arrival
  distributions and several concurrency levels.

Capture time to first token, time to first answer token, time per output token,
end-to-end duration, queue time where exposed, throughput, p50/p90/p95/p99,
deadline success, raw attempt availability, logical-request availability,
retries, timeout stage, rate limits, and error taxonomy. The automated floor is
1,000 requests per system before operational tail gates pass; the reference
global configuration uses 5,000 across multiple scenarios, days, and regions.

Cost reporting includes billed input, cached input, cache writes, reasoning,
output, tools, router overhead, retries, failed work, and service margin. Report
total cost, cost per task, and expected cost per successful outcome. A modeled
list-price estimate must never be labeled as an invoice.

Energy and carbon must state the measurement/attestation source, system
boundary, region, time, allocation method, and uncertainty. Missing supplier
data remains unknown rather than zero.

## Router and agent evaluation

For a router, every route it can select must be evaluated independently on the
same items and repeats. Report best single endpoint, uniform random, policy
baseline, and panel oracle; selected-route regret; achievable oracle gap; route
stability; confidence calibration; candidate availability; failover behavior;
and marginal quality/cost/latency versus the best single endpoint. A router
cannot receive a publication-ready result with partial counterfactual coverage.

For agents/applications, grade verified environment outcomes rather than only
the final text. Capture tool calls, state transitions, side effects, policy
violations, turns, tokens, time, cost, recovery, escalation, and final state.
Task environments must reset cleanly and be inspected for shortcut leakage.

## Safety and trustworthiness

Safety scorecards are separate from capability. The minimum domains are harmful
content, jailbreak robustness, privacy, bias/fairness, factuality,
cybersecurity, overrefusal, and deception. Evaluations require explicit threat
models, adaptive multi-turn attacks, multilingual/modality coverage,
independent red teams, privacy/legal review, calibration/abstention, human
escalation outcomes, and incident/failover exercises.

A low static jailbreak rate does not imply safety against an expert adaptive
attacker. Reports must state the attack harness, budget, tools, attempts,
expertise, model access, success criterion, and confidence interval.

## Reproducibility and artifact contract

Every publication candidate must provide, publicly or under controlled auditor
access:

- preregistration and protocol version;
- immutable system cards and provider-setting sources;
- source/harness commits and patches;
- lockfile/container, hardware, region, and SDK manifests;
- dataset and transformation provenance plus licenses;
- frozen sample plan and hashes;
- raw attempts, answers, judgments, failures, usage, cost, and timing;
- answer-to-attempt-to-judgment lineage;
- machine-readable schemas and validation output;
- offline one-command report reconstruction;
- signed append-only manifest, correction, appeal, and invalidation log;
- benchmark card, standards crosswalk, independent review, and replication
  reports.

Secrets and personal information are never placed in public artifacts. Privacy
redaction must be deterministic, documented, and performed before signing the
publication bundle.

## Governance and the meaning of “globally accepted”

KGBP draws on the measurement and independent-review principles of the NIST AI
Risk Management Framework, the AI-system quality/risk/governance concerns in
ISO/IEC 25059:2023, ISO/IEC 23894, and ISO/IEC 42001, laboratory competence and
impartiality concepts in ISO/IEC 17025:2017, and the
scenario/division/submission discipline demonstrated by MLPerf. Standards
statuses were checked on 2026-08-08; ISO/IEC 25059:2023 is marked for revision.
This repository does not claim certification, conformance, accreditation, or
endorsement from NIST, ISO, MLCommons, or any other standards organization.

For credible international adoption, governance must include an open protocol,
public RFC/change control, conflicts and funding disclosures, at least three
competent independent reviewers, at least two replicating organizations, an
appeal/correction system,
inclusive stakeholders from multiple world regions, ethics/accessibility/data
rights review, and a public change log. No vendor—including Kendr—may privately
change benchmark weights or exclusions after seeing results.

## Commands

Audit the example design without provider calls:

```powershell
.\.venv\Scripts\llm-benchmark-protocol.exe audit `
  config\global-protocol-v1.example.json `
  --output results\protocol\global-v1 `
  --strict
```

Approximate a paired-study item count for a two-point minimum effect under the
given planning assumptions:

```powershell
.\.venv\Scripts\llm-benchmark-protocol.exe power `
  --minimum-detectable-effect 0.02 `
  --standard-deviation 0.25 `
  --paired-correlation 0.5 `
  --power 0.9 `
  --alpha 0.05
```

Generate a complete randomized/interleaved schedule after preparing a JSONL
item plan with `item_id`, `cluster_id`, and `track`:

```powershell
.\.venv\Scripts\llm-benchmark-protocol.exe schedule `
  config\global-protocol-v1.example.json `
  path\to\frozen-items.jsonl `
  --output results\global-study\schedule.jsonl `
  --region asia-south1 `
  --region europe-west1 `
  --region us-east1
```

Create failure-aware hierarchical scorecards from observations conforming to
`config/global-observation-v1.schema.json`:

```powershell
.\.venv\Scripts\llm-benchmark-protocol.exe score `
  results\global-study\observations.jsonl `
  --schedule results\global-study\schedule.jsonl `
  --output results\global-study\scorecards
```

Build the evidence-qualified technical white paper after installing the
`docs` optional dependency and completing a catalog matrix:

```powershell
.\.venv\Scripts\python.exe scripts\build_kgbp_whitepaper.py `
  --source whitepaper\KGBP_1_0_WHITE_PAPER.md `
  --leaderboard results\matrix\MATRIX_ID\leaderboard.json `
  --manifest results\matrix\MATRIX_ID\manifest.json `
  --catalog results\matrix\MATRIX_ID\kendr_model_catalog.json `
  --audit results\protocol\global-v1\protocol-audit.json `
  --panel-metadata config\kendr-catalog-text-panel-20260807.json.metadata.json `
  --output output\pdf\LLM_Benchmark_Protocol_1_0_White_Paper.pdf `
  --resolved-markdown output\pdf\LLM_Benchmark_Protocol_1_0_White_Paper.resolved.md
```

Use `--require-publication-evidence` only for an executed configuration. The
example intentionally fails that external-evidence gate because it is a design
template, not a completed study.

## Reference framework links

- NIST AI Risk Management Framework and TEVV resources:
  <https://airc.nist.gov/>
- NIST automated benchmark evaluation work:
  <https://www.nist.gov/news-events/news/2026/01/towards-best-practices-automated-benchmark-evaluations>
- NIST statistical evaluation work:
  <https://www.nist.gov/news-events/news/2026/02/new-report-expanding-ai-evaluation-toolbox-statistical-models>
- ISO AI standards overview:
  <https://www.iso.org/artificial-intelligence/ai-standards>
- ISO/IEC 17025:2017 laboratory competence and impartiality:
  <https://www.iso.org/standard/66912.html>
- ISO/IEC 25059:2023 AI-system quality model and current revision status:
  <https://www.iso.org/standard/80655.html>
- European Union AI Act, Regulation (EU) 2024/1689:
  <https://eur-lex.europa.eu/eli/reg/2024/1689/oj>
- OECD AI Principles:
  <https://oecd.ai/en/ai-principles>
- MLPerf inference scenarios and submission discipline:
  <https://docs.mlcommons.org/inference/submission/>
- LiveBench methodology and implementation:
  <https://livebench.ai/>
- Anthropic statistical recommendations for model evaluations:
  <https://www.anthropic.com/research/statistical-approach-to-model-evals>
- OpenAI playbook for third-party evaluations:
  <https://openai.com/index/trustworthy-third-party-evaluations-foundations/>
- Artificial Analysis methodology:
  <https://artificialanalysis.ai/methodology/intelligence-benchmarking>
