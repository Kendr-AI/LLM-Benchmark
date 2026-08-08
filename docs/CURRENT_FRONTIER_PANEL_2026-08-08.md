# Current-frontier panel profile: 2026-08-08

This dated profile is a benchmark eligibility decision, not a result set and
not evidence that every endpoint is currently callable. The historical
2026-08-07 catalog pilot and its published rankings remain unchanged.

## Cohorts

The `core-ga` cohort contains Claude Opus 5, Claude Fable 5, GPT-5.6 Sol,
Kimi K3, Muse Spark 1.2 standard, Grok 4.5, GLM 5.2, the dated DeepSeek V4
Flash 0731 endpoint, DeepSeek V4 Pro, the text-only Qwen 3.7 Max 2026-05-20
snapshot, and Gemini 3.6 Flash. GPT-5.5 is included only as the declared
benchmark baseline. DeepSeek V4 Pro and Qwen 3.7 Max are coverage-only staged
identities: they have no asserted Kendr catalog ID, cannot enter an execution
panel, and remain explicit N/A rows until a canonical identity passes
preflight.

The `preview-companion` cohort contains Qwen 3.8 Max Preview
(`qwen3.8-max-preview`) and Gemini 3.1 Pro Preview. Companion results must be
reported separately and must not be pooled into GA rankings or GA superiority
claims.

The machine-readable definition is
[`config/kendr-current-frontier-profile-20260808.json`](../config/kendr-current-frontier-profile-20260808.json).

## Callable-subset execution panel

The dated execution panel is
[`config/kendr-frontier-execution-panel-20260808.json`](../config/kendr-frontier-execution-panel-20260808.json).
It contains the five core-GA candidates that passed exact-identity preflight
through Kendr—Claude Opus 5, GPT-5.6 Sol, Grok 4.5, the dated DeepSeek V4
Flash 0731 route, and Gemini 3.6 Flash—plus GPT-5.5 as the declared baseline.

The separately frozen preview panel is
[`config/kendr-frontier-preview-execution-panel-20260808.json`](../config/kendr-frontier-preview-execution-panel-20260808.json).
It contains only Gemini 3.1 Pro Preview. Qwen 3.8 Max Preview failed the
callable identity/access gate and therefore remains visible as N/A rather than
being assigned a zero.

This panel is a callable subset, not a redefinition of the coverage universe.
Every other core entry and the unavailable Qwen companion remain in the
publication as N/A with a machine-readable reason. The matrices label these
endpoints “Kendr served default” or “Kendr served preview companion”: the
harness does not claim that heterogeneous provider-side effort settings were
normalized or that each model ran at a third-party leaderboard's `max` or
`xhigh` configuration.

## Executed snapshot

The panel was executed as matrix
`20260808T070202Z-frontier-market-kendr-20260808-cfec3672`. All 90 planned
endpoint-question cells and all 90 objective judgments are present. The
candidate-only point-estimate order and explicit N/A rows are published in the
[frontier leaderboard handout](FRONTIER_EXECUTION_LEADERBOARD_2026-08-08.md),
with privacy-reviewed aggregates in [JSON](data/frontier-2026-08-08/kendr-frontier-leaderboard-2026-08-08.json),
[CSV](data/frontier-2026-08-08/kendr-frontier-leaderboard-2026-08-08.csv), and
[Markdown](data/frontier-2026-08-08/kendr-frontier-leaderboard-2026-08-08.md).
Only two of the 15 paired comparisons separated after Holm correction; the
printed order must therefore remain descriptive.

The preview panel was executed separately as matrix
`20260808T083825Z-frontier-preview-kendr-20260808-d910f1e1`. It reused the
same 15 exact question IDs and sample hash as the GA matrix. All 15 answers and
15 judgments are present. Gemini 3.1 Pro Preview recorded 39.78% operational
goodput (95% interval 16.67%–65.11%) with 100% availability. Because it was
the only scored preview endpoint, no ordinal rank or GA comparison is assigned.
The privacy-reviewed companion artifacts are available as
[JSON](data/frontier-preview-2026-08-08/kendr-frontier-preview-companion-2026-08-08.json),
[CSV](data/frontier-preview-2026-08-08/kendr-frontier-preview-companion-2026-08-08.csv), and
[Markdown](data/frontier-preview-2026-08-08/kendr-frontier-preview-companion-2026-08-08.md).

## Offline coverage audit

Capture or retain a catalog JSON array, then audit it without making inference
requests:

```powershell
python scripts/audit_kendr_frontier_catalog.py `
  --catalog path/to/kendr-model-catalog.json `
  --audit-output path/to/frontier-audit.json `
  --core-panel-output path/to/core-panel.json `
  --companion-panel-output path/to/preview-companion-panel.json
```

The audit file is always written. A runnable cohort panel is written only when
every required identity in that cohort resolves by its configured catalog ID,
is available, advertises text capability, is not user-owned, and has no
unresolved selected-label collision. An exact display-name match is reported
as an advisory candidate but is never selected as a substitute for a missing
canonical ID.

The general catalog freezer now excludes user-owned/custom routing aliases by
default. It also fails on duplicate normalized display labels by default. Use
`--duplicate-label-policy annotate` only when retaining both endpoint IDs is
necessary for investigation; the generated labels then state that physical
identity remains unresolved. Annotation does not authorize merging the rows.

Catalog listing and offline auditing do not call a model. Running either panel
through the matrix harness is a separate paid action and requires an explicit
campaign decision.
