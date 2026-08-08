# LLM Benchmark Protocol v1.0.0

Release date: 2026-08-08

> **Correction notice:** Branding and researcher attribution were corrected in
> [`v1.0.1`](RELEASE_NOTES_v1.0.1.md). The `v1.0.0` tag and assets remain
> unchanged as historical evidence.

Researcher: **Dr. Prashant Kumar Dey**<br>
Project steward: **Kendr**

LLM Benchmark Protocol v1.0.0 is the first versioned public release of the
KGBP 1.0 specification, its Python reference harness, machine-readable evidence
contracts, and a privacy-reviewed catalog-pilot result bundle.

This is a release of evaluation methodology and software. It is not a claim
that KGBP is an accredited standard, that the included pilot is globally
representative, or that its descriptive row order is a resolved universal
ranking of language models.

## Highlights

- Claim-first protocol design with ten non-compensatory dimensions and separate
  design, execution, evidence, and publication gates.
- Explicit system types for fixed endpoints, routed systems, research systems,
  agents, ensembles, multimodal systems, and applications.
- Frozen sampling, deterministic interleaving, repeated-generation planning,
  failure-aware scoring, hierarchical bootstrap estimates, paired comparisons,
  multiplicity control, practical-equivalence decisions, operational goodput,
  and router counterfactuals.
- Versioned JSON Schema 2020-12 contracts covering systems, items, schedules,
  attempts, answers, judgments, observations, scorecards, and evidence
  manifests.
- Resumable LiveBench execution that preserves the first captured provider
  trial and supports offline finalization without silently replaying inference.
- Public `llm-benchmark-*` commands with the historical `kendr-*` aliases and
  `kendr_bench` import namespace retained for compatibility.
- Offline examples, release verification, CI, governance, contribution,
  security, data-license, citation, and adoption materials.

## Start here

- [Quick start](QUICKSTART.md)
- [Protocol card](PROTOCOL_CARD.md)
- [Adoption guide](ADOPTION_GUIDE.md)
- [Schema reference](SCHEMA_REFERENCE.md)
- [Provider-adapter guide](PROVIDER_ADAPTER_GUIDE.md)
- [Full protocol](../GLOBAL_BENCHMARK_PROTOCOL.md)
- [Technical white paper](../output/pdf/LLM_Benchmark_Protocol_1_0_White_Paper.pdf)

Install a source checkout with Python 3.11 or newer:

```bash
python -m venv .venv
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python scripts/verify_release.py --expected-version 1.0.0
python -m pytest
```

Provider-backed benchmark commands can incur API charges. The quick start
begins with offline audit and toy-scoring commands and requires explicit paid-run
confirmation before provider inference.

## Public catalog pilot

The bundled [ranking handout](RANKINGS_2026-08-08.md) reports a frozen campaign
against the Kendr API catalog snapshot captured on 2026-08-07:

- 37 catalog entries assessed;
- 35 text-compatible endpoints ranked on endpoint-as-served operational
  goodput;
- two non-text entries reported as not applicable, rather than forced into the
  text ranking;
- 15 selected LiveBench questions across five task categories;
- one generation per endpoint-question cell;
- 595 paired endpoint comparisons and zero Holm-adjusted rejections.

The machine-readable exports are:

- [JSON](data/kendr-catalog-pilot-2026-08-08.json)
- [CSV](data/kendr-catalog-pilot-2026-08-08.csv)
- [SHA-256 checksums](data/SHA256SUMS)

Raw prompts, model responses, provider request identifiers, credentials, and
local paths are not included in the public bundle. See the
[evidence-bundle guide](EVIDENCE_BUNDLE.md) and [data license](../DATA_LICENSE.md)
before publishing additional run artifacts.

## Scientific interpretation

The catalog campaign is a descriptive pilot. It does not satisfy KGBP global
publication gates because:

- all selected questions are English-language items dated in 2024;
- the sample is too small for narrow inference;
- generation-to-generation variation was not estimated;
- no multi-region load phase was run;
- no private rolling holdout was used;
- independent review and external replication are absent.

No pairwise comparison survived the declared Holm family-wise correction. A
failure to reject is not proof of equality, while a zero endpoint-as-served
score can reflect availability or capability negotiation rather than intrinsic
model incapability. Use the [results interpretation guide](RESULTS_INTERPRETATION.md)
and [statistical analysis plan](STATISTICAL_ANALYSIS_PLAN.md) before citing or
extending the pilot.

The strict protocol audit scores the reference design above 9 on all ten
dimensions. That design score evaluates whether controls are specified; it does
not replace execution evidence, conformance review, external replication,
certification, or standards-body adoption.

## Compatibility

- Python 3.11, 3.12, and 3.13 are the declared test matrix.
- The distribution name is `llm-benchmark-protocol`.
- The import namespace remains `kendr_bench`.
- New command names are `llm-benchmark`, `llm-benchmark-livebench`,
  `llm-benchmark-matrix`, and `llm-benchmark-protocol`.
- Existing `kendr-bench`, `kendr-livebench`, `kendr-benchmark-matrix`, and
  `kendr-protocol` commands remain aliases in this release.
- Protocol identity, software version, and benchmark-round identity are
  independently versioned. This software release implements the KGBP 1.0
  profile and publishes the immutable matrix ID named in the ranking bundle.

## Known limitations

- The bundled public pilot is not a freshness, multilingual, multimodal,
  longitudinal, safety, or production-load study.
- Provider aliases and routed candidate sets can change after capture; results
  apply only to the recorded endpoint identities and observation window.
- Some costs are lower bounds when failed calls lacked complete usage
  telemetry.
- The reference harness cannot establish legal compliance, social benefit, or
  field effectiveness without the complementary evidence described by the
  protocol.
- The optional Kendr dependency is pinned to a Git revision and therefore
  requires Git when that extra is installed.

## Governance and security

Protocol changes follow [governance](../GOVERNANCE.md), including public change
control and the [appeals and corrections process](APPEALS_AND_CORRECTIONS.md).
Security issues should follow the private reporting instructions in
[SECURITY.md](../SECURITY.md), not a public issue containing exploit or
credential details. Threat assumptions are documented in the
[threat model](THREAT_MODEL.md).

## Release integrity

Maintainers must follow [RELEASING.md](../RELEASING.md) and run:

```bash
python scripts/verify_release.py --expected-version 1.0.0
python -m pytest
python -m build
```

For the tag-triggered workflow, `python scripts/verify_release.py --tag
v1.0.0` additionally checks exact tag-to-package version alignment. The
verifier is offline and does not create, push, tag, or publish anything.

After the annotated tag is pushed, the release workflow repeats the gates,
audits the isolated runtime dependency set, generates a CycloneDX SBOM and
SHA-256 manifest, attests build provenance, and publishes the GitHub release.

## Citation

Use [CITATION.cff](../CITATION.cff), cite software version 1.0.0 and protocol
profile KGBP 1.0, and include the exact benchmark-round identifier when citing
the catalog results. The researcher is **Dr. Prashant Kumar Dey** and the
reference implementation is published by **Kendr**.

The complete change list is in [CHANGELOG.md](../CHANGELOG.md).
