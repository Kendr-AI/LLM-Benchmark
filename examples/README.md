# Zero-cost scoring example

This fixture demonstrates schedule-aware scoring without contacting any model
provider. It is deliberately tiny and is not KGBP-conforming evidence.

Run:

```bash
llm-benchmark-protocol score examples/toy-observations.jsonl \
  --schedule examples/toy-schedule.jsonl \
  --output build/toy-scorecards \
  --bootstrap-samples 500 --seed 7
```

The schedule contains six planned cells but the observations file contains
five rows. The missing `beta/coding-1` cell is materialized with
`status=missing` and score zero. The `alpha/safety-1` policy block receives
credit because it is explicitly labeled an appropriate refusal on a safety
track. The same policy block on a capability track would score zero.

Expected descriptive macro scores are approximately 0.9333 for `alpha` and
0.2333 for `beta`. With one item per track, bootstrap intervals are degenerate;
that is intentional in this software demonstration and scientifically
inadequate for a real comparison.

The checked-in
[expected summary](expected/toy-scorecards-summary.json) is a compact,
deterministic projection of the generated scorecard. The test suite rebuilds
the scorecard from both JSONL fixtures and compares coverage, failure handling,
track scores, and paired effects with that file. It intentionally omits no
observations but does omit verbose repeated slice metadata from the expected
projection.
