# Project threat model

This threat model covers the benchmark design, execution harness, evidence pipeline, public result release, and governance process. It complements study-specific threat models created from [`templates/threat-model.md`](../templates/threat-model.md). It does not establish that evaluated models are safe.

## Security and integrity objectives

Protect:

- confidentiality of credentials, private holdouts, personal data, and restricted outputs;
- integrity of protocol, item selection, system identity, requests, attempts, judgments, analysis, and releases;
- availability of execution and correction processes without uncontrolled spend;
- auditability of every claim and correction;
- independence of review and resistance to benchmark gaming.

## Trust boundaries

1. Maintainer workstation and source repository
2. CI/build and release environment
3. Dataset/private-holdout storage
4. Operator execution environment
5. Provider SDK, network, gateway, and model service
6. Tool/agent sandboxes and external content
7. Grader/human-review environment
8. Controlled evidence store
9. Public release and downstream mirrors
10. Governance, issue, appeal, and signing channels

Data crossing any boundary must be authenticated where possible, minimized, classified, and recorded.

## Threat actors

- opportunistic attackers seeking credentials or compute;
- malicious benchmark participants seeking favorable scores;
- compromised provider, SDK, dependency, runner, grader, or CI account;
- insiders with dataset, execution, analysis, or release access;
- prompt/content authors attempting injection or data exfiltration;
- well-intentioned operators making undocumented changes;
- downstream publishers omitting limitations or altering artifacts;
- adaptive evaluated systems detecting and gaming benchmark conditions.

## Threats and controls

| Threat | Failure mode | Primary controls | Residual risk |
|---|---|---|---|
| Credential leakage | Keys enter logs, exceptions, bundles, or git | `.env` ignored, least privilege, redaction, secret scan, rotation, no headers in evidence | Provider SDK/error strings may expose novel formats |
| Supply-chain compromise | Malicious dependency or source revision alters calls/scores | Pinned versions/revisions, lock/container/SBOM, review, isolated rebuild, provenance | Upstream service remains outside local control |
| Item poisoning | Crafted or mislabeled items bias a system/party | Provenance, dedup, blind review, immutable hashes, stakeholder review | Subtle construct bias may survive review |
| Benchmark leakage | Systems trained on or retrieve answers/items | Private holdouts, canaries, contamination audits, refresh/retire policy | No audit can prove absence from opaque training data |
| Prompt injection | Item/tool/web content manipulates harness, leaks data, or bypasses rubric | Treat content as untrusted, tool allowlists, sandbox, egress controls, no secrets in context | Open-world agent studies retain exposure |
| System identity spoofing | Requested label differs from actual model/route | Capture requested/actual IDs, route metadata, provider attestations, timestamped card | Some services do not expose immutable snapshots |
| Hidden retry/caching | Reliability/latency/cost understated | Disable or observe retries, unique attempt lineage, cache controls/disclosure | Provider-internal behavior may remain opaque |
| Evidence tampering | Rows removed/changed after results | Freeze-before-call, append-only hashes, signed manifest, offline reconstruction, corrections | Unsigned or weakly governed bundles lack authenticity |
| Grader manipulation | Style/family/position bias or injected answer affects judge | Objective graders, blinded randomized order, multi-family panels, human validation, rubric hash | Automated judges retain distributional bias |
| Selective reporting | Favorable tasks/runs/slices published | Preregistration, full denominator/family, deviations, public aggregate, independent review | Private studies can suppress entire failed studies |
| Denial/cost exhaustion | Run floods APIs or exceeds budget | Explicit paid approval, per-call/run caps, rate limits, circuit breakers, monitoring | Distributed/provider-side cost spikes possible |
| Privacy exposure | Prompts/responses identify people or reveal restricted data | Data minimization, controlled evidence, deterministic redaction, aggregation, privacy review | Re-identification from rare slices remains possible |
| Unsafe model output | Harmful content reaches operators/artifacts | Threat-specific handling, access control, reviewer support, redaction, incident path | Review itself can create exposure |
| Agent side effects | Tool-enabled system modifies external state | Disposable sandbox, least privilege, deny-by-default network/tools, reset/verify state | Some real-world tasks cannot be perfectly isolated |
| Governance capture | Sponsor/provider controls rules or corrections | Conflict/funding disclosure, public change control, independent review/replication, appeals | Independence depends on actual stakeholder diversity |
| Misleading downstream use | Rank detached from scope/uncertainty | Protocol/run IDs, checksums, required caveats, license, correction notices | Screenshots and copied tables can omit context |

## Execution controls

- Use dedicated, least-privilege provider credentials with spend/rate limits.
- Keep production/customer credentials and data out of benchmark environments.
- Disable unnecessary network access and tools; sandbox code/agent workloads.
- Validate item and schedule hashes before starting.
- Require explicit confirmation before paid inference.
- Capture every visible attempt and sanitize errors.
- Use monotonic timing and UTC event timestamps.
- Monitor spend, rate limits, anomalous output, data exfiltration, and repeated failures.
- Stop under preregistered safety/spend/integrity criteria and preserve partial evidence.
- Never replay or replace captured trials merely to improve completeness.

## Prompt-injection model

All item text, retrieved documents, web results, model output, and tool output are untrusted data. They may instruct the harness to reveal secrets, alter grading, call tools, or ignore the task.

Controls:

- separate control instructions from untrusted content;
- never place credentials or hidden answer keys in a model-visible context unless the task strictly requires and contains them;
- use tool schemas and allowlists rather than free-form command execution;
- isolate grader prompts from candidate instructions and strip active content where valid;
- validate structured outputs and cap size/time/tool calls;
- record injection success as a security outcome, not merely an invalid answer.

## Evidence-release controls

Public exports must exclude secrets, provider request IDs, absolute paths, private answers, and unreviewed personal/restricted content. Checksums detect accidental drift; signatures establish publisher authenticity only when keys and verification are governed correctly.

Controlled-access logs should record requester, purpose, authorization, artifacts, time, and deletion/retention obligation. Hashes permit public aggregate linkage without exposing private contents.

## Incident response

For credential, privacy, or active security exposure:

1. stop affected execution/release access without destroying evidence;
2. rotate/revoke credentials and contain external effects;
3. record timestamps, affected artifacts/systems, and actions;
4. notify responsible security/privacy owners and providers where required;
5. assess whether results are invalid or merely interrupted;
6. issue a security advisory/correction under [`SECURITY.md`](../SECURITY.md) and [appeals policy](APPEALS_AND_CORRECTIONS.md);
7. preserve a redacted incident record and update controls.

Do not open a public issue containing an exploitable secret or private data.

## Current pilot exposure

The checked-in pilot release is aggregate-only. Its JSON privacy review declares no raw prompts, raw responses, provider request IDs, or local paths. The public checksums are not signatures, and the aggregate is not a complete auditor bundle. Provider availability failures and uncertain failed-attempt cost remain visible rather than being sanitized out of performance metrics.

## Residual risks and review cadence

The largest unavoidable risks are opaque provider internals, unknown training contamination, changing services, grader validity outside reviewed slices, and social/governance capture. Review this model for every major protocol change, new adapter, tool-enabled/agent track, private dataset, public evidence class, or security incident, and at least once per major release.
