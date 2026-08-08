# Changelog

All notable project changes are documented here. The project follows Semantic
Versioning and keeps the protocol version separate from individual benchmark
round identifiers.

## [1.0.1] - 2026-08-08

### Corrected

- Standardized the public organization name as **Kendr** while preserving the
  `Kendr-AI` GitHub owner slug inside functioning repository URLs.
- Credited **Dr. Prashant Kumar Dey** as the protocol researcher in package,
  citation, governance, release, protocol-card, README, and white-paper
  metadata.
- Added the canonical Kendr mark to the repository, README, source
  distribution, release bundle, and white-paper cover using the supplied brand
  colors and clear-space rules.
- Regenerated the white paper with corrected cover text, PDF author/creator
  metadata, and embedded logo.
- Made tag releases immutable: the workflow now rejects an existing release
  instead of overwriting published assets.
- Preserved the frozen pilot's original `1.0.0` execution-software provenance;
  this patch changes publication branding and attribution, not benchmark data
  or rankings.

### Scientific status

- No model calls were rerun and no ranking values, endpoint identities,
  uncertainty intervals, or inferential conclusions changed.
- The `v1.0.0` tag and its attested assets remain an immutable historical
  release. This correction is published separately as `v1.0.1`.

## [1.0.0] - 2026-08-08

### Added

- LLM Benchmark Protocol 1.0 and its KGBP reference profile.
- Ten non-compensatory design dimensions with a strict score-above-9 gate.
- Machine-readable protocol, observation, and configuration schemas.
- Deterministic sampling, interleaved scheduling, power planning, hierarchical
  bootstrap intervals, paired effects, multiplicity control, failure-aware
  scoring, operational goodput, and router counterfactual analysis.
- Resumable LiveBench campaigns with first-trial preservation and artifact
  lineage from calls through judgments and scorecards.
- A frozen 35-endpoint Kendr catalog pilot plus two modality-specific
  not-applicable entries.
- Technical white paper, quick start, protocol card, adoption guide,
  interpretation guide, governance documentation, and release checklist.
- Public `llm-benchmark-*` commands while preserving the legacy `kendr-*`
  command aliases and `kendr_bench` Python import namespace.
- Continuous integration, package-build checks, security policy, contribution
  guide, citation metadata, and issue/PR templates.

### Scientific status

- The protocol-design audit scores 10.0/10 on all ten dimensions.
- The catalog run is a descriptive pilot, not a globally accepted or
  publication-grade comparison. It uses 15 English-language items from 2024,
  one generation per endpoint, no multi-region load study, and no external
  replication.
- None of 595 paired comparisons is significant after Holm correction. The
  published row order must not be interpreted as a resolved universal rank.

[1.0.1]: https://github.com/Kendr-AI/LLM-Benchmark/releases/tag/v1.0.1
[1.0.0]: https://github.com/Kendr-AI/LLM-Benchmark/releases/tag/v1.0.0
