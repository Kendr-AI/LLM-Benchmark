# Release process

## Version model

Software releases use Semantic Versioning. Protocol versions are named in the
protocol files and can remain stable while the implementation receives patch
releases. Benchmark rounds use immutable matrix identifiers and dates.

## Release checklist

1. Freeze scope, version, protocol identifier, and benchmark-round references.
2. Update `CHANGELOG.md`, `CITATION.cff`, package metadata, and release notes.
3. Run unit tests, compilation, the strict protocol audit, package build, and
   release verification.
4. Rebuild every public generated artifact from frozen inputs.
5. Verify hashes and inspect all rendered PDF pages.
6. Confirm no credentials, raw private items, local paths, or personal data are
   staged.
7. Commit the release on the default branch and push it.
8. Create a signed or annotated `vMAJOR.MINOR.PATCH` tag on the release commit.
9. Push the annotated tag. The tag workflow reruns verification, tests,
   distribution checks, a runtime dependency audit, and then publishes the
   GitHub release with the approved assets and build-provenance attestations.
10. Verify the GitHub release assets and CI results from a clean checkout.

## Automated verification

Run the offline release verifier from the repository root before creating the
release commit:

```bash
python scripts/verify_release.py --expected-version 1.0.0
```

It checks required release and governance files, package/module/citation
versions, internal Markdown links, JSON and JSON Schema validity, the sanitized
public ranking row counts and checksums, package resource declarations, and Git
release-candidate paths for raw artifacts or common credential signatures. It
does not contact providers, mutate Git state, create a tag, or publish files.

The tag workflow supplies the candidate tag explicitly:

```bash
python scripts/verify_release.py --tag v1.0.0
```

The tag must exactly equal `v` followed by `project.version`. A passing verifier
does not replace a history-aware secret scanner, dependency audit, clean-wheel
installation test, PDF visual inspection, or maintainer review of the staged
diff.

## Required release assets

The GitHub release must contain or link to:

- the technical white paper PDF;
- the privacy-reviewed ranking Markdown, JSON, and CSV;
- `SHA256SUMS` for the public data exports;
- the wheel and source distribution produced from the tagged commit;
- a CycloneDX runtime SBOM and release-wide checksums;
- release notes that preserve the pilot's scientific limitations.

Do not upload ignored `results/`, raw prompts or responses, provider request
identifiers, local logs, credentials, or unreviewed evidence bundles.

The tag workflow is idempotent: a rerun updates the named release assets and
notes. Maintainers must still inspect the exact commit and staged files before
any push or tag. A workflow-created release is a software-distribution event,
not an external scientific approval or conformity decision.
