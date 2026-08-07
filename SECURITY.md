# Security policy

## Supported versions

Security fixes are provided for the latest 1.0.x release. Users should run the
latest patch release before reporting a suspected defect.

## Reporting a vulnerability

Do not open a public issue for a vulnerability, exposed credential, private
benchmark item, or prompt/output bundle containing personal data. Use GitHub's
private vulnerability reporting feature on the repository Security tab:

https://github.com/Kendr-AI/LLM-Benchmark/security/advisories/new

Include the affected version or commit, impact, reproduction steps, and any
suggested mitigation. Remove live credentials, personal data, and proprietary
benchmark content. The maintainers will acknowledge a report within five
business days and will coordinate validation, remediation, disclosure, and
credit with the reporter.

## Benchmark-specific risks

- Provider keys belong only in local environment configuration.
- Raw prompts, outputs, tool traces, and request metadata may be sensitive.
- Private holdout items must never be committed to the public repository.
- Result bundles should be privacy-reviewed and stripped of local paths,
  credentials, headers, and personal data before publication.
- Agent and tool-use evaluations should run in isolated, least-privilege
  environments with explicit network and filesystem boundaries.

See [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md) for the release threat model.
