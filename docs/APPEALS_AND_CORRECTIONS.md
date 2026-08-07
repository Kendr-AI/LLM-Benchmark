# Appeals and corrections policy

This process lets providers, researchers, users, dataset owners, and affected stakeholders challenge benchmark evidence or claims without granting any vendor privileged control over results.

## Scope

An appeal may concern:

- wrong system, endpoint, version, route, region, or provider identity;
- broken, ambiguous, leaked, duplicated, mistranslated, unlicensed, or unsafe items;
- incorrect prompt/settings, capability classification, or resource budget;
- missing/duplicated calls, hidden retries, outage, or erroneous failure attribution;
- grader defects, bias, invalid judgment, or adjudication conflict;
- scoring, denominator, weighting, interval, multiplicity, or rank computation;
- privacy, security, accessibility, licensing, or evidence-access concerns;
- misleading claim language or omitted limitations;
- checksum, provenance, reconstruction, or release-packaging defect.

Feature requests and disagreements with a correctly applied frozen rule are protocol-change proposals, not result corrections, unless the rule made the published claim materially invalid.

## Submission

Open a GitHub issue using the correction/appeal template when disclosure is safe. Security vulnerabilities, exposed secrets, personal data, or embargoed evidence must follow [`SECURITY.md`](../SECURITY.md) rather than a public issue.

Include:

1. campaign/run ID, protocol version, result row/claim, and artifact hash;
2. appeal category and requested remedy;
3. specific evidence, reproduction steps, and relevant terms/provenance;
4. whether disclosure creates security, privacy, or licensing risk;
5. submitter affiliation, role, and conflicts;
6. urgency and known downstream uses of the result.

Do not include API keys, raw personal data, confidential prompts, or restricted provider logs in a public issue. Maintainers may arrange controlled transfer.

## Status and service targets

| Status | Meaning | Target |
|---|---|---|
| Received | Submission recorded and identifier assigned | 5 business days |
| Triage | Scope, evidence class, conflicts, and urgency assessed | 10 business days |
| Under review | Qualified reviewers reproduce and assess impact | Normally 30 calendar days |
| Information needed | Specific evidence is requested; clock is paused | Time-bounded request |
| Decision proposed | Rationale and remedy circulated for conflict/quality check | 5 business days |
| Closed | Accepted, partially accepted, rejected, duplicate, or withdrawn | Decision published where safe |

Targets are goals, not guarantees. High-risk privacy/security issues may be handled privately first. Complex independent regrading or replication may require a published extension.

## Triage and interim action

The maintainer assigns a case ID, checks standing and evidence, and classifies potential impact:

- **Critical:** exposed secrets/personal data, fabricated evidence, wrong system identity, or defect likely to reverse a primary claim;
- **Major:** material score/rank/interval or construct impact;
- **Minor:** limited row, metadata, wording, or presentation impact;
- **No result impact:** documentation/protocol clarification.

Possible interim measures include a security embargo, prominent disputed-result notice, suspension of a claim, download removal for unsafe data, or no action pending review. Interim action is not a final finding.

## Review and conflicts

At least one reviewer with relevant technical/domain expertise assesses the appeal; material public-study corrections should include an independent reviewer who did not execute the affected analysis. Statistical issues receive statistical review, and privacy/security/license issues receive the appropriate specialist review.

Reviewers disclose provider, funding, competitive, authorship, dataset, and employment conflicts. A provider may supply technical evidence about its endpoint but does not decide its own appeal. Maintainers likewise recuse when their conflict could reasonably affect adjudication.

Review should attempt to reproduce the issue from the frozen bundle and preserve both:

- the original preregistered analysis;
- a corrected/sensitivity analysis showing impact.

## Decisions

Possible dispositions:

- **Accepted:** evidence establishes the defect and remedy.
- **Partially accepted:** some claims or artifacts require correction.
- **Rejected:** evidence does not establish a defect under the frozen protocol.
- **Inconclusive:** necessary evidence is unavailable; uncertainty is disclosed.
- **Duplicate/superseded:** linked to an existing case.
- **Withdrawn:** submitter withdraws; any independently confirmed risk may still be addressed.

The decision record states evidence reviewed, conflicts, findings, affected artifacts/claims, remedy, dissent, and effective date. Rejection never prevents a protocol-change proposal.

## Remedies

Depending on impact:

- metadata or explanatory erratum;
- corrected aggregate and report with a new version/hash;
- regrading under the frozen rubric;
- rerun when execution identity or corruption prevents valid reconstruction;
- item exclusion under the preregistered broken-item rule, with original and corrected analysis;
- rank/claim withdrawal;
- dataset retirement, privacy removal, or security advisory;
- protocol patch/minor/major change for future studies.

Never overwrite the old artifact or silently substitute a later clean trial. The correction links old and new artifacts and quantifies impact.

## Reconsideration

A submitter may request one reconsideration within 30 calendar days by identifying new evidence, a material factual error, or an unmanaged conflict. A different qualified reviewer should handle it where practical. Repeating the same argument without new evidence does not reopen the case.

## Public correction record

The release record should contain:

- case ID and timestamps;
- affected run/protocol/artifact hashes;
- public summary and classification;
- decision and reviewer roles/conflicts;
- old/new values or statement of no impact;
- links to superseding release and deviation entry;
- any evidence withheld and why.

Sensitive details may remain controlled, but the existence and result-impact of a correction should be public whenever lawful.

## Current pilot

Appeals to the 2026-08-07 Kendr pilot must account for its declared limitations: 15 questions, one generation, older English-oriented items, sequential endpoint blocks, and no Holm-significant pairwise differences. A transient provider outage can support an outage/identity correction investigation; it does not justify deleting failures from the already declared operational-goodput result.
