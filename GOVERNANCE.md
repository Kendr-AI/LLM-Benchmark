# Governance

LLM Benchmark Protocol is maintained as an open technical project. This file
describes repository governance; it does not create an accreditation body or
authorize global certification claims.

## Decision principles

1. Measurement claims come before leaderboard presentation.
2. Protocol rules are frozen before results are observed.
3. Failed and missing planned observations remain in the denominator.
4. Incompatible systems and modalities are reported in separate divisions.
5. Breaking changes create a new protocol or comparison series.
6. Corrections preserve the previous record and explain the impact.
7. Global legitimacy requires governance beyond a single provider.

## Roles

- Maintainers steward code, schemas, documentation, and releases.
- Dataset stewards control item provenance, access, refresh, and retirement.
- Evaluation operators execute frozen schedules without changing scoring rules.
- Statistical reviewers approve estimands, power, models, and uncertainty.
- Domain and safety reviewers validate specialized tracks and threat models.
- Independent reviewers assess evidence and unresolved deviations.
- Replicating organizations independently execute a frozen protocol release.

One person may fill multiple roles in a pilot, but the overlap must be
disclosed. Publication-grade studies require the separation specified by KGBP.

## Change classes

- Patch: documentation corrections, implementation fixes that do not change a
  declared estimand, and additive diagnostics.
- Minor: backward-compatible schema fields, optional tracks, or new tooling.
- Major: changes to system boundaries, primary estimands, scoring, required
  gates, task populations, or governance requirements.

Normative changes require a public issue, rationale, alternatives, compatibility
analysis, tests, and a recorded maintainer decision. Outcome-changing decisions
made after unblinding require an explicit deviation and normally a new result
series.

## Appeals and corrections

Providers and users may challenge identity, task validity, availability,
scoring, policy treatment, or evidence. An appeal must identify the affected
round and supply reproducible evidence. Conflicted maintainers recuse. Accepted
corrections receive a new signed artifact set and changelog entry; the original
release remains available.

## Toward international adoption

The repository can publish a reference implementation and candidate protocol,
but cannot grant certification. A global publication candidate requires at
least three independent reviewers, two independent replicating organizations,
multistakeholder participation across at least five stakeholder groups and five
geographic regions, public comment, an appeals process, and evidence sufficient
for an authorized standards or conformity-assessment process.
