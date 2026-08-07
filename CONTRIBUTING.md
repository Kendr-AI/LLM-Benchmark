# Contributing

Contributions to code, schemas, documentation, benchmark methodology, and
independent replications are welcome.

## Before opening a change

1. Read [GOVERNANCE.md](GOVERNANCE.md) and the normative
   [protocol specification](GLOBAL_BENCHMARK_PROTOCOL.md).
2. Open an issue for breaking protocol, schema, ranking, or governance changes.
3. Disclose provider affiliations, funding, API credits, and other interests
   that could affect an evaluation outcome.
4. Never submit private benchmark items, credentials, personal data, or
   provider-confidential traces.

## Local setup

```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev,docs]"
```

Run the required checks:

```bash
python -m pytest
python -m compileall -q src scripts
llm-benchmark-protocol audit config/global-protocol-v1.example.json \
  --output build/protocol-audit --strict
python -m build
```

## Change requirements

- Add or update tests for behavioral changes.
- Keep schemas backward compatible within a minor protocol series, or explain
  the migration in the changelog.
- Use deterministic seeds and content hashes for generated evidence.
- Preserve first governed trials; do not clean up a result by replacing a
  failed provider call with a later success.
- Qualify claims by system type, sample, elicitation regime, uncertainty, and
  evidence status.
- Rebuild and visually inspect PDFs after any white-paper change.

## Pull requests

Describe what changed, why it changed, user impact, validation performed, and
whether the change affects protocol conformance or historical comparability.
Keep generated raw provider artifacts out of the pull request. Sanitized
aggregate results may be proposed with their frozen manifest and integrity
information.

By participating, you agree to follow [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
