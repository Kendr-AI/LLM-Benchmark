# Evidence bundle guide

An evidence bundle lets another qualified party trace a claim from the frozen plan through provider attempts, answers, judgments, observations, statistics, and corrections. It is content-addressed and privacy-reviewed. It is not simply a directory of generated reports.

## Evidence classes

| Classification | Typical contents | Access rule |
|---|---|---|
| Public | Protocol, cards, aggregate scorecards, hashes, methods, deviations, reviews | Repository/release access |
| Controlled | Licensed/private prompts, redacted responses, detailed judgments, route/cost traces | Approved auditors under recorded terms |
| Private | Personal/sensitive data, credentials-adjacent operational material | Named custodians only |
| Withheld | Evidence that cannot be shared even under the current controlled process | Record hash, owner, and withholding reason |

Classify each artifact individually. "Private dataset" is not a reason to omit all provenance, hashes, sample statistics, or independent attestation.

## Recommended layout

```text
evidence/<protocol-id>/<run-id>/
  protocol/
    protocol.json
    preregistration.md
    statistical-analysis-plan.md
    system-cards/
    benchmark-card.md
    threat-model.md
  sampling/
    source-pool-summary.json
    frozen-items.jsonl
    sample-manifest.json
    contamination-audit.md
  execution/
    schedule.jsonl
    schedule.jsonl.validation.json
    attempts.jsonl
    answers.jsonl
    environment.json
  grading/
    judgments.jsonl
    graders.json
    human-validation.json
  analysis/
    observations.jsonl
    global-scorecards.json
    global-scorecards.md
    sensitivity/
  governance/
    deviation-log.csv
    reviews/
    replications/
    appeals/
  evidence-manifest.json
  SHA256SUMS
```

Public releases can reproduce this structure with controlled/private artifacts represented by manifest entries rather than copied into the public archive.

## Manifest contract

Use [`evidence-manifest-v1.schema.json`](../config/evidence-manifest-v1.schema.json). Each entry includes:

- repository/bundle-relative path;
- media type and byte count;
- lowercase SHA-256;
- classification;
- withholding reason when not shareable.

The manifest also records protocol/run identity, creation time, hash algorithm, signatures, deviations, and the privacy review. Paths must be relative and use a canonical separator; never embed a developer's absolute path.

Hash bytes after canonical artifact generation and redaction. Do not pretty-print, normalize newlines, or reorder JSON after signing without creating a new manifest.

## Required lineage

For every scored schedule cell, an auditor must be able to establish:

`schedule_id -> attempt_id(s) -> answer_id -> judgment_id -> observation -> scorecard`

Required reconciliation:

- planned cells = observed cells + synthesized missing cells;
- every retry is visible or hidden retry behavior is disclosed;
- answer selection references attempts from the same cell;
- failure and missing observations use the declared score treatment;
- grader/rubric versions match frozen hashes;
- system and actual-model/route identity agree with the card or deviation log;
- aggregate totals reconstruct from observations.

## Privacy and secret review

Before hashing the public view:

1. scan for API keys, authorization headers, cookies, signed URLs, and credential-like error text;
2. remove provider request IDs unless publication is explicitly safe and necessary;
3. remove absolute paths, usernames, hostnames, internal endpoints, and account identifiers;
4. assess prompts/responses for personal, sensitive, copyrighted, or contract-restricted content;
5. apply a deterministic redaction policy and record its version;
6. verify that aggregate slices cannot re-identify people or reveal private holdout answers;
7. assign a reviewer role and record completion in the manifest.

Never commit `.env`, key material, raw request headers, or temporary provider logs.

## Provenance and licensing

Software license, data license, benchmark terms, model/provider terms, and generated-output permissions are separate questions. Record for every source:

- owner and acquisition method/date;
- source URI/version and content hash;
- license/terms and allowed redistribution;
- transformations and tool versions;
- private/controlled basis;
- retention and deletion requirements.

See [`DATA_LICENSE.md`](../DATA_LICENSE.md). The project software license does not relicense third-party benchmark data, model outputs, or provider services.

## Independent review package

Give reviewers enough evidence to check:

- construct and target-population fit;
- sampling, freshness, contamination, and broken-item decisions;
- system identity and elicitation fairness;
- power, clustering, multiplicity, equivalence, and sensitivity;
- failure/cost/latency treatment;
- grader validity and bias;
- safety/privacy/license controls;
- deviations and reproducible reconstruction.

Reviewer reports identify scope, conflicts, evidence accessed, checks performed, unresolved issues, and recommendation. A reviewer name in a config file is not a review.

## Hashing and signing

Generate checksums in a stable sorted order. Example PowerShell verification:

```powershell
Get-Content SHA256SUMS | ForEach-Object {
  $expected, $relative = $_ -split '  ', 2
  $actual = (Get-FileHash -LiteralPath $relative -Algorithm SHA256).Hash.ToLower()
  if ($actual -ne $expected) { throw "Hash mismatch: $relative" }
}
```

Sign the manifest or checksum file using an organizational signing process that supports key rotation, signer identity, timestamping, and revocation. Do not store private signing keys in the repository. Record unsigned bundles honestly; a SHA-256 checksum detects drift but does not authenticate who published it.

## Reconstruction test

Before release, use an isolated environment with network disabled where practical:

1. verify every checksum;
2. validate every schema and cross-record invariant;
3. rebuild scorecards from the frozen schedule and observations;
4. compare regenerated artifacts byte-for-byte or by declared semantic hash;
5. render human reports and inspect tables/figures;
6. verify public/controlled classification and redaction;
7. run claim-language checks for scope, uncertainty, and correction links.

A "one-command" replay that silently fetches mutable datasets or calls a model is not offline reconstruction.

## Corrections and immutability

Never overwrite a released bundle. A correction creates:

- a new release/run or correction version;
- a manifest linking the superseded artifact;
- the accepted appeal/deviation record;
- old and new estimates plus impact assessment;
- a visible notice on the original result where hosting permits.

Follow [Appeals and corrections](APPEALS_AND_CORRECTIONS.md).

## Current public pilot bundle

The 2026-08-08 public pilot contains only privacy-reviewed aggregates:

- [`kendr-catalog-pilot-2026-08-08.json`](data/kendr-catalog-pilot-2026-08-08.json);
- [`kendr-catalog-pilot-2026-08-08.csv`](data/kendr-catalog-pilot-2026-08-08.csv);
- [`SHA256SUMS`](data/SHA256SUMS);
- [ranking and scope disclosure](RANKINGS_2026-08-08.md).

The JSON explicitly records that raw prompts, raw responses, provider request IDs, and local paths are absent. The checksum file is not a digital signature. This aggregate release supports inspection of reported rows and scope, but it is not a complete publication-grade evidence bundle or independent replication package.

## Bundle completion checklist

- [ ] Protocol, preregistration, analysis plan, and system cards frozen before calls.
- [ ] Item pool/sample and grader hashes recorded.
- [ ] Schedule completeness validated.
- [ ] Attempts, retries, answers, judgments, and observations reconcile.
- [ ] Failures and missing cells remain in the denominator.
- [ ] Scorecards reconstruct offline.
- [ ] Deviations and appeals are append-only.
- [ ] Privacy, secrets, provenance, license, and accessibility reviews complete.
- [ ] Every artifact classified and hashed.
- [ ] Signatures are verified or the bundle is labelled unsigned.
- [ ] Independent reviews and replications are actual attached reports, not declarations.
