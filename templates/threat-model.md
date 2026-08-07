# Study threat model: [study/protocol ID]

> Version/status: [draft / frozen / amended]<br>
> Owner/reviewers: [names and roles]<br>
> Freeze timestamp/hash: [UTC / SHA-256]<br>
> Related system cards and preregistration: [URIs/hashes]

## 1. Scope and safety claim

- Systems, environments, tools, data, people, and releases in scope:
- Explicitly out of scope:
- Safety/security claim being evaluated:
- Time horizon and deployment context:
- Success/failure criterion:

## 2. Assets

List credentials, budgets, private items/answers, personal/sensitive data, provider/customer data, model/system identity, tools/environments, judgments, raw evidence, signing keys, releases, reviewer independence, and operator wellbeing.

## 3. Trust boundaries and data flow

Diagram data/control flow across operator, item store, runner, provider/router/model, tools/network, grader/human reviewer, evidence store, CI/release, and public consumers. For each boundary, record authentication, encryption, logging, retention, and owner.

## 4. Threat actors and capabilities

| Actor | Motivation | Access/knowledge | Tools/budget | In/out of model |
|---|---|---|---|---|
| | | | | |

Include malicious participants/providers, compromised dependencies/accounts, insiders, prompt/content attackers, adaptive evaluated systems, and accidental operator error.

## 5. Attack surface

- Dataset acquisition/transformation/sampling:
- Prompt templates and hidden context:
- Provider SDK/network/API:
- Router and candidate endpoints:
- Agent tools, filesystem, browser, code execution, and egress:
- Grader prompts/models/humans:
- Analysis notebooks/scripts and dependencies:
- Evidence storage, hashing, signing, CI, release, and mirrors:
- Appeals/governance channels:

## 6. Abuse cases and controls

| ID | Threat/abuse case | Preconditions | Impact | Likelihood | Controls | Detection | Residual risk | Owner |
|---|---|---|---|---|---|---|---|---|
| T-001 | | | | | | | | |

At minimum assess credential leakage, data exfiltration, prompt injection, unsafe output, agent side effects, benchmark leakage/gaming, item poisoning, system identity spoofing, hidden retry/cache behavior, grader manipulation, selective reporting, evidence tampering, denial/cost exhaustion, privacy/re-identification, supply chain, and governance capture.

## 7. Adaptive safety evaluation

- Harm domains and severity taxonomy:
- Attacker expertise, access, tools, attempts, turns, and time budget:
- Languages/modalities and context:
- Static and adaptive attacks:
- Success criterion and grader/human adjudication:
- Independent red-team role and conflicts:
- Overrefusal, abstention, escalation, and safe-completion outcomes:
- Confidence intervals and stopping rules:

State clearly what adversaries the study does not represent.

## 8. Execution safeguards

- Least-privilege credentials and spend/rate limits:
- Sandbox/reset/snapshot and side-effect verification:
- Tool/network allowlists and egress filtering:
- Secret/personal-data exclusion from model context:
- Time/token/turn/tool/cost caps and circuit breakers:
- Monitoring and on-call responsibilities:
- Operator harmful-content exposure/support:
- Provider retention/training settings:

## 9. Evidence and release safeguards

- Artifact classifications and access controls:
- Deterministic redaction and privacy review:
- Provenance/license review:
- Hash/signature/key custody:
- Reconstruction and tamper detection:
- Minimum slice/aggregation for re-identification control:
- Withholding reasons and auditor access:
- Downstream limitation/correction notices:

## 10. Incident response

Define severity, stop/containment authority, credential rotation, evidence preservation, provider/legal/privacy notification, public/security disclosure, result invalidation, correction, and post-incident review. Link the private security channel.

## 11. Residual risk and acceptance

List unresolved risks, why further reduction is infeasible, affected claims, compensating controls, risk owner, expiry/review date, and explicit accept/reject decision. Passing a benchmark does not imply acceptance of untested threats.

## 12. Change history

| Version/date | Threat/control change | Impact on frozen study | Approved by |
|---|---|---|---|
| | | | |
