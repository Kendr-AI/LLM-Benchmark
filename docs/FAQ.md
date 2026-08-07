# Frequently asked questions

## Is LLM Benchmark Protocol globally accepted or certified?

No. Version 1.0 is an open beta research release. The repository references internationally relevant evaluation and governance practices, but it is not endorsed or certified by NIST, ISO, MLCommons, or another standards body. Broad legitimacy requires external review, replication, governance, and formal institutional processes that software cannot self-award.

## What does a design score above 9 mean?

It means the encoded plan cleared the automated checks for one design dimension. Every one of the ten dimensions must be strictly above 9.0. It does not prove the data were collected, the construct is valid, reviewers agree, or the study is publication-ready.

## Why not publish one universal intelligence score?

Different tracks measure different constructs, and users value quality, safety, latency, reliability, and cost differently. A single weighted average can hide catastrophic weakness and embeds contestable value judgments. The protocol makes track scorecards and Pareto trade-offs primary; any composite is secondary and fully disclosed.

## What exactly is a "system"?

The measured boundary can be model weights, an instruction/reasoning checkpoint, a managed endpoint, a router, an ensemble, an agent, or an application. The card must state which. The same weights through two providers are separate endpoints for service-quality claims.

## Can routers and fixed models share a leaderboard?

Not silently. A router dynamically selects endpoints and needs candidate counterfactuals, regret, stability, and calibration. Keep it in a routed-system division. A cross-division table may be shown descriptively if labels and limitations remain visible.

## Why do failures count as zero?

The primary operational endpoint asks what the system delivered over the planned workload. Dropping failed, timed-out, invalid, or missing requests makes unreliable services appear better. Conditional quality among successes is useful as a secondary diagnostic, not a replacement denominator.

## Is an appropriate safety refusal always zero?

No. It may receive positive credit on a safety track whose rubric defines refusal as the correct outcome. On an ordinary capability task, a refusal generally does not satisfy the task. The `score_treatment` field makes the distinction explicit.

## What is operational goodput?

It is task score delivered while satisfying declared operational constraints such as successful completion, deadline, output cap, and optionally budget. It combines outcome and service delivery for one declared scenario; it does not replace separate quality, availability, latency, and cost reporting.

## Does non-significance mean two endpoints are equal?

No. It means the experiment did not resolve a difference under the declared test and correction. Equivalence requires a predeclared practical margin and an equivalence analysis with enough power.

## Why correct for multiple comparisons?

With many endpoint pairs, some small p-values appear by chance. The comparison family must be frozen and controlled. The included pilot tested all 595 pairs as one Holm-corrected family; zero remained significant.

## Why are repeated generations necessary?

LLM output is stochastic, and some reasoning settings add substantial run-to-run variance. Repeats estimate that variation. Average repeats within item or model both item and generation levels; do not count repeats as independent questions.

## How large should my benchmark be?

There is no universal number. Use pilot-derived item, repeat, cluster, and failure variance; the target effect/equivalence margin; comparison family; slice requirements; and desired power. Automated floors are gates, not recommendations.

## Can I use an LLM as the grader?

Yes when objective grading is unsuitable, but validate it blindly against qualified humans across tasks, languages, model families, answer styles/lengths, and score bands. Record rubric/prompt hashes, agreement, bias checks, adjudication, and grader-family sensitivity.

## How does the protocol address contamination?

It requires item dates, content hashes, private-holdout share, exact/semantic deduplication, leakage audits, canaries, blind broken-item review, and refresh/retirement rules. None can prove that opaque training data exclude every item, so residual uncertainty remains.

## Does a recent benchmark release guarantee fresh questions?

No. Report actual item dates. In the current pilot, the LiveBench release identifier is 2026-06-25, while the selected questions date from June and November 2024.

## Can private holdout results be reproducible?

They can be auditable rather than fully public. Publish construction/sampling methods, hashes, aggregate statistics, and independent attestations; give qualified reviewers controlled access. Classify withheld artifacts and explain why.

## How should cost be compared?

State whether cost is invoiced, provider-reported, catalog-estimated, or list-price modeled; include failed/retried work, tools, routing, reasoning, cached tokens, conversion rates, and service margin. Unknown telemetry stays unknown. Compare cost only within compatible price bases and scopes.

## What should an adapter do with hidden retries?

Disable them when possible. Otherwise disclose incomplete attempt visibility. Record all visible retries separately, including failed latency, usage, and cost. Never relabel a provider error as an empty successful answer.

## Can I rerun a failed endpoint?

You may run a prespecified repeat or correction study. Do not silently replace the earliest captured provider trial with a later clean run. Preserve both and explain which estimand each supports.

## What is in the current 35-endpoint release?

A privacy-reviewed aggregate of one Kendr-served text campaign: 35 ranked text endpoint IDs, 15 questions across five task types, one generation per cell, two non-text entries marked N/A, and complete failure/availability reporting. See [Rankings](RANKINGS_2026-08-08.md).

## Why did seven endpoints receive zero in the pilot?

They returned no successful final answers in the captured endpoint-as-served run. Zero is correct for that operational run denominator, but it does not prove the underlying model has no task capability. Outages, capability mismatch, identity, and provider errors are legitimate subjects for an appeal or new controlled run.

## Are raw prompts and responses published?

Not in the current aggregate. Its privacy review declares they are excluded, along with provider request IDs and local paths. A fuller study may provide privacy- and license-reviewed public or controlled evidence under the [evidence bundle policy](EVIDENCE_BUNDLE.md).

## How do I test the software without spending money?

Run the checked-in toy schedule and observations with the protocol `score` command. Follow the [quickstart](QUICKSTART.md). The protocol audit, power, schedule, and scoring commands do not call a provider.

## How do I add a provider?

Implement the provider result contract, preserve identity/telemetry/failures, test with a fake client, and explicitly register the integration. A case-runner adapter and a LiveBench instrumentation adapter are different scopes. See [Provider adapter guide](PROVIDER_ADAPTER_GUIDE.md).

## What files should I prepare before a real run?

At minimum: preregistration, specialized protocol config, system cards, benchmark card, threat model, frozen item descriptors, statistical plan, grader specification, deviation log, and execution budget/approval. Templates are under [`templates/`](../templates/).

## How are errors corrected after release?

Open a correction/appeal with the run ID, artifact hash, evidence, and requested remedy. Accepted corrections create new versioned artifacts and preserve the old record. Security/privacy issues use the private security channel. See [Appeals and corrections](APPEALS_AND_CORRECTIONS.md).

## When can I claim a global benchmark result?

Only when the claim is supported by actual global target-population coverage, current and contamination-resistant items, adequate power, repeated/multi-region operations, relevant safety and cultural review, transparent governance, at least three independent reviewers, and at least two external replications. Even then, call it evidence under the named protocol and scope; do not imply formal standards certification without the certifying body's decision.
