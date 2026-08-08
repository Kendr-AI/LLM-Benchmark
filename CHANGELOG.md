# Changelog

All notable project changes are documented here. The project follows Semantic
Versioning and keeps the protocol version separate from individual benchmark
round identifiers.

## [1.0.3] - 2026-08-08

### Added

- Published a dated current-frontier qualification register using explicit
  model snapshots, access maturity, capability, provider-diversity, and Kendr
  identity/preflight gates.
- Published the privacy-reviewed current-frontier GA callable-subset bundle:
  five ranked GA candidates, one unranked GPT-5.5 baseline, six GA targets
  reported as N/A, and corrected inference across all 15 scored endpoint pairs.
- Published a separate preview companion bundle. Gemini 3.1 Pro Preview
  recorded 39.78% operational goodput (95% interval 16.67% to 65.11%), 100%
  availability, and 15/15 completed cells; Qwen 3.8 Max Preview remains N/A.
- Added fail-closed catalog auditing, immutable-identity panel freezing,
  frontier aggregate exporters, generated handouts, provenance hashes, privacy
  checks, and release verification for both frontier publications.
- Added one-shot serial recovery for a missing successful-answer judgment. It
  regrades only the missing local judgment, never replays provider inference,
  and still fails closed if the objective record remains incomplete.
- Added the frontier handouts, aggregate JSON/CSV/Markdown files, and uniquely
  named bundle checksum manifests to tagged GitHub release assets.

### Scientific status

- The GA and preview-companion executions remain frozen at execution software
  version `1.0.2`; this `v1.0.3` tag is their publication release. The earlier
  35-endpoint catalog pilot remains frozen at execution software `1.0.0`.
- The preview companion contains exactly one scored endpoint, so it has no
  ordinal rank or pairwise comparison. It is not pooled with the GA table.
- GPT-5.6 Sol had the highest GA point estimate, but its paired comparison with
  the GPT-5.5 baseline did not establish a difference or practical
  equivalence. The small English-oriented, one-generation study is not a
  universal ranking, certification, or evidence of global acceptance.
- No frozen GA or preview-companion aggregate, generated handout, or nested
  checksum-manifest byte was changed by the publication-version update.

## [1.0.2] - 2026-08-08

### Corrected

- Reworked the technical white paper around Kendr's official Ink, Saffron,
  Paper, and Warm grey color system as used by `kendr.org`.
- Replaced the former blue/cyan publication palette with an Ink cover and
  header, Saffron accents and chart bars, warm Paper pages, and accessible
  derived tones for small text, tables, code blocks, and callouts.
- Added release verification for both the canonical PDF palette and the
  absence of the legacy blue, cyan, and navy drawing colors.
- Preserved the supplied Kendr logo without recoloring, rotation, gradients,
  or shadows and retained its required clear space.

### Scientific status

- This is a rendering-only publication correction. No model calls were rerun,
  and no prompts, responses, endpoint identities, scores, intervals, costs,
  rankings, statistical tests, or conclusions changed.
- The resolved white-paper Markdown and all frozen benchmark data remain
  byte-identical to v1.0.1. The pilot continues to record execution software
  version `1.0.0`.
- The `v1.0.0` and `v1.0.1` tags and their attested assets remain immutable.

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

[1.0.3]: https://github.com/Kendr-AI/LLM-Benchmark/releases/tag/v1.0.3
[1.0.2]: https://github.com/Kendr-AI/LLM-Benchmark/releases/tag/v1.0.2
[1.0.1]: https://github.com/Kendr-AI/LLM-Benchmark/releases/tag/v1.0.1
[1.0.0]: https://github.com/Kendr-AI/LLM-Benchmark/releases/tag/v1.0.0
