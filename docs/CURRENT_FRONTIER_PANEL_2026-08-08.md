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

This panel is a callable subset, not a redefinition of the coverage universe.
Every other core or companion entry remains in the publication as N/A with a
machine-readable reason. The matrix labels these endpoints “Kendr served
default”: the harness does not claim that heterogeneous provider-side effort
settings were normalized or that each model ran at a third-party
leaderboard's `max` or `xhigh` configuration.

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
