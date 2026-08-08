# LLM Benchmark Protocol v1.0.1

Release date: 2026-08-08

Researcher: **Dr. Prashant Kumar Dey**<br>
Project steward: **Kendr**

## Purpose of this patch

Version 1.0.1 is a branding and attribution correction. It standardizes the
organization name as **Kendr**, adds the supplied Kendr mark to the public
project materials, and identifies **Dr. Prashant Kumar Dey** as the researcher
working on LLM Benchmark Protocol.

The GitHub owner slug remains `Kendr-AI` inside repository URLs because it is a
technical address, not the public organization name.

## What changed

- Added the canonical 512 x 512 transparent Kendr mark under `assets/brand/`.
- Added the mark and researcher attribution to the README.
- Added the mark to the white-paper cover on Kendr Paper with the prescribed
  clear space, without recoloring, rotation, gradients, or shadows.
- Updated the white-paper source, cover byline, PDF author metadata, PDF creator
  metadata, citation file, package metadata, governance, protocol card, data
  attribution, copyright notice, and project authorship page.
- Added automated checks for the canonical logo, image dimensions, researcher
  attribution, legacy display-brand text, PDF cover image, and PDF metadata.
- Included the brand assets in source distributions and GitHub release assets.
- Changed release automation to reject attempts to replace an existing release.

## Frozen benchmark provenance

No provider calls were rerun. No prompts, responses, judgments, model labels,
endpoint identities, scores, intervals, costs, availability values, ranking
rows, pairwise tests, or conclusions changed.

The published pilot bundle continues to record execution software version
`1.0.0`. That is intentional: `v1.0.1` is the publication/correction release,
not a retroactive claim that the 2026-08-07 experiment ran newer software.

The scientific claim boundary is unchanged. The pilot remains a narrow,
English-oriented, 15-item, one-generation study with zero Holm-significant
pairwise differences among 595 comparisons.

## Historical release policy

The `v1.0.0` tag and its attested assets remain unchanged as historical
evidence. This patch uses a new tag and new artifacts instead of moving the old
tag or overwriting its PDF, packages, data, checksums, SBOM, or attestations.

## Citation

Use [CITATION.cff](../CITATION.cff), cite release `v1.0.1`, identify
**Dr. Prashant Kumar Dey** as the researcher, and include the exact benchmark
matrix identifier when citing the frozen catalog pilot.
