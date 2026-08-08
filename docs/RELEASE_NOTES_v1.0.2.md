# LLM Benchmark Protocol v1.0.2

Release date: 2026-08-08

Researcher: **Dr. Prashant Kumar Dey**<br>
Project steward: **Kendr**

## Purpose of this patch

Version 1.0.2 is a publication-design correction. The technical white paper
now uses the same core color system as Kendr's public design language:

- Ink `#151412`
- Saffron `#E2712A`
- Paper `#FAF8F4`
- Warm grey `#8A8378`

The PDF adapts those colors for a long technical report while preserving the
Kendr mark's geometry, colors, and clear space.

## Publication design

- The cover and running header use Ink, with Saffron rails and rules and Paper
  typography.
- Body pages use a warm Paper canvas, Ink text, Saffron structural accents,
  and dark table headers.
- Charts use Saffron bars with a darker Saffron outline.
- Quotes and rank highlights use a pale Saffron tint; code blocks and alternate
  table rows use a neutral warm tint.
- Small orange text uses derived deep Saffron `#9A5022`, and secondary small
  text uses derived muted Ink `#615C54`. These choices avoid the insufficient
  contrast of raw Saffron or Warm grey on Paper.
- Links remain distinguishable without relying on color alone because they are
  both underlined and rendered in deep Saffron.
- The previous blue, cyan, and navy drawing colors are absent from the PDF.

No gradients, shadows, logo recoloring, logo rotation, or substitute wordmark
were introduced.

## Verification evidence

- All 50 A4 pages were rasterized at 150 dpi and visually inspected, including
  the cover, contents, chart, dense result tables, appendices, and references.
- The PDF contains the canonical Ink, Saffron, Paper, and Warm-grey drawing
  colors and no legacy blue, cyan, or navy drawing operations.
- The cover embeds the canonical Kendr logo and credits **Dr. Prashant Kumar
  Dey**.
- PDF SHA-256: `1e73cf2b629168e49fe837134ab1103b1218eaa5f49fb4a0f1ba3b00deef41f1`
- Resolved Markdown SHA-256:
  `5eb99199a3cef536f63d0ca03a43195d01ed751b7bed5d742e10ac4b6a102113`

The resolved Markdown digest is unchanged from v1.0.1, confirming that this
patch changes presentation rather than scientific content.

## Frozen benchmark provenance

No provider calls were rerun. No prompts, responses, judgments, model labels,
endpoint identities, scores, intervals, costs, availability values, ranking
rows, pairwise tests, or conclusions changed.

The pilot remains a narrow, English-oriented, 15-item, one-generation study
with zero Holm-significant pairwise differences among 595 comparisons. Its
execution-software version remains `1.0.0`; `v1.0.2` is the publication release.

## Historical release policy

The `v1.0.0` and `v1.0.1` tags and their attested assets remain unchanged.
This correction uses a new tag and new artifacts instead of moving an existing
tag or overwriting a published PDF, package, checksum, SBOM, or attestation.

## Citation

Use [CITATION.cff](../CITATION.cff), cite release `v1.0.2`, identify
**Dr. Prashant Kumar Dey** as the researcher, and include the exact benchmark
matrix identifier when citing the frozen catalog pilot.
